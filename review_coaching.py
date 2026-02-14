#!/usr/bin/env python3
"""
Assembly Coaching Review Tool
==============================

Renders the full assembly step output for clues as the student would see it.
Use this to review coaching paragraphs, transform prompts, and hints together
for consistency before approving.

Usage:
    python3 review_coaching.py                          # Review all clues
    python3 review_coaching.py --clue times-29463-11a   # Review one clue
    python3 review_coaching.py --puzzle 29463            # Review one puzzle
    python3 review_coaching.py --server http://127.0.0.1:8080

Requires: a running crossword_server.py instance.
Dependencies: stdlib only (urllib, json).
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error

# Reuse constants from shared module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from training_constants import DEPENDENT_TRANSFORM_TYPES

DEFAULT_SERVER = "http://127.0.0.1:8080"


# ---------------------------------------------------------------------------
# HTTP helpers (same as test_regression.py)
# ---------------------------------------------------------------------------

def api_get(server, path):
    url = f"{server}/trainer{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post(server, path, payload):
    url = f"{server}/trainer{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8"))
        return e.code, body


def _session(render):
    return render.get("session")


# ---------------------------------------------------------------------------
# Build clue test data (same logic as test_regression.py)
# ---------------------------------------------------------------------------

def build_clue_data(clue_id, metadata):
    """Build minimal data needed to walk to assembly."""
    parts = clue_id.split("-")
    puzzle_number = parts[1]
    suffix = parts[2]
    match = re.match(r'^(\d+)([ad])$', suffix)
    if not match:
        raise ValueError(f"Cannot parse clue_id '{clue_id}'")
    clue_number = match.group(1)
    direction = "across" if match.group(2) == "a" else "down"

    steps_meta = metadata.get("steps", [])
    step_values = []
    transform_types = {}  # index → type from metadata
    for step in steps_meta:
        step_type = step["type"]
        if step_type == "assembly":
            step_values.append({"type": "assembly", "inputMode": "assembly"})
            for i, t in enumerate(step.get("transforms", [])):
                transform_types[i] = t.get("type", "?")
        elif step_type in ("definition", "indicator", "outer_word", "inner_word", "fodder",
                           "multi_definition", "abbreviation_scan"):
            step_values.append({"type": step_type, "inputMode": "tap_words", "value": step["indices"]})
        elif step_type == "wordplay_type":
            step_values.append({"type": step_type, "inputMode": "multiple_choice", "value": step["expected"]})
        else:
            step_values.append({"type": step_type, "inputMode": "unknown", "value": None})

    return {
        "id": clue_id,
        "puzzle_number": puzzle_number,
        "clue_number": clue_number,
        "direction": direction,
        "answer": metadata.get("answer", ""),
        "enumeration": metadata.get("enumeration", ""),
        "words": metadata.get("words", []),
        "steps": step_values,
        "transform_types": transform_types,
    }


# ---------------------------------------------------------------------------
# Walk to assembly step
# ---------------------------------------------------------------------------

def walk_to_assembly(server, clue):
    """Complete all pre-assembly steps, return render at assembly."""
    status, body = api_post(server, "/start", {
        "puzzle_number": clue["puzzle_number"],
        "clue_number": clue["clue_number"],
        "direction": clue["direction"],
    })
    if status != 200:
        raise RuntimeError(f"Start failed ({status}): {body}")
    render = body
    clue_id = render["clue_id"]

    for step in clue["steps"]:
        if step["inputMode"] == "assembly":
            break
        payload = {"clue_id": clue_id, "session": _session(render), "value": step["value"]}
        status, body = api_post(server, "/input", payload)
        if status != 200:
            raise RuntimeError(f"Step {step['type']} failed ({status}): {body}")
        render = body["render"]

    return clue_id, render


# ---------------------------------------------------------------------------
# Print assembly coaching output
# ---------------------------------------------------------------------------

def print_assembly(clue_id, clue_data, render):
    """Print the full assembly step as the student sees it."""
    words = render.get("words", [])
    answer = render.get("answer", "")
    enumeration = render.get("enumeration", "")
    clue_text = " ".join(words)

    # Parse clue number + direction for display
    parts = clue_id.split("-")
    suffix = parts[2]
    match = re.match(r'^(\d+)([ad])$', suffix)
    num = match.group(1)
    dir_letter = match.group(2).upper()

    print(f"\n{'=' * 70}")
    print(f"{num}{dir_letter} {answer} — \"{clue_text}\" ({enumeration})")
    print(f"{'=' * 70}")

    current = render.get("currentStep")
    if not current or current.get("type") != "assembly":
        print("  [Not at assembly step — may have auto-completed]")
        return

    ad = current.get("assemblyData", {})

    # Coaching paragraph (stored in definitionLine)
    definition_line = ad.get("definitionLine", "")
    indicator_line = ad.get("indicatorLine", "")
    fail_message = ad.get("failMessage", "")
    transforms = ad.get("transforms", [])

    if transforms:
        # Complex clue — definition line, indicator line, fail message, then transforms
        print(f"\n  [Definition line]")
        print(f"    {definition_line}")

        if indicator_line:
            print(f"\n  [Indicator line]")
            print(f"    {indicator_line}")

        if fail_message:
            print(f"\n  [Fail message]")
            print(f"    {fail_message}")

        transform_types = clue_data.get("transform_types", {})
        for t in transforms:
            role = t.get("role", "?")
            t_idx = t.get("index", -1)
            t_type = transform_types.get(t_idx, "?")
            word = t.get("clueWord", "?")
            n = t.get("letterCount", "?")
            prompt = t.get("prompt", "(no prompt)")
            hint = t.get("hint", "")

            print(f"\n  [Transform: {t_type} — '{word}' → {n} letters, role: {role}]")
            print(f"    Prompt: {prompt}")
            if hint:
                print(f"    Hint:   {hint}")

        print(f"\n  [Check phase]")
        print(f"    Now combine them — type the full answer:")
    else:
        # Simple coaching profile — transforms hidden, coaching paragraph only
        print(f"\n  [Coaching — simple profile, transforms hidden]")
        print(f"    {definition_line}")
        print(f"\n  [No visible transforms — student sees letter boxes only]")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Review assembly coaching text for clues")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="Server URL")
    parser.add_argument("--clue", help="Single clue ID (e.g. times-29463-11a)")
    parser.add_argument("--puzzle", help="Puzzle number (e.g. 29463)")
    args = parser.parse_args()

    # Fetch all clues with metadata
    all_data = api_get(args.server, "/clue-ids?full=1")
    clues_raw = all_data.get("clues", {})

    # Filter
    if args.clue:
        if args.clue not in clues_raw:
            print(f"Clue '{args.clue}' not found. Available: {list(clues_raw.keys())[:5]}...")
            sys.exit(1)
        clue_ids = [args.clue]
    elif args.puzzle:
        clue_ids = [cid for cid in clues_raw if f"-{args.puzzle}-" in cid]
        if not clue_ids:
            print(f"No clues found for puzzle {args.puzzle}")
            sys.exit(1)
    else:
        clue_ids = sorted(clues_raw.keys())

    # Sort by puzzle then by clue number
    def sort_key(cid):
        parts = cid.split("-")
        puzzle = int(parts[1])
        suffix = parts[2]
        m = re.match(r'^(\d+)([ad])$', suffix)
        num = int(m.group(1)) if m else 0
        d = 0 if m and m.group(2) == "a" else 1
        return (puzzle, d, num)

    clue_ids.sort(key=sort_key)

    print(f"Reviewing {len(clue_ids)} clue(s)...\n")

    errors = []
    for cid in clue_ids:
        try:
            clue = build_clue_data(cid, clues_raw[cid])
            _, render = walk_to_assembly(args.server, clue)
            print_assembly(cid, clue, render)
        except Exception as e:
            errors.append((cid, str(e)))
            print(f"\n  ERROR for {cid}: {e}\n")

    # Summary
    print(f"\n{'=' * 70}")
    print(f"Reviewed: {len(clue_ids)} clues, Errors: {len(errors)}")
    if errors:
        print("\nFailed clues:")
        for cid, err in errors:
            print(f"  {cid}: {err}")


if __name__ == "__main__":
    main()
