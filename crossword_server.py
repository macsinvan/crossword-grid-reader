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

import json
import os
import re
import tempfile

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import yaml

# Supabase is required — no silent fallback to local storage
from puzzle_store_supabase import get_puzzle_store
puzzle_store = get_puzzle_store()
print(f"Using puzzle store: {type(puzzle_store).__name__}")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Detect production environment — Vercel sets VERCEL=1 automatically
IS_PRODUCTION = bool(os.environ.get("VERCEL"))

# Register trainer Blueprint (all /trainer/* routes)
from trainer_routes import trainer_bp
app.register_blueprint(trainer_bp, url_prefix='/trainer')


def load_clues_file(filepath):
    """
    Load clues from a YAML file.

    Accepts a flat list format where each entry has:
      - number: "1A" or "5D" (direction embedded)
      - text: clue text
      - answer: answer string
      - enumeration: e.g. "7" or "5,3"
      - definition, solve_guide: optional extra fields (preserved)

    Returns data in the standard across/down format:
      { 'across': [{number, clue, answer, enumeration, ...}], 'down': [...] }
    """
    filename = os.path.basename(filepath).lower()

    if not filename.endswith(('.yaml', '.yml')):
        raise ValueError(f"Unsupported clues file format: {filename}. Expected .yaml or .yml")

    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)  # raises YAMLError with details

    # If already in across/down format, return as-is
    if isinstance(data, dict) and ('across' in data or 'down' in data):
        return data

    # Flat list format: split into across/down by parsing number field
    if not isinstance(data, list):
        raise ValueError(f"Unexpected YAML structure: expected a list or dict with across/down keys")

    across = []
    down = []

    for entry in data:
        number_str = str(entry.get('number', ''))
        match = re.match(r'^(\d+)\s*([AaDd])$', number_str)
        if not match:
            raise ValueError(f"Invalid clue number format: '{number_str}'. Expected e.g. '1A' or '5D'")

        num = int(match.group(1))
        direction = match.group(2).upper()

        clue_entry = {
            'number': num,
            'clue': entry.get('text', ''),
            'answer': entry.get('answer', ''),
            'enumeration': entry.get('enumeration', ''),
        }

        # Preserve extra fields
        for key in ('definition', 'solve_guide'):
            if key in entry:
                clue_entry[key] = entry[key]

        if direction == 'A':
            across.append(clue_entry)
        else:
            down.append(clue_entry)

    across.sort(key=lambda x: x['number'])
    down.sort(key=lambda x: x['number'])

    return {'across': across, 'down': down}


def _normalise_clue_text(text):
    """Normalise clue text for comparison: lowercase, collapse whitespace, strip trailing enumeration."""
    text = re.sub(r'\s+', ' ', text.strip().lower())
    # Strip trailing enumeration like (7) or (5,3) or (5-6) or (5- 6) or (2,4,2)
    text = re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', text)
    # Normalise spaces before punctuation: "slap !" → "slap!"
    text = re.sub(r'\s+([!?])', r'\1', text)
    return text


