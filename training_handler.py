"""
Training Handler - Simple Sequencer Engine
==========================================

Reads flat steps from clue metadata, looks up render templates by step type,
presents each step, validates input, advances. That's it.
"""

import hashlib
import hmac
import json
import os
import re
import secrets

from training_constants import DEPENDENT_TRANSFORM_TYPES, find_consumed_predecessors, find_terminal_transforms
from validate_training import validate_training_item

# Session signing secret — from env var or generated at startup (dev only)
_SESSION_SECRET = os.environ.get("SESSION_SECRET", "").encode("utf-8")
if not _SESSION_SECRET:
    _SESSION_SECRET = secrets.token_bytes(32)
    print("[WARNING] No SESSION_SECRET env var — using random key (sessions won't survive restarts)")

# --- Render templates (auto-reload) ---

RENDER_TEMPLATES = {}
RENDER_TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "render_templates.json")
RENDER_TEMPLATES_MTIME = 0


def _load_render_templates():
    global RENDER_TEMPLATES, RENDER_TEMPLATES_MTIME
    current_mtime = os.path.getmtime(RENDER_TEMPLATES_PATH)
    with open(RENDER_TEMPLATES_PATH, "r") as f:
        RENDER_TEMPLATES = json.load(f)
    RENDER_TEMPLATES_MTIME = current_mtime
    print(f"Loaded render_templates.json ({len(RENDER_TEMPLATES)} templates, mtime: {current_mtime})")


def maybe_reload_render_templates():
    """Check if render_templates.json has been modified and reload if needed."""
    current_mtime = os.path.getmtime(RENDER_TEMPLATES_PATH)
    if current_mtime != RENDER_TEMPLATES_MTIME:
        print("[Auto-reload] render_templates.json changed, reloading...")
        _load_render_templates()


_load_render_templates()

# --- Clue loading (lazy, per-request from Supabase with puzzle-level cache) ---

# Process-lifetime cache: keyed by (puzzle_number, clue_number, direction) → (item_id, item)
# Populated per-puzzle on first request for any clue in that puzzle.
# Cleared on server restart (which happens on any .py file change via Werkzeug reloader).
_clue_cache = {}
_cached_puzzles = set()  # Track which puzzles have been bulk-fetched


def _get_store():
    """Get a Supabase store instance."""
    from puzzle_store_supabase import PuzzleStoreSupabase
    return PuzzleStoreSupabase()


def list_clue_ids():
    """Return sorted list of all clue IDs with training data in Supabase."""
    store = _get_store()
    items = store.get_training_clues()
    return sorted(items.keys())


def list_all_clue_data():
    """Return dict of clue_id → clue_data for all clues with training data."""
    store = _get_store()
    return store.get_training_clues()


def lookup_clue(puzzle_number, clue_number, direction):
    """
    Fetch a clue from Supabase by key, validate it, and return it.
    Returns (clue_id, clue_data) or (None, None).
    On validation failure, raises ValueError with error details.

    Uses a puzzle-level cache: first request for any clue in a puzzle
    bulk-fetches all clues for that puzzle in one Supabase query.
    """
    if not (puzzle_number and clue_number and direction):
        return None, None

    dir_full = direction.lower() if direction else ''
    if dir_full not in ('across', 'down'):
        return None, None

    cache_key = (str(puzzle_number), int(clue_number), dir_full)

    # Bulk-fetch the whole puzzle on first access
    if str(puzzle_number) not in _cached_puzzles:
        store = _get_store()
        puzzle_clues = store.get_training_clues_for_puzzle(str(puzzle_number))
        _clue_cache.update(puzzle_clues)
        _cached_puzzles.add(str(puzzle_number))
        print(f"[Cache] Bulk-loaded {len(puzzle_clues)} clues for puzzle {puzzle_number}")

    # Lookup from cache
    cached = _clue_cache.get(cache_key)
    if not cached:
        return None, None

    item_id, item = cached

    # Validate on the spot
    errors, warnings = validate_training_item(item_id, item)
    for warn in warnings:
        print(f"  ⚠ {item_id}: {warn}")
    if errors:
        raise ValueError(errors)

    return item_id, item


def lookup_clue_by_id(clue_id):
    """Look up clue data from a clue_id like 'times-29147-1a'.
    Returns clue_data or None. Used by routes that receive clue_id from the client."""
    import re as _re
    m = _re.match(r'^[a-z]+-(\d+)-(\d+)([ad])$', clue_id)
    if not m:
        return None
    puzzle_number = m.group(1)
    clue_number = int(m.group(2))
    direction = 'across' if m.group(3) == 'a' else 'down'
    try:
        found_id, clue_data = lookup_clue(puzzle_number, clue_number, direction)
    except ValueError:
        return None
    if not found_id:
        return None
    return clue_data


_SESSION_FIELDS = {
    "step_index": 0,
    "completed_steps": [],
    "selected_indices": [],
    "hint_visible": False,
    "step_expanded": False,
    "user_answer": [],
    "answer_locked": False,
    "highlights": [],
    "assembly_transforms_done": {},
    "assembly_hint_index": None,
    "help_visible": False,
    "cross_letters": [],
}


def _new_session():
    """Create a fresh session state dict."""
    return {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in _SESSION_FIELDS.items()}


