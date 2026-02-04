"""
Test Case: times-29453-25a (DRIVE) should reach summary page after completion

BUG REPORT:
After completing all steps for clue 25A "Urge removal of line from silly speech (5)",
the user expects to be taken to the completed summary page with `complete: true`.
Instead, the UI does not show the summary.

CLUE: "Urge removal of line from silly speech (5)"
ANSWER: DRIVE

STEP SEQUENCE:
0. clue_type_identify: Select "Standard" (option 0)
1. standard_definition: Select "Urge" (indices [0]) → teaching → Continue
2. synonym: Select "silly speech" (indices [5,6]) → type "DRIVEL" → teaching → Continue
3. deletion: Select indicator (indices [1,2,3,4]) → type "DRIVE" → teaching → Continue
4. Summary page with complete: true

TEST RESULT:
This test verifies the SERVER-SIDE API flow works correctly.
- If this test PASSES: Bug is in client-side rendering (trainer.js)
- If this test FAILS: Bug is in server-side logic (training_handler.py)

CURRENT STATUS: TEST PASSES
The API correctly returns complete: true after the final Continue.
The bug is likely in trainer.js - either:
1. The "Continue" button is not rendered on teaching phase
2. The Continue button click handler is not working
3. The summary page render is not triggered when complete: true
"""

import sys
import os

# Add parent directory to path so we can import training_handler
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training_handler import (
    start_session,
    get_render,
    handle_input,
    handle_continue,
    _sessions
)


def extract_render(response):
    """Extract the render object from handle_input/handle_continue responses.

    handle_input returns {'correct': bool, 'render': {...}}
    handle_continue and start_session return the render object directly.
    """
    if isinstance(response, dict) and 'render' in response:
        return response['render']
    return response


# Test data - exact copy of times-29453-25a from clues_db.json
TEST_CLUE = {
    "id": "times-29453-25a",
    "clue": {
        "number": "25A",
        "text": "Urge removal of line from silly speech",
        "enumeration": "5",
        "answer": "DRIVE",
        "definition": [{"text": "Urge", "position": "start"}]
    },
    "words": ["Urge", "removal", "of", "line", "from", "silly", "speech"],
    "steps": [
        {
            "type": "standard_definition",
            "expected": {"indices": [0], "text": "Urge"},
            "position": "start"
        },
        {
            "type": "synonym",
            "fodder": {"indices": [5, 6], "text": "silly speech"},
            "result": "DRIVEL",
            "hint": "Drivel is silly, nonsensical speech"
        },
        {
            "type": "deletion",
            "indicator": {"indices": [1, 2, 3, 4], "text": "removal of line from"},
            "fodder": "DRIVEL",
            "deletionType": "specific",
            "deleted": "L",
            "result": "DRIVE",
            "note": "L = line abbreviation"
        }
    ],
    "difficulty": {
        "definition": {"rating": "easy"},
        "wordplay": {"rating": "easy"},
        "overall": "easy",
        "recommendedApproach": "wordplay"
    }
}

CLUE_ID = "times-29453-25a"


