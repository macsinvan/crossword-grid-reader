#!/usr/bin/env python3
"""
Trainer Regression Tests
========================

Tests all trainer API endpoints against a running server.
Dynamically discovers ALL clues with training data from Supabase
via /trainer/clue-ids?full=1 — no hardcoded clue lists.

Usage:
    python3 test_regression.py
    python3 test_regression.py --server http://127.0.0.1:8080

Requires: a running crossword_server.py instance.
Dependencies: stdlib only (urllib).
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_SERVER = "http://127.0.0.1:8080"

# Import from shared constants — single source of truth
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from training_constants import DEPENDENT_TRANSFORM_TYPES

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api_get(server, path):
    """GET JSON from server, return parsed response."""
    url = f"{server}/trainer{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post(server, path, payload):
    """POST JSON to server, return parsed response and status code."""
    url = f"{server}/trainer{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8"))
        return e.code, body


def start_session(server, clue):
    """Start a training session, return render dict."""
    status, body = api_post(server, "/start", {
        "puzzle_number": clue["puzzle_number"],
        "clue_number": clue["clue_number"],
        "direction": clue["direction"],
    })
    if status != 200:
        raise RuntimeError(f"Start failed ({status}): {body}")
    return body


def _session(render):
    """Extract session state from a render response."""
    return render.get("session")


def submit_input(server, clue_id, value, render, transform_index=None):
    """Submit input for the current step. Returns (correct, render)."""
    payload = {"clue_id": clue_id, "session": _session(render), "value": value}
    if transform_index is not None:
        payload["transform_index"] = transform_index
    status, body = api_post(server, "/input", payload)
    if status != 200:
        raise RuntimeError(f"Input failed ({status}): {body}")
    return body["correct"], body["render"]


def check_answer(server, clue_id, answer, render):
    """Check a typed answer. Returns (correct, render)."""
    status, body = api_post(server, "/check-answer", {"clue_id": clue_id, "session": _session(render), "answer": answer})
    if status != 200:
        raise RuntimeError(f"Check-answer failed ({status}): {body}")
    return body["correct"], body["render"]


def send_ui_state(server, clue_id, render, action, extra=None):
    """Send a UI state action. Returns render."""
    payload = {"clue_id": clue_id, "session": _session(render), "action": action}
    if extra:
        payload.update(extra)
    status, body = api_post(server, "/ui-state", payload)
    if status != 200:
        raise RuntimeError(f"UI state '{action}' failed ({status}): {body}")
    return body


def reveal(server, clue_id, render):
    """Reveal the full answer. Returns render."""
    status, body = api_post(server, "/reveal", {"clue_id": clue_id, "session": _session(render)})
    if status != 200:
        raise RuntimeError(f"Reveal failed ({status}): {body}")
    return body


# ---------------------------------------------------------------------------
# Build clue test data from live metadata
# ---------------------------------------------------------------------------

def build_clue_test_data(clue_id, metadata):
    """Build the test data dict for a clue from its Supabase metadata.

    Extracts everything the 12 tests need: step values, indicator info,
    assembly info, wrong values, etc.
    """
    # Parse clue_id: "times-29147-21d" -> puzzle_number="29147", clue_number="21", direction="down"
    parts = clue_id.split("-")
    puzzle_number = parts[1]
    suffix = parts[2]  # e.g. "21d"
    match = re.match(r'^(\d+)([ad])$', suffix)
    if not match:
        raise ValueError(f"Cannot parse clue_id '{clue_id}'")
    clue_number = match.group(1)
    direction = "across" if match.group(2) == "a" else "down"

    steps_meta = metadata.get("steps", [])
    words = metadata.get("words", [])

    # Build step values for walkthrough
    step_values = []
    for step in steps_meta:
        step_type = step["type"]
        if step_type == "assembly":
            transforms = step.get("transforms", [])
            # Identify hidden transforms: source transforms consumed by substitution
            has_sub = any(t.get("type") == "substitution" for t in transforms)
            hidden = set()
            if has_sub:
                for i, t in enumerate(transforms):
                    if t.get("type") == "substitution" and i > 0:
                        for j in range(i):
                            if transforms[j].get("type") not in DEPENDENT_TRANSFORM_TYPES:
                                hidden.add(j)
            transform_entries = [{"index": i, "value": t["result"]}
                                 for i, t in enumerate(transforms) if i not in hidden]
            step_values.append({"type": "assembly", "inputMode": "assembly", "transforms": transform_entries})
        elif step_type in ("definition", "indicator", "outer_word", "inner_word", "fodder",
                           "multi_definition", "abbreviation_scan"):
            step_values.append({"type": step_type, "inputMode": "tap_words", "value": step["indices"]})
        elif step_type == "wordplay_type":
            step_values.append({"type": step_type, "inputMode": "multiple_choice", "value": step["expected"]})
        else:
            step_values.append({"type": step_type, "inputMode": "unknown", "value": None})

    # Wrong value for step 0 — pick indices NOT in the correct answer
    first_step = steps_meta[0] if steps_meta else {}
    if "indices" in first_step:
        def_indices = set(first_step["indices"])
        wrong = [i for i in range(len(words)) if i not in def_indices][:2]
        if not wrong:
            wrong = [0] if 0 not in def_indices else [1]
    elif "expected" in first_step:
        # multiple_choice step (e.g. wordplay_type) — pick a wrong option
        options = first_step.get("options", [])
        wrong = [o for o in options if o != first_step["expected"]][:1] or ["Wrong"]
    else:
        wrong = [0]

    # Indicator info
    indicator_types = []
    has_indicator_steps = False
    for step in steps_meta:
        if step["type"] == "indicator":
            has_indicator_steps = True
            indicator_types.append(step.get("indicator_type", ""))

    # Assembly info
    num_transforms = 0
    dependent_indices = []
    is_container = False
    for step in steps_meta:
        if step["type"] == "assembly":
            transforms = step.get("transforms", [])
            # Compute hidden transforms (same logic as above)
            has_sub = any(t.get("type") == "substitution" for t in transforms)
            hidden_transforms = set()
            if has_sub:
                for i, t in enumerate(transforms):
                    if t.get("type") == "substitution" and i > 0:
                        for j in range(i):
                            if transforms[j].get("type") not in DEPENDENT_TRANSFORM_TYPES:
                                hidden_transforms.add(j)
            num_transforms = len(transforms) - len(hidden_transforms)
            for i, t in enumerate(transforms):
                if i in hidden_transforms:
                    continue
                if t.get("type") in DEPENDENT_TRANSFORM_TYPES:
                    dependent_indices.append(i)
                if t.get("type") == "container":
                    is_container = True

    return {
        "id": clue_id,
        "puzzle_number": puzzle_number,
        "clue_number": clue_number,
        "direction": direction,
        "answer": re.sub(r'[^A-Za-z]', '', metadata.get("answer", "")),
        "answer_raw": metadata.get("answer", ""),
        "enumeration": metadata.get("enumeration", ""),
        "words": words,
        "steps": step_values,
        "steps_meta": steps_meta,  # raw metadata for indicator_coverage etc.
        "wrong_value_step0": wrong,
        "has_indicator_steps": has_indicator_steps,
        "indicator_types": indicator_types,
        "num_assembly_transforms": num_transforms,
        "dependent_transform_indices": dependent_indices,
        "is_container": is_container,
    }


# ---------------------------------------------------------------------------
# Assembly submission helper
# ---------------------------------------------------------------------------

def submit_assembly_transforms(server, clue_id, transforms, render):
    """Submit assembly transforms in order. Auto-skip must complete the clue."""
    for t in transforms:
        idx = t["index"]
        val = t["value"]

        if render.get("complete") or render.get("currentStep") is None:
            break
        current = render["currentStep"]
        if current["type"] != "assembly":
            break

        assembly_data = current.get("assemblyData", {})
        transform_list = assembly_data.get("transforms", [])

        t_entry = None
        for te in transform_list:
            if te["index"] == idx:
                t_entry = te
                break

        if t_entry is None:
            # Transform not in display — auto-completed or hidden (straight anagram).
            # Submit hidden transforms via transform_inputs (the letter boxes).
            payload = {"clue_id": clue_id, "session": _session(render),
                       "value": "", "transform_inputs": {str(idx): list(val)}}
            status, body = api_post(server, "/input", payload)
            if status == 200:
                render = body["render"]
            continue

        if t_entry["status"] == "completed":
            continue
        if t_entry["status"] == "locked":
            raise RuntimeError(f"Transform {idx} is locked — test data ordering error")

        correct, render = submit_input(server, clue_id, val, render, transform_index=idx)
        if not correct:
            raise RuntimeError(f"Transform {idx} value '{val}' rejected as incorrect")

    return render


def walk_to_assembly(server, clue):
    """Walk through all steps up to (but not including) the assembly step."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            break
        correct, render = submit_input(server, clue_id, step["value"], render)
        if not correct:
            raise RuntimeError(f"Pre-assembly step {step['type']} failed for {clue['id']}")

    return clue_id, render


