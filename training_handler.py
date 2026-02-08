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
        current_step = {
            "index": step_index,
            "type": step["type"],
            "inputMode": template["inputMode"],
            "prompt": step.get("prompt") or template["prompt"],
        }

        # Intro (step metadata overrides template)
        if "intro" in step:
            current_step["intro"] = step["intro"]
        elif "intro" in template:
            current_step["intro"] = template["intro"]

        # Hint (step metadata overrides template; template hint keyed by clue_type if dict)
        if "hint" in step:
            current_step["hint"] = step["hint"]
        elif "hint" in template:
            hint_data = template["hint"]
            if isinstance(hint_data, dict):
                clue_type = clue.get("clue_type", "standard")
                current_step["hint"] = hint_data.get(clue_type, "")
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

        return {"correct": True, "render": get_render(clue_id, clue)}
    else:
        return {"correct": False, "render": get_render(clue_id, clue)}


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

    if user_text == expected_text:
        session["answer_locked"] = True
        return {"correct": True, "render": get_render(clue_id, clue)}
    else:
        return {"correct": False, "render": get_render(clue_id, clue)}


# --- Internal helpers ---

def _build_assembly_data(session, step, clue):
    """Build the assemblyData payload for an assembly step.

    Transforms can be solved in any order (parallel), except dependent types
    (deletion, reversal, anagram) which are locked until all prior transforms complete.
    """
    transforms = step["transforms"]
    transforms_done = session["assembly_transforms_done"]  # dict: {index: result}
    assembly_hint_index = session.get("assembly_hint_index")
    words = clue["words"]

    # Explicit wordplay: indicators already told the student what to do — no fail message
    is_explicit = step.get("explicit", False)

    # Fail message: explicit skips it; step metadata overrides the default
    if is_explicit:
        fail_message = ""
    elif "failMessage" in step:
        fail_message = step["failMessage"]
    else:
        raw_words = []
        for t in transforms:
            t_words = [words[i] for i in t["indices"]]
            raw_words.append(" ".join(t_words))
        fail_message = "Try putting '" + "' and '".join(raw_words) + "' together \u2014 it doesn\u2019t spell anything useful, does it? So what is each word really telling you?"

    # Transform prompt templates from render template (template-driven, not hardcoded)
    template = RENDER_TEMPLATES.get("assembly", {})
    TRANSFORM_PROMPTS = template.get("transformPrompts", {})

    # Independent types can be solved in any order; dependent types wait for predecessors
    INDEPENDENT_TYPES = {"synonym", "abbreviation", "literal", "letter_selection"}

    # Build transform display data
    transform_list = []
    for i, t in enumerate(transforms):
        clue_word = " ".join(words[idx] for idx in t["indices"])
        letter_count = len(re.sub(r'[^A-Z]', '', t["result"].upper()))
        t_type = t.get("type", "")

        if t_type not in TRANSFORM_PROMPTS:
            raise ValueError(f"Unknown transform type '{t_type}' in clue metadata. Add it to transformPrompts in render_templates.json.")

        # Per-transform prompt override (for explicit wordplay), otherwise template
        if "prompt" in t:
            prompt = t["prompt"]
        else:
            prompt = TRANSFORM_PROMPTS[t_type].format(role=t["role"], word=clue_word, n=letter_count)

        # Determine status: completed, active, or locked
        if i in transforms_done:
            status = "completed"
            result = transforms_done[i]
        elif t_type in INDEPENDENT_TYPES or i == 0:
            # Independent types and the first transform are always available
            status = "active"
            result = None
        else:
            # Dependent type — check if all prior transforms are done
            all_prior_done = all(j in transforms_done for j in range(i))
            status = "active" if all_prior_done else "locked"
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

    if transform_index is not None and 0 <= transform_index < len(transforms):
        # Transform submission: validate against this specific transform
        expected = transforms[transform_index]["result"]
        user_text = re.sub(r'[^A-Z]', '', str(value).upper())
        expected_text = re.sub(r'[^A-Z]', '', expected.upper())

        if user_text == expected_text:
            transforms_done[transform_index] = expected.upper()
            session["assembly_hint_index"] = None

            # Check if all transforms now complete → auto-skip if answer is spelled out
            if len(transforms_done) == len(transforms):
                position_map = _compute_position_map(step)
                completed_letters = _compute_completed_letters(transforms_done, position_map, step)
                final_result = re.sub(r'[^A-Z]', '', step["result"].upper())
                assembled = "".join(l for l in completed_letters if l)

                if assembled == final_result:
                    # Auto-skip check phase
                    step_index = session["step_index"]
                    session["completed_steps"].append(step_index)
                    session["step_index"] = step_index + 1
                    session["selected_indices"] = []
                    session["step_expanded"] = False
                    session["assembly_transforms_done"] = {}
                    session["assembly_hint_index"] = None

            return {"correct": True, "render": get_render(clue_id, clue)}
        else:
            return {"correct": False, "render": get_render(clue_id, clue)}

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
            return {"correct": True, "render": get_render(clue_id, clue)}
        else:
            return {"correct": False, "render": get_render(clue_id, clue)}

    else:
        raise ValueError(f"Invalid transform_index: {transform_index}")


