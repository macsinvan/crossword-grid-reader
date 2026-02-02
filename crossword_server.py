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
from puzzle_store import PuzzleStore

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Initialize puzzle store
puzzle_store = PuzzleStore(os.path.join(os.path.dirname(__file__), 'puzzles'))


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
# TRAINER API PROXY
# =============================================================================
# These endpoints proxy requests to the cryptic-trainer backend (port 5001)

import requests

TRAINER_API_BASE = 'http://localhost:5001'


@app.route('/trainer/start', methods=['POST'])
def trainer_start():
    """
    Start a training session for a clue.
    Proxies to cryptic-trainer API.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_text = data.get('clue_text', '')
    enumeration = data.get('enumeration', '')
    cross_letters = data.get('cross_letters', [])

    try:
        # First, try to find the clue in the trainer database
        # Search by clue text
        search_response = requests.get(
            f'{TRAINER_API_BASE}/clues',
            timeout=5
        )

        if search_response.status_code != 200:
            return jsonify({'error': 'Trainer service unavailable'}), 503

        clues = search_response.json()

        # Find matching clue by text (fuzzy match)
        clue_id = None
        for clue in clues:
            clue_data = clue.get('clue', {})
            if clue_data.get('text', '').strip() == clue_text.strip():
                clue_id = clue.get('id')
                break
            # Also check without enumeration
            clue_text_no_enum = re.sub(r'\s*\([\d,\-\s]+\)\s*$', '', clue_text).strip()
            if clue_data.get('text', '').strip() == clue_text_no_enum:
                clue_id = clue.get('id')
                break

        if not clue_id:
            return jsonify({
                'error': 'Clue not found in trainer database',
                'message': 'This clue has not been annotated for training.'
            }), 404

        # Start training session
        start_response = requests.post(
            f'{TRAINER_API_BASE}/api/training/start',
            json={'clue_id': clue_id, 'cross_letters': cross_letters},
            timeout=10
        )

        if start_response.status_code != 200:
            return jsonify({'error': 'Failed to start training session'}), 500

        result = start_response.json()
        result['clue_id'] = clue_id
        return jsonify(result)

    except requests.exceptions.ConnectionError:
        return jsonify({
            'error': 'Cannot connect to trainer service',
            'message': 'Make sure cryptic-trainer server is running on port 5001'
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Trainer service timeout'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/trainer/input', methods=['POST'])
def trainer_input():
    """
    Submit user input to the trainer.
    Proxies to cryptic-trainer API.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')
    value = data.get('value')

    if not clue_id:
        return jsonify({'error': 'Missing clue_id'}), 400

    try:
        response = requests.post(
            f'{TRAINER_API_BASE}/api/training/input',
            json={'clue_id': clue_id, 'value': value},
            timeout=10
        )

        result = response.json()
        result['clue_id'] = clue_id
        return jsonify(result)

    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot connect to trainer service'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/trainer/continue', methods=['POST'])
def trainer_continue():
    """
    Continue to the next step in training.
    Proxies to cryptic-trainer API.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_id = data.get('clue_id')

    if not clue_id:
        return jsonify({'error': 'Missing clue_id'}), 400

    try:
        response = requests.post(
            f'{TRAINER_API_BASE}/api/training/continue',
            json={'clue_id': clue_id},
            timeout=10
        )

        result = response.json()
        result['clue_id'] = clue_id
        return jsonify(result)

    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot connect to trainer service'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Starting Crossword Server...")
    print("Open http://localhost:8080 in your browser")
    app.run(debug=True, port=8080)