def walk_to_completion(server, clue):
    """Walk through all steps to completion. Returns (clue_id, render)."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            render = submit_assembly_transforms(
                server, clue_id, step["transforms"], render
            )
        else:
            correct, render = submit_input(server, clue_id, step["value"], render)
            if not correct:
                raise RuntimeError(f"Step {step['type']} was rejected for {clue['id']}")

    return clue_id, render


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def _check_render_shape(render, context=""):
    """Validate the shape of a render response. Returns (ok, error_message)."""
    prefix = f"{context}: " if context else ""

    # Top-level required fields
    top_level = [
        "clue_id", "words", "answer", "enumeration", "answerGroups",
        "steps", "currentStep", "stepExpanded", "highlights",
        "selectedIndices", "userAnswer", "answerLocked", "complete",
    ]
    for field in top_level:
        if field not in render:
            return False, f"{prefix}Missing top-level field '{field}'"

    # Step summary shape
    for i, s in enumerate(render["steps"]):
        for field in ["index", "type", "title", "status"]:
            if field not in s:
                return False, f"{prefix}steps[{i}] missing '{field}'"
        if s["status"] not in ("completed", "active", "pending"):
            return False, f"{prefix}steps[{i}] invalid status '{s['status']}'"
        if s["status"] == "completed" and "completionText" not in s:
            return False, f"{prefix}steps[{i}] completed but missing 'completionText'"

    # Highlight shape
    for i, h in enumerate(render["highlights"]):
        for field in ["indices", "color"]:
            if field not in h:
                return False, f"{prefix}highlights[{i}] missing '{field}'"

    # currentStep shape (when present)
    step = render["currentStep"]
    if step is not None:
        for field in ["index", "type", "inputMode", "prompt"]:
            if field not in step:
                return False, f"{prefix}currentStep missing '{field}'"
        if "hintVisible" not in step:
            return False, f"{prefix}currentStep missing 'hintVisible'"

        # inputMode-specific checks
        if step["inputMode"] == "multiple_choice":
            if "options" not in step:
                return False, f"{prefix}currentStep (multiple_choice) missing 'options'"

        if step["inputMode"] == "assembly":
            if "assemblyData" not in step:
                return False, f"{prefix}currentStep (assembly) missing 'assemblyData'"
            err = _check_assembly_data_shape(step["assemblyData"], prefix)
            if err:
                return False, err

    return True, ""


def _check_assembly_data_shape(data, prefix=""):
    """Validate the shape of assemblyData. Returns error string or None."""
    required = [
        "phase", "failMessage", "transforms", "resultParts",
        "positionMap", "completedLetters", "definitionLine",
        "indicatorLine", "checkPhasePrompt",
    ]
    for field in required:
        if field not in data:
            return f"{prefix}assemblyData missing '{field}'"

    if data["phase"] not in ("transforms", "check"):
        return f"{prefix}assemblyData invalid phase '{data['phase']}'"

    # Transform shape
    for i, t in enumerate(data["transforms"]):
        required_t = ["role", "clueWord", "prompt", "letterCount",
                       "status", "result", "hint", "hintVisible", "index"]
        for field in required_t:
            if field not in t:
                return f"{prefix}transform[{i}] missing '{field}'"
        if t["status"] not in ("completed", "active"):
            return f"{prefix}transform[{i}] invalid status '{t['status']}'"
        if t["status"] == "completed" and "completedText" not in t:
            return f"{prefix}transform[{i}] completed but missing 'completedText'"

    return None


def test_response_contract(server, clue):
    """Verify response shapes across start, input, and completion."""
    # 1. Start response shape
    render = start_session(server, clue)

    ok, err = _check_render_shape(render, "/start")
    if not ok:
        return False, err

    if render["clue_id"] != clue["id"]:
        return False, f"clue_id: got '{render['clue_id']}', expected '{clue['id']}'"

    # Compare alpha-only (server may return hyphenated form like LEAVE-TAKING)
    render_answer = re.sub(r'[^A-Za-z]', '', render["answer"])
    expected_answer = re.sub(r'[^A-Za-z]', '', clue["answer"])
    if render_answer != expected_answer:
        return False, f"answer: got '{render_answer}', expected '{expected_answer}'"

    if render["enumeration"] != clue["enumeration"]:
        return False, f"enumeration: got '{render['enumeration']}', expected '{clue['enumeration']}'"

    # answerGroups sum must equal answer letter count
    answer_letters = len(re.sub(r'[^A-Z]', '', clue["answer"]))
    groups_sum = sum(render["answerGroups"])
    if groups_sum != answer_letters:
        return False, f"answerGroups sum {groups_sum} != answer letter count {answer_letters}"

    if render["answerLocked"]:
        return False, "answerLocked should be False at start"

    if render["complete"]:
        return False, "complete should be False at start"

    # 2. Input response shape — submit first step
    first_step = clue["steps"][0]
    if first_step["inputMode"] != "assembly":
        status, body = api_post(server, "/input", {
            "clue_id": render["clue_id"], "session": _session(render), "value": first_step["value"]
        })
        if status != 200:
            return False, f"First input failed ({status})"
        for field in ["correct", "message", "render"]:
            if field not in body:
                return False, f"/input response missing '{field}'"
        ok, err = _check_render_shape(body["render"], "/input.render")
        if not ok:
            return False, err

    # 3. Completion response shape — walk a fresh session to end
    clue_id, final_render = walk_to_completion(server, clue)
    ok, err = _check_render_shape(final_render, "completion")
    if not ok:
        return False, err

    if not final_render["complete"]:
        return False, "complete should be True after walkthrough"

    if final_render["currentStep"] is not None:
        return False, "currentStep should be None after completion"

    # 4. Check-answer response shape
    render_fresh = start_session(server, clue)
    status, body = api_post(server, "/check-answer", {
        "clue_id": render_fresh["clue_id"], "session": _session(render_fresh), "answer": clue["answer"]
    })
    if status != 200:
        return False, f"Check-answer failed ({status})"
    for field in ["correct", "message", "render"]:
        if field not in body:
            return False, f"/check-answer response missing '{field}'"

    # 5. Reveal response shape
    render_fresh2 = start_session(server, clue)
    reveal_render = reveal(server, render_fresh2["clue_id"], render_fresh2)
    ok, err = _check_render_shape(reveal_render, "/reveal")
    if not ok:
        return False, err

    return True, ""


def test_full_walkthrough(server, clue):
    """Happy path: correct input at every step -> complete."""
    clue_id, render = walk_to_completion(server, clue)

    if not render.get("complete"):
        return False, f"Expected complete=True, got {render.get('complete')}"
    if not render.get("answerLocked"):
        return False, f"Expected answerLocked=True, got {render.get('answerLocked')}"

    user_answer = render.get("userAnswer", [])
    if not user_answer:
        return False, "userAnswer is empty after completion"
    answer_str = "".join(user_answer)
    expected = clue["answer"].replace(" ", "")
    if answer_str != expected:
        return False, f"Answer mismatch: got '{answer_str}', expected '{expected}'"

    return True, ""


def test_wrong_input(server, clue):
    """Wrong value at step 0 -> correct=False, step doesn't advance."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    step_before = render["currentStep"]["index"]
    correct, render = submit_input(server, clue_id, clue["wrong_value_step0"], render)

    if correct:
        return False, "Wrong input was accepted as correct"

    step_after = render["currentStep"]["index"]
    if step_after != step_before:
        return False, f"Step advanced from {step_before} to {step_after} on wrong input"

    return True, ""


