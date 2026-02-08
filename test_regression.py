#!/usr/bin/env python3
"""
Trainer Regression Tests
========================

Tests all trainer API endpoints against a running server.
Walks through 12 representative clues covering all 7 step flow patterns,
all indicator types, all transform types, and key edge cases.

Usage:
    python3 test_regression.py
    python3 test_regression.py --server http://127.0.0.1:8080

Requires: a running crossword_server.py instance.
Dependencies: stdlib only (urllib).
"""

import json
import sys
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_SERVER = "http://127.0.0.1:8080"

# ---------------------------------------------------------------------------
# 12 Test Clues — covering all 7 step flow patterns
# ---------------------------------------------------------------------------
#
# Each clue dict contains:
#   id, clue_text, puzzle_number, clue_number, direction, answer
#   steps: list of {type, inputMode, value, ...} for the happy-path walkthrough
#     - tap_words steps: value = list of indices
#     - multiple_choice steps: value = string (the expected answer)
#     - assembly steps: transforms = [{index, value}, ...]
#   has_indicator_steps: bool — whether any step is type "indicator"
#   indicator_types: list of indicator_type strings (for template text tests)
#   assembly_explicit: bool — whether assembly has explicit=True
#   num_assembly_transforms: int — total transform count
#   dependent_transform_indices: list of int — which transforms are dependent
#   wrong_value_step0: a wrong value for the definition step (for negative test)

