"""
Trainer Routes - Flask Blueprint
=================================

Thin HTTP layer. All business logic lives in training_handler.py.

Routes:
    /trainer/start          - Start training session
    /trainer/input          - Submit user input (word taps, text)
    /trainer/ui-state       - Update UI state (hint toggle, word select, answer typing)
    /trainer/reveal         - Reveal full answer
    /trainer/check-answer   - Validate typed answer
"""

from flask import Blueprint, request, jsonify

import training_handler

trainer_bp = Blueprint('trainer', __name__)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@trainer_bp.route('/start', methods=['POST'])
def trainer_start():
    """Start a training session for a clue."""
    training_handler.maybe_reload_clues_db()
    training_handler.maybe_reload_render_templates()

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    clue_text = data.get('clue_text', '')
    puzzle_number = data.get('puzzle_number')
    clue_number = data.get('clue_number')
    direction = data.get('direction', '')

    try:
        clue_id, clue_data = training_handler.lookup_clue(clue_text, puzzle_number, clue_number, direction)

        if not clue_id or not clue_data:
            # Check if this clue was excluded due to validation errors
            clue_errors = training_handler.get_clue_errors(puzzle_number, clue_number, direction)
            if clue_errors:
                return jsonify({
                    'error': 'Training data has errors',
                    'message': 'Training data for this clue has errors and cannot be loaded.',
                    'validation_errors': clue_errors,
                }), 422
            return jsonify({
                'error': 'Clue not found in trainer database',
                'message': 'This clue has not been annotated for training yet.',
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
    clue_data = training_handler.get_clue_data(clue_id) if clue_id else None

    if not clue_id or not clue_data:
        return jsonify({'error': 'Invalid clue_id'}), 400

    try:
        transform_index = data.get('transform_index')  # None for non-assembly inputs
        result = training_handler.handle_input(clue_id, clue_data, value=data.get('value'), transform_index=transform_index)
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
    clue_data = training_handler.get_clue_data(clue_id) if clue_id else None

    if not clue_id or not clue_data:
        return jsonify({'error': 'Invalid clue_id'}), 400

    try:
        render = training_handler.update_ui_state(clue_id, clue_data, action, data)
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
    clue_data = training_handler.get_clue_data(clue_id) if clue_id else None

    if not clue_id or not clue_data:
        return jsonify({'error': 'Invalid clue_id'}), 400

    try:
        render = training_handler.reveal_answer(clue_id, clue_data)
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
    clue_data = training_handler.get_clue_data(clue_id) if clue_id else None

    if not clue_id or not clue_data:
        return jsonify({'error': 'Invalid clue_id'}), 400

    try:
        result = training_handler.check_answer(clue_id, clue_data, answer)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