def test_assembly_transform_status(server, clue):
    """Walk to assembly -> verify all transforms are active (no locking)."""
    clue_id, render = walk_to_assembly(server, clue)

    current = render.get("currentStep")
    if not current or current["type"] != "assembly":
        # Assembly may have auto-completed (e.g. single-transform double definitions)
        if render.get("complete"):
            return True, ""
        return False, f"Expected assembly step, got {current.get('type') if current else 'None'}"

    assembly_data = current.get("assemblyData", {})
    transform_list = assembly_data.get("transforms", [])

    # Server may hide auto-completed transforms (e.g. straight anagram literal),
    # so visible count can be less than metadata count. Verify it's within range.
    if len(transform_list) > clue["num_assembly_transforms"]:
        return False, f"Expected at most {clue['num_assembly_transforms']} transforms, got {len(transform_list)}"
    # Straight anagrams have 0 visible transforms — student uses letter boxes directly
    if len(transform_list) == 0 and clue["num_assembly_transforms"] > 0:
        return True, ""

    for t in transform_list:
        if t["status"] != "active":
            return False, f"Transform {t['index']} should be 'active', got '{t['status']}'"

    return True, ""


def test_check_answer(server, clue):
    """Wrong answer -> rejected. Correct answer -> locked."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    correct, render = check_answer(server, clue_id, "ZZZZZ", render)
    if correct:
        return False, "Wrong answer was accepted"
    if render.get("answerLocked"):
        return False, "answerLocked should be False after wrong answer"

    correct, render = check_answer(server, clue_id, clue["answer"], render)
    if not correct:
        return False, f"Correct answer '{clue['answer']}' was rejected"
    if not render.get("answerLocked"):
        return False, "answerLocked should be True after correct answer"

    return True, ""


def test_reveal(server, clue):
    """Reveal -> all steps completed, complete=True, answerLocked=True."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    render = reveal(server, clue_id, render)

    if not render.get("complete"):
        return False, f"Expected complete=True after reveal, got {render.get('complete')}"
    if not render.get("answerLocked"):
        return False, f"Expected answerLocked=True after reveal, got {render.get('answerLocked')}"

    for s in render.get("steps", []):
        if s["status"] != "completed":
            return False, f"Step {s['index']} ({s['type']}) status='{s['status']}', expected 'completed'"

    return True, ""


