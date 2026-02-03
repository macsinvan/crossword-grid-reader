#!/usr/bin/env python3
"""
Crossword Web Server
====================

Web UI for the crossword processor. Allows uploading PDF puzzles,
stores them by series, and provides an interactive solving interface.

Usage:
    python crossword_server.py

Then open http://localhost:8080 in your browser.
"""

import os
import json
import re
import tempfile
import shutil
from pathlib import Path

from flask import Flask, render_template, request, jsonify
import yaml

from crossword_processor import CrosswordGridProcessor
from pdf_processor import process_times_pdf

# Use Supabase if configured, otherwise fall back to file-based storage
try:
    from puzzle_store_supabase import get_puzzle_store
    puzzle_store = get_puzzle_store()
    print(f"Using puzzle store: {type(puzzle_store).__name__}")
except Exception as e:
    print(f"Supabase not available ({e}), using file-based storage")
    from puzzle_store import PuzzleStore
    puzzle_store = PuzzleStore(os.path.join(os.path.dirname(__file__), 'puzzles'))

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload


def convert_times_json_to_yaml_format(times_data, puzzle_number=None):
    """
    Convert Times puzzle JSON format to the YAML format expected by CrosswordGridProcessor.
    """
    across_clues = []
    down_clues = []

    if puzzle_number is None:
        for key in times_data.keys():
            match = re.search(r'times-(\d+)', key)
            if match:
                puzzle_number = int(match.group(1))
                break

    for key, value in times_data.items():
        clue_info = value.get('clue', {})
        clue_number_str = clue_info.get('number', '')

        match = re.match(r'(\d+)([AD])', clue_number_str.upper())
        if not match:
            continue

        number = int(match.group(1))
        direction = match.group(2)

        clue_text = clue_info.get('text', '')
        enumeration = clue_info.get('enumeration', '')
        if enumeration:
            clue_text = f"{clue_text} ({enumeration})"

        clue_entry = {
            'number': number,
            'clue': clue_text,
            'answer': clue_info.get('answer', '').upper()
        }

        if direction == 'A':
            across_clues.append(clue_entry)
        else:
            down_clues.append(clue_entry)

    across_clues.sort(key=lambda x: x['number'])
    down_clues.sort(key=lambda x: x['number'])

    return {
        'publication': 'The Times',
        'series': 'Times Cryptic',
        'number': puzzle_number or 'unknown',
        'grid_size': {
            'rows': 15,
            'cols': 15
        },
        'across': across_clues,
        'down': down_clues
    }


def load_clues_file(filepath):
    """
    Load clues from either YAML or JSON file.
    Returns data in the standard YAML format.
    """
    with open(filepath, 'r') as f:
        content = f.read()

    filename = os.path.basename(filepath).lower()

    if filename.endswith('.json') or content.strip().startswith('{'):
        try:
            data = json.loads(content)
            first_key = next(iter(data.keys()), '')
            if re.match(r'times-\d+-\d+[ad]', first_key.lower()):
                return convert_times_json_to_yaml_format(data)
            return data
        except json.JSONDecodeError:
            pass

    try:
        data = yaml.safe_load(content)
        return data
    except yaml.YAMLError:
        pass

    raise ValueError("Could not parse clues file as JSON or YAML")


