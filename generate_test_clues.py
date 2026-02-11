#!/usr/bin/env python3
"""
Generate test clue entries for puzzle 29147.

Queries the running server + clues_db.json to produce TEST_CLUES_29147 entries
in the same format as existing TEST_CLUES entries in test_regression.py.

Usage:
    python3 generate_test_clues.py > test_clues_29147.py

Requires: a running crossword_server.py instance at http://127.0.0.1:8080
"""

import json
import re
import sys
import urllib.request
import urllib.error

SERVER = "http://127.0.0.1:8080"

# 29147 clues to generate test data for
CLUES_29147 = [
    ("1", "across"),   # 1A ASHAMED
    ("1", "down"),     # 1D ANAEMIC
    ("2", "down"),     # 2D HELEN OF TROY
    ("3", "down"),     # 3D MY WORD
    ("4", "down"),     # 4D DARTH VADER
    ("5", "across"),   # 5A REMAINS
    ("5", "down"),     # 5D ROSE
    ("6", "down"),     # 6D MINISTRY
    ("7", "down"),     # 7D IDA
    ("8", "down"),     # 8D SALFORD
    ("9", "across"),   # 9A AIL
    ("11", "across"),  # 11A MONARCHY
    ("14", "down"),    # 14D STRATEGIST
    ("15", "across"),  # 15A CUFF
    ("16", "across"),  # 16A MASTERMIND
    ("17", "down"),    # 17D SPOTLESS
    ("18", "across"),  # 18A PERIPHERAL
    ("18", "down"),    # 18D PICKLED
    ("19", "across"),  # 19A LIMB
    ("20", "down"),    # 20D BUGBEAR
    ("21", "down"),    # 21D GUNG HO
    ("22", "across"),  # 22A COYOTE
    ("23", "across"),  # 23A DEPUTING
    ("24", "down"),    # 24D ZANY
    ("26", "down"),    # 26D ALB
    ("28", "across"),  # 28A DEBUSSY
    ("29", "across"),  # 29A TO ORDER
]


def api_post(path, payload):
    url = f"{SERVER}/trainer{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def start_session(clue_number, direction):
    status, body = api_post("/start", {
        "puzzle_number": "29147",
        "clue_number": clue_number,
        "direction": direction,
    })
    if status != 200:
        return None, f"Start failed ({status}): {body}"
    return body, None


def submit_input(clue_id, value, transform_index=None):
    payload = {"clue_id": clue_id, "value": value}
    if transform_index is not None:
        payload["transform_index"] = transform_index
    status, body = api_post("/input", payload)
    if status != 200:
        raise RuntimeError(f"Input failed ({status}): {body}")
    return body["correct"], body["render"]


def reveal(clue_id):
    status, body = api_post("/reveal", {"clue_id": clue_id})
    if status != 200:
        raise RuntimeError(f"Reveal failed ({status}): {body}")
    return body


def load_clues_db():
    with open("clues_db.json") as f:
        db = json.load(f)
    return db.get("training_items", db)


def get_metadata(clues_db, clue_id):
    return clues_db.get(clue_id)


def discover_step_values(render, clue_id, metadata):
    """Walk through the clue using reveal, then extract step values from metadata."""
    steps_meta = metadata.get("steps", [])
    step_values = []

    for step in steps_meta:
        step_type = step["type"]

        if step_type == "assembly":
            # Get transforms from metadata
            transforms = step.get("transforms", [])
            transform_entries = []
            for i, t in enumerate(transforms):
                transform_entries.append({
                    "index": i,
                    "value": t["result"]
                })
            step_values.append({
                "type": "assembly",
                "inputMode": "assembly",
                "transforms": transform_entries,
            })
        elif step_type in ("definition", "indicator", "outer_word", "inner_word", "fodder"):
            step_values.append({
                "type": step_type,
                "inputMode": "tap_words",
                "value": step["indices"],
            })
        elif step_type == "wordplay_type":
            step_values.append({
                "type": step_type,
                "inputMode": "multiple_choice",
                "value": step["expected"],
            })
        else:
            step_values.append({
                "type": step_type,
                "inputMode": "unknown",
                "value": None,
            })

    return step_values


