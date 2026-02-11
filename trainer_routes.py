"""
Trainer Routes - Flask Blueprint
=================================

Thin HTTP layer. All business logic lives in training_handler.py.

Routes:
    /trainer/clue-ids       - List all clue IDs with training data
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

@trainer_bp.route('/clue-ids', methods=['GET'])
def trainer_clue_ids():
    """Return all clue IDs with training data in Supabase.
    With ?full=1, returns full metadata for each clue (for test runner).
    """
    if request.args.get('full'):
        all_data = training_handler.list_all_clue_data()
        return jsonify({'clues': all_data})
    clue_ids = training_handler.list_clue_ids()
    return jsonify({'clue_ids': clue_ids})


@trainer_bp.route('/start', methods=['POST'])
def trainer_start():
    """Start a training session for a clue."""
    training_handler.maybe_reload_render_templates()

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    puzzle_number = data.get('puzzle_number')
    clue_number = data.get('clue_number')
    direction = data.get('direction', '')

    try:
        clue_id, clue_data = training_handler.lookup_clue(puzzle_number, clue_number, direction)
    except ValueError as e:
        # Validation errors from lookup_clue
        return jsonify({
            'error': 'Training data has errors',
            'message': 'Training data for this clue has errors and cannot be loaded.',
            'validation_errors': e.args[0] if e.args else [],
        }), 422

    if not clue_id or not clue_data:
        return jsonify({
            'error': 'Clue not found in trainer database',
            'message': 'This clue has not been annotated for training yet.',
        }), 404

    render = training_handler.start_session(clue_id, clue_data)
    render['clue_id'] = clue_id
    return jsonify(render)


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

    transform_index = data.get('transform_index')  # None for non-assembly inputs
    transform_inputs = data.get('transform_inputs')  # Combined check: {tIdx: letters}
    result = training_handler.handle_input(clue_id, clue_data, value=data.get('value'), transform_index=transform_index, transform_inputs=transform_inputs)
    return jsonify(result)


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

    render = training_handler.update_ui_state(clue_id, clue_data, action, data)
    return jsonify(render)


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

    render = training_handler.reveal_answer(clue_id, clue_data)
    return jsonify(render)


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

    result = training_handler.check_answer(clue_id, clue_data, answer)
    return jsonify(result)