def _sign_session(session_data):
    """Sign a session dict with HMAC. Returns {"data": ..., "sig": "..."}."""
    payload = json.dumps(session_data, sort_keys=True, separators=(',', ':'))
    sig = hmac.new(_SESSION_SECRET, payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return {"data": session_data, "sig": sig}


def _verify_session(signed):
    """Verify and extract session data from a signed session. Raises ValueError on tamper."""
    if not isinstance(signed, dict) or "data" not in signed or "sig" not in signed:
        raise ValueError("Invalid session format — missing signature")
    payload = json.dumps(signed["data"], sort_keys=True, separators=(',', ':'))
    expected_sig = hmac.new(_SESSION_SECRET, payload.encode('utf-8'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signed["sig"], expected_sig):
        raise ValueError("Session signature invalid — possible tampering")
    return signed["data"]


def restore_session(raw):
    """Restore session from client-sent signed JSON. Verifies signature, validates and normalises types."""
    verified_data = _verify_session(raw)

    session = _new_session()
    if not isinstance(verified_data, dict):
        raise ValueError("Invalid session data")
    for key in _SESSION_FIELDS:
        if key in verified_data:
            session[key] = verified_data[key]
    # JSON round-trip turns int dict keys to strings — convert back
    atd = session["assembly_transforms_done"]
    if atd:
        session["assembly_transforms_done"] = {int(k): v for k, v in atd.items()}
    return session


def start_session(clue_id, clue, cross_letters=None):
    """Initialize a training session. Returns the initial render."""
    session = _new_session()
    if cross_letters:
        session["cross_letters"] = cross_letters
    return get_render(clue_id, clue, session)


def get_render(clue_id, clue, session):
    """Build the complete render object for the current state."""

    steps = clue["steps"]
    step_index = session["step_index"]

    # All steps done → show completed step list (no separate completion view)
    if step_index >= len(steps) or set(range(len(steps))).issubset(set(session["completed_steps"])):
        session["step_index"] = len(steps)
        return _build_all_done(session, clue, clue_id)

    step = steps[step_index]

    # If the expanded step is already completed (e.g. after auto-advance landed on it),
    # find the next available step
    if step_index in session["completed_steps"]:
        step_index = _next_active_step(steps, session["completed_steps"], step_index)
        session["step_index"] = step_index
        if step_index >= len(steps):
            return _build_all_done(session, clue, clue_id)
        step = steps[step_index]

    # Auto-complete assembly for double definitions — no transforms to show,
    # the student just types the answer in the answer box
    if step["type"] == "assembly" and clue.get("clue_type") == "double_definition":
        session["completed_steps"].append(step_index)
        session["step_index"] = step_index + 1
        session["answer_locked"] = True
        answer_letters = list(re.sub(r'[^A-Z]', '', clue["answer"].upper()))
        session["user_answer"] = answer_letters
        return _build_all_done(session, clue, clue_id)

    template = RENDER_TEMPLATES.get(step["type"])

    # Build step summary list for the menu sidebar
    step_list = _build_step_list(session, clue)

    # Every step type must have a matching render template
    if not template:
        raise ValueError(f"No render template found for step type '{step['type']}' — add it to render_templates.json")

    # Build current step render
    # Resolve prompt (template may be dict keyed by indicator_type or definition_part)
    prompt_data = template["prompt"]
    if isinstance(prompt_data, dict):
        dict_key = _get_dict_key(step)
        if dict_key not in prompt_data:
            raise ValueError(f"No prompt for '{dict_key}' in template. Available: {list(prompt_data.keys())}")
        resolved_prompt = prompt_data[dict_key]
    else:
        resolved_prompt = prompt_data

    current_step = {
        "index": step_index,
        "type": step["type"],
        "inputMode": template["inputMode"],
        "prompt": _resolve_variables(resolved_prompt, step, clue),
    }

    # Intro (template may be dict keyed by indicator_type, definition_part, or clue_type)
    if "intro" in template:
        intro_data = template["intro"]
        if isinstance(intro_data, dict):
            # Assembly steps use clue_type as dict key; other steps use indicator_type/definition_part
            if step["type"] == "assembly":
                clue_type = clue.get("clue_type", "")
                intro_text = intro_data.get(clue_type, intro_data.get("default"))
                if intro_text is None:
                    raise ValueError(f"No intro for clue_type '{clue_type}' and no 'default' in assembly template. Available: {list(intro_data.keys())}")
                current_step["intro"] = intro_text
            else:
                dict_key = _get_dict_key(step)
                if dict_key not in intro_data:
                    raise ValueError(f"No intro for '{dict_key}' in template. Available: {list(intro_data.keys())}")
                current_step["intro"] = intro_data[dict_key]
        else:
            current_step["intro"] = intro_data

    # Hint (step metadata overrides template; template hint keyed by clue_type if dict)
    if "hint" in step:
        current_step["hint"] = step["hint"]
    elif "hint" in template:
        hint_data = template["hint"]
        if isinstance(hint_data, dict):
            if "clue_type" not in clue:
                raise ValueError(f"Template hint is dict-keyed but clue metadata is missing 'clue_type'")
            clue_type = clue["clue_type"]
            if clue_type not in hint_data:
                raise ValueError(f"No hint for clue_type '{clue_type}' in template. Available: {list(hint_data.keys())}")
            current_step["hint"] = hint_data[clue_type]
        else:
            current_step["hint"] = hint_data

    current_step["hintVisible"] = session["hint_visible"]

    # Dictionary lookup (optional, from step metadata)
    if "lookup" in step:
        current_step["lookup"] = step["lookup"]

    # Multiple choice options (from step metadata)
    if template["inputMode"] == "multiple_choice":
        if "options" not in step:
            raise ValueError(f"Step type '{step['type']}' uses multiple_choice but has no 'options' in metadata.")
        current_step["options"] = step["options"]

    # Assembly-specific data
    if template["inputMode"] == "assembly":
        current_step["assemblyData"] = _build_assembly_data(session, step, clue)

    # Completion text for completed steps
    if step_index in session["completed_steps"]:
        current_step["completionText"] = _resolve_on_correct(template, step, clue)

    # Compute answer box groups from enumeration: commas separate words,
    # hyphens join within a word. "5-6" → [11], "5,3" → [5, 3], "7" → [7]
    enum_str = clue.get("enumeration", "")
    answer_groups = []
    for part in re.split(r'[,\s]+', enum_str):
        if part:
            total = sum(int(n) for n in part.split('-') if n.isdigit())
            if total > 0:
                answer_groups.append(total)

    # Phase help — scan or assembly text based on current step type
    phase_help = RENDER_TEMPLATES.get("phaseHelp")
    if not phase_help:
        raise ValueError("render_templates.json missing 'phaseHelp' section")
    help_key = "assembly" if step["type"] == "assembly" else "scan"
    help_text = phase_help.get(help_key)
    if not help_text:
        raise ValueError(f"phaseHelp missing '{help_key}' text in render_templates.json")

    return {
        "clue_id": clue_id,
        "words": clue["words"],
        "answer": clue["answer"],
        "enumeration": clue["enumeration"],
        "answerGroups": answer_groups,
        "steps": step_list,
        "currentStep": current_step,
        "stepExpanded": session["step_expanded"],
        "helpVisible": session["help_visible"],
        "helpText": help_text,
        "highlights": session["highlights"],
        "selectedIndices": session["selected_indices"],
        "showSubmitButton": current_step["inputMode"] == "tap_words" and len(session["selected_indices"]) > 0,
        "userAnswer": session["user_answer"],
        "answerLocked": session["answer_locked"],
        "complete": False,
        "session": _sign_session(session),
    }


def handle_input(clue_id, clue, session, value, transform_index=None, transform_inputs=None, letter_positions=None):
    """Validate user input for the current step. Returns {correct, render, message?}."""

    steps = clue["steps"]
    step_index = session["step_index"]

    if step_index >= len(steps):
        raise ValueError("All steps already completed")

    step = steps[step_index]
    template = RENDER_TEMPLATES.get(step["type"])
    if not template:
        raise ValueError(f"No render template for step type '{step['type']}'. Add it to render_templates.json.")

    # Assembly steps have their own multi-phase validation
    if template["inputMode"] == "assembly":
        return _handle_assembly_input(session, step, clue, clue_id, value, transform_index, transform_inputs, letter_positions)

    input_mode = template["inputMode"]
    expected = _resolve_expected(step, template)

    # Validate
    if input_mode == "tap_words":
        correct = set(value) == set(expected)
    elif input_mode == "text":
        user_text = re.sub(r'[^A-Z]', '', str(value).upper())
        expected_text = re.sub(r'[^A-Z]', '', str(expected).upper())
        correct = user_text == expected_text
    elif input_mode == "multiple_choice":
        correct = str(value).strip().lower() == str(expected).strip().lower()
    else:
        raise ValueError(f"Unsupported input mode: {input_mode}")

    feedback = RENDER_TEMPLATES["feedback"]

    if correct:
        # Add highlight for tap_words
        if input_mode == "tap_words":
            session["highlights"].append({
                "indices": list(expected),
                "color": "GREEN",
                "role": step["type"],
            })

        # Mark completed, advance to next available step
        session["completed_steps"].append(step_index)
        session["step_index"] = _next_active_step(steps, session["completed_steps"], step_index)
        session["selected_indices"] = []
        session["hint_visible"] = False
        session["step_expanded"] = False
        session["assembly_transforms_done"] = {}
        session["assembly_hint_index"] = None

        return {"correct": True, "message": feedback["step_correct"], "render": get_render(clue_id, clue, session)}
    else:
        # Partial match for tap_words: user found some correct words but not all
        if input_mode == "tap_words" and isinstance(value, list) and isinstance(expected, list):
            user_set = set(value)
            expected_set = set(expected)
            if user_set and user_set < expected_set and user_set.issubset(expected_set):
                found = len(user_set)
                remaining = len(expected_set) - found
                partial_template = feedback.get("step_partial", "Good — {found} found, {remaining} more to find.")
                msg = partial_template.replace("{found}", str(found)).replace("{remaining}", str(remaining))
                return {"correct": False, "message": msg, "render": get_render(clue_id, clue, session)}
        return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue, session)}


def update_ui_state(clue_id, clue, session, action, data):
    """Update UI state without validating. Returns updated render."""

    if action == "toggle_hint":
        session["hint_visible"] = not session["hint_visible"]

    elif action == "toggle_assembly_hint":
        transform_idx = data.get("transform_index")
        if transform_idx is not None:
            if session.get("assembly_hint_index") == transform_idx:
                session["assembly_hint_index"] = None
            else:
                session["assembly_hint_index"] = transform_idx

    elif action == "toggle_help":
        session["help_visible"] = not session["help_visible"]

    elif action == "select_word":
        index = data.get("index")
        if index is not None:
            if index in session["selected_indices"]:
                session["selected_indices"].remove(index)
            else:
                session["selected_indices"].append(index)

    elif action == "type_answer":
        session["user_answer"] = data.get("letters", [])

    elif action == "expand_step":
        session["step_expanded"] = True

    elif action == "select_step":
        # Switch to a different active step (non-linear step completion)
        new_index = data.get("step_index")
        steps = clue["steps"]
        if new_index is not None and 0 <= new_index < len(steps):
            step = steps[new_index]
            if _is_step_available(new_index, step, steps, session["completed_steps"]):
                session["step_index"] = new_index
                session["selected_indices"] = []
                session["hint_visible"] = False
                session["step_expanded"] = True
                session["assembly_transforms_done"] = {}
                session["assembly_hint_index"] = None

    elif action == "type_step_input":
        # For text input steps (not used in definition, but ready)
        pass

    else:
        raise ValueError(f"Unknown UI action: {action}")

    render = get_render(clue_id, clue, session)

    # Silent sync: type_answer doesn't need re-render unless answer was locked
    if action == "type_answer" and not session["answer_locked"]:
        render["shouldRender"] = False
    else:
        render["shouldRender"] = True

    return render


def reveal_answer(clue_id, clue, session):
    """Skip to completion, revealing the full decode."""

    steps = clue["steps"]

    # Mark ALL steps as completed so the full decode is shown
    session["completed_steps"] = list(range(len(steps)))
    session["step_index"] = len(steps)
    session["answer_locked"] = True

    # Add highlights for all tap_words steps
    session["highlights"] = []
    for step in steps:
        if "indices" in step:
            session["highlights"].append({
                "indices": step["indices"],
                "color": "GREEN",
                "role": step["type"],
            })

    # Populate answer boxes
    answer_letters = list(re.sub(r'[^A-Z]', '', clue["answer"].upper()))
    session["user_answer"] = answer_letters

    return get_render(clue_id, clue, session)


def check_answer(clue_id, clue, session, answer):
    """Check if the typed answer matches. Returns {correct, render}."""
    user_text = re.sub(r'[^A-Z]', '', str(answer).upper())
    expected_text = re.sub(r'[^A-Z]', '', clue["answer"].upper())
    feedback = RENDER_TEMPLATES["feedback"]

    if user_text == expected_text:
        session["answer_locked"] = True
        return {"correct": True, "message": feedback["answer_correct"], "render": get_render(clue_id, clue, session)}
    else:
        return {"correct": False, "message": feedback["answer_incorrect"], "render": get_render(clue_id, clue, session)}


# --- Internal helpers ---


def _format_role(role):
    """Look up a transform role's display name from render_templates.json."""
    role_names = RENDER_TEMPLATES.get("assembly", {}).get("roleDisplayNames", {})
    if role not in role_names:
        raise ValueError(f"Unknown transform role '{role}' — add it to roleDisplayNames in render_templates.json")
    return role_names[role]


def _compute_fail_message(template, step, clue, words, transforms):
    """Compute the fail message for an assembly step.

    Three scenarios: explicit clues skip it, step metadata can override,
    otherwise use the template with raw word list substitution.
    """
    if step.get("explicit", False):
        return ""
    if "failMessage" in step:
        return step["failMessage"]
    fail_msg_data = template["defaultFailMessage"]
    if isinstance(fail_msg_data, dict):
        if "clue_type" not in clue:
            raise ValueError("Clue metadata missing 'clue_type' field")
        fail_msg_template = fail_msg_data.get(clue["clue_type"], fail_msg_data.get("default", ""))
    else:
        fail_msg_template = fail_msg_data
    raw_words = []
    for t in transforms:
        t_words = [words[i] for i in t["indices"]]
        raw_words.append(" ".join(t_words))
    raw_list = "'" + "' and '".join(raw_words) + "'"
    return fail_msg_template.format(rawWordsList=raw_list)