TEST_CLUES = [
    # 1. 11A VISIT — def→wordplay→assembly (simplest charade, 2 independent)
    {
        "id": "times-29453-11a",
        "clue_text": "Come by five, do you mean?",
        "puzzle_number": "29453",
        "clue_number": "11",
        "direction": "across",
        "answer": "VISIT",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "V"}, {"index": 1, "value": "ISIT"}]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [3, 4],
    },

    # 2. 6D RAVEN — def→indicator(ordering)→assembly
    {
        "id": "times-29453-6d",
        "clue_text": "Any number after dance party are starving",
        "puzzle_number": "29453",
        "clue_number": "6",
        "direction": "down",
        "answer": "RAVEN",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [5, 6]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "RAVE"}, {"index": 1, "value": "N"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["ordering"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [0, 1],
    },

    # 3. 1A BROLLY — def→indicator(container)→outer→inner→assembly
    {
        "id": "times-29453-1a",
        "clue_text": "Cover up in shower? Not after nurses turn round",
        "puzzle_number": "29453",
        "clue_number": "1",
        "direction": "across",
        "answer": "BROLLY",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1, 2, 3]},
            {"type": "indicator", "inputMode": "tap_words", "value": [6]},
            {"type": "outer_word", "inputMode": "tap_words", "value": [4, 5]},
            {"type": "inner_word", "inputMode": "tap_words", "value": [7, 8]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "BY"}, {"index": 1, "value": "ROLL"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [5, 6],
    },

    # 4. 2D OMERTA — def→indicator(anagram)→fodder→assembly (anagram dependent)
    {
        "id": "times-29453-2d",
        "clue_text": "Crooked old mater \u2014 which strongly suggests criminal is mum",
        "puzzle_number": "29453",
        "clue_number": "2",
        "direction": "down",
        "answer": "OMERTA",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [4, 5, 6, 7, 8, 9]},
            {"type": "indicator", "inputMode": "tap_words", "value": [0]},
            {"type": "fodder", "inputMode": "tap_words", "value": [1, 2]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "O"},
                 {"index": 1, "value": "MATER"},
                 {"index": 2, "value": "OMERTA"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["anagram"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],  # anagram at index 2 depends on 0, 1
        "wrong_value_step0": [0, 1],
    },

    # 5. 3D LATECOMER — def→indicator(letter_selection)→indicator(anagram)→assembly (explicit=True)
    {
        "id": "times-29453-3d",
        "clue_text": "One missing initially, admitted to Electra with some upheaval?",
        "puzzle_number": "29453",
        "clue_number": "3",
        "direction": "down",
        "answer": "LATECOMER",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "indicator", "inputMode": "tap_words", "value": [7, 8]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "OM"},
                 {"index": 1, "value": "ELECTRA"},
                 {"index": 2, "value": "LATECOMER"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["letter_selection", "anagram"],
        "assembly_explicit": True,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],  # anagram at index 2
        "wrong_value_step0": [3, 4],
    },

    # 6. 17D ASWAN DAM — def→wordplay(Container)→indicator(container)→outer→inner→assembly (hybrid)
    {
        "id": "times-29453-17d",
        "clue_text": "Embankment architect lengthened with cob?",
        "puzzle_number": "29453",
        "clue_number": "17",
        "direction": "down",
        "answer": "ASWAN DAM",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Container"},
            {"type": "indicator", "inputMode": "tap_words", "value": [2]},
            {"type": "outer_word", "inputMode": "tap_words", "value": [1]},
            {"type": "inner_word", "inputMode": "tap_words", "value": [4]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [{"index": 0, "value": "ADAM"}, {"index": 1, "value": "SWAN"}]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["container"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [],
        "wrong_value_step0": [1, 2],
    },

    # 7. 5D EEK — def→indicator(deletion)→fodder→indicator(reversal)→assembly (chain)
    {
        "id": "times-29453-5d",
        "clue_text": "A lot of sharp turns, I'm afraid",
        "puzzle_number": "29453",
        "clue_number": "5",
        "direction": "down",
        "answer": "EEK",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [5, 6]},
            {"type": "indicator", "inputMode": "tap_words", "value": [0, 1, 2]},
            {"type": "fodder", "inputMode": "tap_words", "value": [3]},
            {"type": "indicator", "inputMode": "tap_words", "value": [4]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "KEEN"},
                 {"index": 1, "value": "KEE"},
                 {"index": 2, "value": "EEK"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["deletion", "reversal"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [1, 2],  # deletion at 1, reversal at 2
        "wrong_value_step0": [0, 1],
    },

    # 8. 13A ANDANTINO — def→wordplay→assembly (3 independent synonyms)
    {
        "id": "times-29453-13a",
        "clue_text": "Moderate movement also opposed to one referendum option",
        "puzzle_number": "29453",
        "clue_number": "13",
        "direction": "across",
        "answer": "ANDANTINO",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "AND"},
                 {"index": 1, "value": "ANTI"},
                 {"index": 2, "value": "NO"},
             ]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [],
        "wrong_value_step0": [2, 3],
    },

    # 9. 4A REPROACH — def→wordplay→assembly (deletion dependent)
    {
        "id": "times-29453-4a",
        "clue_text": "Twit copying antique with pine, mostly",
        "puzzle_number": "29453",
        "clue_number": "4",
        "direction": "across",
        "answer": "REPROACH",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "REPRO"},
                 {"index": 1, "value": "ACHE"},
                 {"index": 2, "value": "ACH"},
             ]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],  # deletion at index 2
        "wrong_value_step0": [1, 2],
    },

    # 10. 28A CAESAR — def→indicator(reversal)→assembly (reversal chain)
    {
        "id": "times-29453-28a",
        "clue_text": "Tsar\u2019s like, roughly level after revolution",
        "puzzle_number": "29453",
        "clue_number": "28",
        "direction": "across",
        "answer": "CAESAR",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "indicator", "inputMode": "tap_words", "value": [5]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "CA"},
                 {"index": 1, "value": "RASE"},
                 {"index": 2, "value": "ESAR"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["reversal"],
        "assembly_explicit": False,
        "num_assembly_transforms": 3,
        "dependent_transform_indices": [2],  # reversal at index 2
        "wrong_value_step0": [2, 3],
    },

    # 11. 26A WINDSWEPT — def→wordplay→assembly (5 transforms, mixed chain)
    {
        "id": "times-29453-26a",
        "clue_text": "Turn bench back in street exposed to blasts",
        "puzzle_number": "29453",
        "clue_number": "26",
        "direction": "across",
        "answer": "WINDSWEPT",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [5, 6, 7]},
            {"type": "wordplay_type", "inputMode": "multiple_choice", "value": "Charade"},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "WIND"},
                 {"index": 1, "value": "PEW"},
                 {"index": 2, "value": "WEP"},
                 {"index": 3, "value": "ST"},
                 {"index": 4, "value": "SWEPT"},
             ]},
        ],
        "has_indicator_steps": False,
        "indicator_types": [],
        "assembly_explicit": False,
        "num_assembly_transforms": 5,
        "dependent_transform_indices": [2, 4],  # reversal at 2, anagram at 4
        "wrong_value_step0": [0, 1],
    },

    # 12. 23D PSEUD — def→indicator(hidden_word)→fodder→assembly
    {
        "id": "times-29453-23d",
        "clue_text": "Pretend authority raised undue spending limits",
        "puzzle_number": "29453",
        "clue_number": "23",
        "direction": "down",
        "answer": "PSEUD",
        "steps": [
            {"type": "definition", "inputMode": "tap_words", "value": [0, 1]},
            {"type": "indicator", "inputMode": "tap_words", "value": [2, 5]},
            {"type": "fodder", "inputMode": "tap_words", "value": [3, 4]},
            {"type": "assembly", "inputMode": "assembly",
             "transforms": [
                 {"index": 0, "value": "DUESP"},
                 {"index": 1, "value": "PSEUD"},
             ]},
        ],
        "has_indicator_steps": True,
        "indicator_types": ["hidden_word"],
        "assembly_explicit": False,
        "num_assembly_transforms": 2,
        "dependent_transform_indices": [1],  # reversal at index 1
        "wrong_value_step0": [3, 4],
    },
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

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
        "clue_text": clue["clue_text"],
        "puzzle_number": clue["puzzle_number"],
        "clue_number": clue["clue_number"],
        "direction": clue["direction"],
    })
    if status != 200:
        raise RuntimeError(f"Start failed ({status}): {body}")
    return body