def get_wrong_value_step0(metadata, render):
    """Find indices that are NOT the definition step indices."""
    definition_step = metadata["steps"][0]
    def_indices = set(definition_step["indices"])
    words = metadata.get("words", [])
    # Pick indices that aren't in the definition
    wrong = []
    for i in range(len(words)):
        if i not in def_indices:
            wrong.append(i)
            if len(wrong) >= 2:
                break
    # If we couldn't find 2 different indices, just use first non-def index
    if not wrong:
        wrong = [0] if 0 not in def_indices else [1]
    return wrong


def get_indicator_info(metadata):
    """Extract indicator_types and has_indicator_steps from metadata."""
    indicator_types = []
    has_indicator_steps = False
    for step in metadata.get("steps", []):
        if step["type"] == "indicator":
            has_indicator_steps = True
            indicator_types.append(step.get("indicator_type", ""))
    return has_indicator_steps, indicator_types


def get_assembly_info(metadata):
    """Extract assembly transform info from metadata."""
    DEPENDENT_TYPES = {"reversal", "deletion", "anagram", "container"}
    for step in metadata.get("steps", []):
        if step["type"] == "assembly":
            transforms = step.get("transforms", [])
            num = len(transforms)
            explicit = step.get("explicit", False)
            dependent_indices = []
            for i, t in enumerate(transforms):
                if t.get("type") in DEPENDENT_TYPES:
                    dependent_indices.append(i)
            return num, explicit, dependent_indices
    return 0, False, []


def compute_answer_groups(enumeration):
    """Same logic as training_handler.py get_state()."""
    groups = []
    for part in re.split(r'[,\s]+', enumeration):
        if part:
            total = sum(int(n) for n in part.split('-') if n.isdigit())
            if total > 0:
                groups.append(total)
    return groups


def is_container_clue(metadata):
    """Check if clue has container transform in assembly."""
    for step in metadata.get("steps", []):
        if step["type"] == "assembly":
            for t in step.get("transforms", []):
                if t.get("type") == "container":
                    return True
    return False


def format_value(val):
    """Format a Python value for source output."""
    if isinstance(val, str):
        # Use double quotes, escape internal quotes
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        # Handle special unicode
        result = f'"{escaped}"'
        return result
    elif isinstance(val, bool):
        return "True" if val else "False"
    elif isinstance(val, list):
        if not val:
            return "[]"
        items = [format_value(v) for v in val]
        if all(isinstance(v, (int, float)) for v in val) and len(val) <= 8:
            return f"[{', '.join(items)}]"
        return f"[{', '.join(items)}]"
    elif isinstance(val, dict):
        items = [f'"{k}": {format_value(v)}' for k, v in val.items()]
        return "{" + ", ".join(items) + "}"
    elif isinstance(val, int):
        return str(val)
    elif val is None:
        return "None"
    return repr(val)


def generate_clue_entry(clue_number, direction, clues_db):
    """Generate a test clue dict for one clue."""
    clue_id = f"times-29147-{clue_number}{direction[0]}"

    render, err = start_session(clue_number, direction)
    if err:
        print(f"  SKIP {clue_id}: {err}", file=sys.stderr)
        return None

    answer = render["answer"]
    words = render["words"]
    enumeration = render["enumeration"]
    answer_groups = render["answerGroups"]
    step_types = [s["type"] for s in render["steps"]]

    # Get clue text from the render
    # The clue text comes from metadata — construct from words + enumeration
    metadata = get_metadata(clues_db, clue_id)
    if not metadata:
        print(f"  SKIP {clue_id}: not in clues_db.json", file=sys.stderr)
        return None

    clue_text = metadata.get("clue", "")
    step_values = discover_step_values(render, render["clue_id"], metadata)
    wrong_value = get_wrong_value_step0(metadata, render)
    has_indicator_steps, indicator_types = get_indicator_info(metadata)
    num_transforms, explicit, dependent_indices = get_assembly_info(metadata)
    is_container = is_container_clue(metadata)

    entry = {
        "id": clue_id,
        "clue_text": clue_text,
        "puzzle_number": "29147",
        "clue_number": clue_number,
        "direction": direction,
        "answer": answer,
        "steps": step_values,
        "has_indicator_steps": has_indicator_steps,
        "indicator_types": indicator_types,
        "assembly_explicit": explicit,
        "num_assembly_transforms": num_transforms,
        "dependent_transform_indices": dependent_indices,
        "wrong_value_step0": wrong_value,
        "enumeration": enumeration,
        "expected_answer_groups": answer_groups,
        "expected_words": words,
        "expected_step_types": step_types,
    }

    if is_container:
        entry["is_container"] = True

    return entry