def _resolve_transform_prompt(prompt_template, clue_type, format_kwargs, profile_key=None):
    """Resolve a transform prompt, which may be a string or a dict keyed by clue_type.

    If the template value is a dict, picks the profile_key-specific version first,
    then clue_type-specific, then falls back to 'default'. If it's a string, uses
    it directly. Then applies .format().
    """
    if isinstance(prompt_template, dict):
        prompt_str = None
        if profile_key:
            prompt_str = prompt_template.get(profile_key)
        if prompt_str is None:
            prompt_str = prompt_template.get(clue_type, prompt_template.get("default"))
        if prompt_str is None:
            raise ValueError(
                f"Transform prompt dict has no key for clue_type '{clue_type}' and no 'default'. "
                f"Available: {list(prompt_template.keys())}")
    else:
        prompt_str = prompt_template
    return prompt_str.format(**format_kwargs)


def _build_transform_list(transforms, transforms_done, template, clue, words,
                           assembly_hint_index, substitution_consumed, has_substitution,
                           prior_data=None, profile_key=None):
    """Build the display list of transforms for the assembly step.

    Each transform gets a prompt, status, completion text, and hint visibility.
    All transforms are always active — no locking.
    """
    TRANSFORM_PROMPTS = template.get("transformPrompts", {})
    clue_type = clue.get("clue_type", "")
    definition_words = prior_data.get("definitionWords", "") if prior_data else ""
    transform_list = []
    for i, t in enumerate(transforms):
        clue_word = " ".join(words[idx] for idx in t["indices"])
        letter_count = len(re.sub(r'[^A-Z]', '', t["result"].upper()))
        word_letter_count = len(re.sub(r'[^A-Za-z]', '', clue_word))
        if "type" not in t:
            raise ValueError(f"Transform {i} is missing 'type' field in assembly step")
        t_type = t["type"]

        if t_type not in TRANSFORM_PROMPTS:
            raise ValueError(f"Unknown transform type '{t_type}' in clue metadata. Add it to transformPrompts in render_templates.json.")

        # Skip consumed source transforms when substitutionLine provides the context
        if i in substitution_consumed and has_substitution:
            continue

        # Template-driven prompt — no per-clue overrides
        if t_type in DEPENDENT_TRANSFORM_TYPES and i > 0:
            # Dependent transform: {word} is the indicator, not the input
            consumed = find_consumed_predecessors(transforms, i)
            # Use _with_context prompt when substitutionLine already explains the operation
            if t_type == "substitution" and substitution_consumed:
                prompt_key = "substitution_with_context"
                if prompt_key not in TRANSFORM_PROMPTS:
                    raise ValueError(f"Missing '{prompt_key}' in transformPrompts in render_templates.json")
                prompt = _resolve_transform_prompt(
                    TRANSFORM_PROMPTS[prompt_key], clue_type,
                    {"n": letter_count, "wordLetterCount": word_letter_count,
                     "definitionWords": definition_words},
                    profile_key=profile_key)
            else:
                all_solved = all(c in transforms_done for c in consumed)
                if all_solved:
                    pred_parts = [transforms_done[c] for c in consumed]
                    predecessor_letters = " + ".join(pred_parts)
                    prompt_key = t_type + "_with_input"
                    if prompt_key not in TRANSFORM_PROMPTS:
                        raise ValueError(f"Missing '{prompt_key}' in transformPrompts in render_templates.json")
                    prompt = _resolve_transform_prompt(
                        TRANSFORM_PROMPTS[prompt_key], clue_type,
                        {"word": clue_word, "predecessorLetters": predecessor_letters,
                         "n": letter_count, "wordLetterCount": word_letter_count,
                         "definitionWords": definition_words},
                        profile_key=profile_key)
                else:
                    prompt = _resolve_transform_prompt(
                        TRANSFORM_PROMPTS[t_type], clue_type,
                        {"word": clue_word, "n": letter_count,
                         "wordLetterCount": word_letter_count,
                         "definitionWords": definition_words},
                        profile_key=profile_key)
        else:
            display_role = _format_role(t["role"])
            prompt = _resolve_transform_prompt(
                TRANSFORM_PROMPTS[t_type], clue_type,
                {"role": display_role, "word": clue_word, "n": letter_count,
                 "wordLetterCount": word_letter_count,
                 "definitionWords": definition_words},
                profile_key=profile_key)

        # Determine status: completed, active, or locked
        if i in transforms_done:
            status = "completed"
            result = transforms_done[i]
        else:
            status = "active"
            result = None

        # Build completedText for ALL transforms (used for completed display AND hint reveal)
        # Use actual result from transforms_done if completed, else from metadata
        display_result = result if result else t["result"].upper()
        completed_templates = template["completedTextTemplates"]
        if t_type in DEPENDENT_TRANSFORM_TYPES and i > 0:
            consumed = find_consumed_predecessors(transforms, i)
            if status == "completed":
                for c in consumed:
                    if c not in transforms_done:
                        raise ValueError(f"Transform {i} is dependent but predecessor {c} has no result in transforms_done")
                prev_parts = [transforms_done[c] for c in consumed]
            else:
                prev_parts = [transforms[c]["result"].upper() for c in consumed]
            prev_result = " + ".join(prev_parts)
            completed_text = completed_templates["dependent"].format(
                prevResult=prev_result, result=display_result)
        else:
            completed_text = completed_templates["independent"].format(
                clueWord=clue_word, result=display_result)
        # Append hint as coaching explanation
        hint = t.get("hint", "")
        if hint:
            completed_text += "\n" + hint

        transform_entry = {
            "role": t["role"],
            "clueWord": clue_word,
            "prompt": prompt,
            "letterCount": letter_count,
            "status": status,
            "result": result,
            "hint": t.get("hint", ""),
            "hintVisible": (assembly_hint_index == i),
            "index": i,
            "completedText": completed_text,
        }
        if "lookup" in t:
            transform_entry["lookup"] = t["lookup"]
        transform_list.append(transform_entry)
    return transform_list


def _extract_prior_step_data(clue, words):
    """Extract data from earlier steps (definition, indicator, etc.) for template resolution.

    Returns a dict with: definitionWords, indicatorHint, indicatorWords,
    innerWords, outerWords, abbreviationScanMappings.
    """
    data = {
        "definitionWords": "",
        "indicatorHint": "",
        "indicatorWords": "",
        "innerWords": "",
        "outerWords": "",
        "abbreviationScanMappings": {},
        "indicatorsByType": {},
    }
    for s in clue["steps"]:
        if s["type"] == "definition" and "indices" in s:
            data["definitionWords"] = " ".join(words[i] for i in s["indices"])
        elif s["type"] == "indicator" and "indices" in s:
            data["indicatorHint"] = s.get("hint", "")
            data["indicatorWords"] = " ".join(words[i] for i in s["indices"])
            indicator_type = s.get("indicator_type", "")
            if indicator_type:
                data["indicatorsByType"][indicator_type] = " ".join(words[i] for i in s["indices"])
        elif s["type"] == "outer_word" and "indices" in s:
            data["outerWords"] = " ".join(words[i] for i in s["indices"])
        elif s["type"] == "inner_word" and "indices" in s:
            data["innerWords"] = " ".join(words[i] for i in s["indices"])
        elif s["type"] == "abbreviation_scan" and "mappings" in s:
            data["abbreviationScanMappings"] = s["mappings"]
    return data


def _build_abbreviation_summary(abbreviation_scan_mappings, words, template):
    """Build abbreviation summary string from abbreviation_scan mappings.

    Uses abbreviationPairTemplate and abbreviationPairJoiner from render template.
    """
    if not abbreviation_scan_mappings:
        return ""
    pair_template = template.get("abbreviationPairTemplate", "")
    if not pair_template:
        raise ValueError("Assembly template missing 'abbreviationPairTemplate'")
    pair_joiner = template.get("abbreviationPairJoiner", " and ")
    pairs = []
    for idx_str, letter in abbreviation_scan_mappings.items():
        word = words[int(idx_str)]
        pairs.append(pair_template.replace("{letter}", letter).replace("{word}", word))
    return pair_joiner.join(pairs) if pairs else ""


def _build_coaching_lines(template, virtual_step, clue, has_substitution,
                           indicator_words, source_word, abbreviation_summary):
    """Resolve the coaching context lines (definition, indicator, check phase prompt).

    Returns (definition_line, indicator_line, check_phase_prompt).
    """
    # Definition line — incorporates abbreviation facts when they exist
    if abbreviation_summary:
        definition_line = _resolve_variables(template.get("definitionLineWithAbbreviations", ""), virtual_step, clue)
    else:
        definition_line = _resolve_variables(template.get("definitionLine", ""), virtual_step, clue)

    # Resolve the appropriate context line based on clue type
    indicator_line = ""
    inner_words = virtual_step.get("innerWords", "")
    outer_words = virtual_step.get("outerWords", "")
    if has_substitution and indicator_words and source_word:
        indicator_line = _resolve_variables(template.get("substitutionLine", ""), virtual_step, clue)
    elif indicator_words and inner_words and outer_words:
        indicator_line = _resolve_variables(template.get("indicatorLine", ""), virtual_step, clue)

    # Check phase prompt
    check_phase_prompt = template.get("checkPhasePrompt", "")
    if not check_phase_prompt:
        raise ValueError("Assembly template missing 'checkPhasePrompt'")

    return definition_line, indicator_line, check_phase_prompt


