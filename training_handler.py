"""
Training Handler - Simple Sequencer Engine
==========================================

Reads flat steps from clue metadata, looks up render templates by step type,
presents each step, validates input, advances. That's it.
"""

import json
import os
import re

from training_constants import DEPENDENT_TRANSFORM_TYPES
from validate_training import validate_training_item

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


def get_clue_data(clue_id):
    """Get clue data from the active session. Returns clue_data or None."""
    session = _sessions.get(clue_id)
    if session:
        return session.get('clue_data')
    return None

# --- Sessions ---

_sessions = {}


def start_session(clue_id, clue):
    """Initialize a training session. Returns the initial render."""
    _sessions[clue_id] = {
        "clue_id": clue_id,
        "clue_data": clue,
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
    }
    return get_render(clue_id, clue)


def get_render(clue_id, clue):
    """Build the complete render object for the current state."""
    session = _sessions.get(clue_id)
    if not session:
        raise ValueError(f"No session for clue_id: {clue_id}")

    steps = clue["steps"]
    step_index = session["step_index"]

    # All steps done → show completed step list (no separate completion view)
    if step_index >= len(steps):
        return _build_all_done(session, clue)

    step = steps[step_index]

    # Auto-complete assembly for double definitions — no transforms to show,
    # the student just types the answer in the answer box
    if step["type"] == "assembly" and clue.get("clue_type") == "double_definition":
        session["completed_steps"].append(step_index)
        session["step_index"] = step_index + 1
        session["answer_locked"] = True
        answer_letters = list(re.sub(r'[^A-Z]', '', clue["answer"].upper()))
        session["user_answer"] = answer_letters
        return _build_all_done(session, clue)

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
        "prompt": resolved_prompt,
    }

    # Intro (template may be dict keyed by indicator_type or definition_part)
    if "intro" in template:
        intro_data = template["intro"]
        if isinstance(intro_data, dict):
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

    return {
        "clue_id": clue_id,
        "words": clue["words"],
        "answer": clue["answer"],
        "enumeration": clue["enumeration"],
        "answerGroups": answer_groups,
        "steps": step_list,
        "currentStep": current_step,
        "stepExpanded": session["step_expanded"],
        "highlights": session["highlights"],
        "selectedIndices": session["selected_indices"],
        "userAnswer": session["user_answer"],
        "answerLocked": session["answer_locked"],
        "complete": False,
    }


def handle_input(clue_id, clue, value, transform_index=None, transform_inputs=None):
    """Validate user input for the current step. Returns {correct, render, message?}."""
    session = _sessions.get(clue_id)
    if not session:
        raise ValueError(f"No session for clue_id: {clue_id}")

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
        return _handle_assembly_input(session, step, clue, clue_id, value, transform_index, transform_inputs)

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

        # Mark completed, advance
        session["completed_steps"].append(step_index)
        session["step_index"] = step_index + 1
        session["selected_indices"] = []
        session["hint_visible"] = False
        session["step_expanded"] = False
        session["assembly_transforms_done"] = {}
        session["assembly_hint_index"] = None

        return {"correct": True, "message": feedback["step_correct"], "render": get_render(clue_id, clue)}
    else:
        return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue)}


def update_ui_state(clue_id, clue, action, data):
    """Update UI state without validating. Returns updated render."""
    session = _sessions.get(clue_id)
    if not session:
        raise ValueError(f"No session for clue_id: {clue_id}")

    if action == "toggle_hint":
        session["hint_visible"] = not session["hint_visible"]

    elif action == "toggle_assembly_hint":
        transform_idx = data.get("transform_index")
        if transform_idx is not None:
            if session.get("assembly_hint_index") == transform_idx:
                session["assembly_hint_index"] = None
            else:
                session["assembly_hint_index"] = transform_idx

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

    elif action == "type_step_input":
        # For text input steps (not used in definition, but ready)
        pass

    else:
        raise ValueError(f"Unknown UI action: {action}")

    return get_render(clue_id, clue)


def reveal_answer(clue_id, clue):
    """Skip to completion, revealing the full decode."""
    session = _sessions.get(clue_id)
    if not session:
        raise ValueError(f"No session for clue_id: {clue_id}")

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

    return get_render(clue_id, clue)