def test_template_text(server, clue):
    """Indicator menuTitles contain indicator_type text. Definition completedTitle shows hint."""
    render = start_session(server, clue)
    clue_id, full_render = walk_to_completion(server, clue)

    # Definition completed title must NOT contain prompt text
    for s in full_render.get("steps", []):
        if s["type"] == "definition" and s["status"] == "completed":
            title = s.get("title", "")
            if "can you find" in title.lower():
                return False, (
                    f"Definition completed title '{title}' still contains "
                    f"prompt text 'can you find' — should show the hint instead"
                )

    # Definition hint must NOT contain the answer word (case-insensitive)
    # This catches hints that give away the answer before the student solves it.
    # The hint is available via the lightbulb during the step, so it must not
    # reveal what the student is trying to find.
    # Only check answers of 5+ letters — short words (TIE, ALB, AIL) will
    # inevitably appear in natural language hints.
    # Uses word-boundary matching to avoid false positives where the answer
    # is a substring of a longer word (e.g. OPTIC in "optician", RAVEN in "ravenous").
    answer = clue["answer"].upper()
    answer_raw = clue["answer_raw"].upper()
    if len(answer) >= 5:
        for s in clue["steps_meta"]:
            if s["type"] == "definition" and "hint" in s:
                hint_text = s["hint"]
                hint_upper = hint_text.upper()
                # Check the stripped answer (no hyphens/spaces) as a whole word
                found = bool(re.search(r'\b' + re.escape(answer) + r'\b', hint_upper))
                # Also check the original answer form for hyphenated/spaced answers
                if not found and answer_raw != answer:
                    found = bool(re.search(r'\b' + re.escape(answer_raw) + r'\b', hint_upper))
                # Also check individual words of multi-word answers (5+ letters each)
                if not found and (' ' in answer_raw or '-' in answer_raw):
                    for part in re.split(r'[\s-]+', answer_raw):
                        part_clean = re.sub(r'[^A-Za-z]', '', part).upper()
                        if len(part_clean) >= 5 and re.search(r'\b' + re.escape(part_clean) + r'\b', hint_upper):
                            found = True
                            break
                if found:
                    return False, (
                        f"Definition hint contains the answer '{answer_raw}': "
                        f"'{hint_text}' — hints must not give away the answer"
                    )

    # Check completed indicator titles don't redundantly repeat "[type] indicator"
    INDICATOR_TYPE_LABELS = [
        "deletion indicator", "reversal indicator", "container indicator",
        "anagram indicator", "ordering indicator", "letter selection indicator",
        "hidden word indicator"
    ]
    for s in full_render.get("steps", []):
        if s["type"] == "indicator" and s["status"] == "completed":
            title = s.get("title", "")
            parts = title.split(" \u2014 ", 1)
            if len(parts) == 2:
                hint_part = parts[1].lower()
                for label in INDICATOR_TYPE_LABELS:
                    if label in hint_part:
                        return False, (
                            f"Indicator completed title '{title}' redundantly "
                            f"mentions '{label}' in the hint — the template "
                            f"already prefixes with the indicator type"
                        )

    # Check indicator steps in the initial render
    render = start_session(server, clue)
    steps = render.get("steps", [])
    indicator_step_idx = 0

    for s in steps:
        if s["type"] == "indicator":
            if indicator_step_idx >= len(clue["indicator_types"]):
                return False, f"More indicator steps than expected indicator_types"

            expected_type = clue["indicator_types"][indicator_step_idx]
            display_type = expected_type.replace("_", " ")

            title = s.get("title", "")
            if display_type not in title.lower():
                return False, (
                    f"Indicator step title '{title}' does not contain "
                    f"indicator type '{display_type}'"
                )

            indicator_step_idx += 1

    if indicator_step_idx != len(clue["indicator_types"]):
        return False, (
            f"Expected {len(clue['indicator_types'])} indicator steps, "
            f"found {indicator_step_idx}"
        )

    if not clue["has_indicator_steps"]:
        for s in steps:
            if s["type"] == "indicator":
                return False, "Found unexpected indicator step"

    return True, ""


