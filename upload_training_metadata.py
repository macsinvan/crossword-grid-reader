#!/usr/bin/env python3
"""
Upload Training Metadata to Supabase
=====================================

Reads clues_db.json and uploads the training metadata for each clue
to the `training_metadata` JSONB column on the `clues` table.

Prerequisites:
    1. Run migration 002_add_training_metadata.sql in Supabase SQL Editor
    2. Puzzle 29453 must already be imported (clues exist in the DB)
    3. .env file with SUPABASE_URL and SUPABASE_ANON_KEY

Usage:
    python3 upload_training_metadata.py --puzzle 29147              # Upload one puzzle
    python3 upload_training_metadata.py --puzzle 29147 --dry-run   # Preview without writing
    python3 upload_training_metadata.py --clue times-29147-1d      # Upload one clue
    python3 upload_training_metadata.py --clue times-29147-1d --dry-run
"""

import json
import re
import sys
import os

# Add script directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from puzzle_store_supabase import PuzzleStoreSupabase
from validate_training import validate_training_item


def parse_training_id(item_id):
    """
    Parse a training item ID into its components.

    'times-29453-11a' -> ('times', '29453', 11, 'across')
    'times-29453-1d'  -> ('times', '29453', 1, 'down')
    """
    match = re.match(r'^(\w+)-(\d+)-(\d+)(a|d)$', item_id)
    if not match:
        raise ValueError(f"Cannot parse training item ID: {item_id}")

    publication = match.group(1)
    puzzle_number = match.group(2)
    clue_number = int(match.group(3))
    direction = 'across' if match.group(4) == 'a' else 'down'

    return publication, puzzle_number, clue_number, direction


def extract_metadata(item):
    """
    Extract the training metadata from a clues_db.json item.

    Returns only the fields that belong in training_metadata
    (excludes fields already stored in the clues table columns).
    """
    # Fields already in clues table columns — do NOT duplicate
    COLUMN_FIELDS = {'id', 'clue', 'number', 'enumeration', 'answer'}

    metadata = {}
    for key, value in item.items():
        if key not in COLUMN_FIELDS:
            metadata[key] = value

    return metadata


def main():
    dry_run = '--dry-run' in sys.argv

    # Require --puzzle or --clue filter — never upload everything
    puzzle_filter = None
    clue_filter = None

    if '--puzzle' in sys.argv:
        idx = sys.argv.index('--puzzle')
        if idx + 1 >= len(sys.argv):
            print("ERROR: --puzzle requires a puzzle number (e.g. --puzzle 29147)")
            return 1
        puzzle_filter = sys.argv[idx + 1]

    if '--clue' in sys.argv:
        idx = sys.argv.index('--clue')
        if idx + 1 >= len(sys.argv):
            print("ERROR: --clue requires a clue ID (e.g. --clue times-29147-1d)")
            return 1
        clue_filter = sys.argv[idx + 1]

    if not puzzle_filter and not clue_filter:
        print("ERROR: You must specify --puzzle or --clue to upload. Bulk upload is disabled.")
        print("  python3 upload_training_metadata.py --puzzle 29147")
        print("  python3 upload_training_metadata.py --clue times-29147-1d")
        return 1

    # Load clues_db.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    clues_db_path = os.path.join(script_dir, 'clues_db.json')

    with open(clues_db_path, 'r') as f:
        data = json.load(f)

    training_items = data.get('training_items', {})

    if clue_filter:
        training_items = {k: v for k, v in training_items.items() if k == clue_filter}
        print(f"Filtered to clue: {clue_filter}")
    elif puzzle_filter:
        training_items = {k: v for k, v in training_items.items() if f'-{puzzle_filter}-' in k}
        print(f"Filtered to {len(training_items)} training items for puzzle {puzzle_filter}")

    if len(training_items) == 0:
        print(f"ERROR: No matching training items found")
        return 1

    if dry_run:
        print("\n=== DRY RUN — no changes will be written ===\n")

    # Connect to Supabase
    store = PuzzleStoreSupabase()

    # Pre-flight: check if the target puzzle is locked
    target_puzzle = puzzle_filter
    if not target_puzzle and clue_filter:
        match = re.match(r'^\w+-(\d+)-\d+[ad]$', clue_filter)
        if match:
            target_puzzle = match.group(1)
    if target_puzzle:
        check_result = store.client.table('puzzles').select(
            'training_locked'
        ).eq('puzzle_number', target_puzzle).execute()
        if check_result.data and check_result.data[0].get('training_locked'):
            print(f"ERROR: Puzzle #{target_puzzle} is locked. Training data cannot be modified.")
            print(f"Use: python3 lock_puzzle.py --unlock {target_puzzle}")
            return 1

    success = 0
    failed = 0
    errors = []

    for item_id, item in training_items.items():
        try:
            # Validate before uploading
            validation_errors, validation_warnings = validate_training_item(item_id, item)

            if validation_warnings:
                for warn in validation_warnings:
                    print(f"  ⚠ {item_id}: {warn}")

            if validation_errors:
                failed += 1
                for err in validation_errors:
                    print(f"  ✗ {item_id}: {err}")
                errors.append(f"{item_id}: {len(validation_errors)} validation error(s)")
                continue

            publication, puzzle_number, clue_number, direction = parse_training_id(item_id)
            metadata = extract_metadata(item)

            dir_label = f"{clue_number}{'A' if direction == 'across' else 'D'}"

            if dry_run:
                keys = list(metadata.keys())
                step_count = len(metadata.get('steps', []))
                print(f"  {dir_label}: {len(keys)} fields, {step_count} steps")
            else:
                store.save_training_metadata(
                    series=publication,
                    puzzle_number=puzzle_number,
                    clue_number=clue_number,
                    direction=direction,
                    metadata=metadata
                )
                print(f"  ✓ {dir_label}")

            success += 1

        except Exception as e:
            failed += 1
            errors.append(f"{item_id}: {e}")
            print(f"  ✗ {item_id}: {e}")

    print(f"\n=== Summary ===")
    print(f"Success: {success}")
    print(f"Failed:  {failed}")

    if errors:
        print(f"\nErrors:")
        for err in errors:
            print(f"  - {err}")

    if dry_run:
        print(f"\nDry run complete. Run without --dry-run to upload.")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