def process_pdf_and_store(pdf_file, answers_file=None):
    """
    Process a PDF file and store the puzzle.
    Returns puzzle data and storage info.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, 'crossword.pdf')
        pdf_file.save(pdf_path)

        # Save answers file if provided
        answers_data = None
        if answers_file and answers_file.filename:
            answers_path = os.path.join(tmpdir, 'answers_file')
            answers_file.save(answers_path)
            answers_data = load_clues_file(answers_path)

        # Extract grid image and clues from PDF
        grid_path, clue_data = process_times_pdf(pdf_path, tmpdir)

        # If answers provided, merge them into clue_data
        if answers_data:
            answers_by_num = {}
            for clue in answers_data.get('across', []):
                answers_by_num[('across', clue['number'])] = clue.get('answer', '')
            for clue in answers_data.get('down', []):
                answers_by_num[('down', clue['number'])] = clue.get('answer', '')

            for clue in clue_data.get('across', []):
                if ('across', clue['number']) in answers_by_num:
                    clue['answer'] = answers_by_num[('across', clue['number'])]
            for clue in clue_data.get('down', []):
                if ('down', clue['number']) in answers_by_num:
                    clue['answer'] = answers_by_num[('down', clue['number'])]

        # Write clues as YAML for the processor
        yaml_path = os.path.join(tmpdir, 'clues.yaml')
        with open(yaml_path, 'w') as f:
            yaml.dump(clue_data, f)

        # Process the crossword
        processor = CrosswordGridProcessor(grid_path, yaml_path)
        processor.load_image()
        processor.load_clues()
        processor.find_cell_size()
        processor.extract_grid_structure()

        across_starts, down_starts = processor.find_clue_positions()
        across_lengths, down_lengths = processor.calculate_clue_lengths(
            across_starts, down_starts)

        # Validate with answers if provided
        if answers_data:
            grid, errors = processor.validate_with_answers(across_starts, down_starts)
            validation_warnings = errors if errors else []
        else:
            grid = [['-' for _ in range(processor.cols)] for _ in range(processor.rows)]
            for r in range(processor.rows):
                for c in range(processor.cols):
                    if processor.layout[r][c] == '#':
                        grid[r][c] = '#'
            validation_warnings = []

        # Build cell numbers
        cell_numbers = {}
        all_starts = {}
        all_starts.update(across_starts)
        all_starts.update(down_starts)
        for num, (row, col) in all_starts.items():
            key = f"{row},{col}"
            if key not in cell_numbers or num < cell_numbers[key]:
                cell_numbers[key] = num

        across_clues = [
            {'number': c['number'], 'clue': c['clue']}
            for c in clue_data.get('across', [])
        ]
        down_clues = [
            {'number': c['number'], 'clue': c['clue']}
            for c in clue_data.get('down', [])
        ]

        numbering_across = [
            {'number': num, 'row': row, 'col': col, 'length': across_lengths[num]}
            for num, (row, col) in sorted(across_starts.items())
        ]
        numbering_down = [
            {'number': num, 'row': row, 'col': col, 'length': down_lengths[num]}
            for num, (row, col) in sorted(down_starts.items())
        ]

        puzzle_data = {
            'publication': clue_data.get('publication', ''),
            'series': clue_data.get('series', ''),
            'number': clue_data.get('number', ''),
            'grid': {
                'rows': processor.rows,
                'cols': processor.cols,
                'layout': processor.layout,
                'solution': grid,
                'cellNumbers': cell_numbers
            },
            'numbering': {
                'across': numbering_across,
                'down': numbering_down
            },
            'clues': {
                'across': across_clues,
                'down': down_clues
            }
        }

        # Store the puzzle
        storage_info = puzzle_store.save_puzzle(
            puzzle_data,
            pdf_path=pdf_path,
            answers_data=answers_data
        )

        return puzzle_data, validation_warnings, storage_info


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/status')
def status():
    """Return server status including database backend type."""
    store_type = type(puzzle_store).__name__
    is_supabase = store_type == 'PuzzleStoreSupabase'

    return jsonify({
        'storage_backend': 'supabase' if is_supabase else 'local',
        'store_type': store_type,
        'connected': True
    })


@app.route('/upload', methods=['POST'])
def upload():
    """
    Process uploaded PDF file with optional answers file.
    Stores puzzle and returns puzzle data as JSON.
    """
    if 'pdf_file' not in request.files or not request.files['pdf_file'].filename:
        return jsonify({'error': 'No PDF file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    answers_file = request.files.get('answers_file')

    try:
        puzzle_data, warnings, storage_info = process_pdf_and_store(pdf_file, answers_file)

        return jsonify({
            'success': True,
            'warnings': warnings,
            'puzzle': puzzle_data,
            'storage': storage_info
        })

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/puzzles', methods=['GET'])
def list_puzzles():
    """List all stored puzzles."""
    series = request.args.get('series')
    puzzles = puzzle_store.list_puzzles(series)
    series_list = puzzle_store.list_series()

    return jsonify({
        'puzzles': puzzles,
        'series': series_list
    })


@app.route('/puzzles/<series>/<puzzle_number>', methods=['GET'])
def get_puzzle(series, puzzle_number):
    """Get a stored puzzle."""
    puzzle = puzzle_store.get_puzzle(series, puzzle_number)

    if puzzle is None:
        return jsonify({'error': 'Puzzle not found'}), 404

    return jsonify(puzzle)


@app.route('/puzzles/<series>/<puzzle_number>/answers', methods=['POST'])
def add_answers(series, puzzle_number):
    """Add answers to an existing puzzle."""
    if 'answers_file' not in request.files:
        return jsonify({'error': 'No answers file provided'}), 400

    answers_file = request.files['answers_file']

    with tempfile.TemporaryDirectory() as tmpdir:
        answers_path = os.path.join(tmpdir, 'answers_file')
        answers_file.save(answers_path)

        try:
            answers_data = load_clues_file(answers_path)
            puzzle_store.add_answers(series, puzzle_number, answers_data)

            return jsonify({
                'success': True,
                'message': f'Answers added to {series} #{puzzle_number}'
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/puzzles/<series>/<puzzle_number>', methods=['DELETE'])
def delete_puzzle(series, puzzle_number):
    """Delete a stored puzzle."""
    if puzzle_store.delete_puzzle(series, puzzle_number):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Puzzle not found'}), 404


@app.route('/validate', methods=['POST'])
def validate():
    """
    Validate user answers against solution.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_grid = data.get('userGrid', [])
    solution = data.get('solution', [])

    if not user_grid or not solution:
        return jsonify({'error': 'Missing grid data'}), 400

    incorrect = []
    for r, row in enumerate(user_grid):
        for c, cell in enumerate(row):
            if cell and cell != '#' and cell != solution[r][c]:
                incorrect.append({'row': r, 'col': c})

    return jsonify({
        'incorrect': incorrect,
        'total_errors': len(incorrect)
    })