def test_assembly_completion_text(server, clue):
    """Verify assembly completion title for container clues shows insertion notation."""
    if not clue["is_container"]:
        return True, ""

    clue_id, render = walk_to_completion(server, clue)

    if not render.get("complete"):
        return False, "Clue did not complete"

    assembly_step = None
    for s in render.get("steps", []):
        if s["type"] == "assembly":
            assembly_step = s
            break

    if not assembly_step:
        return False, "No assembly step found in completed steps"

    title = assembly_step.get("title", "")

    # Container clue: title must NOT be plain "A + B + C + D" concatenation
    assembly_meta = None
    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            assembly_meta = step
            break
    if assembly_meta:
        transform_results = [t["value"] for t in assembly_meta["transforms"]]
        plain_concat = " + ".join(transform_results)
        if title == plain_concat:
            return False, (
                f"Assembly completion title is plain concatenation '{title}' — "
                f"should show container insertion, not charade-style joining"
            )

    return True, ""


def test_indicator_coverage(server, clue):
    """Verify that dependent transforms have matching indicator steps."""
    steps = clue["steps_meta"]

    indicator_types_covered = set()
    for s in steps:
        if s["type"] == "indicator":
            ind_type = s.get("indicator_type", "")
            indicator_types_covered.add(ind_type)
            if ind_type == "hidden_word":
                indicator_types_covered.add("reversal")

    for s in steps:
        if s["type"] != "assembly":
            continue
        for t in s.get("transforms", []):
            t_type = t.get("type", "")
            if t_type not in DEPENDENT_TRANSFORM_TYPES:
                continue
            if t_type not in indicator_types_covered:
                words = clue.get("words", [])
                t_indices = t.get("indices", [])
                t_words = [words[i] for i in t_indices if i < len(words)]
                return False, (
                    f"Assembly has a '{t_type}' transform ('{' '.join(t_words)}') "
                    f"but no indicator step of type '{t_type}' exists — "
                    f"student never gets to identify the indicator word"
                )

    return True, ""


