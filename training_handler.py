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
        "assembly_phase": 0,
        "assembly_transforms_done": [],
    }
    return get_render(clue_id, clue)


def get_render(clue_id, clue):
    """Build the complete render object for the current state."""
    session = _sessions.get(clue_id)
    if not session:
        raise ValueError(f"No session for clue_id: {clue_id}")

    steps = clue["steps"]
    step_index = session["step_index"]

    # All steps done → completion
    if step_index >= len(steps):
        return _build_completion(session, clue)

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
            "prompt": template["prompt"],
        }

        # Intro (always visible)
        if "intro" in template:
            current_step["intro"] = template["intro"]

        # Hint (revealed on request, keyed by clue_type if dict)
        if "hint" in template:
            hint_data = template["hint"]
            if isinstance(hint_data, dict):
                clue_type = clue.get("clue_type", "standard")
                current_step["hint"] = hint_data.get(clue_type, "")
            else:
                current_step["hint"] = hint_data

        current_step["hintVisible"] = session["hint_visible"]

        # Assembly-specific data
        if step["type"] == "container_assembly":
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


def handle_input(clue_id, clue, value):
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
    if step["type"] == "container_assembly":
        return _handle_assembly_input(session, step, clue, clue_id, value)

    input_mode = template["inputMode"]
    expected = _resolve_expected(step, template)

    # Validate
    if input_mode == "tap_words":
        correct = set(value) == set(expected)
    elif input_mode == "text":
        user_text = re.sub(r'[^A-Z]', '', str(value).upper())
        expected_text = re.sub(r'[^A-Z]', '', str(expected).upper())
        correct = user_text == expected_text
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
        session["assembly_phase"] = 0
        session["assembly_transforms_done"] = []

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
    """Skip to completion, revealing the answer."""
    session = _sessions.get(clue_id)
    if not session:
        raise ValueError(f"No session for clue_id: {clue_id}")

    session["step_index"] = len(clue["steps"])
    session["answer_locked"] = True

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
    """Build the assemblyData payload for a container_assembly step."""
    transforms = step["transforms"]
    phase_idx = session["assembly_phase"]
    transforms_done = session["assembly_transforms_done"]
    words = clue["words"]

    # Build raw fail message from clue words at transform indices
    raw_words = []
    for t in transforms:
        t_words = [words[i] for i in t["indices"]]
        raw_words.append(" ".join(t_words))
    fail_message = "Try putting '" + "' and '".join(raw_words) + "' together \u2014 it doesn\u2019t spell anything useful, does it? So what is each word really telling you?"

    # Build transform display data
    transform_list = []
    for i, t in enumerate(transforms):
        clue_word = " ".join(words[idx] for idx in t["indices"])
        if i < len(transforms_done):
            status = "completed"
            result = transforms_done[i]
        elif i == phase_idx:
            status = "active"
            result = None
        else:
            status = "pending"
            result = None

        transform_list.append({
            "role": t["role"],
            "clueWord": clue_word,
            "prompt": f"'{clue_word}' is a clue to a {len(re.sub(r'[^A-Z]', '', t['result'].upper()))}-letter word. What\u2019s it pointing to?",
            "letterCount": len(re.sub(r'[^A-Z]', '', t["result"].upper())),
            "status": status,
            "result": result,
            "hint": t.get("hint", ""),
            "hintVisible": (i == phase_idx and session["hint_visible"]),
        })

    # Determine phase and result parts
    if phase_idx < len(transforms):
        phase = "transform"
    else:
        phase = "check"

    # Compute result letter grouping for tile spacing (e.g. "ASWAN DAM" → [5, 3])
    result_text = step["result"]
    result_parts = [len(word) for word in result_text.split()]

    return {
        "phase": phase,
        "failMessage": fail_message,
        "transformIndex": phase_idx if phase_idx < len(transforms) else None,
        "transforms": transform_list,
        "resultParts": result_parts,
    }


def _handle_assembly_input(session, step, clue, clue_id, value):
    """Handle input for the container_assembly step's multi-phase flow."""
    transforms = step["transforms"]
    phase_idx = session["assembly_phase"]

    if phase_idx < len(transforms):
        # Transform phase: validate text input
        expected = transforms[phase_idx]["result"]
        user_text = re.sub(r'[^A-Z]', '', str(value).upper())
        expected_text = re.sub(r'[^A-Z]', '', expected.upper())

        if user_text == expected_text:
            session["assembly_transforms_done"].append(expected.upper())
            session["assembly_phase"] = phase_idx + 1
            session["hint_visible"] = False
            return {"correct": True, "render": get_render(clue_id, clue)}
        else:
            return {"correct": False, "render": get_render(clue_id, clue)}

    elif phase_idx == len(transforms):
        # Assembly check phase: validate assembled result
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
            session["assembly_phase"] = 0
            session["assembly_transforms_done"] = []
            return {"correct": True, "render": get_render(clue_id, clue)}
        else:
            return {"correct": False, "render": get_render(clue_id, clue)}

    else:
        raise ValueError(f"Invalid assembly_phase: {phase_idx}")


def _build_step_list(session, clue):
    """Build the step summary list for the sidebar/menu."""
    steps = clue["steps"]
    step_index = session["step_index"]
    result = []

    for i, step in enumerate(steps):
        template = RENDER_TEMPLATES.get(step["type"])
        title = template["menuTitle"] if template else step["type"]

        if i in session["completed_steps"]:
            status = "completed"
            # Use completedTitle if available (resolved with variables)
            if template and "completedTitle" in template:
                title = _resolve_variables(template["completedTitle"], step, clue)
            completion_text = _resolve_on_correct(template, step, clue) if template else ""
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


def _build_completion(session, clue):
    """Build the final completion render."""
    return {
        "clue_id": session["clue_id"],
        "words": clue["words"],
        "answer": clue["answer"],
        "enumeration": clue["enumeration"],
        "steps": _build_step_list(session, clue),
        "currentStep": None,
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

    return text


def _resolve_on_correct(template, step, clue):
    """Resolve the onCorrect text with variable substitution."""
    return _resolve_variables(template.get("onCorrect", ""), step, clue)