def test_25a_reaches_summary_page():
    """
    Simulate completing all steps for clue 25A and verify we get complete: true.
    """
    print("=" * 60)
    print("TEST: times-29453-25a should reach summary page")
    print("=" * 60)

    # Clear any existing session
    if CLUE_ID in _sessions:
        del _sessions[CLUE_ID]

    # Step 1: Start session (starts at clue_type_identify step, index -1)
    print("\n1. Starting session...")
    render = start_session(CLUE_ID, TEST_CLUE)
    print(f"   stepIndex: {render.get('stepIndex')}, phaseId: {render.get('phaseId')}, stepType: {render.get('stepType')}")
    assert render.get("stepType") == "clue_type_identify", f"Expected clue_type_identify, got {render.get('stepType')}"
    assert render.get("stepIndex") == -1, f"Expected stepIndex -1, got {render.get('stepIndex')}"

    # Step 1b: Select clue type "Standard" (option 0)
    print("\n1b. Selecting clue type 'Standard' (option 0)...")
    render = extract_render(handle_input(CLUE_ID, TEST_CLUE, 0))
    print(f"   stepIndex: {render.get('stepIndex')}, phaseId: {render.get('phaseId')}, stepType: {render.get('stepType')}")
    # Should now be at standard_definition step (index 0)
    assert render.get("stepType") == "standard_definition", f"Expected standard_definition, got {render.get('stepType')}"

    # Step 2: Select definition word "Urge" (index 0)
    print("\n2. Selecting definition word 'Urge' (indices [0])...")
    render = extract_render(handle_input(CLUE_ID, TEST_CLUE, [0]))
    print(f"   stepIndex: {render.get('stepIndex')}, phaseId: {render.get('phaseId')}")
    assert render.get("phaseId") == "teaching", f"Expected teaching phase, got {render.get('phaseId')}"

    # Step 3: Continue past definition teaching
    print("\n3. Continue past definition teaching...")
    render = extract_render(handle_continue(CLUE_ID, TEST_CLUE))
    print(f"   stepIndex: {render.get('stepIndex')}, phaseId: {render.get('phaseId')}, stepType: {render.get('stepType')}")
    assert render.get("stepType") == "synonym", f"Expected synonym step, got {render.get('stepType')}"

    # Step 4: Select fodder "silly speech" (indices [5, 6])
    print("\n4. Selecting fodder 'silly speech' (indices [5, 6])...")
    render = extract_render(handle_input(CLUE_ID, TEST_CLUE, [5, 6]))
    print(f"   stepIndex: {render.get('stepIndex')}, phaseId: {render.get('phaseId')}")
    # Should advance to result phase
    assert render.get("phaseId") == "result", f"Expected result phase, got {render.get('phaseId')}"

    # Step 5: Type synonym result "DRIVEL"
    print("\n5. Typing synonym result 'DRIVEL'...")
    render = extract_render(handle_input(CLUE_ID, TEST_CLUE, "DRIVEL"))
    print(f"   stepIndex: {render.get('stepIndex')}, phaseId: {render.get('phaseId')}")
    assert render.get("phaseId") == "teaching", f"Expected teaching phase, got {render.get('phaseId')}"

    # Step 6: Continue past synonym teaching
    print("\n6. Continue past synonym teaching...")
    render = extract_render(handle_continue(CLUE_ID, TEST_CLUE))
    print(f"   stepIndex: {render.get('stepIndex')}, phaseId: {render.get('phaseId')}, stepType: {render.get('stepType')}")
    assert render.get("stepType") == "deletion", f"Expected deletion step, got {render.get('stepType')}"

    # Step 7: Select deletion indicator (indices [1, 2, 3, 4])
    print("\n7. Selecting deletion indicator (indices [1, 2, 3, 4])...")
    render = extract_render(handle_input(CLUE_ID, TEST_CLUE, [1, 2, 3, 4]))
    print(f"   stepIndex: {render.get('stepIndex')}, phaseId: {render.get('phaseId')}")
    assert render.get("phaseId") == "result", f"Expected result phase, got {render.get('phaseId')}"

    # Step 8: Type deletion result "DRIVE"
    print("\n8. Typing deletion result 'DRIVE'...")
    render = extract_render(handle_input(CLUE_ID, TEST_CLUE, "DRIVE"))
    print(f"   stepIndex: {render.get('stepIndex')}, phaseId: {render.get('phaseId')}")
    assert render.get("phaseId") == "teaching", f"Expected teaching phase, got {render.get('phaseId')}"

    # Check state at teaching phase (before Continue)
    print("\n   At deletion teaching phase:")
    print(f"   - button present: {'button' in render}")
    print(f"   - button: {render.get('button')}")
    print(f"   - inputMode: {render.get('inputMode')}")

    # Step 9: Continue past deletion teaching - THIS SHOULD COMPLETE!
    print("\n9. Continue past deletion teaching - SHOULD REACH SUMMARY...")
    render = extract_render(handle_continue(CLUE_ID, TEST_CLUE))

    print(f"\n   RESULT:")
    print(f"   complete: {render.get('complete')}")
    print(f"   stepIndex: {render.get('stepIndex')}")
    print(f"   phaseId: {render.get('phaseId')}")
    print(f"   stepType: {render.get('stepType')}")
    print(f"   answer: {render.get('answer')}")
    print(f"   breakdown: {render.get('breakdown')}")
    print(f"   learnings count: {len(render.get('learnings', []))}")

    # THE KEY ASSERTION - this is where the bug manifests
    if render.get("complete") == True:
        print("\n" + "=" * 60)
        print("PASS: Reached summary page with complete: true")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("FAIL: Did NOT reach summary page!")
        print(f"      Expected complete: true")
        print(f"      Got: {render}")
        print("=" * 60)
        return False


def main():
    success = test_25a_reaches_summary_page()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