def test_abbreviation_scan_consistency(server, clue):
    """Verify abbreviation_scan mappings keys match indices and assembly transforms."""
    steps = clue["steps_meta"]
    words = clue.get("words", [])

    for s in steps:
        if s["type"] != "abbreviation_scan":
            continue

        indices = s.get("indices", [])
        mappings = s.get("mappings", {})

        # Every mappings key must be in indices
        for key_str in mappings:
            key_int = int(key_str)
            if key_int not in indices:
                word_at_key = words[key_int] if key_int < len(words) else "?"
                return False, (
                    f"abbreviation_scan mappings key '{key_str}' (word: '{word_at_key}') "
                    f"is not in indices {indices}"
                )

        # Every index must either have a mappings entry or be part of a
        # multi-word abbreviation (where only the first index has the mapping)
        # Build set of all indices covered by assembly abbreviation transforms
        covered_by_transforms = set()
        for asm in steps:
            if asm["type"] != "assembly":
                continue
            for t in asm.get("transforms", []):
                if t.get("type") == "abbreviation":
                    for ti in t.get("indices", []):
                        covered_by_transforms.add(ti)

        for idx in indices:
            if str(idx) not in mappings and idx not in covered_by_transforms:
                word_at_idx = words[idx] if idx < len(words) else "?"
                return False, (
                    f"abbreviation_scan index {idx} (word: '{word_at_idx}') "
                    f"has no entry in mappings {mappings} and is not part of "
                    f"a multi-word abbreviation transform"
                )

        # Each mapped abbreviation must match an assembly abbreviation transform
        # Exception: substitution clues express abbreviations through the substitution
        # operation, not through separate abbreviation transforms
        for asm in steps:
            if asm["type"] != "assembly":
                continue
            has_substitution = any(t.get("type") == "substitution" for t in asm.get("transforms", []))
            if has_substitution:
                break  # substitution clues don't need abbreviation transforms
            for key_str, letter in mappings.items():
                key_int = int(key_str)
                matched = False
                for t in asm.get("transforms", []):
                    if t.get("type") == "abbreviation" and key_int in t.get("indices", []):
                        if t["result"].upper() == letter.upper():
                            matched = True
                            break
                if not matched:
                    word_at_key = words[key_int] if key_int < len(words) else "?"
                    return False, (
                        f"abbreviation_scan maps '{word_at_key}' (index {key_int}) → {letter}, "
                        f"but no assembly abbreviation transform matches"
                    )

    return True, ""