def reconcile_clues(stored_clues, yaml_data):
    """
    Cross-reference stored PDF-extracted clues with YAML-provided clues and answers.
    Auto-resolves text differences where possible, flags all differences for review.

    Lazy-imports OCR utilities to avoid loading heavy dependencies at startup.

    Args:
        stored_clues: dict with 'across'/'down' lists from Supabase,
                      each entry: {number, clue, enumeration}
                      (clue text may include trailing enumeration from PDF OCR)
        yaml_data: dict with 'across'/'down' lists from load_clues_file(),
                   each entry: {number, clue, answer, enumeration}

    Returns:
        reconciliation_log: list of log entry dicts
    """
    from pdf_processor import fix_ocr_errors, validate_words

    log = []

    # Build YAML lookup by (direction, number)
    yaml_lookup = {}
    for direction in ['across', 'down']:
        for clue in yaml_data.get(direction, []):
            yaml_lookup[(direction, clue['number'])] = clue

    # Build stored lookup by (direction, number)
    stored_lookup = {}
    for direction in ['across', 'down']:
        for clue in stored_clues.get(direction, []):
            stored_lookup[(direction, clue['number'])] = clue

    # Track which YAML entries were matched
    matched_yaml_keys = set()

    for direction in ['across', 'down']:
        dir_label = 'A' if direction == 'across' else 'D'

        for stored_clue in stored_clues.get(direction, []):
            key = (direction, stored_clue['number'])
            clue_label = f"{stored_clue['number']}{dir_label}"

            if key not in yaml_lookup:
                log.append({
                    'clue': clue_label,
                    'level': 'warning',
                    'message': f"No YAML entry for {direction} {stored_clue['number']}",
                })
                continue

            matched_yaml_keys.add(key)
            yaml_clue = yaml_lookup[key]

            # Compare clue text if YAML provides it
            yaml_text = yaml_clue.get('clue', '')
            if not yaml_text:
                continue

            stored_text = stored_clue.get('clue', '')
            stored_norm = _normalise_clue_text(stored_text)
            yaml_norm = _normalise_clue_text(yaml_text)

            if stored_norm == yaml_norm:
                continue  # Texts match — nothing to log

            # Texts differ — try to auto-resolve
            stored_fixed = fix_ocr_errors(stored_text)
            yaml_fixed = fix_ocr_errors(yaml_text)

            # If OCR fix makes them match, use the fixed version
            if _normalise_clue_text(stored_fixed) == _normalise_clue_text(yaml_fixed):
                log.append({
                    'clue': clue_label,
                    'level': 'resolved',
                    'message': f"OCR fix resolved difference — using YAML text",
                    'pdf_text': stored_text,
                    'yaml_text': yaml_text,
                    'chosen': 'yaml',
                })
                continue

            # Spell-check both — fewer warnings wins
            stored_warnings = validate_words(stored_fixed)
            yaml_warnings = validate_words(yaml_fixed)

            if len(stored_warnings) < len(yaml_warnings):
                log.append({
                    'clue': clue_label,
                    'level': 'resolved',
                    'message': f"PDF text has fewer spelling issues ({len(stored_warnings)} vs {len(yaml_warnings)})",
                    'pdf_text': stored_text,
                    'yaml_text': yaml_text,
                    'chosen': 'pdf',
                })
            elif len(yaml_warnings) < len(stored_warnings):
                log.append({
                    'clue': clue_label,
                    'level': 'resolved',
                    'message': f"YAML text has fewer spelling issues ({len(yaml_warnings)} vs {len(stored_warnings)})",
                    'pdf_text': stored_text,
                    'yaml_text': yaml_text,
                    'chosen': 'yaml',
                })
            elif len(stored_warnings) == 0 and len(yaml_warnings) == 0:
                # Both clean but different — cannot auto-resolve
                log.append({
                    'clue': clue_label,
                    'level': 'error',
                    'message': f"Clue text differs between PDF and YAML — cannot auto-resolve",
                    'pdf_text': stored_text,
                    'yaml_text': yaml_text,
                })
            else:
                # Both have warnings, tied — prefer YAML (human-typed)
                log.append({
                    'clue': clue_label,
                    'level': 'resolved',
                    'message': f"Both have spelling issues (tied at {len(yaml_warnings)}) — preferring YAML (human-typed)",
                    'pdf_text': stored_text,
                    'yaml_text': yaml_text,
                    'chosen': 'yaml',
                })

    # Check for YAML entries not in stored clues
    for direction in ['across', 'down']:
        dir_label = 'A' if direction == 'across' else 'D'
        for clue in yaml_data.get(direction, []):
            key = (direction, clue['number'])
            if key not in matched_yaml_keys:
                log.append({
                    'clue': f"{clue['number']}{dir_label}",
                    'level': 'warning',
                    'message': f"YAML has {direction} {clue['number']} but stored puzzle does not",
                })

    # Count summary
    for direction in ['across', 'down']:
        stored_count = len(stored_clues.get(direction, []))
        yaml_count = len(yaml_data.get(direction, []))
        if stored_count != yaml_count:
            log.append({
                'clue': '-',
                'level': 'warning',
                'message': f"{direction.title()} clue count mismatch: stored has {stored_count}, YAML has {yaml_count}",
            })

    return log


def persist_reconciliation_log(log, series, puzzle_number):
    """Write reconciliation log to imports/ directory as JSON."""
    imports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'imports')
    os.makedirs(imports_dir, exist_ok=True)

    safe_series = re.sub(r'[^a-zA-Z0-9_-]', '_', str(series))
    safe_number = re.sub(r'[^a-zA-Z0-9_-]', '_', str(puzzle_number))
    filename = f"{safe_series}_{safe_number}_reconciliation.json"
    filepath = os.path.join(imports_dir, filename)

    with open(filepath, 'w') as f:
        json.dump(log, f, indent=2)

    return filepath