def check_answer(clue_id, clue, answer):
    """Check if the typed answer matches. Returns {correct, render}."""
    session = _sessions.get(clue_id)
    if not session:
        raise ValueError(f"No session for clue_id: {clue_id}")

    user_text = re.sub(r'[^A-Z]', '', str(answer).upper())
    expected_text = re.sub(r'[^A-Z]', '', clue["answer"].upper())
    feedback = RENDER_TEMPLATES["feedback"]

    if user_text == expected_text:
        session["answer_locked"] = True
        return {"correct": True, "message": feedback["answer_correct"], "render": get_render(clue_id, clue)}
    else:
        return {"correct": False, "message": feedback["answer_incorrect"], "render": get_render(clue_id, clue)}


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


def _build_transform_list(transforms, transforms_done, template, clue, words,
                           assembly_hint_index, substitution_consumed, has_substitution):
    """Build the display list of transforms for the assembly step.

    Each transform gets a prompt, status, completion text, and hint visibility.
    All transforms are always active — no locking.
    """
    TRANSFORM_PROMPTS = template.get("transformPrompts", {})
    transform_list = []
    for i, t in enumerate(transforms):
        clue_word = " ".join(words[idx] for idx in t["indices"])
        letter_count = len(re.sub(r'[^A-Z]', '', t["result"].upper()))
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
            consumed = _find_consumed_predecessors(transforms, i)
            # Use _with_context prompt when substitutionLine already explains the operation
            if t_type == "substitution" and substitution_consumed:
                prompt_key = "substitution_with_context"
                if prompt_key not in TRANSFORM_PROMPTS:
                    raise ValueError(f"Missing '{prompt_key}' in transformPrompts in render_templates.json")
                prompt = TRANSFORM_PROMPTS[prompt_key].format(n=letter_count)
            else:
                all_solved = all(c in transforms_done for c in consumed)
                if all_solved:
                    pred_parts = [transforms_done[c] for c in consumed]
                    predecessor_letters = " + ".join(pred_parts)
                    prompt_key = t_type + "_with_input"
                    if prompt_key not in TRANSFORM_PROMPTS:
                        raise ValueError(f"Missing '{prompt_key}' in transformPrompts in render_templates.json")
                    prompt = TRANSFORM_PROMPTS[prompt_key].format(
                        word=clue_word, predecessorLetters=predecessor_letters, n=letter_count)
                else:
                    prompt = TRANSFORM_PROMPTS[t_type].format(word=clue_word, n=letter_count)
        else:
            display_role = _format_role(t["role"])
            prompt = TRANSFORM_PROMPTS[t_type].format(role=display_role, word=clue_word, n=letter_count)

        # Determine status: completed, active, or locked
        if i in transforms_done:
            status = "completed"
            result = transforms_done[i]
            # Build completed text from templates
            completed_templates = template["completedTextTemplates"]
            if t_type in DEPENDENT_TRANSFORM_TYPES and i > 0:
                consumed = _find_consumed_predecessors(transforms, i)
                for c in consumed:
                    if c not in transforms_done:
                        raise ValueError(f"Transform {i} is dependent but predecessor {c} has no result in transforms_done")
                prev_parts = [transforms_done[c] for c in consumed]
                prev_result = " + ".join(prev_parts)
                completed_text = completed_templates["dependent"].format(
                    prevResult=prev_result, result=result)
            else:
                completed_text = completed_templates["independent"].format(
                    clueWord=clue_word, result=result)
        else:
            status = "active"
            result = None

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
        }
        if status == "completed":
            transform_entry["completedText"] = completed_text
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
    }
    for s in clue["steps"]:
        if s["type"] == "definition" and "indices" in s:
            data["definitionWords"] = " ".join(words[i] for i in s["indices"])
        elif s["type"] == "indicator" and "indices" in s:
            data["indicatorHint"] = s.get("hint", "")
            data["indicatorWords"] = " ".join(words[i] for i in s["indices"])
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
                substitution_consumed = _find_consumed_predecessors(transforms, i)
                break

    # Build transform display data
    transform_list = _build_transform_list(
        transforms, transforms_done, template, clue, words,
        assembly_hint_index, substitution_consumed, has_substitution)

    # Determine phase: check only when all transforms are done
    phase = "check" if len(transforms_done) == len(transforms) else "transforms"

    # Compute result letter grouping for tile spacing (e.g. "ASWAN DAM" → [5, 3])
    result_parts = [len(word) for word in step["result"].split()]

    # Compute position map (completed letters computed after auto-complete below)
    position_map = _compute_position_map(step)

    # Extract data from earlier steps
    prior = _extract_prior_step_data(clue, words)
    abbreviation_scan_mappings = prior["abbreviationScanMappings"]

    # Auto-complete abbreviation transforms when abbreviation_scan step exists
    if abbreviation_scan_mappings:
        for i, t in enumerate(transforms):
            if t["type"] == "abbreviation" and i not in transforms_done:
                transforms_done[i] = t["result"].upper()

    # Compute completed letters after auto-complete so abbreviation letters show in boxes
    completed_letters = _compute_completed_letters(transforms_done, position_map, step)

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

    # Resolve coaching lines
    definition_line, indicator_line, check_phase_prompt = _build_coaching_lines(
        template, virtual_step, clue, has_substitution,
        prior["indicatorWords"], source_word, abbreviation_summary)

    return {
        "phase": phase,
        "failMessage": fail_message,
        "transforms": transform_list,
        "resultParts": result_parts,
        "positionMap": {str(k): v for k, v in position_map.items()},
        "completedLetters": completed_letters,
        "definitionLine": definition_line,
        "indicatorLine": indicator_line,
        "checkPhasePrompt": check_phase_prompt,
    }


