#!/usr/bin/env python3
"""
Crossword Web Server
====================

Web UI for the crossword processor. Allows uploading grid images and clues,
then displays an interactive crossword puzzle that can be solved in the browser.

Supports:
- YAML clues format (original format)
- Times puzzle JSON format (from Times_Puzzle_Import/solved)

Usage:
    python crossword_server.py

Then open http://localhost:5000 in your browser.
"""

import os
import json
import re
import tempfile
from pathlib import Path

from flask import Flask, render_template, request, jsonify
import yaml

from crossword_processor import CrosswordGridProcessor

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload


def convert_times_json_to_yaml_format(times_data, puzzle_number=None):
    """
    Convert Times puzzle JSON format to the YAML format expected by CrosswordGridProcessor.

    Times JSON format:
    {
        "times-29453-11a": {
            "clue": {
                "number": "11A",
                "text": "Come by five, do you mean?",
                "enumeration": "5",
                "answer": "VISIT"
            },
            ...
        },
        ...
    }

    Expected YAML format:
    {
        "publication": "The Times",
        "series": "Times Cryptic",
        "number": 29453,
        "grid_size": {"rows": 15, "cols": 15},
        "across": [{"number": 11, "clue": "...", "answer": "VISIT"}, ...],
        "down": [{"number": 1, "clue": "...", "answer": "..."}, ...]
    }
    """
    across_clues = []
    down_clues = []

    # Extract puzzle number from first key if not provided
    if puzzle_number is None:
        for key in times_data.keys():
            match = re.search(r'times-(\d+)', key)
            if match:
                puzzle_number = int(match.group(1))
                break

    for key, value in times_data.items():
        clue_info = value.get('clue', {})
        clue_number_str = clue_info.get('number', '')

        # Parse clue number (e.g., "11A" -> 11, "across")
        match = re.match(r'(\d+)([AD])', clue_number_str.upper())
        if not match:
            continue

        number = int(match.group(1))
        direction = match.group(2)

        # Build clue text with enumeration
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

    # Sort by clue number
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

    # Try to detect format
    filename = os.path.basename(filepath).lower()

    # Try JSON first if it looks like JSON
    if filename.endswith('.json') or content.strip().startswith('{'):
        try:
            data = json.loads(content)
            # Check if it's Times format (has keys like "times-XXXXX-XXx")
            first_key = next(iter(data.keys()), '')
            if re.match(r'times-\d+-\d+[ad]', first_key.lower()):
                return convert_times_json_to_yaml_format(data)
            return data
        except json.JSONDecodeError:
            pass

    # Try YAML
    try:
        data = yaml.safe_load(content)
        return data
    except yaml.YAMLError:
        pass

    raise ValueError("Could not parse clues file as JSON or YAML")


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """
    Process uploaded grid image and clues file.
    Returns puzzle data as JSON.
    """
    if 'grid_image' not in request.files:
        return jsonify({'error': 'No grid image uploaded'}), 400
    if 'clues_yaml' not in request.files:
        return jsonify({'error': 'No clues file uploaded'}), 400

    grid_file = request.files['grid_image']
    clues_file = request.files['clues_yaml']

    if grid_file.filename == '':
        return jsonify({'error': 'No grid image selected'}), 400
    if clues_file.filename == '':
        return jsonify({'error': 'No clues file selected'}), 400

    # Save uploaded files temporarily
    with tempfile.TemporaryDirectory() as tmpdir:
        grid_path = os.path.join(tmpdir, 'grid.png')
        clues_path = os.path.join(tmpdir, 'clues_file')

        grid_file.save(grid_path)
        clues_file.save(clues_path)

        try:
            # Load and convert clues file
            clue_data = load_clues_file(clues_path)

            # Write as YAML for the processor
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

            grid, errors = processor.validate_with_answers(across_starts, down_starts)

            # Store validation warnings but continue with import
            validation_warnings = errors if errors else []

            # Build response JSON
            # Create numbering with cell numbers
            cell_numbers = {}
            all_starts = {}
            all_starts.update(across_starts)
            all_starts.update(down_starts)
            for num, (row, col) in all_starts.items():
                key = f"{row},{col}"
                if key not in cell_numbers or num < cell_numbers[key]:
                    cell_numbers[key] = num

            # Build clues list
            across_clues = [
                {'number': c['number'], 'clue': c['clue']}
                for c in clue_data.get('across', [])
            ]
            down_clues = [
                {'number': c['number'], 'clue': c['clue']}
                for c in clue_data.get('down', [])
            ]

            # Build numbering info
            numbering_across = [
                {'number': num, 'row': row, 'col': col, 'length': across_lengths[num]}
                for num, (row, col) in sorted(across_starts.items())
            ]
            numbering_down = [
                {'number': num, 'row': row, 'col': col, 'length': down_lengths[num]}
                for num, (row, col) in sorted(down_starts.items())
            ]

            response = {
                'success': True,
                'warnings': validation_warnings,
                'puzzle': {
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
            }

            return jsonify(response)

        except Exception as e:
            import traceback
            return jsonify({
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500


@app.route('/validate', methods=['POST'])
def validate():
    """
    Validate user answers against solution.
    Expects JSON with 'userGrid' and 'solution'.
    Returns list of incorrect cells.
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
    app.run(debug=True, port=8080)
