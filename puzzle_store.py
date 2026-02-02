#!/usr/bin/env python3
"""
Puzzle Storage Manager
======================

Stores and retrieves crossword puzzles organized by series (folder).

Storage structure:
    puzzles/
    ├── Times Cryptic/
    │   ├── 29453/
    │   │   ├── puzzle.json    # Puzzle data (grid, clues, numbering)
    │   │   ├── original.pdf   # Original PDF file
    │   │   └── answers.json   # Optional answers file
    │   └── 29454/
    │       └── ...
    └── Times Quick Cryptic/
        └── ...
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime


class PuzzleStore:
    def __init__(self, base_path='puzzles'):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)

    def _get_puzzle_dir(self, series, puzzle_number):
        """Get the directory path for a specific puzzle."""
        # Sanitize series name for filesystem
        safe_series = "".join(c for c in series if c.isalnum() or c in ' -_').strip()
        if not safe_series:
            safe_series = "Unknown"
        return self.base_path / safe_series / str(puzzle_number)

    def save_puzzle(self, puzzle_data, pdf_path=None, answers_data=None):
        """
        Save a puzzle to storage.

        Args:
            puzzle_data: Dict with puzzle info (from server response)
            pdf_path: Optional path to original PDF to copy
            answers_data: Optional dict with answers

        Returns:
            Dict with storage info
        """
        series = puzzle_data.get('series', '') or puzzle_data.get('publication', 'Unknown')
        puzzle_number = puzzle_data.get('number', 'unknown')

        puzzle_dir = self._get_puzzle_dir(series, puzzle_number)
        puzzle_dir.mkdir(parents=True, exist_ok=True)

        # Save puzzle data
        puzzle_file = puzzle_dir / 'puzzle.json'
        save_data = {
            'puzzle': puzzle_data,
            'imported_at': datetime.now().isoformat(),
            'has_answers': answers_data is not None
        }
        with open(puzzle_file, 'w') as f:
            json.dump(save_data, f, indent=2)

        # Copy original PDF if provided
        if pdf_path and os.path.exists(pdf_path):
            shutil.copy2(pdf_path, puzzle_dir / 'original.pdf')

        # Save answers if provided
        if answers_data:
            answers_file = puzzle_dir / 'answers.json'
            with open(answers_file, 'w') as f:
                json.dump(answers_data, f, indent=2)

        return {
            'series': series,
            'number': puzzle_number,
            'path': str(puzzle_dir)
        }

    def add_answers(self, series, puzzle_number, answers_data):
        """
        Add or update answers for an existing puzzle.

        Args:
            series: Puzzle series name
            puzzle_number: Puzzle number
            answers_data: Dict with answers

        Returns:
            True if successful, raises error otherwise
        """
        puzzle_dir = self._get_puzzle_dir(series, puzzle_number)

        if not puzzle_dir.exists():
            raise ValueError(f"Puzzle not found: {series} #{puzzle_number}")

        # Save answers
        answers_file = puzzle_dir / 'answers.json'
        with open(answers_file, 'w') as f:
            json.dump(answers_data, f, indent=2)

        # Update puzzle.json to mark has_answers
        puzzle_file = puzzle_dir / 'puzzle.json'
        if puzzle_file.exists():
            with open(puzzle_file, 'r') as f:
                data = json.load(f)
            data['has_answers'] = True
            with open(puzzle_file, 'w') as f:
                json.dump(data, f, indent=2)

        return True

    def get_puzzle(self, series, puzzle_number):
        """
        Retrieve a puzzle from storage.

        Returns:
            Dict with puzzle data and answers (if available)
        """
        puzzle_dir = self._get_puzzle_dir(series, puzzle_number)

        if not puzzle_dir.exists():
            return None

        result = {}

        # Load puzzle data
        puzzle_file = puzzle_dir / 'puzzle.json'
        if puzzle_file.exists():
            with open(puzzle_file, 'r') as f:
                result = json.load(f)

        # Load answers if available
        answers_file = puzzle_dir / 'answers.json'
        if answers_file.exists():
            with open(answers_file, 'r') as f:
                result['answers'] = json.load(f)

        return result

    def list_series(self):
        """
        List all puzzle series (folders).

        Returns:
            List of series names
        """
        series = []
        for item in self.base_path.iterdir():
            if item.is_dir():
                series.append(item.name)
        return sorted(series)

    def list_puzzles(self, series=None):
        """
        List all puzzles, optionally filtered by series.

        Returns:
            List of dicts with puzzle info
        """
        puzzles = []

        if series:
            series_dirs = [self.base_path / series]
        else:
            series_dirs = [d for d in self.base_path.iterdir() if d.is_dir()]

        for series_dir in series_dirs:
            if not series_dir.exists():
                continue

            series_name = series_dir.name

            for puzzle_dir in series_dir.iterdir():
                if not puzzle_dir.is_dir():
                    continue

                puzzle_file = puzzle_dir / 'puzzle.json'
                if not puzzle_file.exists():
                    continue

                with open(puzzle_file, 'r') as f:
                    data = json.load(f)

                puzzle_info = {
                    'series': series_name,
                    'number': puzzle_dir.name,
                    'date': data.get('puzzle', {}).get('date'),
                    'imported_at': data.get('imported_at'),
                    'has_answers': data.get('has_answers', False),
                    'publication': data.get('puzzle', {}).get('publication', ''),
                }
                puzzles.append(puzzle_info)

        # Sort by series, then by number (descending)
        puzzles.sort(key=lambda p: (p['series'], -int(p['number']) if p['number'].isdigit() else 0))

        return puzzles

    def delete_puzzle(self, series, puzzle_number):
        """Delete a puzzle from storage."""
        puzzle_dir = self._get_puzzle_dir(series, puzzle_number)

        if puzzle_dir.exists():
            shutil.rmtree(puzzle_dir)
            return True
        return False