def _compute_position_map(step):
    """Compute which final-answer positions each terminal transform fills.

    A transform is 'terminal' if no later dependent transform supersedes it.
    For containers: find where inner sits inside outer via pattern matching.
    For charades/chains: terminal transforms concatenate left-to-right.
    """
    transforms = step["transforms"]
    result = re.sub(r'[^A-Z]', '', step["result"].upper())
    DEPENDENT_TYPES = {"deletion", "reversal", "anagram"}

    # Identify terminal transforms (those not superseded by a later dependent)
    terminal = set(range(len(transforms)))
    for i, t in enumerate(transforms):
        if i > 0 and t.get("type", "") in DEPENDENT_TYPES:
            if t.get("type", "") == "anagram":
                # Anagram rearranges ALL prior results — discard all predecessors
                for j in range(i):
                    terminal.discard(j)
            else:
                # Deletion/reversal only modifies the immediately preceding result
                terminal.discard(i - 1)

    # Check if this is a container clue (has outer/inner roles)
    roles = {t["role"] for t in transforms}

    if "outer" in roles and "inner" in roles:
        return _compute_container_positions(transforms, terminal, result)
    else:
        return _compute_charade_positions(transforms, terminal, result)


def _compute_container_positions(transforms, terminal, result):
    """For container clues: find where inner word sits inside outer word."""
    outer_idx = None
    inner_idx = None
    for i, t in enumerate(transforms):
        if t["role"] == "outer" and i in terminal:
            outer_idx = i
        if t["role"] == "inner" and i in terminal:
            inner_idx = i

    if outer_idx is None or inner_idx is None:
        return {}

    outer_result = re.sub(r'[^A-Z]', '', transforms[outer_idx]["result"].upper())
    inner_result = re.sub(r'[^A-Z]', '', transforms[inner_idx]["result"].upper())

    for insert_pos in range(len(result) - len(inner_result) + 1):
        if result[insert_pos:insert_pos + len(inner_result)] == inner_result:
            remaining = result[:insert_pos] + result[insert_pos + len(inner_result):]
            if remaining == outer_result:
                outer_positions = list(range(0, insert_pos)) + list(range(insert_pos + len(inner_result), len(result)))
                inner_positions = list(range(insert_pos, insert_pos + len(inner_result)))
                return {outer_idx: outer_positions, inner_idx: inner_positions}

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
        title = step.get("menuTitle") or (template["menuTitle"] if template else step["type"])

        if i in session["completed_steps"]:
            status = "completed"
            # Use completedTitle if available (step overrides template)
            completed_title = step.get("completedTitle") or (template.get("completedTitle") if template else None)
            if completed_title:
                title = _resolve_variables(completed_title, step, clue)
            completion_text = _resolve_on_correct(template, step, clue) if template else ""

            # Backfill: enrich outer_word/inner_word titles with transform results
            if step["type"] in ("outer_word", "inner_word") and transform_results:
                role = "outer" if step["type"] == "outer_word" else "inner"
                transform_result = transform_results.get(role)
                if transform_result:
                    words = " ".join(clue["words"][idx] for idx in step["indices"])
                    title = f"'{words}' \u2192 {transform_result}"
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
        text = text.replace("{enumeration}", clue.get("enumeration", ""))

    # {hint} — from step hint field
    if "{hint}" in text:
        text = text.replace("{hint}", step.get("hint", ""))

    # {position}
    if "{position}" in text:
        text = text.replace("{position}", step.get("position", ""))

    # {result}
    if "{result}" in text:
        text = text.replace("{result}", step.get("result", ""))

    # {expected}
    if "{expected}" in text:
        text = text.replace("{expected}", str(step.get("expected", "")))

    # {definitionWords} — extracted from definition step
    if "{definitionWords}" in text:
        text = text.replace("{definitionWords}", step.get("definitionWords", ""))

    # {indicatorHint} — extracted from indicator step
    if "{indicatorHint}" in text:
        text = text.replace("{indicatorHint}", step.get("indicatorHint", ""))

    # {indicatorWords} — the indicator word(s) from the indicator step
    if "{indicatorWords}" in text:
        text = text.replace("{indicatorWords}", step.get("indicatorWords", ""))

    # {innerWords} — from the inner_word step
    if "{innerWords}" in text:
        text = text.replace("{innerWords}", step.get("innerWords", ""))

    # {outerWords} — from the outer_word step
    if "{outerWords}" in text:
        text = text.replace("{outerWords}", step.get("outerWords", ""))

    return text


def _resolve_on_correct(template, step, clue):
    """Resolve the onCorrect text with variable substitution."""
    return _resolve_variables(template.get("onCorrect", ""), step, clue)
