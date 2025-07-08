import os
import uuid
from flask import render_template, request, jsonify, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename

from app.routes import main_bp
from app.config import UPLOAD_FOLDER, OUTPUT_FOLDER, LANGUAGES, SAMPLE_VOICES
from app.utils import allowed_file
from app.audio import generate_audio
from app.models.routine import add_routine, update_routine, get_routine, list_routines, delete_routine
from app.tasks.tasks import start_task, get_task_status
from app.tts_model.model import get_model_status, start_model_download, is_model_downloaded


@main_bp.route('/')
def index():
    """Render the main page with the list of routines"""
    routines = list_routines()
    return render_template('index.html', languages=LANGUAGES, routines=routines)


@main_bp.route('/routine/new')
def new_routine():
    """Render the page for creating a new routine"""
    return render_template('routine.html', languages=LANGUAGES, sample_voices=SAMPLE_VOICES, routine=None)


@main_bp.route('/routine/<routine_id>')
def edit_routine(routine_id):
    """Render the page for editing an existing routine"""
    routine = get_routine(routine_id)
    if not routine:
        return redirect(url_for('main.index'))
    return render_template('routine.html', languages=LANGUAGES, sample_voices=SAMPLE_VOICES, routine=routine)


@main_bp.route('/generate', methods=['POST'])
def generate():
    """Handle the generation of audio from text"""
    # Get form data
    name = request.form.get('name', f'Routine {uuid.uuid4().hex[:8]}')  # Default name if not provided
    text = request.form.get('text', '')
    language = request.form.get('language', 'en')
    voice_type = request.form.get('voice_type', 'sample')
    routine_id = request.form.get('routine_id', '')  # If regenerating an existing routine
    redirect_to_list = request.form.get('redirect', 'false') == 'true'  # Whether to redirect to list page

    # Validate inputs
    if not text:
        return jsonify({'error': 'Text is required'}), 400

    if language not in LANGUAGES:
        return jsonify({'error': 'Invalid language selected'}), 400

    # Handle voice selection
    voice_path = None
    if voice_type == 'sample':
        voice_id = request.form.get('sample_voice', '')
        if voice_id in SAMPLE_VOICES:
            voice_path = SAMPLE_VOICES[voice_id]['path']
        else:
            return jsonify({'error': 'Invalid sample voice selected'}), 400
    else:  # voice_type == 'upload'
        if 'voice_file' not in request.files:
            return jsonify({'error': 'No voice file uploaded'}), 400

        file = request.files['voice_file']
        if file.filename == '':
            return jsonify({'error': 'No voice file selected'}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4()}_{filename}")
            file.save(temp_path)
            voice_path = temp_path
        else:
            return jsonify({'error': 'Invalid file format'}), 400

    try:
        # Store voice ID if using sample voice
        voice_id = None
        if voice_type == 'sample':
            voice_id = request.form.get('sample_voice', '')

        # Start the background task
        task_id = start_task(
            text=text,
            language=language,
            voice_path=voice_path,
            routine_name=name,
            routine_id=routine_id,
            voice_type=voice_type,
            voice_id=voice_id
        )

        # Return the task ID
        return jsonify({
            'success': True,
            'task_id': task_id,
            'redirect_url': url_for('main.index') if redirect_to_list else None
        })
    except Exception as e:
        # Clean up temporary uploaded file if needed
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            os.remove(voice_path)
        return jsonify({'error': f'Error starting task: {str(e)}'}), 500


@main_bp.route('/download/<filename>')
def download(filename):
    """Handle the download of generated audio files"""
    return send_from_directory(OUTPUT_FOLDER, filename)


@main_bp.route('/routines', methods=['GET'])
def get_routines():
    """Get all routines"""
    routines = list_routines()
    return jsonify(list(routines.values()))


@main_bp.route('/routines/<routine_id>', methods=['GET'])
def get_routine_by_id(routine_id):
    """Get a routine by ID"""
    routine = get_routine(routine_id)
    if not routine:
        return jsonify({'error': 'Routine not found'}), 404
    return jsonify(routine)


@main_bp.route('/routines/<routine_id>', methods=['DELETE'])
def delete_routine_by_id(routine_id):
    """Delete a routine by ID"""
    success = delete_routine(routine_id)
    if not success:
        return jsonify({'error': 'Routine not found'}), 404
    return jsonify({'success': True})


@main_bp.route('/task/<task_id>', methods=['GET'])
def check_task_status(task_id):
    """Check the status of a background task"""
    task_status = get_task_status(task_id)

    if task_status is None:
        return jsonify({'error': 'Task not found'}), 404

    response = {
        'status': task_status['status']
    }

    # Include result or error if available
    if task_status['status'] == 'completed' and task_status['result']:
        response['result'] = task_status['result']

        # Add redirect URL if needed
        redirect_to_list = request.args.get('redirect', 'false') == 'true'
        if redirect_to_list:
            response['result']['redirect_url'] = url_for('main.index')
        else:
            response['result']['redirect_url'] = url_for('main.edit_routine', routine_id=task_status['result']['routine_id'])

    if task_status['status'] == 'failed' and task_status['error']:
        response['error'] = task_status['error']

    return jsonify(response)


@main_bp.route('/tts-model/status', methods=['GET'])
def check_model_status():
    """Check the status of the TTS model"""
    model_status_data = get_model_status()

    return jsonify({
        'status': model_status_data['status'],
        'error': model_status_data['error']
    })


@main_bp.route('/tts-model/download', methods=['POST'])
def download_model():
    """Trigger the download of the TTS model"""
    # Check if the model is already downloaded or downloading
    model_status_data = get_model_status()

    if model_status_data['status'] == 'downloaded':
        return jsonify({
            'status': 'downloaded',
            'message': 'TTS model is already downloaded'
        })

    if model_status_data['status'] == 'downloading':
        return jsonify({
            'status': 'downloading',
            'message': 'TTS model download is already in progress'
        })

    # Start the model download
    started = start_model_download()

    if started:
        return jsonify({
            'status': 'downloading',
            'message': 'TTS model download started'
        })
    else:
        return jsonify({
            'status': model_status_data['status'],
            'message': 'Failed to start TTS model download',
            'error': model_status_data['error']
        }), 500
