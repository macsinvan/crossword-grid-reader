#!/usr/bin/env python3
"""
Backup puzzle training data from Supabase to a JSON file.

Dumps the current Supabase training metadata for a puzzle into
backups/{puzzle_number}.json. Commit the file to git for version history.

Usage:
    python3 backup_puzzle.py --puzzle 29453
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from puzzle_store_supabase import PuzzleStoreSupabase


def backup_puzzle(puzzle_number):
    """Backup a puzzle's training data from Supabase to backups/{puzzle_number}.json.

    Returns the number of clues backed up, or -1 on error.
    """
    store = PuzzleStoreSupabase()
    all_items = store.get_training_clues()

    # Filter to target puzzle
    puzzle_items = {k: v for k, v in all_items.items() if f'-{puzzle_number}-' in k}

    if not puzzle_items:
        print(f"ERROR: No training data found for puzzle #{puzzle_number}")
        return -1

    # Write to backups directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backups_dir = os.path.join(script_dir, 'backups')
    os.makedirs(backups_dir, exist_ok=True)

    backup_path = os.path.join(backups_dir, f'{puzzle_number}.json')
    with open(backup_path, 'w') as f:
        json.dump({"training_items": puzzle_items}, f, indent=2)

    print(f"Backed up {len(puzzle_items)} clues to backups/{puzzle_number}.json")
    return len(puzzle_items)


def main():
    if '--puzzle' not in sys.argv:
        print("Usage: python3 backup_puzzle.py --puzzle 29453")
        return 1

    idx = sys.argv.index('--puzzle')
    if idx + 1 >= len(sys.argv):
        print("ERROR: --puzzle requires a puzzle number")
        return 1

    puzzle_number = sys.argv[idx + 1]
    result = backup_puzzle(puzzle_number)
    return 0 if result > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