def process_pdf_and_store(pdf_file, answers_file=None):
    """
    Process a PDF file and store the puzzle.
    Returns (puzzle_data, warnings, storage_info).
    Answers are added separately via the /answers route (with reconciliation).

    Lazy-imports PDF processing libraries (opencv, pdfplumber, Pillow, numpy)
    so they don't slow down cold starts for non-import requests.
    """
    # Lazy-load heavy PDF dependencies
    from crossword_processor import CrosswordGridProcessor
    from pdf_processor import process_times_pdf

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, 'crossword.pdf')
        pdf_file.save(pdf_path)

        # Save answers file if provided
        answers_data = None
        if answers_file and answers_file.filename:
            safe_name = secure_filename(answers_file.filename)
            if not safe_name:
                return jsonify({'error': 'Invalid filename'}), 400
            answers_path = os.path.join(tmpdir, safe_name)
            answers_file.save(answers_path)
            answers_data = load_clues_file(answers_path)

        # Extract grid image and clues from PDF
        grid_path, clue_data = process_times_pdf(pdf_path, tmpdir)

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
            {'number': c['number'], 'clue': c['clue'], 'enumeration': c.get('enumeration', '')}
            for c in clue_data.get('across', [])
        ]
        down_clues = [
            {'number': c['number'], 'clue': c['clue'], 'enumeration': c.get('enumeration', '')}
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

        # Validate stored clue data against training expectations
        puzzle_number = puzzle_data.get('number', '')
        if puzzle_number:
            stored_items = puzzle_store.get_training_clues()
            puzzle_items = {k: v for k, v in stored_items.items() if f'-{puzzle_number}-' in k}
            if puzzle_items:
                from validate_training import validate_training_item
                for item_id, item in puzzle_items.items():
                    errors, warnings = validate_training_item(item_id, item)
                    for warn in warnings:
                        validation_warnings.append(f"{item_id}: {warn}")
                    for err in errors:
                        validation_warnings.append(f"VALIDATION ERROR {item_id}: {err}")

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


@app.route('/server-info')
def server_info():
    """Return server directory and git branch for debugging. Disabled in production."""
    if IS_PRODUCTION:
        return jsonify({})
    import subprocess
    server_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=server_dir, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        branch = 'unknown'
    return jsonify({'dir': server_dir, 'branch': branch})


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
        puzzle_data, warnings, storage_info = process_pdf_and_store(
            pdf_file, answers_file)

        return jsonify({
            'success': True,
            'warnings': warnings,
            'puzzle': puzzle_data,
            'storage': storage_info
        })

    except Exception as e:
        import traceback
        app.logger.error(f"Upload error: {e}\n{traceback.format_exc()}")
        error_response = {'error': str(e)}
        if not IS_PRODUCTION:
            error_response['traceback'] = traceback.format_exc()
        return jsonify(error_response), 500


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
        safe_name = secure_filename(answers_file.filename)
        if not safe_name:
            return jsonify({'error': 'Invalid filename'}), 400
        answers_path = os.path.join(tmpdir, safe_name)
        answers_file.save(answers_path)

        try:
            answers_data = load_clues_file(answers_path)

            # Fetch stored clues from Supabase for reconciliation
            stored_puzzle = puzzle_store.get_puzzle(series, puzzle_number)
            if not stored_puzzle:
                return jsonify({'error': f'Puzzle not found: {series} #{puzzle_number}'}), 404

            stored_clues = stored_puzzle.get('puzzle', {}).get('clues', {})

            # Reconcile stored PDF clues with YAML
            reconciliation_log = reconcile_clues(stored_clues, answers_data)

            # Persist reconciliation log
            log_path = persist_reconciliation_log(reconciliation_log, series, puzzle_number)
            print(f"Reconciliation log written to: {log_path}")

            # If there are unresolved errors, block the import
            has_errors = any(entry['level'] == 'error' for entry in reconciliation_log)
            if has_errors:
                return jsonify({
                    'success': False,
                    'status': 'conflicts',
                    'reconciliation_log': reconciliation_log,
                })

            # No blocking errors — save answers
            puzzle_store.add_answers(series, puzzle_number, answers_data)

            return jsonify({
                'success': True,
                'status': 'reconciled',
                'message': f'Answers added to {series} #{puzzle_number}',
                'reconciliation_log': reconciliation_log,
            })

        except Exception as e:
            import traceback
            app.logger.error(f"Add answers error: {e}\n{traceback.format_exc()}")
            error_response = {'error': str(e)}
            if not IS_PRODUCTION:
                error_response['traceback'] = traceback.format_exc()
            return jsonify(error_response), 500


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


if __name__ == '__main__':
    print("Starting Crossword Server...")
    print("Open http://localhost:8080 in your browser")
    print("Or from other devices on your network: http://<your-ip>:8080")
    app.run(debug=True, port=8080, host='0.0.0.0',
            extra_files=['render_templates.json'])