def _handle_assembly_input(session, step, clue, clue_id, value, transform_index=None, transform_inputs=None):
    """Handle input for an assembly step. Transforms can be submitted in any order."""
    transforms = step["transforms"]
    transforms_done = session["assembly_transforms_done"]
    feedback = RENDER_TEMPLATES["feedback"]

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
            return {"correct": True, "message": feedback["step_correct"], "render": get_render(clue_id, clue)}
        elif any_wrong:
            return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue)}
        else:
            # Nothing to check (all empty or already done)
            return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue)}

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
                    consumed = _find_consumed_predecessors(transforms, dep)
                    for c in consumed:
                        if c not in transforms_done:
                            transforms_done[c] = transforms[c]["result"].upper()
                            # If this predecessor is itself dependent, recurse
                            if c > 0 and transforms[c]["type"] in DEPENDENT_TRANSFORM_TYPES:
                                queue.append(c)

            # Check if all transforms now complete → auto-skip if answer is spelled out
            if len(transforms_done) == len(transforms):
                position_map = _compute_position_map(step)
                completed_letters = _compute_completed_letters(transforms_done, position_map, step)
                final_result = re.sub(r'[^A-Z]', '', step["result"].upper())
                assembled = "".join(l for l in completed_letters if l)

                if assembled == final_result:
                    # Auto-skip check phase — assembly is complete
                    step_index = session["step_index"]
                    session["completed_steps"].append(step_index)
                    session["step_index"] = step_index + 1
                    session["selected_indices"] = []
                    session["step_expanded"] = False
                    session["assembly_transforms_done"] = {}
                    session["assembly_hint_index"] = None
                    # Lock the answer and populate answer boxes
                    session["answer_locked"] = True
                    answer_letters = list(re.sub(r'[^A-Z]', '', clue["answer"].upper()))
                    session["user_answer"] = answer_letters

            return {"correct": True, "message": feedback["step_correct"], "render": get_render(clue_id, clue)}
        else:
            return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue)}

    elif transform_index is None:
        # Check phase: validate the full assembled result
        all_done = len(transforms_done) == len(transforms)
        if not all_done:
            raise ValueError("Cannot check assembly: not all transforms completed")

        expected = step["result"]
        user_text = re.sub(r'[^A-Z]', '', str(value).upper())
        expected_text = re.sub(r'[^A-Z]', '', expected.upper())

        if user_text == expected_text:
            step_index = session["step_index"]
            session["completed_steps"].append(step_index)
            session["step_index"] = step_index + 1
            session["selected_indices"] = []
            session["hint_visible"] = False
            session["step_expanded"] = False
            session["assembly_transforms_done"] = {}
            session["assembly_hint_index"] = None
            # Lock the answer and populate answer boxes
            session["answer_locked"] = True
            answer_letters = list(re.sub(r'[^A-Z]', '', clue["answer"].upper()))
            session["user_answer"] = answer_letters
            return {"correct": True, "message": feedback["step_correct"], "render": get_render(clue_id, clue)}
        else:
            return {"correct": False, "message": feedback["step_incorrect"], "render": get_render(clue_id, clue)}

    else:
        raise ValueError(f"Invalid transform_index: {transform_index}")


