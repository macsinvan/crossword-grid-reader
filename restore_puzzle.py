#!/usr/bin/env python3
"""
Restore puzzle training data from a backup JSON file to Supabase.

Reads backups/{puzzle_number}.json and uploads each clue's training
metadata back to Supabase. The puzzle must be unlocked first.

Usage:
    python3 restore_puzzle.py --puzzle 29453
    python3 restore_puzzle.py --puzzle 29453 --dry-run
"""

import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from puzzle_store_supabase import PuzzleStoreSupabase
from upload_training_metadata import parse_training_id, extract_metadata


def main():
    dry_run = '--dry-run' in sys.argv

    if '--puzzle' not in sys.argv:
        print("Usage: python3 restore_puzzle.py --puzzle 29453")
        print("       python3 restore_puzzle.py --puzzle 29453 --dry-run")
        return 1

    idx = sys.argv.index('--puzzle')
    if idx + 1 >= len(sys.argv):
        print("ERROR: --puzzle requires a puzzle number")
        return 1

    puzzle_number = sys.argv[idx + 1]

    # Load backup file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backup_path = os.path.join(script_dir, 'backups', f'{puzzle_number}.json')

    if not os.path.exists(backup_path):
        print(f"ERROR: No backup found at backups/{puzzle_number}.json")
        return 1

    with open(backup_path, 'r') as f:
        data = json.load(f)

    training_items = data.get('training_items', {})
    if not training_items:
        print(f"ERROR: Backup file is empty")
        return 1

    print(f"Loaded {len(training_items)} clues from backups/{puzzle_number}.json")

    if dry_run:
        print("\n=== DRY RUN — no changes will be written ===\n")

    # Connect to Supabase
    store = PuzzleStoreSupabase()

    # Pre-flight lock check
    check_result = store.client.table('puzzles').select(
        'training_locked'
    ).eq('puzzle_number', puzzle_number).execute()
    if check_result.data and check_result.data[0].get('training_locked'):
        print(f"ERROR: Puzzle #{puzzle_number} is locked. Unlock first with:")
        print(f"  python3 lock_puzzle.py --unlock {puzzle_number}")
        return 1

    success = 0
    failed = 0
    errors = []

    for item_id, item in training_items.items():
        try:
            # No validation — backup data comes from Supabase (already validated).
            # The DB clue text includes the enumeration which doesn't match the
            # words array, so validation would always fail on restored data.
            publication, pn, clue_number, direction = parse_training_id(item_id)
            metadata = extract_metadata(item)

            dir_label = f"{clue_number}{'A' if direction == 'across' else 'D'}"

            if dry_run:
                step_count = len(metadata.get('steps', []))
                print(f"  {dir_label}: {len(metadata)} fields, {step_count} steps")
            else:
                store.save_training_metadata(
                    series=publication,
                    puzzle_number=pn,
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
    print(f"Restored: {success}")
    print(f"Failed:   {failed}")

    if errors:
        print(f"\nErrors:")
        for err in errors:
            print(f"  - {err}")

    if dry_run:
        print(f"\nDry run complete. Run without --dry-run to restore.")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