def submit_input(server, clue_id, value, transform_index=None):
    """Submit input for the current step. Returns (correct, render)."""
    payload = {"clue_id": clue_id, "value": value}
    if transform_index is not None:
        payload["transform_index"] = transform_index
    status, body = api_post(server, "/input", payload)
    if status != 200:
        raise RuntimeError(f"Input failed ({status}): {body}")
    return body["correct"], body["render"]


def check_answer(server, clue_id, answer):
    """Check a typed answer. Returns (correct, render)."""
    status, body = api_post(server, "/check-answer", {"clue_id": clue_id, "answer": answer})
    if status != 200:
        raise RuntimeError(f"Check-answer failed ({status}): {body}")
    return body["correct"], body["render"]


def reveal(server, clue_id):
    """Reveal the full answer. Returns render."""
    status, body = api_post(server, "/reveal", {"clue_id": clue_id})
    if status != 200:
        raise RuntimeError(f"Reveal failed ({status}): {body}")
    return body


# ---------------------------------------------------------------------------
# Assembly submission helper
# ---------------------------------------------------------------------------

def submit_assembly_transforms(server, clue_id, transforms, render, answer=None):
    """Submit assembly transforms in order, handling status and auto-completion.

    If all transforms complete but auto-skip doesn't trigger (check phase),
    submits the final assembled result using the answer parameter.

    Returns the final render after all transforms are submitted.
    """
    for t in transforms:
        idx = t["index"]
        val = t["value"]

        # Check current step — if assembly already auto-completed, stop
        if render.get("complete") or render.get("currentStep") is None:
            break
        current = render["currentStep"]
        if current["type"] != "assembly":
            break  # step already advanced past assembly

        # Find this transform's status
        assembly_data = current.get("assemblyData", {})
        transform_list = assembly_data.get("transforms", [])

        # Find the transform entry by index
        t_entry = None
        for te in transform_list:
            if te["index"] == idx:
                t_entry = te
                break

        if t_entry is None:
            raise RuntimeError(f"Transform index {idx} not found in assembly data")

        status = t_entry["status"]
        if status == "completed":
            continue  # auto-superseded
        if status == "locked":
            raise RuntimeError(f"Transform {idx} is locked — test data ordering error")

        correct, render = submit_input(server, clue_id, val, transform_index=idx)
        if not correct:
            raise RuntimeError(f"Transform {idx} value '{val}' rejected as incorrect")

    # If assembly entered check phase (auto-skip didn't fire), submit the full result
    current = render.get("currentStep")
    if current and current["type"] == "assembly":
        assembly_data = current.get("assemblyData", {})
        if assembly_data.get("phase") == "check" and answer:
            correct, render = submit_input(server, clue_id, answer)
            if not correct:
                raise RuntimeError(f"Assembly check phase rejected answer '{answer}'")

    return render


# ---------------------------------------------------------------------------
# Walk to assembly step (submit all steps before assembly)
# ---------------------------------------------------------------------------