def test_assembly_combined_check(server, clue):
    """Submit all assembly transforms and verify auto-skip completes the clue.

    Auto-skip means: once every transform result is submitted, the engine
    assembles the letters via position_map and — if they spell the answer —
    automatically completes the step without a separate check phase.
    If auto-skip fails (position_map is wrong), the engine falls through to
    check phase, which this test must detect as a failure.
    """
    assembly_step = None
    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            assembly_step = step
            break
    if not assembly_step:
        return True, ""

    clue_id, render = walk_to_assembly(server, clue)

    render = submit_assembly_transforms(
        server, clue_id, assembly_step["transforms"], render
    )

    if not render.get("complete"):
        # Auto-skip didn't fire — check if we're stuck in check phase
        current = render.get("currentStep", {})
        assembly_data = current.get("assemblyData", {})
        if assembly_data.get("phase") == "check":
            return False, (
                "All transforms completed but auto-skip failed — stuck in check phase. "
                "This usually means _compute_position_map returned empty for this clue."
            )
        transforms = assembly_data.get("transforms", [])
        incomplete = [t for t in transforms if t["status"] != "completed"]
        incomplete_desc = ", ".join(f"{t['index']}({t['role']})" for t in incomplete)
        return False, (
            f"Expected completion after all transforms, "
            f"but these transforms are still incomplete: {incomplete_desc}"
        )

    return True, ""


def test_dependent_prompt_update(server, clue):
    """Dependent transform prompts update when predecessors are solved."""
    if not clue["dependent_transform_indices"]:
        return True, ""

    assembly_step = None
    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            assembly_step = step
            break
    if not assembly_step:
        return True, ""

    clue_id, render = walk_to_assembly(server, clue)

    assembly_data = render["currentStep"]["assemblyData"]
    transforms = assembly_data["transforms"]

    dep_idx = clue["dependent_transform_indices"][0]
    dep_transform = None
    for t in transforms:
        if t["index"] == dep_idx:
            dep_transform = t
            break
    if dep_transform is None:
        # Straight anagrams have no visible transforms — skip this test.
        # Container transforms are also hidden (auto-completed) — skip.
        if len(transforms) == 0:
            return True, ""
        # Check if the dependent transform is a container type (hidden from display)
        for step_meta in clue["steps_meta"]:
            if step_meta["type"] == "assembly":
                raw_transforms = step_meta.get("transforms", [])
                if dep_idx < len(raw_transforms) and raw_transforms[dep_idx].get("type") == "container":
                    return True, ""
                break
        return False, f"Dependent transform {dep_idx} not found in assembly data"

    initial_prompt = dep_transform["prompt"]

    # Solve the predecessor(s)
    for t in assembly_step["transforms"]:
        if t["index"] < dep_idx:
            correct, render = submit_input(server, clue_id, t["value"], render,
                                           transform_index=t["index"])
            if not correct:
                return False, f"Predecessor transform {t['index']} rejected"

    # Re-check the dependent transform's prompt
    assembly_data = render["currentStep"]["assemblyData"]
    transforms = assembly_data["transforms"]
    for t in transforms:
        if t["index"] == dep_idx:
            dep_transform = t
            break

    updated_prompt = dep_transform["prompt"]

    TEMPLATE_MARKERS = ["tells you to reverse", "tells you to shorten",
                        "rearrange those letters",
                        "tells you one piece goes inside another"]
    uses_template = any(m in initial_prompt for m in TEMPLATE_MARKERS)

    if updated_prompt == initial_prompt:
        if not uses_template:
            return True, ""  # per-clue override, skip
        return False, (
            f"Dependent transform {dep_idx} template prompt did not update "
            f"after predecessors solved. Still: '{updated_prompt}'"
        )

    return True, ""


