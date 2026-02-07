#!/usr/bin/env python3
"""
Trainer Routes - Flask Blueprint
=================================

All teaching/solver functionality extracted from crossword_server.py.
Registered as Blueprint with url_prefix='/trainer'.

Routes:
    /trainer/start          - Start training session
    /trainer/input          - Submit user input
    /trainer/continue       - Advance to next step
    /trainer/hypothesis     - Submit answer hypothesis
    /trainer/solve-step     - Reveal current step answer
    /trainer/reveal         - Reveal full answer
    /trainer/check-answer   - Validate typed answer
    /trainer/solved-view    - Get solved breakdown
    /trainer/ui-state       - Update UI state
    /trainer/menu-select    - Select menu step
    /trainer/return-menu    - Return to menu
    /trainer/menu-action    - Handle menu interactions
    /trainer/import-puzzle  - Import annotated puzzle
    /trainer/check-puzzle   - Check for annotations
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
CLUES_DB_MTIME = 0  # Last modification time of the file

# Directory containing annotated puzzle files (Times_XXXXX_v2.json)
ANNOTATED_PUZZLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'Times_Puzzle_Import', 'solved')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_quotes(text):
    """Normalize curly quotes to straight quotes for comparison.

    PDFs often contain curly quotes (' ' " ") while annotations use straight quotes (' ").
    This function normalizes both to straight quotes for reliable comparison.
    """
    if not text:
        return text
    # Curly single quotes to straight
    text = text.replace('\u2018', "'")  # LEFT SINGLE QUOTATION MARK
    text = text.replace('\u2019', "'")  # RIGHT SINGLE QUOTATION MARK
    text = text.replace('\u201a', "'")  # SINGLE LOW-9 QUOTATION MARK
    # Curly double quotes to straight
    text = text.replace('\u201c', '"')  # LEFT DOUBLE QUOTATION MARK
    text = text.replace('\u201d', '"')  # RIGHT DOUBLE QUOTATION MARK
    text = text.replace('\u201e', '"')  # DOUBLE LOW-9 QUOTATION MARK
    return text


def validate_clue_annotation(clue_id, clue_data):
    """
    Validate a clue annotation's data structure.
    Returns list of errors (empty if valid).
    """
    errors = []

    # Check required fields
    if not clue_data.get('clue'):
        errors.append(f"{clue_id}: missing 'clue' field")
        return errors

    if not clue_data['clue'].get('text'):
        errors.append(f"{clue_id}: missing 'clue.text' field")

    # Validate step data structure
    steps = clue_data.get('steps', [])
    for i, step in enumerate(steps):
        step_type = step.get('type', 'unknown')

        # Check fodder structure - must be dict, list, or str
        if 'fodder' in step:
            fodder = step['fodder']
            if not isinstance(fodder, (dict, list, str)):
                errors.append(f"{clue_id} step {i} ({step_type}): fodder is {type(fodder).__name__}, expected dict/list/str")

        # Check indicator structure
        if 'indicator' in step:
            indicator = step['indicator']
            if isinstance(indicator, dict) and 'text' not in indicator and 'indices' not in indicator:
                errors.append(f"{clue_id} step {i} ({step_type}): indicator dict missing 'text' or 'indices'")

    return errors


def load_clues_db(force=False):
    """Load the clues database from JSON file and validate.

    Auto-reloads if file has been modified since last load.
    Set force=True to reload regardless of modification time.
    """
    global CLUES_DB, CLUES_DB_MTIME

    current_mtime = os.path.getmtime(CLUES_DB_PATH)  # raises OSError if missing

    # Skip if file hasn't changed (unless forced)
    if not force and current_mtime == CLUES_DB_MTIME:
        return

    with open(CLUES_DB_PATH, 'r') as f:
        data = json.load(f)  # raises JSONDecodeError if malformed

    if 'training_items' not in data:
        raise KeyError(f"clues_db.json missing required 'training_items' key. Keys found: {list(data.keys())}")

    CLUES_DB = data['training_items']
    CLUES_DB_MTIME = current_mtime
    print(f"Loaded {len(CLUES_DB)} clues from clues_db.json (mtime: {current_mtime})")

    # Validate all clues on load
    validation_errors = []
    for clue_id, clue_data in CLUES_DB.items():
        errors = validate_clue_annotation(clue_id, clue_data)
        validation_errors.extend(errors)

    if validation_errors:
        print(f"WARNING: {len(validation_errors)} validation errors found in clues_db.json:")
        for e in validation_errors[:10]:
            print(f"  {e}")
        if len(validation_errors) > 10:
            print(f"  ... and {len(validation_errors) - 10} more")
    else:
        print("All clue annotations validated successfully")


def maybe_reload_clues_db():
    """Check if clues_db.json has been modified and reload if needed."""
    current_mtime = os.path.getmtime(CLUES_DB_PATH)  # raises OSError if file deleted
    if current_mtime != CLUES_DB_MTIME:
        print(f"[Auto-reload] clues_db.json changed, reloading...")
        load_clues_db(force=True)


def find_annotated_puzzle_file(puzzle_number):
    """
    Find the annotated puzzle file for a given puzzle number.
    Returns the file path if found, None otherwise.
    """
    if not os.path.exists(ANNOTATED_PUZZLES_DIR):
        return None

    # Look for Times_XXXXX_v2.json format
    filename = f'Times_{puzzle_number}_v2.json'
    filepath = os.path.join(ANNOTATED_PUZZLES_DIR, filename)

    if os.path.exists(filepath):
        return filepath

    return None


def load_annotated_puzzle(puzzle_number):
    """
    Load the annotated puzzle data from file.
    Returns the puzzle data dict or None if file doesn't exist.
    Raises on corrupt/unreadable files.
    """
    filepath = find_annotated_puzzle_file(puzzle_number)
    if not filepath:
        return None

    with open(filepath, 'r') as f:
        data = json.load(f)  # raises JSONDecodeError if corrupt
    print(f"Loaded annotated puzzle from {filepath}")
    return data


def import_puzzle_to_trainer(puzzle_number):
    """
    Import an annotated puzzle into the local clues database.
    Returns (success, message, mismatches) tuple.
    Validates data structure before import.
    """
    global CLUES_DB
    puzzle_data = load_annotated_puzzle(puzzle_number)
    if not puzzle_data:
        return False, f'No annotated puzzle file found for puzzle {puzzle_number}', []

    try:
        saved = 0
        skipped = 0
        mismatches = []
        validation_errors = []

        for clue_id, clue_data in puzzle_data.items():
            # Validate data structure first
            errors = validate_clue_annotation(clue_id, clue_data)
            if errors:
                validation_errors.extend(errors)
                print(f"VALIDATION ERROR: {clue_id}")
                for e in errors:
                    print(f"  {e}")
                continue
            if clue_id in CLUES_DB:
                # Check for text mismatch when clue already exists
                existing_text = CLUES_DB[clue_id].get('clue', {}).get('text', '')
                new_text = clue_data.get('clue', {}).get('text', '')
                if existing_text != new_text:
                    mismatches.append({
                        'clue_id': clue_id,
                        'existing_text': existing_text,
                        'new_text': new_text
                    })
                    print(f"WARNING: Text mismatch for {clue_id}")
                    print(f"  Existing: {existing_text}")
                    print(f"  New:      {new_text}")
                skipped += 1
            else:
                CLUES_DB[clue_id] = clue_data
                saved += 1

        message = f"Imported {saved} clues, skipped {skipped}"
        if validation_errors:
            message += f" ({len(validation_errors)} validation errors)"
        if mismatches:
            message += f" ({len(mismatches)} text mismatches)"

        # Return failure if there were validation errors
        if validation_errors:
            return False, message + "\n" + "\n".join(validation_errors), mismatches

        return True, message, mismatches
    except Exception as e:
        return False, str(e), []


# ---------------------------------------------------------------------------
# Startup — load clues database
# ---------------------------------------------------------------------------

load_clues_db(force=True)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@trainer_bp.route('/import-puzzle', methods=['POST'])
def trainer_import_puzzle():
    """
    Import an annotated puzzle into the trainer database.
    This loads the puzzle from Times_Puzzle_Import/solved/ directory.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    puzzle_number = data.get('puzzle_number')
    if not puzzle_number:
        return jsonify({'error': 'Missing puzzle_number'}), 400

    success, message, mismatches = import_puzzle_to_trainer(puzzle_number)

    if success:
        result = {'success': True, 'message': message}
        if mismatches:
            result['mismatches'] = mismatches
            result['warning'] = f'{len(mismatches)} clue text mismatches detected - annotations may be for wrong clues'
        return jsonify(result)
    else:
        return jsonify({'success': False, 'error': message}), 400


@trainer_bp.route('/check-puzzle', methods=['GET'])
def trainer_check_puzzle():
    """
    Check if annotated data exists for a puzzle.
    """
    puzzle_number = request.args.get('puzzle_number')
    if not puzzle_number:
        return jsonify({'error': 'Missing puzzle_number'}), 400

    filepath = find_annotated_puzzle_file(puzzle_number)
    has_annotations = filepath is not None

    return jsonify({
        'puzzle_number': puzzle_number,
        'has_annotations': has_annotations,
        'filepath': filepath if has_annotations else None
    })


@trainer_bp.route('/start', methods=['POST'])
def trainer_start():
    """
    Start a training session for a clue.
    Uses local training_handler (no proxy).
    """
    # Auto-reload data files if changed
    maybe_reload_clues_db()
    training_handler.maybe_reload_render_templates()

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_text = data.get('clue_text', '')
    puzzle_number = data.get('puzzle_number')
    clue_number = data.get('clue_number')
    direction = data.get('direction', '')
    cross_letters = data.get('cross_letters', [])
    enumeration = data.get('enumeration', '')

    try:
        # Debug: log what we received
        print(f"[trainer_start] puzzle_number={puzzle_number}, clue_number={clue_number}, direction={direction}")
        print(f"[trainer_start] clue_text={clue_text[:50]}..." if clue_text else "[trainer_start] clue_text=None")

        # Try to find by constructed ID (most reliable)
        clue_id = None
        clue_data = None

        if puzzle_number and clue_number and direction:
            dir_suffix = 'a' if direction.lower() == 'across' else 'd'
            expected_id = f'times-{puzzle_number}-{clue_number}{dir_suffix}'
            if expected_id in CLUES_DB:
                candidate_data = CLUES_DB[expected_id]
                # Verify clue text matches to detect annotation mismatches
                # Normalize quotes (PDF uses curly, annotations use straight)
                annotation_text = normalize_quotes(candidate_data.get('clue', {}).get('text', '').strip())
                clue_text_normalized = normalize_quotes(clue_text.strip())
                clue_text_no_enum = normalize_quotes(re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', clue_text).strip())
                if annotation_text == clue_text_normalized or annotation_text == clue_text_no_enum:
                    clue_id = expected_id
                    clue_data = candidate_data
                else:
                    # Mismatch detected - annotation has wrong clue for this ID
                    print(f"WARNING: Clue text mismatch for {expected_id}")
                    print(f"  Puzzle has: {clue_text_no_enum}")
                    print(f"  Annotation: {annotation_text}")
                    return jsonify({
                        'error': 'Annotation mismatch detected',
                        'message': f'The annotation for {expected_id} has different clue text. Please fix clues_db.json.',
                        'expected_text': clue_text_no_enum,
                        'annotation_text': annotation_text
                    }), 409  # 409 Conflict

        # Fallback: try matching by text
        if not clue_id:
            clue_text_normalized = normalize_quotes(clue_text.strip())
            clue_text_no_enum = normalize_quotes(re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', clue_text).strip())
            for cid, cdata in CLUES_DB.items():
                trainer_clue_text = normalize_quotes(cdata.get('clue', {}).get('text', '').strip())
                if trainer_clue_text == clue_text_normalized or trainer_clue_text == clue_text_no_enum:
                    clue_id = cid
                    clue_data = cdata
                    break

        # If not found, try to auto-import from annotated files
        if not clue_id and puzzle_number:
            annotated_data = load_annotated_puzzle(puzzle_number)
            if annotated_data:
                success, message, mismatches = import_puzzle_to_trainer(puzzle_number)
                if success and clue_number and direction:
                    dir_suffix = 'a' if direction.lower() == 'across' else 'd'
                    clue_id = f'times-{puzzle_number}-{clue_number}{dir_suffix}'
                    clue_data = CLUES_DB.get(clue_id)
                    # After import, verify the text matches
                    if clue_data:
                        annotation_text = normalize_quotes(clue_data.get('clue', {}).get('text', '').strip())
                        clue_text_normalized = normalize_quotes(clue_text.strip())
                        clue_text_no_enum = normalize_quotes(re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', clue_text).strip())
                        if annotation_text != clue_text_normalized and annotation_text != clue_text_no_enum:
                            print(f"WARNING: Post-import mismatch for {clue_id}")
                            return jsonify({
                                'error': 'Annotation mismatch detected',
                                'message': f'Imported annotation for {clue_id} has different clue text.',
                                'expected_text': clue_text_no_enum,
                                'annotation_text': annotation_text
                            }), 409

        if not clue_id or not clue_data:
            has_annotations = puzzle_number and find_annotated_puzzle_file(puzzle_number) is not None
            return jsonify({
                'error': 'Clue not found in trainer database',
                'message': 'This clue has not been annotated for training.',
                'has_annotations': has_annotations
            }), 404

        # Start training session using local handler (store cross_letters and enumeration in session)
        enum = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        training_handler.start_session(clue_id, clue_data, cross_letters, enum)
        render = training_handler.get_render(clue_id, clue_data)

        result = render
        result['clue_id'] = clue_id
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/input', methods=['POST'])
def trainer_input():
    """
    Submit user input to the trainer.
    Uses local training_handler (no proxy).
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    value = data.get('value')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')

    if not clue_id:
        return jsonify({'error': 'Missing clue_id'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        result = training_handler.handle_input(clue_id, clue_data, value)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/continue', methods=['POST'])
def trainer_continue():
    """
    Continue to the next step in training.
    Uses local training_handler (no proxy).
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')

    if not clue_id:
        return jsonify({'error': 'Missing clue_id'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        result = training_handler.handle_continue(clue_id, clue_data)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/hypothesis', methods=['POST'])
def trainer_hypothesis():
    """
    Submit an answer hypothesis from the answer boxes.
    If correct, marks answer_known=True in the session.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    answer = data.get('answer')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')

    if not clue_id:
        return jsonify({'error': 'Missing clue_id'}), 400
    if not answer:
        return jsonify({'error': 'Missing answer'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        result = training_handler.handle_hypothesis(clue_id, clue_data, answer)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/solve-step', methods=['POST'])
def trainer_solve_step():
    """
    Reveal the answer for the current step and advance to the next phase.
    Used when user gives up on a step.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')
    if not clue_id:
        return jsonify({'error': 'clue_id required'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        result = training_handler.solve_step(clue_id, clue_data)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/reveal', methods=['POST'])
def trainer_reveal():
    """
    Reveal the full answer and show the summary/teaching step.
    Used when user gives up entirely.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')
    if not clue_id:
        return jsonify({'error': 'clue_id required'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        # Skip to final teaching step and get render
        result = training_handler.reveal_answer(clue_id, clue_data)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/check-answer', methods=['POST'])
def trainer_check_answer():
    """
    Validate user's typed answer. If correct, return solved view.
    If incorrect, return error for client feedback.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    user_answer = data.get('answer', '')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')

    if not clue_id:
        return jsonify({'error': 'Missing clue_id'}), 400
    if not user_answer:
        return jsonify({'success': False, 'error': 'No answer entered'}), 200

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        expected = clue_data.get('clue', {}).get('answer', '').upper().replace(' ', '')
        if user_answer.upper().replace(' ', '') != expected:
            return jsonify({'success': False, 'error': 'Incorrect answer'})

        # Correct — return solved view
        result = training_handler.get_solved_view(clue_id, clue_data)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/solved-view', methods=['POST'])
def trainer_solved_view():
    """
    Get the solved view for a clue - shows full breakdown immediately.
    No step-by-step interaction, just the final summary.
    """
    # Auto-reload data files if changed
    maybe_reload_clues_db()
    training_handler.maybe_reload_render_templates()

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')
    if not clue_id:
        return jsonify({'error': 'clue_id required'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        # Get solved view from training handler
        result = training_handler.get_solved_view(clue_id, clue_data)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/ui-state', methods=['POST'])
def trainer_ui_state():
    """
    Update UI state (server-driven, client is dumb).
    Handles: select_word, type_answer, type_step, toggle_hint
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    action = data.get('action')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')

    if not clue_id:
        return jsonify({'error': 'Missing clue_id'}), 400
    if not action:
        return jsonify({'error': 'Missing action'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        result = training_handler.update_ui_state(clue_id, clue_data, action, data)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/menu-select', methods=['POST'])
def trainer_menu_select():
    """Select a step from the menu."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    step_index = data.get('step_index')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')

    if clue_id is None:
        return jsonify({'error': 'Missing clue_id'}), 400
    if step_index is None:
        return jsonify({'error': 'Missing step_index'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        result = training_handler.handle_menu_selection(clue_id, clue_data, step_index)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/return-menu', methods=['POST'])
def trainer_return_menu():
    """Return to menu from any step."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    cross_letters = data.get('crossLetters', [])
    enumeration = data.get('enumeration', '')

    if not clue_id:
        return jsonify({'error': 'Missing clue_id'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        result = training_handler.return_to_menu(clue_id, clue_data)
        result['clue_id'] = clue_id
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trainer_bp.route('/menu-action', methods=['POST'])
def trainer_menu_action():
    """Handle step menu user interactions (word clicks, assembly checks, fallback buttons)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    action = data.get('action')

    if not clue_id:
        return jsonify({'error': 'Missing clue_id'}), 400
    if not action:
        return jsonify({'error': 'Missing action'}), 400

    try:
        clue_data = CLUES_DB.get(clue_id)
        if not clue_data:
            return jsonify({'error': 'Clue not found'}), 404

        result = training_handler.handle_menu_action(clue_id, clue_data, action, data)
        if 'mode' in result:
            # Success - full menu render returned
            result['clue_id'] = clue_id
            result['crossLetters'] = data.get('crossLetters', [])
            result['enumeration'] = data.get('enumeration', '') or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