def _find_consumed_predecessors(transforms, dep_index):
    """Find ALL predecessor indices consumed by a dependent transform.

    Works backwards from dep_index, accumulating predecessors until the
    combined letter count matches what the dependent transform needs:
    - reversal/anagram: combined input length == result length
    - deletion: combined input length == result length + 1

    Returns a list of predecessor indices in ascending order.
    """
    t = transforms[dep_index]
    t_type = t["type"]
    result_len = len(re.sub(r'[^A-Z]', '', t["result"].upper()))

    if t_type == "deletion":
        target_len = result_len + 1
    else:
        target_len = result_len

    consumed = []
    accumulated = 0
    for j in range(dep_index - 1, -1, -1):
        pred_len = len(re.sub(r'[^A-Z]', '', transforms[j]["result"].upper()))
        consumed.append(j)
        accumulated += pred_len
        if accumulated >= target_len:
            break

    consumed.reverse()
    return consumed


def _find_terminal_transforms(transforms):
    """Identify terminal transforms — those not consumed by a later dependent.

    Returns a set of terminal transform indices.
    """

    terminal = set(range(len(transforms)))
    for i, t in enumerate(transforms):
        if "type" not in t:
            raise ValueError(f"Transform {i} is missing 'type' field")
        if i > 0 and t["type"] in DEPENDENT_TRANSFORM_TYPES:
            consumed = _find_consumed_predecessors(transforms, i)
            for c in consumed:
                terminal.discard(c)
    return terminal


def _compute_position_map(step):
    """Compute which final-answer positions each terminal transform fills.

    A transform is 'terminal' if no later dependent transform supersedes it.
    For containers: find where inner sits inside outer via pattern matching.
    For charades/chains: terminal transforms concatenate left-to-right.
    """
    transforms = step["transforms"]
    result = re.sub(r'[^A-Z]', '', step["result"].upper())

    # Identify terminal transforms (those not superseded by a later dependent)
    terminal = _find_terminal_transforms(transforms)

    # Check if this is a pure container clue (container result IS the full answer)
    # vs a hybrid charade+container (container is just one piece among others)
    # Pure container: outer/inner roles exist and the container result spans the full answer
    # Hybrid: container exists but other terminal transforms also contribute → charade at top level
    container_idx = None
    for i, t in enumerate(transforms):
        if t["role"] == "container":
            container_idx = i
            break

    # Route based on terminal transform structure:
    # 1. Single container terminal whose result IS the full answer → assign all positions to it
    # 2. Outer/inner roles without explicit container transform (29453 style) → container positions
    # 3. Everything else (charades, hybrids) → charade positions
    roles = {t["role"] for t in transforms}
    has_inner = "inner" in roles or any(r.startswith("inner_") for r in roles)

    if container_idx is not None and container_idx in terminal and len(terminal) == 1:
        # Single container terminal — it owns all positions
        container_result = re.sub(r'[^A-Z]', '', transforms[container_idx]["result"].upper())
        if container_result == result:
            return {container_idx: list(range(len(result)))}
        return _compute_container_positions(transforms, terminal, result)
    elif "outer" in roles and has_inner and container_idx is None:
        # No explicit container transform — outer/inner roles define the container (29453 style)
        return _compute_container_positions(transforms, terminal, result)
    else:
        return _compute_charade_positions(transforms, terminal, result)