def walk_to_assembly(server, clue):
    """Walk through all steps up to (but not including) the assembly step.
    Returns (clue_id, render) with currentStep pointing to assembly.
    """
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            break
        correct, render = submit_input(server, clue_id, step["value"])
        if not correct:
            raise RuntimeError(f"Pre-assembly step {step['type']} failed for {clue['id']}")

    return clue_id, render


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def test_full_walkthrough(server, clue):
    """Happy path: correct input at every step -> complete."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            render = submit_assembly_transforms(
                server, clue_id, step["transforms"], render, answer=clue["answer"]
            )
        else:
            correct, render = submit_input(server, clue_id, step["value"])
            if not correct:
                return False, f"Step {step['type']} was rejected as incorrect"

    # Verify completion
    if not render.get("complete"):
        return False, f"Expected complete=True, got {render.get('complete')}"
    if not render.get("answerLocked"):
        return False, f"Expected answerLocked=True, got {render.get('answerLocked')}"
    # Answer should be populated
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

    # Get current step index before wrong input
    step_before = render["currentStep"]["index"]

    # Submit wrong value
    correct, render = submit_input(server, clue_id, clue["wrong_value_step0"])

    if correct:
        return False, "Wrong input was accepted as correct"

    step_after = render["currentStep"]["index"]
    if step_after != step_before:
        return False, f"Step advanced from {step_before} to {step_after} on wrong input"

    return True, ""


def test_assembly_transform_status(server, clue):
    """Walk to assembly -> verify independent=active, dependent=locked (or all active if explicit)."""
    clue_id, render = walk_to_assembly(server, clue)

    current = render.get("currentStep")
    if not current or current["type"] != "assembly":
        return False, f"Expected assembly step, got {current.get('type') if current else 'None'}"

    assembly_data = current.get("assemblyData", {})
    transform_list = assembly_data.get("transforms", [])

    if len(transform_list) != clue["num_assembly_transforms"]:
        return False, f"Expected {clue['num_assembly_transforms']} transforms, got {len(transform_list)}"

    for t in transform_list:
        idx = t["index"]
        status = t["status"]

        if clue["assembly_explicit"]:
            # All transforms should be active when explicit=True
            if status != "active":
                return False, f"Transform {idx} should be 'active' (explicit=True), got '{status}'"
        else:
            if idx in clue["dependent_transform_indices"]:
                # Dependent transforms should be locked (unless idx 0, which is always active)
                if idx == 0:
                    if status != "active":
                        return False, f"Transform 0 should be 'active', got '{status}'"
                else:
                    if status != "locked":
                        return False, f"Transform {idx} should be 'locked' (dependent), got '{status}'"
            else:
                if status != "active":
                    return False, f"Transform {idx} should be 'active' (independent), got '{status}'"

    return True, ""


def test_check_answer(server, clue):
    """Wrong answer -> rejected. Correct answer -> locked."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    # Wrong answer
    correct, render = check_answer(server, clue_id, "ZZZZZ")
    if correct:
        return False, "Wrong answer was accepted"
    if render.get("answerLocked"):
        return False, "answerLocked should be False after wrong answer"

    # Correct answer
    correct, render = check_answer(server, clue_id, clue["answer"])
    if not correct:
        return False, f"Correct answer '{clue['answer']}' was rejected"
    if not render.get("answerLocked"):
        return False, "answerLocked should be True after correct answer"

    return True, ""


def test_reveal(server, clue):
    """Reveal -> all steps completed, complete=True, answerLocked=True."""
    render = start_session(server, clue)
    clue_id = render["clue_id"]

    render = reveal(server, clue_id)

    if not render.get("complete"):
        return False, f"Expected complete=True after reveal, got {render.get('complete')}"
    if not render.get("answerLocked"):
        return False, f"Expected answerLocked=True after reveal, got {render.get('answerLocked')}"

    # All steps should be completed
    steps = render.get("steps", [])
    for s in steps:
        if s["status"] != "completed":
            return False, f"Step {s['index']} ({s['type']}) status='{s['status']}', expected 'completed'"

    return True, ""


def test_template_text(server, clue):
    """Indicator menuTitles contain indicator_type text. Prompts are type-specific."""
    render = start_session(server, clue)

    # Check indicator steps in the step list
    steps = render.get("steps", [])
    indicator_step_idx = 0

    for s in steps:
        if s["type"] == "indicator":
            if indicator_step_idx >= len(clue["indicator_types"]):
                return False, f"More indicator steps than expected indicator_types"

            expected_type = clue["indicator_types"][indicator_step_idx]
            display_type = expected_type.replace("_", " ")

            # menuTitle should contain the indicator type
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

    # If no indicator steps expected, verify none are present
    if not clue["has_indicator_steps"]:
        for s in steps:
            if s["type"] == "indicator":
                return False, "Found unexpected indicator step"

    return True, ""


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

ALL_TESTS = [
    ("Full walkthrough", test_full_walkthrough),
    ("Wrong input", test_wrong_input),
    ("Assembly transform status", test_assembly_transform_status),
    ("Check answer", test_check_answer),
    ("Reveal", test_reveal),
    ("Template text", test_template_text),
]


def run_tests(server):
    """Run all tests and print results."""
    passed = 0
    failed = 0
    errors = []

    print(f"=== Trainer Regression Tests ===")
    print(f"Server: {server}")
    print()

    for clue in TEST_CLUES:
        label = f"{clue['clue_number']}{'A' if clue['direction'] == 'across' else 'D'} {clue['answer']}"
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

    # Simple arg parsing (no argparse needed)
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--server" and i < len(sys.argv) - 1:
            server = sys.argv[i + 1]
        elif sys.argv[i - 1] == "--server":
            pass  # already consumed
        elif arg.startswith("--server="):
            server = arg.split("=", 1)[1]

    # Quick connectivity check
    try:
        req = urllib.request.Request(f"{server}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception as e:
        print(f"Cannot connect to server at {server}: {e}")
        print("Make sure crossword_server.py is running.")
        sys.exit(1)

    success = run_tests(server)
    sys.exit(0 if success else 1)
