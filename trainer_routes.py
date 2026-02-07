"""
Trainer Routes - Flask Blueprint
=================================

Simplified routes for the new flat-step training engine.

Routes:
    /trainer/start          - Start training session
    /trainer/input          - Submit user input (word taps, text)
    /trainer/ui-state       - Update UI state (hint toggle, word select, answer typing)
    /trainer/reveal         - Reveal full answer
    /trainer/check-answer   - Validate typed answer
"""

import os
import json
import re

from flask import Blueprint, request, jsonify

import training_handler

trainer_bp = Blueprint('trainer', __name__)


# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

CLUES_DB = {}
CLUES_DB_PATH = os.path.join(os.path.dirname(__file__), 'clues_db.json')
CLUES_DB_MTIME = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_quotes(text):
    """Normalize curly quotes to straight quotes for comparison."""
    if not text:
        return text
    text = text.replace('\u2018', "'").replace('\u2019', "'").replace('\u201a', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"').replace('\u201e', '"')
    return text


def _get_clue_text(clue_data):
    """Extract clue text from either old or new format."""
    clue_field = clue_data.get('clue', '')
    if isinstance(clue_field, dict):
        return clue_field.get('text', '')
    return clue_field


def load_clues_db(force=False):
    """Load the clues database from JSON file."""
    global CLUES_DB, CLUES_DB_MTIME

    current_mtime = os.path.getmtime(CLUES_DB_PATH)
    if not force and current_mtime == CLUES_DB_MTIME:
        return

    with open(CLUES_DB_PATH, 'r') as f:
        data = json.load(f)

    if 'training_items' not in data:
        raise KeyError(f"clues_db.json missing 'training_items'. Keys: {list(data.keys())}")

    CLUES_DB = data['training_items']
    CLUES_DB_MTIME = current_mtime
    print(f"Loaded {len(CLUES_DB)} clues from clues_db.json (mtime: {current_mtime})")


def maybe_reload_clues_db():
    """Reload clues_db.json if it has changed on disk."""
    current_mtime = os.path.getmtime(CLUES_DB_PATH)
    if current_mtime != CLUES_DB_MTIME:
        print("[Auto-reload] clues_db.json changed, reloading...")
        load_clues_db(force=True)


def _lookup_clue(clue_text, puzzle_number, clue_number, direction):
    """Find a clue in the database. Returns (clue_id, clue_data) or (None, None)."""
    clue_text_normalized = normalize_quotes(clue_text.strip()) if clue_text else ''
    clue_text_no_enum = normalize_quotes(re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', clue_text).strip()) if clue_text else ''

    # Primary: construct ID from puzzle/clue/direction
    if puzzle_number and clue_number and direction:
        dir_suffix = 'a' if direction.lower() == 'across' else 'd'
        expected_id = f'times-{puzzle_number}-{clue_number}{dir_suffix}'
        if expected_id in CLUES_DB:
            candidate = CLUES_DB[expected_id]
            annotation_text = normalize_quotes(_get_clue_text(candidate).strip())
            if annotation_text == clue_text_normalized or annotation_text == clue_text_no_enum:
                return expected_id, candidate
            else:
                return None, None  # Mismatch

    # Fallback: match by text
    for cid, cdata in CLUES_DB.items():
        candidate_text = normalize_quotes(_get_clue_text(cdata).strip())
        if candidate_text == clue_text_normalized or candidate_text == clue_text_no_enum:
            return cid, cdata

    return None, None


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

load_clues_db(force=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@trainer_bp.route('/start', methods=['POST'])
def trainer_start():
    """Start a training session for a clue."""
    maybe_reload_clues_db()
    training_handler.maybe_reload_render_templates()

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_text = data.get('clue_text', '')
    puzzle_number = data.get('puzzle_number')
    clue_number = data.get('clue_number')
    direction = data.get('direction', '')

    try:
        clue_id, clue_data = _lookup_clue(clue_text, puzzle_number, clue_number, direction)

        if not clue_id or not clue_data:
            return jsonify({
                'error': 'Clue not found in trainer database',
                'message': 'This clue has not been annotated for training.',
            }), 404

        render = training_handler.start_session(clue_id, clue_data)
        render['clue_id'] = clue_id
        return jsonify(render)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/input', methods=['POST'])
def trainer_input():
    """Submit user input (word taps or text) for the current step."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    value = data.get('value')

    if not clue_id or clue_id not in CLUES_DB:
        return jsonify({'error': 'Invalid clue_id'}), 400

    try:
        result = training_handler.handle_input(clue_id, CLUES_DB[clue_id], value)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/ui-state', methods=['POST'])
def trainer_ui_state():
    """Update UI state (hint toggle, word selection, answer typing)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    action = data.get('action')

    if not clue_id or clue_id not in CLUES_DB:
        return jsonify({'error': 'Invalid clue_id'}), 400

    try:
        render = training_handler.update_ui_state(clue_id, CLUES_DB[clue_id], action, data)
        return jsonify(render)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/reveal', methods=['POST'])
def trainer_reveal():
    """Reveal the full answer, skipping remaining steps."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')

    if not clue_id or clue_id not in CLUES_DB:
        return jsonify({'error': 'Invalid clue_id'}), 400

    try:
        render = training_handler.reveal_answer(clue_id, CLUES_DB[clue_id])
        return jsonify(render)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/check-answer', methods=['POST'])
def trainer_check_answer():
    """Check if the typed answer is correct."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    answer = data.get('answer', '')

    if not clue_id or clue_id not in CLUES_DB:
        return jsonify({'error': 'Invalid clue_id'}), 400

    try:
        result = training_handler.check_answer(clue_id, CLUES_DB[clue_id], answer)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