def _build_assembly_data(session, step, clue):
    """Build the assemblyData payload for an assembly step.

    All transforms are always active — no locking. The student sees the full
    plan and works through them in any order.
    """
    transforms = step["transforms"]
    transforms_done = session["assembly_transforms_done"]  # dict: {index: result}
    assembly_hint_index = session.get("assembly_hint_index")
    words = clue["words"]
    template = RENDER_TEMPLATES.get("assembly", {})

    # Fail message
    fail_message = _compute_fail_message(template, step, clue, words, transforms)

    # Detect substitution clues early (needed for display logic)
    has_substitution = any(t["type"] == "substitution" for t in transforms)
    substitution_consumed = set()
    if has_substitution:
        for i, t in enumerate(transforms):
            if t["type"] == "substitution" and i > 0:
                substitution_consumed = find_consumed_predecessors(transforms, i)
                break

    # Extract data from earlier steps (needed for transform prompts and abbreviation auto-complete)
    prior = _extract_prior_step_data(clue, words)

    # Straight anagram detection: exactly 2 transforms (literal → anagram), clue_type is 'anagram'.
    # Auto-complete the literal so the student sees only coaching text + letter boxes.
    is_straight_anagram = (
        clue.get("clue_type") == "anagram"
        and len(transforms) == 2
        and transforms[0]["type"] == "literal"
        and transforms[1]["type"] == "anagram"
    )
    if is_straight_anagram and 0 not in transforms_done:
        transforms_done[0] = transforms[0]["result"].upper()
        # Clear the fail message — the single coaching paragraph covers everything
        fail_message = ""

    # Simple hidden word detection: exactly 1 transform (letter_selection), clue has a hidden_word indicator.
    # The student sees only coaching text + letter boxes — no transform prompts.
    has_hidden_word_indicator = any(
        s.get("type") == "indicator" and s.get("indicator_type") == "hidden_word"
        for s in clue.get("steps", [])
    )
    is_simple_hidden_word = (
        has_hidden_word_indicator
        and len(transforms) == 1
        and transforms[0]["type"] == "letter_selection"
    )
    if is_simple_hidden_word:
        fail_message = ""

    # Simple substitution detection: exactly 2 transforms (literal source + substitution),
    # clue has a substitution indicator. Auto-complete the literal so the student sees
    # only coaching text + letter boxes.
    has_substitution_indicator = any(
        s.get("type") == "indicator" and s.get("indicator_type") == "substitution"
        for s in clue.get("steps", [])
    )
    is_simple_substitution = (
        has_substitution_indicator
        and len(transforms) == 2
        and transforms[0]["type"] == "literal"
        and transforms[0].get("role") == "source"
        and transforms[1]["type"] == "substitution"
    )
    if is_simple_substitution and 0 not in transforms_done:
        transforms_done[0] = transforms[0]["result"].upper()
        fail_message = ""

    # Container with transforms detection: clue has a container indicator,
    # and the assembly has a container transform plus other transforms (synonym,
    # abbreviation, etc.). The coaching paragraph replaces definition + indicator +
    # fail message. The container transform is visible — the student completes the
    # insertion step themselves.
    has_container_indicator = any(
        s.get("type") == "indicator" and s.get("indicator_type") == "container"
        for s in clue.get("steps", [])
    )
    container_transform_indices = [
        i for i, t in enumerate(transforms) if t["type"] == "container"
    ]
    has_outer_inner_roles = (
        any(t.get("role") == "outer" for t in transforms)
        and any(t.get("role", "").startswith("inner") for t in transforms)
    )
    is_container_with_transforms = (
        has_container_indicator
        and (len(container_transform_indices) > 0 or has_outer_inner_roles)
    )
    if is_container_with_transforms:
        fail_message = ""

    # Pure charade detection: no indicator steps at all, all transforms are
    # synonyms/abbreviations/literals with part roles (part1, part2, etc.)
    has_any_indicators = any(
        s.get("type") == "indicator" for s in clue.get("steps", [])
    )
    charade_transform_types = {"synonym", "abbreviation", "literal"}
    is_pure_charade = (
        not has_any_indicators
        and not is_container_with_transforms
        and all(t["type"] in charade_transform_types for t in transforms)
    )
    if is_pure_charade:
        fail_message = ""

    # Charade with single indicator detection: exactly one indicator (deletion or
    # reversal), no container transform, transforms include the indicator type
    # plus synonyms/abbreviations/literals.
    indicator_types = [
        s.get("indicator_type") for s in clue.get("steps", [])
        if s.get("type") == "indicator"
    ]
    charade_with_indicator_types = {"synonym", "abbreviation", "literal", "deletion", "reversal", "letter_selection"}
    is_deletion_charade = (
        indicator_types == ["deletion"]
        and not is_container_with_transforms
        and all(t["type"] in charade_with_indicator_types for t in transforms)
    )
    is_reversal_charade = (
        indicator_types == ["reversal"]
        and not is_container_with_transforms
        and all(t["type"] in charade_with_indicator_types for t in transforms)
    )
    is_letter_selection_charade = (
        indicator_types == ["letter_selection"]
        and not is_container_with_transforms
        and all(t["type"] in charade_with_indicator_types for t in transforms)
    )
    if is_deletion_charade or is_reversal_charade or is_letter_selection_charade:
        fail_message = ""

    # Compound anagram detection: anagram indicator, transforms include anagram
    # plus literals/abbreviations/synonyms/letter_selection/deletion
    # (more than just one literal → anagram)
    compound_anagram_types = {"synonym", "abbreviation", "literal", "anagram", "letter_selection", "deletion"}
    is_compound_anagram = (
        "anagram" in indicator_types
        and not is_container_with_transforms
        and any(t["type"] == "anagram" for t in transforms)
        and all(t["type"] in compound_anagram_types for t in transforms)
        and not is_straight_anagram
    )
    if is_compound_anagram:
        fail_message = ""

    # Homophone charade detection: exactly one homophone indicator, no container,
    # transforms are synonyms/abbreviations/literals/homophones
    homophone_charade_types = {"synonym", "abbreviation", "literal", "homophone"}
    is_homophone_charade = (
        "homophone" in indicator_types
        and not is_container_with_transforms
        and any(t["type"] == "homophone" for t in transforms)
        and all(t["type"] in homophone_charade_types for t in transforms)
    )
    if is_homophone_charade:
        fail_message = ""

    # Ordering charade detection: exactly one ordering indicator, no container,
    # transforms are synonyms/abbreviations/literals
    ordering_charade_types = {"synonym", "abbreviation", "literal"}
    is_ordering_charade = (
        indicator_types == ["ordering"]
        and not is_container_with_transforms
        and all(t["type"] in ordering_charade_types for t in transforms)
    )
    if is_ordering_charade:
        fail_message = ""

    # Reversed hidden word detection: hidden_word indicator, transforms are
    # letter_selection + reversal (answer hidden backwards in adjacent text)
    is_reversed_hidden_word = (
        "hidden_word" in indicator_types
        and any(t["type"] == "letter_selection" for t in transforms)
        and any(t["type"] == "reversal" for t in transforms)
        and all(t["type"] in {"letter_selection", "reversal"} for t in transforms)
    )
    if is_reversed_hidden_word:
        fail_message = ""

    # Deletion+reversal charade detection: both deletion and reversal indicators,
    # transforms chain through synonym → deletion → reversal
    deletion_reversal_types = {"synonym", "abbreviation", "literal", "deletion", "reversal"}
    is_deletion_reversal_charade = (
        "deletion" in indicator_types
        and "reversal" in indicator_types
        and not is_container_with_transforms
        and all(t["type"] in deletion_reversal_types for t in transforms)
    )
    if is_deletion_reversal_charade:
        fail_message = ""

    # Determine profile_key for transform prompt lookup
    if is_container_with_transforms:
        profile_key = "container"
    elif is_compound_anagram:
        profile_key = "compound_anagram"
    else:
        profile_key = None

    # Build transform display data
    transform_list = _build_transform_list(
        transforms, transforms_done, template, clue, words,
        assembly_hint_index, substitution_consumed, has_substitution,
        prior_data=prior, profile_key=profile_key)

    # For simple coaching profiles, hide ALL transforms from display —
    # the coaching paragraph replaces the definition line + transform prompt with one
    # flowing sentence. The transform still runs server-side via the letter boxes.
    if is_straight_anagram or is_simple_hidden_word or is_simple_substitution:
        transform_list = []

    # Compute result letter grouping for tile spacing (e.g. "ASWAN DAM" → [5, 3])
    result_parts = [len(word) for word in step["result"].split()]

    # Compute position map (completed letters computed after auto-complete below)
    position_map = _compute_position_map(step)

    # Auto-complete abbreviation transforms when abbreviation_scan step exists
    abbreviation_scan_mappings = prior["abbreviationScanMappings"]
    if abbreviation_scan_mappings:
        for i, t in enumerate(transforms):
            if t["type"] == "abbreviation" and i not in transforms_done:
                transforms_done[i] = t["result"].upper()

    # Compute completed letters after auto-complete so abbreviation letters show in boxes
    completed_letters = _compute_completed_letters(transforms_done, position_map, step)

    # Pre-compute result groups for combined display (eliminates client reverse-map logic)
    result_groups = _compute_result_groups(position_map, step, completed_letters, transforms_done, session.get("cross_letters"))

    # Determine phase: check when completed letters spell the answer but auto-skip didn't fire
    final_result = re.sub(r'[^A-Z]', '', step["result"].upper())
    assembled = "".join(l for l in completed_letters if l)
    phase = "check" if assembled == final_result else "transforms"

    # Build abbreviation summary
    abbreviation_summary = _build_abbreviation_summary(abbreviation_scan_mappings, words, template)

    # Extract substitution source word
    source_word = ""
    for t in transforms:
        if t["type"] == "literal" and t.get("role") == "source":
            source_word = " ".join(words[i] for i in t["indices"])

    # Build virtual step with extra variables for template resolution
    virtual_step = dict(step)
    virtual_step["definitionWords"] = prior["definitionWords"]
    virtual_step["indicatorHint"] = prior["indicatorHint"]
    virtual_step["indicatorWords"] = prior["indicatorWords"]
    virtual_step["innerWords"] = prior["innerWords"]
    virtual_step["outerWords"] = prior["outerWords"]
    virtual_step["abbreviationSummary"] = abbreviation_summary
    virtual_step["sourceWord"] = source_word
    # Per-indicator-type words for coaching templates
    indicators_by_type = prior["indicatorsByType"]
    virtual_step["containerIndicatorWords"] = indicators_by_type.get("container", "")
    virtual_step["reversalIndicatorWords"] = indicators_by_type.get("reversal", "")
    virtual_step["deletionIndicatorWords"] = indicators_by_type.get("deletion", "")
    virtual_step["letterSelectionIndicatorWords"] = indicators_by_type.get("letter_selection", "")
    virtual_step["anagramIndicatorWords"] = indicators_by_type.get("anagram", "")
    virtual_step["homophoneIndicatorWords"] = indicators_by_type.get("homophone", "")
    virtual_step["orderingIndicatorWords"] = indicators_by_type.get("ordering", "")
    virtual_step["hiddenWordIndicatorWords"] = indicators_by_type.get("hidden_word", "")

    # For straight anagrams and simple hidden words, add fodder word variables for the coaching template
    if is_straight_anagram or is_simple_hidden_word:
        fodder_word = " ".join(words[i] for i in transforms[0]["indices"])
        virtual_step["fodderWord"] = fodder_word
        virtual_step["fodderWordUpper"] = fodder_word.upper()

    # For compound anagrams, add letter-counting variables for coaching paragraph
    if is_compound_anagram:
        independent_words = []
        raw_letter_total = 0
        for t in transforms:
            if t["type"] not in DEPENDENT_TRANSFORM_TYPES:
                t_word = " ".join(words[idx] for idx in t["indices"])
                independent_words.append(t_word)
                raw_letter_total += len(re.sub(r'[^A-Za-z]', '', t_word))
        virtual_step["rawLetterTotal"] = str(raw_letter_total)
        if len(independent_words) == 1:
            virtual_step["remainingWordsList"] = "'" + independent_words[0] + "'"
        else:
            virtual_step["remainingWordsList"] = (
                "'" + "' and '".join(independent_words) + "'"
            )

    # Resolve coaching lines
    definition_line, indicator_line, check_phase_prompt = _build_coaching_lines(
        template, virtual_step, clue, has_substitution,
        prior["indicatorWords"], source_word, abbreviation_summary)

    # Straight anagram: replace definitionLine with single coaching paragraph
    if is_straight_anagram:
        coaching_template = template.get("straightAnagramCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""  # No separate indicator line needed

    # Simple hidden word: replace definitionLine with single coaching paragraph
    if is_simple_hidden_word:
        coaching_template = template.get("simpleHiddenWordCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""  # No separate indicator line needed

    # Simple substitution: replace definitionLine with single coaching paragraph
    if is_simple_substitution:
        coaching_template = template.get("simpleSubstitutionCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""  # No separate indicator line needed

    # Container with transforms: per-variant coaching paragraph
    if is_container_with_transforms:
        coaching_dict = template.get("containerCoaching", {})
        # Determine variant key from non-container indicators
        non_container_indicators = [
            itype for itype in indicators_by_type if itype != "container"
        ]
        variant_key = non_container_indicators[0] if len(non_container_indicators) == 1 else "default"
        coaching_template = coaching_dict.get(variant_key, coaching_dict.get("default", ""))
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Pure charade: coaching paragraph
    if is_pure_charade:
        coaching_template = template.get("charadeCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Deletion charade: coaching paragraph
    if is_deletion_charade:
        coaching_template = template.get("deletionCharadeCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Reversal charade: coaching paragraph
    if is_reversal_charade:
        coaching_template = template.get("reversalCharadeCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Letter selection charade: coaching paragraph
    if is_letter_selection_charade:
        coaching_template = template.get("letterSelectionCharadeCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Compound anagram: coaching paragraph
    if is_compound_anagram:
        coaching_template = template.get("compoundAnagramCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Homophone charade: coaching paragraph
    if is_homophone_charade:
        coaching_template = template.get("homophoneCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Ordering charade: coaching paragraph
    if is_ordering_charade:
        coaching_template = template.get("orderingCharadeCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Reversed hidden word: coaching paragraph
    if is_reversed_hidden_word:
        coaching_template = template.get("reversedHiddenWordCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Deletion+reversal charade: coaching paragraph
    if is_deletion_reversal_charade:
        coaching_template = template.get("deletionReversalCharadeCoaching", "")
        definition_line = _resolve_variables(coaching_template, virtual_step, clue)
        indicator_line = ""

    # Show combined check button when any letter box is editable
    show_combined_check = any(
        entry["isEditable"] for group in result_groups for entry in group
    )

    return {
        "phase": phase,
        "failMessage": fail_message,
        "transforms": transform_list,
        "resultParts": result_parts,
        "positionMap": {str(k): v for k, v in position_map.items()},
        "resultGroups": result_groups,
        "completedLetters": completed_letters,
        "showCombinedCheck": show_combined_check,
        "definitionLine": definition_line,
        "indicatorLine": indicator_line,
        "checkPhasePrompt": check_phase_prompt,
    }


def _handle_assembly_input(session, step, clue, clue_id, value, transform_index=None, transform_inputs=None, letter_positions=None):
    """Handle input for an assembly step. Transforms can be submitted in any order."""
    steps = clue["steps"]
    transforms = step["transforms"]
    transforms_done = session["assembly_transforms_done"]
    feedback = RENDER_TEMPLATES["feedback"]

    # Position-based check: client sends raw {pos: letter} pairs,
    # server groups them by transform using positionMap
    if letter_positions is not None:
        position_map = _compute_position_map(step)
        # Build reverse map: position → transform index
        pos_to_transform = {}
        for t_idx, positions in position_map.items():
            for pos in positions:
                pos_to_transform[pos] = t_idx
        # Group letters by transform
        by_transform = {}
        for pos_str, letter in letter_positions.items():
            pos = int(pos_str)
            t_idx = pos_to_transform.get(pos)
            if t_idx is not None:
                if t_idx not in by_transform:
                    by_transform[t_idx] = {}
                by_transform[t_idx][pos] = letter
        # Convert to ordered letter arrays matching position_map order
        grouped = {}
        for t_idx, pos_letters in by_transform.items():
            ordered_positions = position_map[t_idx]
            grouped[str(t_idx)] = [pos_letters.get(p, '') for p in ordered_positions]
        # Delegate to existing transform_inputs logic
        return _handle_assembly_input(session, step, clue, clue_id, value, transform_inputs=grouped)

    # Combined check: client sends all letter inputs grouped by transform
    # Server decides which are complete and validates them
    if transform_inputs is not None:
        any_correct = False
        any_wrong = False
        for t_idx_str, letters in transform_inputs.items():
            t_idx = int(t_idx_str)
            if t_idx in transforms_done:
                continue  # Already completed, skip
            if not letters or not all(c.strip() for c in letters):
                continue  # Incomplete input, skip (not an error)
            letter_str = "".join(letters)
            # Validate this transform
            result = _handle_assembly_input(session, step, clue, clue_id, letter_str, transform_index=t_idx)
            if result["correct"]:
                any_correct = True
            else:
                any_wrong = True
        # Return combined result
        if any_correct:
            return {"correct": True, "message": feedback["step_correct"], "render": get_render(clue_id, clue, session)}
        elif any_wrong:
            return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue, session)}
        else:
            # Nothing to check (all empty or already done)
            return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue, session)}

    if transform_index is not None and 0 <= transform_index < len(transforms):
        # Transform submission: validate against this specific transform
        expected = transforms[transform_index]["result"]
        user_text = re.sub(r'[^A-Z]', '', str(value).upper())
        expected_text = re.sub(r'[^A-Z]', '', expected.upper())

        if user_text == expected_text:
            transforms_done[transform_index] = expected.upper()
            session["assembly_hint_index"] = None

            # Auto-complete all predecessors consumed by this dependent transform,
            # recursively handling chained dependents (e.g. anagram consumes reversal
            # which consumes synonym)
            if "type" not in transforms[transform_index]:
                raise ValueError(f"Transform {transform_index} is missing 'type' field")
            t_type = transforms[transform_index]["type"]
            if t_type in DEPENDENT_TRANSFORM_TYPES and transform_index > 0:
                queue = [transform_index]
                while queue:
                    dep = queue.pop(0)
                    consumed = find_consumed_predecessors(transforms, dep)
                    for c in consumed:
                        if c not in transforms_done:
                            transforms_done[c] = transforms[c]["result"].upper()
                            # If this predecessor is itself dependent, recurse
                            if c > 0 and transforms[c]["type"] in DEPENDENT_TRANSFORM_TYPES:
                                queue.append(c)

            # Auto-skip: do the completed letters spell the answer?
            position_map = _compute_position_map(step)
            completed_letters = _compute_completed_letters(transforms_done, position_map, step)
            final_result = re.sub(r'[^A-Z]', '', step["result"].upper())
            assembled = "".join(l for l in completed_letters if l)

            if assembled == final_result:
                    # Auto-skip check phase — assembly is complete
                    step_index = session["step_index"]
                    session["completed_steps"].append(step_index)
                    session["step_index"] = _next_active_step(steps, session["completed_steps"], step_index)
                    session["selected_indices"] = []
                    session["step_expanded"] = False
                    session["assembly_transforms_done"] = {}
                    session["assembly_hint_index"] = None
                    # Lock the answer and populate answer boxes
                    session["answer_locked"] = True
                    answer_letters = list(re.sub(r'[^A-Z]', '', clue["answer"].upper()))
                    session["user_answer"] = answer_letters

            return {"correct": True, "message": feedback["step_correct"], "render": get_render(clue_id, clue, session)}
        else:
            return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue, session)}

    elif transform_index is None:
        # Check phase: validate the full assembled result

        expected = step["result"]
        user_text = re.sub(r'[^A-Z]', '', str(value).upper())
        expected_text = re.sub(r'[^A-Z]', '', expected.upper())

        if user_text == expected_text:
            step_index = session["step_index"]
            session["completed_steps"].append(step_index)
            session["step_index"] = _next_active_step(steps, session["completed_steps"], step_index)
            session["selected_indices"] = []
            session["hint_visible"] = False
            session["step_expanded"] = False
            session["assembly_transforms_done"] = {}
            session["assembly_hint_index"] = None
            # Lock the answer and populate answer boxes
            session["answer_locked"] = True
            answer_letters = list(re.sub(r'[^A-Z]', '', clue["answer"].upper()))
            session["user_answer"] = answer_letters
            return {"correct": True, "message": feedback["step_correct"], "render": get_render(clue_id, clue, session)}
        else:
            return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue, session)}

    else:
        raise ValueError(f"Invalid transform_index: {transform_index}")



# find_consumed_predecessors and find_terminal_transforms live in training_constants.py


def _compute_position_map(step):
    """Compute which final-answer positions each terminal transform fills.

    A transform is 'terminal' if no later dependent transform supersedes it.

    Two container styles:
    - Explicit container transform (29463 style): container is terminal,
      outer/inner feed into it. Handled by expanding container terminals.
    - Implicit container (29453 style): outer and inners are all terminal,
      no container transform. Handled by _expand_implicit_container.

    Non-container terminals are laid out left-to-right (charade order).
    """
    transforms = step["transforms"]
    result = re.sub(r'[^A-Z]', '', step["result"].upper())

    # Identify terminal transforms (those not superseded by a later dependent)
    terminal = find_terminal_transforms(transforms)

    # Check for implicit container: outer/inner roles, all terminal, no container transform
    roles = {transforms[i]["role"] for i in terminal}
    has_outer = "outer" in roles
    has_inner = "inner" in roles or any(r.startswith("inner_") for r in roles)
    has_container_type = any(transforms[i]["type"] == "container" for i in terminal)

    if has_outer and has_inner and not has_container_type:
        # 29453 style: all outer/inner are terminal, insertion is implicit
        return _expand_implicit_container(transforms, terminal, result)

    # Lay out terminals left-to-right, expanding any container terminals
    position_map = {}
    pos = 0
    for idx in sorted(terminal):
        t = transforms[idx]
        if t["type"] == "container":
            # Expand container into outer/inner sub-groups
            sub_map = _expand_container_terminal(transforms, terminal, idx, pos)
            position_map.update(sub_map)
            container_len = len(re.sub(r'[^A-Z]', '', t["result"].upper()))
            pos += container_len
        else:
            t_result = re.sub(r'[^A-Z]', '', t["result"].upper())
            position_map[idx] = list(range(pos, pos + len(t_result)))
            pos += len(t_result)
    return position_map


def _expand_container_terminal(transforms, terminal, container_idx, offset):
    """Expand a container terminal into outer/inner position sub-groups.

    Finds the outer and terminal inner transforms that feed into this container,
    pattern-matches where the inner sits inside the outer, and returns position
    assignments for each piece (offset by the container's start position).

    Uses find_consumed_predecessors to identify the container's direct inputs,
    then classifies each as outer or inner by tracing back through dependency
    chains to the original role (e.g. reversal of inner_b inherits inner role).
    """
    # Find the container's direct inputs via dependency analysis
    direct_inputs = find_consumed_predecessors(transforms, container_idx)

    outer_idx = None
    inner_indices = []
    for i in direct_inputs:
        effective_role = _trace_effective_role(transforms, i)
        if effective_role == "outer":
            outer_idx = i
        elif effective_role == "inner" or effective_role.startswith("inner_"):
            inner_indices.append(i)

    container_result = re.sub(r'[^A-Z]', '', transforms[container_idx]["result"].upper())

    # If role-based classification didn't find outer/inner (e.g. sub-container
    # in a charade using part roles), determine from letter pattern matching:
    # try each direct input as outer, rest as inner, check if insertion works.
    if outer_idx is None or not inner_indices:
        from itertools import permutations as _perms
        input_results = {
            i: re.sub(r'[^A-Z]', '', transforms[i]["result"].upper())
            for i in direct_inputs
        }
        found = False
        for candidate_outer in direct_inputs:
            candidate_inners = [i for i in direct_inputs if i != candidate_outer]
            for perm in _perms(candidate_inners):
                combined = "".join(input_results[i] for i in perm)
                for pos in range(len(container_result) - len(combined) + 1):
                    if container_result[pos:pos + len(combined)] == combined:
                        remaining = container_result[:pos] + container_result[pos + len(combined):]
                        if remaining == input_results[candidate_outer]:
                            outer_idx = candidate_outer
                            inner_indices = list(perm)
                            found = True
                            break
                if found:
                    break
            if found:
                break
        if not found:
            raise ValueError(
                f"Container transform {container_idx} (result={container_result}) "
                f"cannot determine outer/inner from inputs. "
                f"Roles: {[transforms[i]['role'] for i in direct_inputs]}"
            )

    outer_result = re.sub(r'[^A-Z]', '', transforms[outer_idx]["result"].upper())
    combined_inner = "".join(
        re.sub(r'[^A-Z]', '', transforms[idx]["result"].upper())
        for idx in inner_indices
    )

    for insert_pos in range(len(container_result) - len(combined_inner) + 1):
        if container_result[insert_pos:insert_pos + len(combined_inner)] == combined_inner:
            remaining = container_result[:insert_pos] + container_result[insert_pos + len(combined_inner):]
            if remaining == outer_result:
                position_map = {}
                # Outer positions: prefix + suffix around the inner
                outer_positions = (
                    list(range(offset, offset + insert_pos)) +
                    list(range(offset + insert_pos + len(combined_inner), offset + len(container_result)))
                )
                position_map[outer_idx] = outer_positions
                # Each inner transform gets its slice
                inner_pos = offset + insert_pos
                for idx in inner_indices:
                    inner_len = len(re.sub(r'[^A-Z]', '', transforms[idx]["result"].upper()))
                    position_map[idx] = list(range(inner_pos, inner_pos + inner_len))
                    inner_pos += inner_len
                return position_map

    raise ValueError(
        f"Could not find insertion point for container transform {container_idx}: "
        f"outer={outer_result}, inner={combined_inner}, container={container_result}"
    )


def _expand_implicit_container(transforms, terminal, result):
    """For 29453-style containers: outer/inner are all terminal, no container transform.

    Find the outer and inner terminals, pattern-match the insertion point,
    and assign positions to each piece.
    """
    outer_idx = None
    inner_indices = []
    for i in sorted(terminal):
        t = transforms[i]
        if t["role"] == "outer":
            outer_idx = i
        elif t["role"] == "inner" or t["role"].startswith("inner_"):
            inner_indices.append(i)

    if outer_idx is None or not inner_indices:
        raise ValueError(
            f"Implicit container has no outer/inner terminals. "
            f"Terminal roles: {[transforms[i]['role'] for i in sorted(terminal)]}"
        )

    outer_result = re.sub(r'[^A-Z]', '', transforms[outer_idx]["result"].upper())
    combined_inner = "".join(
        re.sub(r'[^A-Z]', '', transforms[idx]["result"].upper())
        for idx in inner_indices
    )

    for insert_pos in range(len(result) - len(combined_inner) + 1):
        if result[insert_pos:insert_pos + len(combined_inner)] == combined_inner:
            remaining = result[:insert_pos] + result[insert_pos + len(combined_inner):]
            if remaining == outer_result:
                position_map = {}
                outer_positions = (
                    list(range(0, insert_pos)) +
                    list(range(insert_pos + len(combined_inner), len(result)))
                )
                position_map[outer_idx] = outer_positions
                inner_pos = insert_pos
                for idx in inner_indices:
                    inner_len = len(re.sub(r'[^A-Z]', '', transforms[idx]["result"].upper()))
                    position_map[idx] = list(range(inner_pos, inner_pos + inner_len))
                    inner_pos += inner_len
                return position_map

    raise ValueError(
        f"Could not find insertion point for implicit container: "
        f"outer={outer_result}, inner={combined_inner}, result={result}"
    )


def _trace_effective_role(transforms, idx):
    """Trace back through dependency chains to find the original role.

    A dependent transform (e.g. reversal) inherits the role of its source.
    For example, if transform 3 (role="reversal") consumes transform 2
    (role="inner_b"), the effective role of transform 3 is "inner_b".
    Non-dependent transforms return their own role directly.
    """
    t = transforms[idx]
    role = t.get("role", "")
    # If this transform has an outer/inner role already, use it
    if role == "outer" or role == "inner" or role.startswith("inner_"):
        return role
    # If it's a dependent, trace back to its source
    if t.get("type") in DEPENDENT_TRANSFORM_TYPES and idx > 0:
        consumed = find_consumed_predecessors(transforms, idx)
        if consumed:
            # Recurse into the first consumed predecessor to find the inherited role
            return _trace_effective_role(transforms, consumed[0])
    return role


def _is_consumed_before(transforms, idx, before_idx):
    """Check if transform at idx is consumed by a dependent transform before before_idx."""
    for i in range(idx + 1, before_idx):
        t = transforms[i]
        if t.get("type") in DEPENDENT_TRANSFORM_TYPES:
            consumed = find_consumed_predecessors(transforms, i)
            if idx in consumed:
                return True
    return False


def _compute_result_groups(position_map, step, completed_letters, transforms_done, cross_letters=None):
    """Pre-compute grouped position data for the combined result display.

    Returns a list of groups, where each group is a list of
    {pos, transformIndex, letter, isEditable, crossLetter}.
    Groups are contiguous runs of positions belonging to the same transform.

    Per-position metadata:
    - letter: the completed letter at this position (string or None)
    - isEditable: False when letter is filled or the position's transform is done
    - crossLetter: letter from crossing word at this position (string or "")
    """
    result = re.sub(r'[^A-Z]', '', step["result"].upper())
    total_positions = len(result)

    # Build cross-letter lookup: position → letter
    cross_map = {}
    if cross_letters:
        for cl in cross_letters:
            if cl.get("letter"):
                cross_map[cl["position"]] = cl["letter"]

    # Build reverse map: position → transform index
    pos_to_transform = {}
    for t_idx_str, positions in position_map.items():
        t_idx = int(t_idx_str) if isinstance(t_idx_str, str) else t_idx_str
        for pos in positions:
            pos_to_transform[pos] = t_idx

    # Walk positions in order, grouping contiguous runs with the same transform
    groups = []
    current_group = []
    current_transform = None

    for pos in range(total_positions):
        t = pos_to_transform.get(pos)
        if t != current_transform and current_group:
            groups.append(current_group)
            current_group = []
        letter = completed_letters[pos] if pos < len(completed_letters) else None
        is_editable = letter is None and t not in transforms_done
        current_group.append({
            "pos": pos,
            "transformIndex": t,
            "letter": letter,
            "isEditable": is_editable,
            "crossLetter": cross_map.get(pos, ""),
        })
        current_transform = t

    if current_group:
        groups.append(current_group)

    return groups


def _compute_completed_letters(transforms_done, position_map, step):
    """Build the partially-filled answer array from completed transforms."""
    result = re.sub(r'[^A-Z]', '', step["result"].upper())
    letters = [None] * len(result)

    for idx, transform_result in transforms_done.items():
        if idx in position_map:
            clean_result = re.sub(r'[^A-Z]', '', transform_result.upper())
            for i, pos in enumerate(position_map[idx]):
                if i < len(clean_result) and pos < len(letters):
                    letters[pos] = clean_result[i]

    return letters


def _is_step_available(step_index, step, steps, completed_steps):
    """Determine if a step is available (active) for the student to work on.

    All non-assembly steps are always available (unless already completed).
    Assembly steps are gated: available only when ALL prior steps are completed.
    """
    if step_index in completed_steps:
        return False  # Already done
    if step["type"] == "assembly":
        pre_assembly = set(range(step_index))
        return pre_assembly.issubset(set(completed_steps))
    return True  # All non-assembly steps always available


def _next_active_step(steps, completed_steps, current_index):
    """Find the next uncompleted, available step after current_index.

    Scans forward from current_index+1, then wraps to 0.
    Returns the step index, or len(steps) if all steps are completed.
    """
    n = len(steps)
    for offset in range(1, n + 1):
        candidate = (current_index + offset) % n
        if _is_step_available(candidate, steps[candidate], steps, completed_steps):
            return candidate
    # All steps completed
    return n


def _build_step_list(session, clue):
    """Build the step summary list for the sidebar/menu."""
    steps = clue["steps"]
    completed_steps = session["completed_steps"]

    # Build transform results map: role → result (from assembly step data)
    # Only backfill when the assembly step itself is completed
    transform_results = _get_transform_results(steps, completed_steps)

    result = []

    for i, step in enumerate(steps):
        template = RENDER_TEMPLATES.get(step["type"])
        if not template:
            raise ValueError(f"No render template for step type '{step['type']}'")
        title = _resolve_variables(template["menuTitle"], step, clue)

        if i in completed_steps:
            status = "completed"
            if "completedTitle" not in template:
                raise ValueError(f"Render template for step type '{step['type']}' missing 'completedTitle' field")
            title = _resolve_variables(template["completedTitle"], step, clue)
            completion_text = _resolve_on_correct(template, step, clue)

            # Backfill: enrich outer_word/inner_word titles with transform results
            if step["type"] in ("outer_word", "inner_word") and transform_results:
                if step["type"] == "outer_word":
                    transform_result = transform_results.get("outer")
                else:
                    # inner_word: check "inner" first, then collect inner_a, inner_b, etc.
                    transform_result = transform_results.get("inner")
                    if not transform_result:
                        inner_parts = sorted(
                            (k, v) for k, v in transform_results.items()
                            if k.startswith("inner_")
                        )
                        if inner_parts:
                            transform_result = " + ".join(v for _, v in inner_parts)
                if transform_result:
                    words_str = " ".join(clue["words"][idx] for idx in step["indices"])
                    backfill_tmpl = template["backfillTitle"]
                    title = backfill_tmpl.replace("{words}", words_str).replace("{transformResult}", transform_result)
        elif _is_step_available(i, step, steps, completed_steps):
            status = "active"
            completion_text = None
        else:
            status = "pending"
            completion_text = None

        result.append({
            "index": i,
            "type": step["type"],
            "title": title,
            "status": status,
            "completionText": completion_text,
        })

    return result


def _get_transform_results(steps, completed_steps):
    """Extract transform role→result map from a completed assembly step.

    When multiple transforms share the same role (e.g. two 'inner' transforms),
    their results are joined with ' + '.
    """
    for i, step in enumerate(steps):
        if "transforms" in step and i in completed_steps:
            results = {}
            for t in step["transforms"]:
                role = t["role"]
                result = t["result"].upper()
                if role in results:
                    results[role] += " + " + result
                else:
                    results[role] = result
            return results
    return {}


def _build_all_done(session, clue, clue_id):
    """Build the render when all steps are completed. Same layout, no currentStep."""
    # Populate answer boxes if not already filled
    if not session["user_answer"]:
        answer_letters = list(re.sub(r'[^A-Z]', '', clue["answer"].upper()))
        session["user_answer"] = answer_letters

    # Compute answer box groups from enumeration (same logic as get_render)
    enum_str = clue.get("enumeration", "")
    answer_groups = []
    for part in re.split(r'[,\s]+', enum_str):
        if part:
            total = sum(int(n) for n in part.split('-') if n.isdigit())
            if total > 0:
                answer_groups.append(total)

    return {
        "clue_id": clue_id,
        "words": clue["words"],
        "answer": clue["answer"],
        "enumeration": clue["enumeration"],
        "answerGroups": answer_groups,
        "steps": _build_step_list(session, clue),
        "currentStep": None,
        "stepExpanded": False,
        "helpVisible": False,
        "helpText": "",
        "highlights": session["highlights"],
        "selectedIndices": [],
        "userAnswer": session["user_answer"],
        "answerLocked": session["answer_locked"],
        "complete": True,
        "session": _sign_session(session),
    }


def _resolve_expected(step, template):
    """Get the expected answer for validation from the step data."""
    source = template.get("expected_source")
    if not source:
        raise ValueError(f"No expected_source in template for {step['type']}")

    if source == "indices":
        return step["indices"]
    elif source == "result":
        return step["result"]
    elif source == "expected":
        return step["expected"]
    else:
        raise ValueError(f"Unknown expected_source: {source}")


def _get_dict_key(step):
    """Get the dict lookup key from step metadata.

    Templates use dict-keyed fields (prompt, intro) where the key comes from
    the step's type-specific field: indicator_type or definition_part.
    """
    if "indicator_type" in step:
        return step["indicator_type"]
    if "definition_part" in step:
        return step["definition_part"]
    raise ValueError(
        f"Step type '{step.get('type', '?')}' has dict-based template field "
        f"but step metadata has neither 'indicator_type' nor 'definition_part'"
    )


def _resolve_simple_variables(text, step, clue):
    """Resolve basic {variable} placeholders: words, enumeration, hint, result, expected."""
    # {words} — joined from clue words at step indices
    if "{words}" in text and "indices" in step:
        words = [clue["words"][i] for i in step["indices"]]
        text = text.replace("{words}", " ".join(words))

    # {enumeration}
    if "{enumeration}" in text:
        if "enumeration" not in clue:
            raise ValueError(f"Template uses {{enumeration}} but clue metadata is missing 'enumeration'")
        text = text.replace("{enumeration}", clue["enumeration"])

    # {hint} — from step hint field
    if "{hint}" in text:
        if "hint" not in step:
            raise ValueError(f"Template uses {{hint}} but step metadata is missing 'hint' for step type '{step.get('type', '?')}'")
        text = text.replace("{hint}", step["hint"])

    # {result}
    if "{result}" in text:
        if "result" not in step:
            raise ValueError(f"Template uses {{result}} but step metadata is missing 'result' for step type '{step.get('type', '?')}'")
        text = text.replace("{result}", step["result"])

    # {expected}
    if "{expected}" in text:
        if "expected" not in step:
            raise ValueError(f"Template uses {{expected}} but step metadata is missing 'expected' for step type '{step.get('type', '?')}'")
        text = text.replace("{expected}", str(step["expected"]))

    # {definitionPart} — from multi_definition step's definition_part field
    if "{definitionPart}" in text:
        if "definition_part" not in step:
            raise ValueError(f"Template uses {{definitionPart}} but step metadata is missing 'definition_part'")
        text = text.replace("{definitionPart}", step["definition_part"])

    # {wordPlural} — "word" or "words" based on how many indices the step expects
    if "{wordPlural}" in text:
        if "indices" not in step:
            raise ValueError(f"Template uses {{wordPlural}} but step metadata is missing 'indices'")
        text = text.replace("{wordPlural}", "word" if len(step["indices"]) == 1 else "words")

    # {indicatorType} — from indicator step's indicator_type field
    if "{indicatorType}" in text:
        if "indicator_type" not in step:
            raise ValueError(f"Template uses {{indicatorType}} but step metadata is missing 'indicator_type'")
        text = text.replace("{indicatorType}", step["indicator_type"].replace("_", " "))

    return text


def _resolve_assembly_context_variables(text, step):
    """Resolve assembly-specific context variables injected via virtual step."""
    variable_map = {
        "{definitionWords}": "definitionWords",
        "{indicatorHint}": "indicatorHint",
        "{indicatorWords}": "indicatorWords",
        "{innerWords}": "innerWords",
        "{outerWords}": "outerWords",
        "{abbreviationSummary}": "abbreviationSummary",
        "{sourceWord}": "sourceWord",
        "{fodderWord}": "fodderWord",
        "{fodderWordUpper}": "fodderWordUpper",
        "{containerIndicatorWords}": "containerIndicatorWords",
        "{reversalIndicatorWords}": "reversalIndicatorWords",
        "{deletionIndicatorWords}": "deletionIndicatorWords",
        "{letterSelectionIndicatorWords}": "letterSelectionIndicatorWords",
        "{anagramIndicatorWords}": "anagramIndicatorWords",
        "{homophoneIndicatorWords}": "homophoneIndicatorWords",
        "{orderingIndicatorWords}": "orderingIndicatorWords",
        "{hiddenWordIndicatorWords}": "hiddenWordIndicatorWords",
        "{rawLetterTotal}": "rawLetterTotal",
        "{remainingWordsList}": "remainingWordsList",
    }
    for placeholder, field in variable_map.items():
        if placeholder in text:
            if field not in step:
                raise ValueError(f"Template uses {placeholder} but step is missing '{field}'")
            text = text.replace(placeholder, step[field])
    return text


def _resolve_abbreviation_breakdown(text, step, clue):
    """Resolve {abbreviationBreakdown} — one line per abbreviation from mappings."""
    if "{abbreviationBreakdown}" not in text:
        return text
    if "mappings" not in step:
        raise ValueError(f"Template uses {{abbreviationBreakdown}} but step is missing 'mappings'")
    abbrev_template = RENDER_TEMPLATES.get("abbreviation_scan", {})
    line_template = abbrev_template.get("breakdownLineTemplate", "")
    if not line_template:
        raise ValueError("abbreviation_scan template missing 'breakdownLineTemplate'")
    words = clue["words"]
    lines = []
    for idx_str, letter in step["mappings"].items():
        word = words[int(idx_str)]
        lines.append(line_template.replace("{word}", word).replace("{letter}", letter))
    return text.replace("{abbreviationBreakdown}", "\n".join(lines))


def _resolve_assembly_breakdown(text, step, clue):
    """Resolve {assemblyBreakdown} — build the assembly journey display.

    Shows container notation (e.g. SOL(ARE)E) or charade parts (e.g. 'work' → OP + US)
    using display patterns from completedTextTemplates in render_templates.json.
    """
    if "{assemblyBreakdown}" not in text or "transforms" not in step:
        return text
    transforms = step["transforms"]

    # Load display patterns from render template
    assembly_template = RENDER_TEMPLATES.get("assembly", {})
    ct = assembly_template.get("completedTextTemplates", {})
    independent_tpl = ct.get("independent", "")
    dependent_tpl = ct.get("dependentGroup", "")
    container_notation_tpl = ct.get("containerNotation", "")
    container_fallback_tpl = ct.get("containerFallback", "")
    part_joiner = ct.get("partJoiner", " + ")
    if not independent_tpl or not dependent_tpl or not container_notation_tpl or not container_fallback_tpl:
        raise ValueError("Assembly template missing required completedTextTemplates entries")

    # Detect container clues (outer/inner roles — inner can be "inner", "inner_a", etc.)
    roles = {t["role"] for t in transforms}
    has_inner = "inner" in roles or any(r.startswith("inner_") for r in roles)
    is_container = "outer" in roles and has_inner

    if is_container:
        breakdown = _resolve_container_breakdown(
            transforms, step, clue, independent_tpl, container_notation_tpl,
            container_fallback_tpl, part_joiner)
    else:
        breakdown = _resolve_charade_breakdown(
            transforms, clue, independent_tpl, dependent_tpl, part_joiner)

    return text.replace("{assemblyBreakdown}", breakdown)


def _resolve_container_breakdown(transforms, step, clue, independent_tpl,
                                  container_notation_tpl, container_fallback_tpl, part_joiner):
    """Build container notation breakdown (e.g. SOL(ARE + C + LIPS)E)."""
    # Find outer, inner, and container transform by role
    outer_idx = None
    inner_parts = []
    container_idx = None
    for i, t in enumerate(transforms):
        if t["role"] == "outer":
            outer_idx = i
        elif t["role"] == "inner" or t["role"].startswith("inner_"):
            inner_parts.append((i, t["result"].upper()))
        elif t["type"] == "container":
            container_idx = i

    # If an inner part is consumed by a dependent transform (e.g. reversal),
    # use the dependent's result instead of the raw inner result.
    consumed_by = {}  # maps consumed index → dependent index
    for i, t in enumerate(transforms):
        if i > 0 and t["type"] in DEPENDENT_TRANSFORM_TYPES and t["type"] != "container":
            consumed = find_consumed_predecessors(transforms, i)
            for c in consumed:
                consumed_by[c] = i
    inner_parts = [
        (consumed_by[idx], transforms[consumed_by[idx]]["result"].upper())
        if idx in consumed_by else (idx, result)
        for idx, result in inner_parts
    ]

    if outer_idx is None or not inner_parts:
        raise ValueError("Container clue has outer/inner roles but no terminal outer or inner transforms found")

    outer_result = re.sub(r'[^A-Z]', '', transforms[outer_idx]["result"].upper())
    combined_inner = "".join(re.sub(r'[^A-Z]', '', p[1]) for p in inner_parts)
    # Use the container transform's result for position matching
    if container_idx is not None:
        container_result = re.sub(r'[^A-Z]', '', transforms[container_idx]["result"].upper())
    else:
        container_result = re.sub(r'[^A-Z]', '', step["result"].upper())

    # Find where inner sits inside outer
    inner_display = part_joiner.join(p[1] for p in inner_parts)
    inserted = False
    for insert_pos in range(len(container_result) - len(combined_inner) + 1):
        if container_result[insert_pos:insert_pos + len(combined_inner)] == combined_inner:
            remaining = container_result[:insert_pos] + container_result[insert_pos + len(combined_inner):]
            if remaining == outer_result:
                prefix = outer_result[:insert_pos]
                suffix = outer_result[insert_pos:]
                container_notation = container_notation_tpl.replace("{prefix}", prefix).replace("{inner}", inner_display).replace("{suffix}", suffix)
                inserted = True
                break

    if not inserted:
        container_notation = container_fallback_tpl.replace("{outer}", outer_result).replace("{inner}", inner_display)

    # Collect terminal transforms and build full breakdown
    container_roles = {"outer", "inner", "container"}
    terminal = find_terminal_transforms(transforms)
    words = clue.get("words", [])

    # Build source-word mappings for outer/inner transforms (non-abbreviation)
    # These show what the student discovered during assembly (e.g. 'carriage' → GAIT)
    # Use the transform's own result (what the student found), not a dependent's result
    # (e.g. show 'scheme' → RUSE, not 'scheme' → ESUR — the reversal is in the notation).
    # Abbreviation transforms are skipped — they're shown by the abbreviation_scan step.
    source_parts = []
    for i, t in enumerate(transforms):
        role = t.get("role", "")
        if role not in ("outer", "inner") and not role.startswith("inner_"):
            continue
        if t["type"] == "abbreviation":
            continue
        result_upper = t["result"].upper()
        clue_word = " ".join(words[idx] for idx in t["indices"]) if words and "indices" in t else ""
        if clue_word and clue_word.upper().replace(" ", "") != result_upper.replace(" ", ""):
            source_parts.append(independent_tpl.replace("{clueWord}", clue_word).replace("{result}", result_upper))

    parts = []
    # Add source-word mappings before the container notation
    parts.extend(source_parts)

    container_placed = False
    for i in sorted(terminal):
        t = transforms[i]
        if t["type"] == "container" and not container_placed:
            parts.append(container_notation)
            container_placed = True
        elif t["role"] not in container_roles and not t["role"].startswith("inner_"):
            result_upper = t["result"].upper()
            clue_word = " ".join(words[idx] for idx in t["indices"]) if words and "indices" in t else ""
            if clue_word and clue_word.upper().replace(" ", "") != result_upper.replace(" ", ""):
                parts.append(independent_tpl.replace("{clueWord}", clue_word).replace("{result}", result_upper))
            else:
                parts.append(result_upper)
    if not container_placed:
        parts.append(container_notation)

    return part_joiner.join(parts)


def _resolve_charade_breakdown(transforms, clue, independent_tpl, dependent_tpl, part_joiner):
    """Build charade/chain breakdown (e.g. 'doldrums' → LOW + 'Sailor' → TAR)."""
    words = clue.get("words", [])
    parts = []  # list of (display_text, raw_result)
    for i, t in enumerate(transforms):
        if "type" not in t:
            raise ValueError(f"Transform is missing 'type' field in assembly step")
        t_type = t["type"]
        result = t["result"].upper()
        if t_type in DEPENDENT_TRANSFORM_TYPES and parts:
            consumed = find_consumed_predecessors(transforms, i)
            consumed_displays = []
            for _ in consumed:
                if parts:
                    disp, _ = parts.pop()
                    consumed_displays.insert(0, disp)
            consumed_str = part_joiner.join(consumed_displays)
            display = dependent_tpl.replace("{consumed}", consumed_str).replace("{result}", result)
            parts.append((display, result))
        else:
            clue_word = " ".join(words[idx] for idx in t["indices"]) if words else ""
            if clue_word.upper().replace(" ", "") == result.replace(" ", ""):
                display = result
            else:
                display = independent_tpl.replace("{clueWord}", clue_word).replace("{result}", result)
            parts.append((display, result))
    return part_joiner.join(d for d, _ in parts)


def _resolve_variables(text, step, clue):
    """Replace {variable} placeholders in a template string.

    Delegates to focused helpers for each category of variable.
    """
    if text is None:
        raise ValueError("_resolve_variables received None — template field is missing")
    if text == "":
        return ""

    text = _resolve_simple_variables(text, step, clue)
    text = _resolve_assembly_context_variables(text, step)
    text = _resolve_abbreviation_breakdown(text, step, clue)
    text = _resolve_assembly_breakdown(text, step, clue)

    return text


def _resolve_on_correct(template, step, clue):
    """Resolve the onCorrect text with variable substitution."""
    if "onCorrect" not in template:
        raise ValueError(f"Render template for step type '{step['type']}' missing 'onCorrect' field")
    return _resolve_variables(template["onCorrect"], step, clue)