# =============================================================================
# TRAINER API (Local - No Proxy)
# =============================================================================
# Uses local training_handler.py ported from cryptic-trainer

import training_handler

# Load clues database
CLUES_DB = {}
CLUES_DB_PATH = os.path.join(os.path.dirname(__file__), 'clues_db.json')


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


def load_clues_db():
    """Load the clues database from JSON file and validate."""
    global CLUES_DB
    try:
        with open(CLUES_DB_PATH, 'r') as f:
            data = json.load(f)
            CLUES_DB = data.get('training_items', {})
            print(f"Loaded {len(CLUES_DB)} clues from clues_db.json")

            # Validate all clues on startup
            validation_errors = []
            for clue_id, clue_data in CLUES_DB.items():
                errors = validate_clue_annotation(clue_id, clue_data)
                validation_errors.extend(errors)

            if validation_errors:
                print(f"WARNING: {len(validation_errors)} validation errors found in clues_db.json:")
                for e in validation_errors[:10]:  # Show first 10
                    print(f"  {e}")
                if len(validation_errors) > 10:
                    print(f"  ... and {len(validation_errors) - 10} more")
            else:
                print("All clue annotations validated successfully")
    except Exception as e:
        print(f"Warning: Could not load clues_db.json: {e}")
        CLUES_DB = {}

# Load on startup
load_clues_db()

# Directory containing annotated puzzle files (Times_XXXXX_v2.json)
ANNOTATED_PUZZLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'Times_Puzzle_Import', 'solved')


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
    Returns the puzzle data dict or None if not found.
    """
    filepath = find_annotated_puzzle_file(puzzle_number)
    if not filepath:
        return None

    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


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

        # Optionally persist to file (uncomment if needed)
        # with open(CLUES_DB_PATH, 'w') as f:
        #     json.dump({'version': 3, 'training_items': CLUES_DB}, f, indent=2)

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


def find_clue_in_annotated_data(puzzle_number, clue_number, direction):
    """
    Find a specific clue in the annotated puzzle data.
    Returns the clue entry or None if not found.
    """
    puzzle_data = load_annotated_puzzle(puzzle_number)
    if not puzzle_data:
        return None

    # Build the clue ID format: times-XXXXX-Na or times-XXXXX-Nd
    dir_suffix = 'a' if direction.lower() == 'across' else 'd'
    clue_id = f'times-{puzzle_number}-{clue_number}{dir_suffix}'

    return puzzle_data.get(clue_id)


@app.route('/trainer/import-puzzle', methods=['POST'])
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


@app.route('/trainer/check-puzzle', methods=['GET'])
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


@app.route('/trainer/start', methods=['POST'])
def trainer_start():
    """
    Start a training session for a clue.
    Uses local training_handler (no proxy).
    """
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
        # Try to find by constructed ID (most reliable)
        clue_id = None
        clue_data = None

        if puzzle_number and clue_number and direction:
            dir_suffix = 'a' if direction.lower() == 'across' else 'd'
            expected_id = f'times-{puzzle_number}-{clue_number}{dir_suffix}'
            if expected_id in CLUES_DB:
                candidate_data = CLUES_DB[expected_id]
                # Verify clue text matches to detect annotation mismatches
                annotation_text = candidate_data.get('clue', {}).get('text', '').strip()
                clue_text_no_enum = re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', clue_text).strip()
                if annotation_text == clue_text.strip() or annotation_text == clue_text_no_enum:
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
            clue_text_no_enum = re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', clue_text).strip()
            for cid, cdata in CLUES_DB.items():
                trainer_clue_text = cdata.get('clue', {}).get('text', '').strip()
                if trainer_clue_text == clue_text.strip() or trainer_clue_text == clue_text_no_enum:
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
                        annotation_text = clue_data.get('clue', {}).get('text', '').strip()
                        clue_text_no_enum = re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', clue_text).strip()
                        if annotation_text != clue_text.strip() and annotation_text != clue_text_no_enum:
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

        # Start training session using local handler
        training_handler.start_session(clue_id, clue_data)
        render = training_handler.get_render(clue_id, clue_data)

        result = render
        result['clue_id'] = clue_id
        # Pass through cross_letters and enumeration for dumb client rendering
        result['crossLetters'] = cross_letters
        result['enumeration'] = enumeration or clue_data.get('clue', {}).get('enumeration', '')
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/trainer/input', methods=['POST'])
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


@app.route('/trainer/continue', methods=['POST'])
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


@app.route('/trainer/hypothesis', methods=['POST'])
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


@app.route('/trainer/solve-step', methods=['POST'])
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


@app.route('/trainer/reveal', methods=['POST'])
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


if __name__ == '__main__':
    print("Starting Crossword Server...")
    print("Open http://localhost:8080 in your browser")
    app.run(debug=True, port=8080)
