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
import yaml

from crossword_processor import CrosswordGridProcessor
from pdf_processor import process_times_pdf, fix_ocr_errors, validate_words

# Supabase is required — no silent fallback to local storage
from puzzle_store_supabase import get_puzzle_store
puzzle_store = get_puzzle_store()
print(f"Using puzzle store: {type(puzzle_store).__name__}")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

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
    """Normalise clue text for comparison: lowercase, collapse whitespace."""
    return re.sub(r'\s+', ' ', text.strip().lower())


def reconcile_clues(pdf_clues, yaml_data):
    """
    Cross-reference PDF-extracted clues with YAML-provided clues and answers.
    Auto-resolves text differences where possible, flags all differences for review.

    Args:
        pdf_clues: dict with 'across'/'down' lists from process_times_pdf()
        yaml_data: dict with 'across'/'down' lists from load_clues_file()

    Returns:
        (reconciled_clues, reconciliation_log)
        - reconciled_clues: pdf_clues dict with best-guess text and YAML answers merged in
        - reconciliation_log: list of log entry dicts
    """
    log = []

    # Build YAML lookup by (direction, number)
    yaml_lookup = {}
    for direction in ['across', 'down']:
        for clue in yaml_data.get(direction, []):
            yaml_lookup[(direction, clue['number'])] = clue

    # Track which YAML entries were matched
    matched_yaml_keys = set()

    for direction in ['across', 'down']:
        dir_label = 'A' if direction == 'across' else 'D'

        for pdf_clue in pdf_clues.get(direction, []):
            key = (direction, pdf_clue['number'])
            clue_label = f"{pdf_clue['number']}{dir_label}"

            if key not in yaml_lookup:
                log.append({
                    'clue': clue_label,
                    'level': 'warning',
                    'message': f"No YAML entry for {direction} {pdf_clue['number']}",
                })
                continue

            matched_yaml_keys.add(key)
            yaml_clue = yaml_lookup[key]

            # Copy answer from YAML
            pdf_clue['answer'] = yaml_clue.get('answer', '')

            # Compare clue text if YAML provides it
            yaml_text = yaml_clue.get('clue', '')
            if not yaml_text:
                continue

            pdf_text = pdf_clue.get('clue', '')
            pdf_norm = _normalise_clue_text(pdf_text)
            yaml_norm = _normalise_clue_text(yaml_text)

            if pdf_norm == yaml_norm:
                continue  # Texts match — nothing to log

            # Texts differ — try to auto-resolve
            pdf_fixed = fix_ocr_errors(pdf_text)
            yaml_fixed = fix_ocr_errors(yaml_text)

            # If OCR fix makes them match, use the fixed version
            if _normalise_clue_text(pdf_fixed) == _normalise_clue_text(yaml_fixed):
                pdf_clue['clue'] = yaml_fixed
                log.append({
                    'clue': clue_label,
                    'level': 'resolved',
                    'message': f"OCR fix resolved difference — using corrected text",
                    'pdf_text': pdf_text,
                    'yaml_text': yaml_text,
                    'chosen': 'yaml',
                })
                continue

            # Spell-check both — fewer warnings wins
            pdf_warnings = validate_words(pdf_fixed)
            yaml_warnings = validate_words(yaml_fixed)

            if len(pdf_warnings) < len(yaml_warnings):
                pdf_clue['clue'] = pdf_fixed
                log.append({
                    'clue': clue_label,
                    'level': 'resolved',
                    'message': f"PDF text has fewer spelling issues ({len(pdf_warnings)} vs {len(yaml_warnings)})",
                    'pdf_text': pdf_text,
                    'yaml_text': yaml_text,
                    'chosen': 'pdf',
                })
            elif len(yaml_warnings) < len(pdf_warnings):
                pdf_clue['clue'] = yaml_fixed
                log.append({
                    'clue': clue_label,
                    'level': 'resolved',
                    'message': f"YAML text has fewer spelling issues ({len(yaml_warnings)} vs {len(pdf_warnings)})",
                    'pdf_text': pdf_text,
                    'yaml_text': yaml_text,
                    'chosen': 'yaml',
                })
            elif len(pdf_warnings) == 0 and len(yaml_warnings) == 0:
                # Both clean but different — cannot auto-resolve
                log.append({
                    'clue': clue_label,
                    'level': 'error',
                    'message': f"Clue text differs between PDF and YAML — cannot auto-resolve",
                    'pdf_text': pdf_text,
                    'yaml_text': yaml_text,
                })
            else:
                # Both have warnings, tied — prefer YAML (human-typed)
                pdf_clue['clue'] = yaml_fixed
                log.append({
                    'clue': clue_label,
                    'level': 'resolved',
                    'message': f"Both have spelling issues (tied at {len(yaml_warnings)}) — preferring YAML (human-typed)",
                    'pdf_text': pdf_text,
                    'yaml_text': yaml_text,
                    'chosen': 'yaml',
                })

    # Check for YAML entries not in PDF
    for direction in ['across', 'down']:
        dir_label = 'A' if direction == 'across' else 'D'
        for clue in yaml_data.get(direction, []):
            key = (direction, clue['number'])
            if key not in matched_yaml_keys:
                log.append({
                    'clue': f"{clue['number']}{dir_label}",
                    'level': 'warning',
                    'message': f"YAML has {direction} {clue['number']} but PDF does not",
                })

    # Count summary
    for direction in ['across', 'down']:
        pdf_count = len(pdf_clues.get(direction, []))
        yaml_count = len(yaml_data.get(direction, []))
        if pdf_count != yaml_count:
            log.append({
                'clue': '-',
                'level': 'warning',
                'message': f"{direction.title()} clue count mismatch: PDF has {pdf_count}, YAML has {yaml_count}",
            })

    return pdf_clues, log


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
    Returns (puzzle_data, warnings, storage_info, reconciliation_log).
    If reconciliation has unresolved errors, returns early before grid processing.
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

        # Reconcile PDF clues with YAML if provided
        reconciliation_log = []
        if answers_data:
            clue_data, reconciliation_log = reconcile_clues(clue_data, answers_data)

            # Persist reconciliation log
            series = clue_data.get('series', 'unknown')
            number = clue_data.get('number', 'unknown')
            log_path = persist_reconciliation_log(reconciliation_log, series, number)
            print(f"Reconciliation log written to: {log_path}")

            # If there are unresolved errors, stop before grid processing
            has_errors = any(entry['level'] == 'error' for entry in reconciliation_log)
            if has_errors:
                return None, [], None, reconciliation_log

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

        return puzzle_data, validation_warnings, storage_info, reconciliation_log


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
    """Return server directory and git branch for debugging."""
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

    Response includes 'status':
    - 'reconciled': clean import, grid processed and stored
    - 'conflicts': unresolved reconciliation errors, grid NOT processed
    """
    if 'pdf_file' not in request.files or not request.files['pdf_file'].filename:
        return jsonify({'error': 'No PDF file uploaded'}), 400

    pdf_file = request.files['pdf_file']
    answers_file = request.files.get('answers_file')

    try:
        puzzle_data, warnings, storage_info, reconciliation_log = process_pdf_and_store(
            pdf_file, answers_file)

        # If reconciliation stopped due to errors, return conflicts
        if puzzle_data is None:
            return jsonify({
                'success': False,
                'status': 'conflicts',
                'reconciliation_log': reconciliation_log,
            })

        return jsonify({
            'success': True,
            'status': 'reconciled',
            'warnings': warnings,
            'reconciliation_log': reconciliation_log,
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


if __name__ == '__main__':
    print("Starting Crossword Server...")
    print("Open http://localhost:8080 in your browser")
    print("Or from other devices on your network: http://<your-ip>:8080")
    app.run(debug=True, port=8080, host='0.0.0.0',
            extra_files=['render_templates.json'])