def test_help_toggle(server, clue):
    """Verify phase help toggle: starts collapsed, toggles open/closed, has text."""
    render = start_session(server, clue)

    # Help should start collapsed with non-empty text
    if render.get("helpVisible") is not False:
        return False, f"helpVisible should be False at start, got {render.get('helpVisible')}"
    if not render.get("helpText"):
        return False, "helpText should be non-empty at start"

    # Toggle open
    render = send_ui_state(server, clue["id"], render, "toggle_help")
    if render.get("helpVisible") is not True:
        return False, f"helpVisible should be True after toggle, got {render.get('helpVisible')}"
    text_after_open = render.get("helpText")
    if not text_after_open:
        return False, "helpText should be non-empty when visible"

    # Toggle closed
    render = send_ui_state(server, clue["id"], render, "toggle_help")
    if render.get("helpVisible") is not False:
        return False, f"helpVisible should be False after second toggle, got {render.get('helpVisible')}"
    if render.get("helpText") != text_after_open:
        return False, "helpText should not change on toggle"

    return True, ""


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

ALL_TESTS = [
    ("Response contract", test_response_contract),
    ("Full walkthrough", test_full_walkthrough),
    ("Wrong input", test_wrong_input),
    ("Assembly transform status", test_assembly_transform_status),
    ("Check answer", test_check_answer),
    ("Reveal", test_reveal),
    ("Template text", test_template_text),
    ("Assembly completion text", test_assembly_completion_text),
    ("Indicator coverage", test_indicator_coverage),
    ("Abbreviation scan consistency", test_abbreviation_scan_consistency),
    ("Assembly combined check", test_assembly_combined_check),
    ("Dependent prompt update", test_dependent_prompt_update),
    ("Help toggle", test_help_toggle),
]


def run_tests(server, clue_filter=None):
    """Fetch all clues from server, build test data, run all tests."""
    passed = 0
    failed = 0
    errors = []

    print(f"=== Trainer Regression Tests ===")
    print(f"Server: {server}")
    print()

    # Fetch all clues with training data (one bulk call)
    print("Loading clues from Supabase via /trainer/clue-ids?full=1 ...")
    all_data = api_get(server, "/clue-ids?full=1")
    clues_dict = all_data["clues"]
    if clue_filter:
        matches = {k: v for k, v in clues_dict.items() if clue_filter in k}
        if not matches:
            print(f"No clues matching '{clue_filter}' found.")
            return True
        clues_dict = matches
    print(f"Testing {len(clues_dict)} clue(s)")
    print()

    # Build test data for each clue
    all_clues = []
    for clue_id in sorted(clues_dict.keys()):
        metadata = clues_dict[clue_id]
        try:
            clue = build_clue_test_data(clue_id, metadata)
            all_clues.append(clue)
        except Exception as e:
            print(f"  [ERROR] Cannot build test data for {clue_id}: {e}")
            failed += 1
            errors.append((f"{clue_id} - Build test data", str(e)))

    # Run all tests for each clue
    for clue in all_clues:
        d_char = 'A' if clue['direction'] == 'across' else 'D'
        label = f"{clue['clue_number']}{d_char} {clue['answer']}"
        print(f"--- {label} ---")

        for test_name, test_fn in ALL_TESTS:
            full_name = f"{label} - {test_name}"
            try:
                ok, msg = test_fn(server, clue)
                if ok:
                    print(f"  [PASS] {full_name}")
                    passed += 1
                else:
                    print(f"  [FAIL] {full_name}: {msg}")
                    failed += 1
                    errors.append((full_name, msg))
            except Exception as e:
                print(f"  [ERROR] {full_name}: {e}")
                failed += 1
                errors.append((full_name, str(e)))

        print()

    print(f"=== Summary ===")
    print(f"Clues tested: {len(all_clues)}")
    print(f"Passed: {passed}/{passed + failed}")
    print(f"Failed: {failed}")

    if errors:
        print()
        print("Failures:")
        for name, msg in errors:
            print(f"  {name}: {msg}")

    return failed == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    server = DEFAULT_SERVER
    clue_filter = None

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--server" and i < len(sys.argv) - 1:
            server = sys.argv[i + 1]
        elif arg == "--clue" and i < len(sys.argv) - 1:
            clue_filter = sys.argv[i + 1]
        elif sys.argv[i - 1] in ("--server", "--clue"):
            pass
        elif arg.startswith("--server="):
            server = arg.split("=", 1)[1]
        elif arg.startswith("--clue="):
            clue_filter = arg.split("=", 1)[1]

    # Quick connectivity check
    try:
        req = urllib.request.Request(f"{server}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception as e:
        print(f"Cannot connect to server at {server}: {e}")
        print("Make sure crossword_server.py is running.")
        sys.exit(1)

    success = run_tests(server, clue_filter)
    sys.exit(0 if success else 1)
