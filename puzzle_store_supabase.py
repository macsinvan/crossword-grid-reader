#!/usr/bin/env python3
"""
Puzzle Storage Manager - Supabase Backend
==========================================

Stores and retrieves crossword puzzles using Supabase PostgreSQL.
Maintains same API as file-based PuzzleStore for compatibility.

Tables:
    publications - Times, Guardian, etc.
    puzzles - The primary entity (grid + metadata)
    clues - Belong to puzzles
    user_progress - Per-puzzle progress tracking
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

# Load environment variables — search multiple locations for .env
# (worktrees don't share the main repo's .env)
_script_dir = os.path.dirname(os.path.abspath(__file__))

def _find_dotenv():
    """Find .env file: local dir, then main git repo root."""
    # 1. Standard: same directory as this script
    local_env = os.path.join(_script_dir, '.env')
    if os.path.isfile(local_env):
        return local_env
    # 2. Git worktree: find the main repo and check there
    try:
        main_tree = subprocess.check_output(
            ['git', 'worktree', 'list', '--porcelain'],
            cwd=_script_dir, stderr=subprocess.DEVNULL
        ).decode()
        for line in main_tree.splitlines():
            if line.startswith('worktree '):
                candidate = os.path.join(line.split(' ', 1)[1], '.env')
                if os.path.isfile(candidate):
                    return candidate
    except Exception:
        pass
    return None

_env_path = _find_dotenv()
if _env_path:
    load_dotenv(_env_path)
    print(f"Loaded .env from {_env_path}")
else:
    raise FileNotFoundError(
        f".env file not found in {_script_dir} or any git worktree root. "
        "Create a .env with SUPABASE_URL and SUPABASE_ANON_KEY."
    )

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("Warning: supabase package not installed. Run: pip install supabase")


class PuzzleStoreSupabase:
    """Supabase-backed puzzle storage with same API as file-based PuzzleStore."""

    def __init__(self):
        if not SUPABASE_AVAILABLE:
            raise ImportError("supabase package required. Run: pip install supabase")

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment")

        self.client: Client = create_client(url, key)

    def _map_series_to_publication(self, series: str) -> str:
        """Map series name to publication ID."""
        series_lower = series.lower()
        if 'times' in series_lower and 'quick' not in series_lower:
            return 'times'
        elif 'guardian' in series_lower:
            return 'guardian'
        elif 'telegraph' in series_lower:
            return 'telegraph'
        elif 'express' in series_lower:
            return 'express'
        else:
            return 'times'  # Default

    def _check_training_lock(self, publication_id: str, puzzle_number: str) -> None:
        """Check if a puzzle's training data is locked. Raises ValueError if locked."""
        result = self.client.table('puzzles').select('training_locked').eq(
            'publication_id', publication_id
        ).eq('puzzle_number', str(puzzle_number)).execute()

        if not result.data:
            return  # Puzzle doesn't exist yet — can't be locked

        if result.data[0].get('training_locked'):
            raise ValueError(
                f"Puzzle {publication_id} #{puzzle_number} is locked. "
                f"Training data cannot be modified. "
                f"Use lock_puzzle.py --unlock to remove the lock if needed."
            )

    def save_puzzle(self, puzzle_data: Dict, pdf_path: str = None, answers_data: Dict = None) -> Dict:
        """
        Save a puzzle to Supabase.

        Args:
            puzzle_data: Dict with puzzle info (grid, clues, metadata)
            pdf_path: Ignored (no file storage in Supabase)
            answers_data: Optional dict with answers

        Returns:
            Dict with storage info
        """
        series = puzzle_data.get('series') or puzzle_data.get('publication')
        if not series:
            raise ValueError("puzzle_data must contain 'series' or 'publication'")
        puzzle_number = puzzle_data.get('number')
        if puzzle_number is None:
            raise ValueError("puzzle_data must contain 'number'")
        puzzle_number = str(puzzle_number)
        publication_id = self._map_series_to_publication(series)
        self._check_training_lock(publication_id, puzzle_number)

        # Extract grid info
        grid = puzzle_data.get('grid')
        if not grid:
            raise ValueError("puzzle_data must contain 'grid'")
        grid_layout = grid.get('layout')
        if not grid_layout:
            raise ValueError("puzzle_data.grid must contain 'layout'")
        grid_size = grid.get('size', len(grid_layout))

        # Insert or update puzzle
        puzzle_record = {
            'publication_id': publication_id,
            'puzzle_number': puzzle_number,
            'title': puzzle_data.get('title'),
            'date': puzzle_data.get('date'),
            'grid_layout': grid_layout,
            'grid_size': grid_size,
        }

        # Upsert puzzle
        result = self.client.table('puzzles').upsert(
            puzzle_record,
            on_conflict='publication_id,puzzle_number'
        ).execute()

        if not result.data:
            raise Exception("Failed to save puzzle")

        puzzle_id = result.data[0]['id']

        # Save clues
        clues_data = puzzle_data.get('clues', {})

        # Get numbering from puzzle_data.numbering (across/down structure)
        # or from grid.numbering (flat list structure)
        numbering_data = puzzle_data.get('numbering', {})
        grid_numbering = grid.get('numbering', [])

        # Build clue position map from numbering
        clue_positions = {}

        # Handle structured numbering (across/down lists with row/col)
        if numbering_data:
            for num_info in numbering_data.get('across', []):
                num = num_info.get('number')
                row = num_info.get('row')
                col = num_info.get('col')
                clue_positions[f"{num}across"] = (row, col)
            for num_info in numbering_data.get('down', []):
                num = num_info.get('number')
                row = num_info.get('row')
                col = num_info.get('col')
                clue_positions[f"{num}down"] = (row, col)
        # Handle flat numbering list (from grid.numbering)
        elif grid_numbering:
            for num_info in grid_numbering:
                num = num_info.get('number')
                row = num_info.get('row')
                col = num_info.get('col')
                if num_info.get('across'):
                    clue_positions[f"{num}across"] = (row, col)
                if num_info.get('down'):
                    clue_positions[f"{num}down"] = (row, col)

        # Delete existing clues for this puzzle
        self.client.table('clues').delete().eq('puzzle_id', puzzle_id).execute()

        # Insert clues
        clue_records = []
        for direction in ['across', 'down']:
            for clue in clues_data.get(direction, []):
                clue_num = clue.get('number')
                pos_key = f"{clue_num}{direction}"
                if pos_key not in clue_positions:
                    raise ValueError(f"No grid position found for clue {clue_num} {direction}. Available: {list(clue_positions.keys())}")
                row, col = clue_positions[pos_key]

                # Get answer if available
                answer = None
                if answers_data:
                    for ans in answers_data.get(direction, []):
                        if ans.get('number') == clue_num:
                            answer = ans.get('answer')
                            break

                clue_records.append({
                    'puzzle_id': puzzle_id,
                    'number': clue_num,
                    'direction': direction,
                    'text': clue.get('clue', ''),
                    'enumeration': clue.get('enumeration', ''),
                    'answer': answer,
                    'start_row': row,
                    'start_col': col,
                })

        if clue_records:
            self.client.table('clues').insert(clue_records).execute()

        return {
            'series': series,
            'number': puzzle_number,
            'id': puzzle_id,
        }

    def add_answers(self, series: str, puzzle_number: str, answers_data: Dict) -> bool:
        """
        Add or update answers for an existing puzzle.
        """
        publication_id = self._map_series_to_publication(series)
        self._check_training_lock(publication_id, puzzle_number)

        # Get puzzle
        result = self.client.table('puzzles').select('id').eq(
            'publication_id', publication_id
        ).eq('puzzle_number', str(puzzle_number)).execute()

        if not result.data:
            raise ValueError(f"Puzzle not found: {series} #{puzzle_number}")

        puzzle_id = result.data[0]['id']

        # Update clues with answers
        for direction in ['across', 'down']:
            for ans in answers_data.get(direction, []):
                self.client.table('clues').update({
                    'answer': ans.get('answer')
                }).eq('puzzle_id', puzzle_id).eq(
                    'number', ans.get('number')
                ).eq('direction', direction).execute()

        return True

    def get_puzzle(self, series: str, puzzle_number: str) -> Optional[Dict]:
        """
        Retrieve a puzzle from Supabase.

        Returns:
            Dict with puzzle data and answers (if available)
        """
        publication_id = self._map_series_to_publication(series)

        # Get puzzle
        result = self.client.table('puzzles').select('*').eq(
            'publication_id', publication_id
        ).eq('puzzle_number', str(puzzle_number)).execute()

        if not result.data:
            return None

        puzzle = result.data[0]
        puzzle_id = puzzle['id']

        # Get clues
        clues_result = self.client.table('clues').select('*').eq(
            'puzzle_id', puzzle_id
        ).order('number').execute()

        # Organize clues by direction
        clues = {'across': [], 'down': []}
        answers = {'across': [], 'down': []}
        has_answers = False

        for clue in clues_result.data or []:
            direction = clue['direction']
            clues[direction].append({
                'number': clue['number'],
                'clue': clue['text'],
                'enumeration': clue['enumeration'],
            })
            if clue['answer']:
                has_answers = True
                answers[direction].append({
                    'number': clue['number'],
                    'answer': clue['answer'],
                })

        # Get grid dimensions
        grid_size = puzzle['grid_size']
        grid_layout = puzzle['grid_layout']
        rows = len(grid_layout) if grid_layout else grid_size
        cols = len(grid_layout[0]) if grid_layout and grid_layout[0] else grid_size

        # Build cellNumbers and numbering by scanning the grid layout
        # A cell gets a number if it's white and starts an across or down word
        cell_numbers = {}
        numbering_across = []
        numbering_down = []
        clue_number = 1

        for r in range(rows):
            for c in range(cols):
                if grid_layout[r][c] == '#':
                    continue  # Black cell

                # Check if this cell starts an across word
                starts_across = (c == 0 or grid_layout[r][c-1] == '#') and \
                               (c < cols - 1 and grid_layout[r][c+1] != '#')

                # Check if this cell starts a down word
                starts_down = (r == 0 or grid_layout[r-1][c] == '#') and \
                             (r < rows - 1 and grid_layout[r+1][c] != '#')

                if starts_across or starts_down:
                    # JavaScript uses 1-indexed "row,col" keys
                    key = f"{r + 1},{c + 1}"
                    cell_numbers[key] = clue_number

                    # Calculate word length and add to numbering
                    if starts_across:
                        # Count across length
                        length = 0
                        cc = c
                        while cc < cols and grid_layout[r][cc] != '#':
                            length += 1
                            cc += 1
                        numbering_across.append({
                            'number': clue_number,
                            'row': r + 1,  # 1-indexed for JS
                            'col': c + 1,
                            'length': length
                        })

                    if starts_down:
                        # Count down length
                        length = 0
                        rr = r
                        while rr < rows and grid_layout[rr][c] != '#':
                            length += 1
                            rr += 1
                        numbering_down.append({
                            'number': clue_number,
                            'row': r + 1,  # 1-indexed for JS
                            'col': c + 1,
                            'length': length
                        })

                    clue_number += 1

        # Build response matching file-based format expected by crossword.js
        response = {
            'puzzle': {
                'series': series,
                'publication': series,
                'number': puzzle['puzzle_number'],
                'date': puzzle['date'],
                'title': puzzle['title'],
                'grid': {
                    'rows': rows,
                    'cols': cols,
                    'layout': grid_layout,
                    'cellNumbers': cell_numbers,
                },
                'numbering': {
                    'across': numbering_across,
                    'down': numbering_down,
                },
                'clues': clues,
            },
            'imported_at': puzzle['created_at'],
            'has_answers': has_answers,
        }

        if has_answers:
            response['answers'] = answers

        return response

    def list_series(self) -> List[str]:
        """
        List all publication names as series.
        """
        result = self.client.table('publications').select('name').execute()
        return sorted([p['name'] for p in result.data or []])

    def list_puzzles(self, series: str = None) -> List[Dict]:
        """
        List all puzzles, optionally filtered by series/publication.
        """
        query = self.client.table('puzzles').select(
            'id, publication_id, puzzle_number, title, date, created_at, publications(name)'
        )

        if series:
            publication_id = self._map_series_to_publication(series)
            query = query.eq('publication_id', publication_id)

        result = query.order('puzzle_number', desc=True).execute()

        puzzles = []
        for p in result.data or []:
            pub_data = p.get('publications')
            if not pub_data or 'name' not in pub_data:
                raise ValueError(f"Puzzle {p['id']} has no linked publication. Check publications table.")
            pub_name = pub_data['name']

            # Check if has answers
            clues_result = self.client.table('clues').select('answer').eq(
                'puzzle_id', p['id']
            ).not_.is_('answer', 'null').limit(1).execute()
            has_answers = bool(clues_result.data)

            puzzles.append({
                'series': pub_name,
                'number': p['puzzle_number'],
                'date': p['date'],
                'imported_at': p['created_at'],
                'has_answers': has_answers,
                'publication': pub_name,
            })

        return puzzles

    def delete_puzzle(self, series: str, puzzle_number: str) -> bool:
        """Delete a puzzle from storage."""
        publication_id = self._map_series_to_publication(series)
        self._check_training_lock(publication_id, puzzle_number)

        result = self.client.table('puzzles').delete().eq(
            'publication_id', publication_id
        ).eq('puzzle_number', str(puzzle_number)).execute()

        return bool(result.data)

    # Training metadata methods

    def get_training_clues(self) -> Dict[str, Dict]:
        """
        Load all clues with training_metadata from Supabase.

        Returns:
            Dict keyed by training item ID (e.g. 'times-29453-11a'),
            with values matching the clues_db.json training_items format.
        """
        # Get all clues that have training metadata, joined with puzzle info
        result = self.client.table('clues').select(
            '*, puzzles!inner(publication_id, puzzle_number)'
        ).not_.is_('training_metadata', 'null').execute()

        items = {}
        for row in result.data or []:
            puzzle_info = row['puzzles']
            pub_id = puzzle_info['publication_id']
            puzzle_num = puzzle_info['puzzle_number']
            clue_num = row['number']
            direction = row['direction']
            dir_suffix = 'a' if direction == 'across' else 'd'

            item_id = f"{pub_id}-{puzzle_num}-{clue_num}{dir_suffix}"

            # Reconstruct the training item format from DB columns + metadata
            metadata = row['training_metadata']
            item = {
                'clue': row['text'],
                'number': f"{clue_num}{'A' if direction == 'across' else 'D'}",
                'enumeration': row['enumeration'],
                'answer': row['answer'],
            }
            # Merge in the training metadata (words, clue_type, difficulty, steps, etc.)
            item.update(metadata)

            items[item_id] = item

        return items

    def save_training_metadata(self, series: str, puzzle_number: str,
                                clue_number: int, direction: str,
                                metadata: Dict) -> bool:
        """
        Save training metadata for a specific clue.

        Args:
            series: Publication series (e.g. 'times')
            puzzle_number: Puzzle number (e.g. '29453')
            clue_number: Clue number (e.g. 11)
            direction: 'across' or 'down'
            metadata: Training metadata dict (words, clue_type, difficulty, steps)
        """
        publication_id = self._map_series_to_publication(series)
        self._check_training_lock(publication_id, puzzle_number)

        # Get puzzle ID
        puzzle_result = self.client.table('puzzles').select('id').eq(
            'publication_id', publication_id
        ).eq('puzzle_number', str(puzzle_number)).execute()

        if not puzzle_result.data:
            raise ValueError(f"Puzzle not found: {series} #{puzzle_number}")

        puzzle_id = puzzle_result.data[0]['id']

        # Update the clue's training_metadata
        result = self.client.table('clues').update({
            'training_metadata': metadata
        }).eq('puzzle_id', puzzle_id).eq(
            'number', clue_number
        ).eq('direction', direction).execute()

        return bool(result.data)

    # Progress tracking methods (new functionality)

    def save_progress(self, session_id: str, puzzle_id: str, grid_state: List[List[str]],
                     selected_cell: Dict = None, direction: str = None) -> Dict:
        """
        Save user progress for a puzzle.
        """
        record = {
            'session_id': session_id,
            'puzzle_id': puzzle_id,
            'grid_state': grid_state,
            'selected_cell': selected_cell,
            'direction': direction,
            'updated_at': datetime.now().isoformat(),
        }

        result = self.client.table('user_progress').upsert(
            record,
            on_conflict='session_id,puzzle_id'
        ).execute()

        return result.data[0] if result.data else None

    def get_progress(self, session_id: str, puzzle_id: str) -> Optional[Dict]:
        """
        Get user progress for a puzzle.
        """
        result = self.client.table('user_progress').select('*').eq(
            'session_id', session_id
        ).eq('puzzle_id', puzzle_id).execute()

        return result.data[0] if result.data else None

    def clear_progress(self, session_id: str, puzzle_id: str) -> bool:
        """
        Clear user progress for a puzzle.
        """
        result = self.client.table('user_progress').delete().eq(
            'session_id', session_id
        ).eq('puzzle_id', puzzle_id).execute()

        return bool(result.data)


# Factory function — Supabase is required
def get_puzzle_store():
    """Get Supabase puzzle store instance. Raises if not configured."""
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise ValueError("SUPABASE_URL not set in environment. Check .env file.")
    return PuzzleStoreSupabase()
