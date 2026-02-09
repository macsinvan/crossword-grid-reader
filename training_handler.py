"""
Training Handler - Simple Sequencer Engine
==========================================

Reads flat steps from clue metadata, looks up render templates by step type,
presents each step, validates input, advances. That's it.
"""

import json
import os
import re

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

# --- Clues database (auto-reload) ---

_CLUES_DB = {}
_CLUES_DB_PATH = os.path.join(os.path.dirname(__file__), "clues_db.json")
_CLUES_DB_MTIME = 0


def _normalize_quotes(text):
    """Normalize curly quotes to straight quotes for comparison."""
    if not text:
        return text
    text = text.replace('\u2018', "'").replace('\u2019', "'").replace('\u201a', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"').replace('\u201e', '"')
    return text


def _get_clue_text(clue_data):
    """Extract clue text from either old or new format."""
    clue_field = clue_data.get('clue', '')
    if isinstance(clue_field, dict):
        return clue_field.get('text', '')
    return clue_field


def load_clues_db(force=False):
    """Load the clues database from JSON file."""
    global _CLUES_DB, _CLUES_DB_MTIME

    current_mtime = os.path.getmtime(_CLUES_DB_PATH)
    if not force and current_mtime == _CLUES_DB_MTIME:
        return

    with open(_CLUES_DB_PATH, 'r') as f:
        data = json.load(f)

    if 'training_items' not in data:
        raise KeyError(f"clues_db.json missing 'training_items'. Keys: {list(data.keys())}")

    _CLUES_DB = data['training_items']
    _CLUES_DB_MTIME = current_mtime
    print(f"Loaded {len(_CLUES_DB)} clues from clues_db.json (mtime: {current_mtime})")


def maybe_reload_clues_db():
    """Reload clues_db.json if it has changed on disk."""
    current_mtime = os.path.getmtime(_CLUES_DB_PATH)
    if current_mtime != _CLUES_DB_MTIME:
        print("[Auto-reload] clues_db.json changed, reloading...")
        load_clues_db(force=True)


def lookup_clue(clue_text, puzzle_number, clue_number, direction):
    """Find a clue in the database. Returns (clue_id, clue_data) or (None, None)."""
    clue_text_normalized = _normalize_quotes(clue_text.strip()) if clue_text else ''
    clue_text_no_enum = _normalize_quotes(re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', clue_text).strip()) if clue_text else ''

    # Primary: construct ID from puzzle/clue/direction
    if puzzle_number and clue_number and direction:
        dir_suffix = 'a' if direction.lower() == 'across' else 'd'
        expected_id = f'times-{puzzle_number}-{clue_number}{dir_suffix}'
        if expected_id in _CLUES_DB:
            candidate = _CLUES_DB[expected_id]
            annotation_text = _normalize_quotes(_get_clue_text(candidate).strip())
            if annotation_text == clue_text_normalized or annotation_text == clue_text_no_enum:
                return expected_id, candidate
            else:
                return None, None  # Mismatch

    # Fallback: match by text
    for cid, cdata in _CLUES_DB.items():
        candidate_text = _normalize_quotes(_get_clue_text(cdata).strip())
        if candidate_text == clue_text_normalized or candidate_text == clue_text_no_enum:
            return cid, cdata

    return None, None


def get_clue_data(clue_id):
    """Get clue data by ID. Returns clue_data or None if not found."""
    return _CLUES_DB.get(clue_id)


load_clues_db(force=True)

# --- Sessions ---

_sessions = {}


def start_session(clue_id, clue):
    """Initialize a training session. Returns the initial render."""
    _sessions[clue_id] = {
        "clue_id": clue_id,
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
    template = RENDER_TEMPLATES.get(step["type"])

    # Build step summary list for the menu sidebar
    step_list = _build_step_list(session, clue)

    # If no template exists for this step type, show a placeholder
    if not template:
        current_step = {
            "index": step_index,
            "type": step["type"],
            "inputMode": "none",
            "prompt": f"Step type '{step['type']}' not yet implemented.",
            "hintVisible": False,
            "notImplemented": True,
        }
    else:
        # Build current step render
        # Resolve prompt (template may be dict keyed by indicator_type)
        prompt_data = template["prompt"]
        if isinstance(prompt_data, dict):
            if "indicator_type" not in step:
                raise ValueError(f"Step type '{step['type']}' has dict-based prompt template but step metadata is missing 'indicator_type'")
            itype = step["indicator_type"]
            if itype not in prompt_data:
                raise ValueError(f"No prompt for indicator_type '{itype}' in template. Available: {list(prompt_data.keys())}")
            resolved_prompt = prompt_data[itype]
        else:
            resolved_prompt = prompt_data

        current_step = {
            "index": step_index,
            "type": step["type"],
            "inputMode": template["inputMode"],
            "prompt": resolved_prompt,
        }

        # Intro (template may be dict keyed by indicator_type)
        if "intro" in template:
            intro_data = template["intro"]
            if isinstance(intro_data, dict):
                if "indicator_type" not in step:
                    raise ValueError(f"Step type '{step['type']}' has dict-based intro template but step metadata is missing 'indicator_type'")
                itype = step["indicator_type"]
                if itype not in intro_data:
                    raise ValueError(f"No intro for indicator_type '{itype}' in template. Available: {list(intro_data.keys())}")
                current_step["intro"] = intro_data[itype]
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

    return {
        "clue_id": clue_id,
        "words": clue["words"],
        "answer": clue["answer"],
        "enumeration": clue["enumeration"],
        "steps": step_list,
        "currentStep": current_step,
        "stepExpanded": session["step_expanded"],
        "highlights": session["highlights"],
        "selectedIndices": session["selected_indices"],
        "userAnswer": session["user_answer"],
        "answerLocked": session["answer_locked"],
        "complete": False,
    }


def handle_input(clue_id, clue, value, transform_index=None):
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
        return _handle_assembly_input(session, step, clue, clue_id, value, transform_index)

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
    """Format a transform role for display: 'part2a' → 'Part 2a', 'outer' → 'Outer'."""
    # Insert space before first digit: 'part2a' → 'part 2a'
    display = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', role)
    # Capitalise first letter
    return display[0].upper() + display[1:] if display else display


def _build_assembly_data(session, step, clue):
    """Build the assemblyData payload for an assembly step.

    All transforms are always active — no locking. The student sees the full
    plan and works through them in any order.
    """
    transforms = step["transforms"]
    transforms_done = session["assembly_transforms_done"]  # dict: {index: result}
    assembly_hint_index = session.get("assembly_hint_index")
    words = clue["words"]

    # Explicit wordplay: indicators already told the student what to do — no fail message
    is_explicit = step.get("explicit", False)

    # Transform prompt templates from render template (template-driven, not hardcoded)
    template = RENDER_TEMPLATES.get("assembly", {})
    TRANSFORM_PROMPTS = template.get("transformPrompts", {})

    # Fail message: explicit skips it; step metadata overrides the default; otherwise template
    if is_explicit:
        fail_message = ""
    elif "failMessage" in step:
        fail_message = step["failMessage"]
    else:
        raw_words = []
        for t in transforms:
            t_words = [words[i] for i in t["indices"]]
            raw_words.append(" ".join(t_words))
        raw_list = "'" + "' and '".join(raw_words) + "'"
        fail_message = template["defaultFailMessage"].format(rawWordsList=raw_list)

    DEPENDENT_TYPES = {"deletion", "reversal", "anagram"}

    # Build transform display data
    transform_list = []
    for i, t in enumerate(transforms):
        clue_word = " ".join(words[idx] for idx in t["indices"])
        letter_count = len(re.sub(r'[^A-Z]', '', t["result"].upper()))
        if "type" not in t:
            raise ValueError(f"Transform {i} is missing 'type' field in assembly step")
        t_type = t["type"]

        if t_type not in TRANSFORM_PROMPTS:
            raise ValueError(f"Unknown transform type '{t_type}' in clue metadata. Add it to transformPrompts in render_templates.json.")

        # Per-transform prompt override (for explicit wordplay), otherwise template
        if "prompt" in t:
            prompt = t["prompt"]
        else:
            display_role = _format_role(t["role"])
            prompt = TRANSFORM_PROMPTS[t_type].format(role=display_role, word=clue_word, n=letter_count)

        # Determine status: completed, active, or locked
        if i in transforms_done:
            status = "completed"
            result = transforms_done[i]
            # Build completed text from templates
            completed_templates = template["completedTextTemplates"]
            if t_type in DEPENDENT_TYPES and i > 0:
                # Dependent types may consume multiple predecessors
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
            # All transforms are always active — no locking
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
        # Dictionary lookup (optional, from transform metadata)
        if "lookup" in t:
            transform_entry["lookup"] = t["lookup"]
        transform_list.append(transform_entry)

    # Determine phase: check only when all transforms are done
    all_done = len(transforms_done) == len(transforms)
    phase = "check" if all_done else "transforms"

    # Compute result letter grouping for tile spacing (e.g. "ASWAN DAM" → [5, 3])
    result_text = step["result"]
    result_parts = [len(word) for word in result_text.split()]

    # Compute position map and completed letters for the combined display
    position_map = _compute_position_map(step)
    completed_letters = _compute_completed_letters(transforms_done, position_map, step)

    # Extract raw data from earlier steps for template variable resolution
    definition_words = ""
    indicator_hint = ""
    indicator_words = ""
    inner_words = ""
    outer_words = ""
    for s in clue["steps"]:
        if s["type"] == "definition" and "indices" in s:
            definition_words = " ".join(words[i] for i in s["indices"])
        elif s["type"] == "indicator" and "indices" in s:
            indicator_hint = s.get("hint", "")
            indicator_words = " ".join(words[i] for i in s["indices"])
        elif s["type"] == "outer_word" and "indices" in s:
            outer_words = " ".join(words[i] for i in s["indices"])
        elif s["type"] == "inner_word" and "indices" in s:
            inner_words = " ".join(words[i] for i in s["indices"])

    # Resolve coaching lines from assembly render template
    # Build a virtual step with the extra variables for resolution
    virtual_step = dict(step)
    virtual_step["definitionWords"] = definition_words
    virtual_step["indicatorHint"] = indicator_hint
    virtual_step["indicatorWords"] = indicator_words
    virtual_step["innerWords"] = inner_words
    virtual_step["outerWords"] = outer_words

    definition_line = _resolve_variables(template.get("definitionLine", ""), virtual_step, clue)
    # Only resolve indicatorLine when the required data exists (e.g. container clues)
    indicator_line = ""
    if indicator_words and inner_words and outer_words:
        indicator_line = _resolve_variables(template.get("indicatorLine", ""), virtual_step, clue)

    return {
        "phase": phase,
        "failMessage": fail_message,
        "transforms": transform_list,
        "resultParts": result_parts,
        "positionMap": {str(k): v for k, v in position_map.items()},
        "completedLetters": completed_letters,
        "definitionLine": definition_line,
        "indicatorLine": indicator_line,
    }


def _handle_assembly_input(session, step, clue, clue_id, value, transform_index=None):
    """Handle input for an assembly step. Transforms can be submitted in any order."""
    transforms = step["transforms"]
    transforms_done = session["assembly_transforms_done"]
    feedback = RENDER_TEMPLATES["feedback"]

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
            DEPENDENT_TYPES = {"deletion", "reversal", "anagram"}
            if "type" not in transforms[transform_index]:
                raise ValueError(f"Transform {transform_index} is missing 'type' field")
            t_type = transforms[transform_index]["type"]
            if t_type in DEPENDENT_TYPES and transform_index > 0:
                queue = [transform_index]
                while queue:
                    dep = queue.pop(0)
                    consumed = _find_consumed_predecessors(transforms, dep)
                    for c in consumed:
                        if c not in transforms_done:
                            transforms_done[c] = transforms[c]["result"].upper()
                            # If this predecessor is itself dependent, recurse
                            if c > 0 and transforms[c]["type"] in DEPENDENT_TYPES:
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
    DEPENDENT_TYPES = {"deletion", "reversal", "anagram"}
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
    DEPENDENT_TYPES = {"deletion", "reversal", "anagram"}
    terminal = set(range(len(transforms)))
    for i, t in enumerate(transforms):
        if "type" not in t:
            raise ValueError(f"Transform {i} is missing 'type' field")
        if i > 0 and t["type"] in DEPENDENT_TYPES:
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

    # Check if this is a container clue (has outer/inner roles)
    roles = {t["role"] for t in transforms}

    if "outer" in roles and "inner" in roles:
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
        if t["role"] == "outer" and i in terminal:
            outer_idx = i
        if t["role"] == "inner" and i in terminal:
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
            completed_title = template.get("completedTitle")
            if completed_title:
                title = _resolve_variables(completed_title, step, clue)
            completion_text = _resolve_on_correct(template, step, clue) if template else ""

            # Backfill: enrich outer_word/inner_word titles with transform results
            if step["type"] in ("outer_word", "inner_word") and transform_results:
                role = "outer" if step["type"] == "outer_word" else "inner"
                transform_result = transform_results.get(role)
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
    """Extract transform role→result map from a completed assembly step."""
    for i, step in enumerate(steps):
        if "transforms" in step and i in completed_steps:
            return {t["role"]: t["result"].upper() for t in step["transforms"]}
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


def _resolve_variables(text, step, clue):
    """Replace {variable} placeholders in a template string."""
    if not text:
        return ""

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

    # {position}
    if "{position}" in text:
        if "position" not in step:
            raise ValueError(f"Template uses {{position}} but step metadata is missing 'position' for step type '{step.get('type', '?')}'")
        text = text.replace("{position}", step["position"])

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

    # {definitionWords} — extracted from definition step
    if "{definitionWords}" in text:
        if "definitionWords" not in step:
            raise ValueError(f"Template uses {{definitionWords}} but step is missing 'definitionWords'")
        text = text.replace("{definitionWords}", step["definitionWords"])

    # {indicatorHint} — extracted from indicator step
    if "{indicatorHint}" in text:
        if "indicatorHint" not in step:
            raise ValueError(f"Template uses {{indicatorHint}} but step is missing 'indicatorHint'")
        text = text.replace("{indicatorHint}", step["indicatorHint"])

    # {indicatorType} — from indicator step's indicator_type field (e.g. "container", "anagram")
    if "{indicatorType}" in text:
        if "indicator_type" not in step:
            raise ValueError(f"Template uses {{indicatorType}} but step metadata is missing 'indicator_type'")
        # Convert snake_case to display form: "letter_selection" -> "letter selection"
        text = text.replace("{indicatorType}", step["indicator_type"].replace("_", " "))

    # {indicatorWords} — the indicator word(s) from the indicator step
    if "{indicatorWords}" in text:
        if "indicatorWords" not in step:
            raise ValueError(f"Template uses {{indicatorWords}} but step is missing 'indicatorWords'")
        text = text.replace("{indicatorWords}", step["indicatorWords"])

    # {innerWords} — from the inner_word step
    if "{innerWords}" in text:
        if "innerWords" not in step:
            raise ValueError(f"Template uses {{innerWords}} but step is missing 'innerWords'")
        text = text.replace("{innerWords}", step["innerWords"])

    # {outerWords} — from the outer_word step
    if "{outerWords}" in text:
        if "outerWords" not in step:
            raise ValueError(f"Template uses {{outerWords}} but step is missing 'outerWords'")
        text = text.replace("{outerWords}", step["outerWords"])

    # {assemblyBreakdown} — build from transforms: show the assembly journey
    if "{assemblyBreakdown}" in text and "transforms" in step:
        transforms = step["transforms"]
        DEPENDENT_TYPES = {"deletion", "reversal", "anagram"}

        # Detect container clues (outer/inner roles)
        roles = {t["role"] for t in transforms}
        is_container = "outer" in roles and "inner" in roles

        if is_container:
            # Container: show insertion notation like SOL(ARE + C + LIPS)E
            terminal = _find_terminal_transforms(transforms)

            # Find terminal outer and collect terminal inner parts
            outer_idx = None
            inner_parts = []
            for i, t in enumerate(transforms):
                if t["role"] == "outer" and i in terminal:
                    outer_idx = i
                elif t["role"] == "inner" and i in terminal:
                    inner_parts.append((i, t["result"].upper()))

            if outer_idx is not None and inner_parts:
                outer_result = re.sub(r'[^A-Z]', '', transforms[outer_idx]["result"].upper())
                # Combine all inner terminal results
                combined_inner = "".join(re.sub(r'[^A-Z]', '', p[1]) for p in inner_parts)
                final_result = re.sub(r'[^A-Z]', '', step["result"].upper())

                # Find where inner sits inside outer by matching the final result
                inserted = False
                for insert_pos in range(len(final_result) - len(combined_inner) + 1):
                    if final_result[insert_pos:insert_pos + len(combined_inner)] == combined_inner:
                        remaining = final_result[:insert_pos] + final_result[insert_pos + len(combined_inner):]
                        if remaining == outer_result:
                            prefix = outer_result[:insert_pos]
                            suffix = outer_result[insert_pos:]
                            inner_display = " + ".join(p[1] for p in inner_parts)
                            breakdown = prefix + "(" + inner_display + ")" + suffix
                            text = text.replace("{assemblyBreakdown}", breakdown)
                            inserted = True
                            break

                if not inserted:
                    # Fallback: show outer(inner) without split
                    inner_display = " + ".join(p[1] for p in inner_parts)
                    breakdown = outer_result + "(" + inner_display + ")"
                    text = text.replace("{assemblyBreakdown}", breakdown)
            else:
                raise ValueError("Container clue has outer/inner roles but no terminal outer or inner transforms found")
        else:
            # Charade/chain: show clue word attribution for independent transforms,
            # and dependent operations with arrows
            # e.g. 'doldrums' → LOW + 'Sailor' → TAR
            # e.g. (PICS + ID → DISCIP) + 'cover the inside of' → LINE
            words = clue.get("words", [])
            # Track both display text and raw result for each part
            # display: what the student sees; raw: just the result letters (for dependent arrows)
            parts = []  # list of (display_text, raw_result)
            for i, t in enumerate(transforms):
                if "type" not in t:
                    raise ValueError(f"Transform is missing 'type' field in assembly step")
                t_type = t["type"]
                result = t["result"].upper()
                if t_type in DEPENDENT_TYPES and parts:
                    consumed = _find_consumed_predecessors(transforms, i)
                    # Pop all consumed predecessors — use raw results for the arrow
                    consumed_raws = []
                    for _ in consumed:
                        if parts:
                            _, raw = parts.pop()
                            consumed_raws.insert(0, raw)
                    display = "(" + " + ".join(consumed_raws) + " \u2192 " + result + ")"
                    parts.append((display, result))
                else:
                    # Independent transform: show 'clueWord' → RESULT
                    clue_word = " ".join(words[idx] for idx in t["indices"]) if words else ""
                    display = "'" + clue_word + "' \u2192 " + result
                    parts.append((display, result))
            text = text.replace("{assemblyBreakdown}", " + ".join(d for d, _ in parts))

    return text


def _resolve_on_correct(template, step, clue):
    """Resolve the onCorrect text with variable substitution."""
    return _resolve_variables(template.get("onCorrect", ""), step, clue)