def _compute_container_positions(transforms, terminal, result):
    """For container clues: find where inner word(s) sit inside outer word.

    Supports multiple inner transforms (charade within container):
    e.g. SOLE wrapping ARE+C+LIPS → SOL(ARECLIPS)E
    Each inner transform gets its own slice of the inner region.
    """
    outer_idx = None
    inner_indices = []
    for i, t in enumerate(transforms):
        if t["role"] == "outer":
            outer_idx = i
        if t["role"] == "inner" or t["role"].startswith("inner_"):
            inner_indices.append(i)

    if outer_idx is None or not inner_indices:
        return {}

    outer_result = re.sub(r'[^A-Z]', '', transforms[outer_idx]["result"].upper())
    # Combine all inner results in order
    combined_inner = "".join(
        re.sub(r'[^A-Z]', '', transforms[idx]["result"].upper())
        for idx in inner_indices
    )

    for insert_pos in range(len(result) - len(combined_inner) + 1):
        if result[insert_pos:insert_pos + len(combined_inner)] == combined_inner:
            remaining = result[:insert_pos] + result[insert_pos + len(combined_inner):]
            if remaining == outer_result:
                outer_positions = list(range(0, insert_pos)) + list(range(insert_pos + len(combined_inner), len(result)))
                position_map = {outer_idx: outer_positions}
                # Assign each inner transform its slice of the inner region
                inner_pos = insert_pos
                for idx in inner_indices:
                    inner_len = len(re.sub(r'[^A-Z]', '', transforms[idx]["result"].upper()))
                    position_map[idx] = list(range(inner_pos, inner_pos + inner_len))
                    inner_pos += inner_len
                return position_map

    return {}


def _compute_charade_positions(transforms, terminal, result):
    """For charade/chain clues: terminal transforms concatenate left-to-right."""
    position_map = {}
    pos = 0
    for idx in sorted(terminal):
        t_result = re.sub(r'[^A-Z]', '', transforms[idx]["result"].upper())
        positions = list(range(pos, pos + len(t_result)))
        position_map[idx] = positions
        pos += len(t_result)
    return position_map


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


def _build_step_list(session, clue):
    """Build the step summary list for the sidebar/menu."""
    steps = clue["steps"]
    step_index = session["step_index"]

    # Build transform results map: role → result (from assembly step data)
    # Only backfill when the assembly step itself is completed
    transform_results = _get_transform_results(steps, session["completed_steps"])

    result = []

    for i, step in enumerate(steps):
        template = RENDER_TEMPLATES.get(step["type"])
        if not template:
            raise ValueError(f"No render template for step type '{step['type']}'")
        title = _resolve_variables(template["menuTitle"], step, clue)

        if i in session["completed_steps"]:
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
        elif i == step_index:
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


def _build_all_done(session, clue):
    """Build the render when all steps are completed. Same layout, no currentStep."""
    # Populate answer boxes if not already filled
    if not session["user_answer"]:
        answer_letters = list(re.sub(r'[^A-Z]', '', clue["answer"].upper()))
        session["user_answer"] = answer_letters

    return {
        "clue_id": session["clue_id"],
        "words": clue["words"],
        "answer": clue["answer"],
        "enumeration": clue["enumeration"],
        "steps": _build_step_list(session, clue),
        "currentStep": None,
        "stepExpanded": False,
        "highlights": session["highlights"],
        "selectedIndices": [],
        "userAnswer": session["user_answer"],
        "answerLocked": session["answer_locked"],
        "complete": True,
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
            consumed = _find_consumed_predecessors(transforms, i)
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
    terminal = _find_terminal_transforms(transforms)
    parts = []
    container_placed = False
    for i in sorted(terminal):
        t = transforms[i]
        if t["type"] == "container" and not container_placed:
            parts.append(container_notation)
            container_placed = True
        elif t["role"] not in container_roles and not t["role"].startswith("inner_"):
            result_upper = t["result"].upper()
            words = clue.get("words", [])
            clue_word = " ".join(words[idx] for idx in t["indices"]) if words and "indices" in t else ""
            if clue_word and clue_word.upper().replace(" ", "") != result_upper.replace(" ", ""):
                parts.append(independent_tpl.replace("{clueWord}", clue_word).replace("{result}", result_upper))
            else:
                parts.append(result_upper)
    if not container_placed:
        parts.insert(0, container_notation)

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
            consumed = _find_consumed_predecessors(transforms, i)
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
