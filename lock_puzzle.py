#!/usr/bin/env python3
"""
Lock or unlock a puzzle's training data.

When locked, no training metadata or clue data can be modified for the puzzle.
This prevents accidental overwrites of verified training data.

Usage:
    python3 lock_puzzle.py --lock 29453          # Lock puzzle 29453
    python3 lock_puzzle.py --unlock 29453        # Unlock puzzle 29453
    python3 lock_puzzle.py --status 29453        # Check lock status
    python3 lock_puzzle.py --list                # List all locked puzzles
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from puzzle_store_supabase import PuzzleStoreSupabase


def main():
    if '--list' in sys.argv:
        store = PuzzleStoreSupabase()
        result = store.client.table('puzzles').select(
            'publication_id, puzzle_number, training_locked'
        ).eq('training_locked', True).execute()

        if not result.data:
            print("No locked puzzles.")
            return 0

        print("Locked puzzles:")
        for row in result.data:
            print(f"  {row['publication_id']} #{row['puzzle_number']}")
        return 0

    if '--status' in sys.argv:
        idx = sys.argv.index('--status')
        if idx + 1 >= len(sys.argv):
            print("ERROR: --status requires a puzzle number")
            return 1
        puzzle_number = sys.argv[idx + 1]

        store = PuzzleStoreSupabase()
        result = store.client.table('puzzles').select(
            'publication_id, puzzle_number, training_locked'
        ).eq('puzzle_number', puzzle_number).execute()

        if not result.data:
            print(f"ERROR: Puzzle #{puzzle_number} not found")
            return 1

        row = result.data[0]
        locked = row.get('training_locked', False)
        status = "LOCKED" if locked else "UNLOCKED"
        print(f"Puzzle {row['publication_id']} #{puzzle_number}: {status}")
        return 0

    lock_mode = None
    puzzle_number = None

    if '--lock' in sys.argv:
        lock_mode = True
        idx = sys.argv.index('--lock')
        if idx + 1 >= len(sys.argv):
            print("ERROR: --lock requires a puzzle number")
            return 1
        puzzle_number = sys.argv[idx + 1]
    elif '--unlock' in sys.argv:
        lock_mode = False
        idx = sys.argv.index('--unlock')
        if idx + 1 >= len(sys.argv):
            print("ERROR: --unlock requires a puzzle number")
            return 1
        puzzle_number = sys.argv[idx + 1]
    else:
        print("Usage:")
        print("  python3 lock_puzzle.py --lock 29453")
        print("  python3 lock_puzzle.py --unlock 29453")
        print("  python3 lock_puzzle.py --status 29453")
        print("  python3 lock_puzzle.py --list")
        return 1

    store = PuzzleStoreSupabase()

    result = store.client.table('puzzles').update({
        'training_locked': lock_mode
    }).eq('puzzle_number', puzzle_number).execute()

    if not result.data:
        print(f"ERROR: Puzzle #{puzzle_number} not found")
        return 1

    action = "Locked" if lock_mode else "Unlocked"
    pub_id = result.data[0]['publication_id']
    print(f"{action} puzzle {pub_id} #{puzzle_number}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