def print_entry(entry, idx, total):
    """Print one test clue entry as Python source."""
    d_char = 'A' if entry['direction'] == 'across' else 'D'
    label = f"{entry['clue_number']}{d_char} {entry['answer']}"

    print(f"    # {idx}. {label}")
    print(f"    {{")
    print(f'        "id": {format_value(entry["id"])},')
    print(f'        "clue_text": {format_value(entry["clue_text"])},')
    print(f'        "puzzle_number": "29147",')
    print(f'        "clue_number": {format_value(entry["clue_number"])},')
    print(f'        "direction": {format_value(entry["direction"])},')
    print(f'        "answer": {format_value(entry["answer"])},')

    # Steps
    print(f'        "steps": [')
    for step in entry["steps"]:
        if step["type"] == "assembly":
            transforms_str = ", ".join(
                f'{{"index": {t["index"]}, "value": {format_value(t["value"])}}}'
                for t in step["transforms"]
            )
            print(f'            {{"type": "assembly", "inputMode": "assembly",')
            print(f'             "transforms": [{transforms_str}]}},')
        else:
            print(f'            {{"type": {format_value(step["type"])}, '
                  f'"inputMode": {format_value(step["inputMode"])}, '
                  f'"value": {format_value(step["value"])}}},')
    print(f'        ],')

    print(f'        "has_indicator_steps": {format_value(entry["has_indicator_steps"])},')
    print(f'        "indicator_types": {format_value(entry["indicator_types"])},')
    print(f'        "assembly_explicit": {format_value(entry["assembly_explicit"])},')
    print(f'        "num_assembly_transforms": {entry["num_assembly_transforms"]},')
    print(f'        "dependent_transform_indices": {format_value(entry["dependent_transform_indices"])},')
    print(f'        "wrong_value_step0": {format_value(entry["wrong_value_step0"])},')

    if entry.get("is_container"):
        print(f'        "is_container": True,')

    print(f'        "enumeration": {format_value(entry["enumeration"])},')
    print(f'        "expected_answer_groups": {format_value(entry["expected_answer_groups"])},')
    print(f'        "expected_words": {format_value(entry["expected_words"])},')
    print(f'        "expected_step_types": {format_value(entry["expected_step_types"])},')

    comma = "," if idx < total else ""
    print(f"    }}{comma}")
    print()


def main():
    clues_db = load_clues_db()

    # Test server connectivity
    try:
        req = urllib.request.Request(f"{SERVER}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception as e:
        print(f"Cannot connect to server at {SERVER}: {e}", file=sys.stderr)
        print("Make sure crossword_server.py is running.", file=sys.stderr)
        sys.exit(1)

    entries = []
    for clue_number, direction in CLUES_29147:
        entry = generate_clue_entry(clue_number, direction, clues_db)
        if entry:
            entries.append(entry)

    if not entries:
        print("No entries generated!", file=sys.stderr)
        sys.exit(1)

    # Print as Python source
    print("# Puzzle 29147 test clues — auto-generated by generate_test_clues.py")
    print(f"# {len(entries)} clues")
    print()
    print("TEST_CLUES_29147 = [")
    for i, entry in enumerate(entries, 1):
        print_entry(entry, i, len(entries))
    print("]")

    print(f"\n# Generated {len(entries)} test clue entries", file=sys.stderr)


if __name__ == "__main__":
    main()
