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
from datetime import datetime
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
        series = puzzle_data.get('series', '') or puzzle_data.get('publication', 'Unknown')
        puzzle_number = str(puzzle_data.get('number', 'unknown'))
        publication_id = self._map_series_to_publication(series)

        # Extract grid info
        grid = puzzle_data.get('grid', {})
        grid_layout = grid.get('layout', [])
        grid_size = grid.get('size', len(grid_layout) if grid_layout else 15)

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
        numbering = grid.get('numbering', [])

        # Build clue position map from numbering
        clue_positions = {}
        for num_info in numbering:
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
                row, col = clue_positions.get(pos_key, (0, 0))

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

        # Build numbering from clues
        numbering = []
        seen_numbers = set()
        for clue in clues_result.data or []:
            num = clue['number']
            if num not in seen_numbers:
                seen_numbers.add(num)
                num_info = {
                    'number': num,
                    'row': clue['start_row'],
                    'col': clue['start_col'],
                }
                # Check if this number has across/down
                for c in clues_result.data:
                    if c['number'] == num:
                        num_info[c['direction']] = True
                numbering.append(num_info)

        # Build response matching file-based format
        response = {
            'puzzle': {
                'series': series,
                'publication': series,
                'number': puzzle['puzzle_number'],
                'date': puzzle['date'],
                'title': puzzle['title'],
                'grid': {
                    'size': puzzle['grid_size'],
                    'layout': puzzle['grid_layout'],
                    'numbering': sorted(numbering, key=lambda x: x['number']),
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
            pub_name = p.get('publications', {}).get('name', 'Unknown') if p.get('publications') else 'Unknown'

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

        result = self.client.table('puzzles').delete().eq(
            'publication_id', publication_id
        ).eq('puzzle_number', str(puzzle_number)).execute()

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


# Factory function to get appropriate store
def get_puzzle_store(use_supabase: bool = None):
    """
    Get puzzle store instance.

    Args:
        use_supabase: Force Supabase (True) or file-based (False).
                     If None, auto-detect based on environment.
    """
    if use_supabase is None:
        # Auto-detect: use Supabase if configured
        use_supabase = bool(os.environ.get("SUPABASE_URL"))

    if use_supabase:
        return PuzzleStoreSupabase()
    else:
        from puzzle_store import PuzzleStore
        return PuzzleStore()
