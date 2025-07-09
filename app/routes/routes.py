import os
import uuid
import logging
from flask import render_template, request, jsonify, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename

from app.routes import main_bp
from app.config import UPLOAD_FOLDER, OUTPUT_FOLDER, LANGUAGES, SAMPLE_VOICES
from app.utils import allowed_file
from app.audio import generate_audio
from app.models.routine import add_routine, update_routine, get_routine, list_routines, delete_routine
from app.tasks.tasks import start_task, get_task_status

# Initialize logger
logger = logging.getLogger(__name__)


@main_bp.route('/')
def index():
    """Render the main page with the list of routines"""
    logger.info(f"Index page requested from {request.remote_addr}")
    routines = list_routines()
    logger.debug(f"Retrieved {len(routines)} routines for index page")
    return render_template('index.html', languages=LANGUAGES, routines=routines)


@main_bp.route('/routine/new')
def new_routine():
    """Render the page for creating a new routine"""
    logger.info(f"New routine page requested from {request.remote_addr}")
    return render_template('routine.html', languages=LANGUAGES, sample_voices=SAMPLE_VOICES, routine=None)


@main_bp.route('/routine/<routine_id>')
def edit_routine(routine_id):
    """Render the page for editing an existing routine"""
    logger.info(f"Edit routine page requested for routine_id={routine_id} from {request.remote_addr}")
    routine = get_routine(routine_id)
    if not routine:
        logger.warning(f"Routine not found: {routine_id}, redirecting to index")
        return redirect(url_for('main.index'))
    logger.debug(f"Retrieved routine: {routine_id} - {routine.get('name', 'Unnamed')}")
    return render_template('routine.html', languages=LANGUAGES, sample_voices=SAMPLE_VOICES, routine=routine)


@main_bp.route('/generate', methods=['POST'])
def generate():
    """Handle the generation of audio from text"""
    logger.info(f"Audio generation requested from {request.remote_addr}")

    # Get form data
    name = request.form.get('name', f'Routine {uuid.uuid4().hex[:8]}')  # Default name if not provided
    text = request.form.get('text', '')
    language = request.form.get('language', 'en')
    voice_type = request.form.get('voice_type', 'sample')
    routine_id = request.form.get('routine_id', '')  # If regenerating an existing routine
    redirect_to_list = request.form.get('redirect', 'false') == 'true'  # Whether to redirect to list page

    logger.info(f"Generation request: name='{name}', language={language}, voice_type={voice_type}, " +
               f"routine_id={routine_id if routine_id else 'new'}, text_length={len(text)}")

    # Get number of threads for audio generation (default to 4 if not specified)
    try:
        num_threads = int(request.form.get('num_threads', 4))
        # Ensure num_threads is at least 1
        num_threads = max(1, num_threads)
        logger.debug(f"Using {num_threads} threads for audio generation")
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid num_threads value: {request.form.get('num_threads', 'not provided')}, using default of 4. Error: {str(e)}")
        num_threads = 4

    # Validate inputs
    if not text:
        logger.warning("Generation request rejected: empty text")
        return jsonify({'error': 'Text is required'}), 400

    if language not in LANGUAGES:
        logger.warning(f"Generation request rejected: invalid language '{language}'")
        return jsonify({'error': 'Invalid language selected'}), 400

    # Handle voice selection
    voice_path = None
    if voice_type == 'sample':
        voice_id = request.form.get('sample_voice', '')
        logger.debug(f"Using sample voice: {voice_id}")
        if voice_id in SAMPLE_VOICES:
            voice_path = SAMPLE_VOICES[voice_id]['path']
            logger.debug(f"Sample voice path: {voice_path}")
        else:
            logger.warning(f"Generation request rejected: invalid sample voice '{voice_id}'")
            return jsonify({'error': 'Invalid sample voice selected'}), 400
    else:  # voice_type == 'upload'
        logger.debug("Using uploaded voice file")
        if 'voice_file' not in request.files:
            logger.warning("Generation request rejected: no voice file uploaded")
            return jsonify({'error': 'No voice file uploaded'}), 400

        file = request.files['voice_file']
        if file.filename == '':
            logger.warning("Generation request rejected: empty voice filename")
            return jsonify({'error': 'No voice file selected'}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4()}_{filename}")
            logger.debug(f"Saving uploaded voice file to {temp_path}")
            file.save(temp_path)
            voice_path = temp_path
        else:
            logger.warning(f"Generation request rejected: invalid file format for '{file.filename if file else 'None'}'")
            return jsonify({'error': 'Invalid file format'}), 400

    try:
        # Store voice ID if using sample voice
        voice_id = None
        if voice_type == 'sample':
            voice_id = request.form.get('sample_voice', '')

        # Start the background task
        logger.info(f"Starting background task for routine '{name}'")
        task_id = start_task(
            text=text,
            language=language,
            voice_path=voice_path,
            routine_name=name,
            routine_id=routine_id,
            voice_type=voice_type,
            voice_id=voice_id,
            num_threads=num_threads
        )
        logger.info(f"Background task started with ID: {task_id}")

        # Return the task ID
        redirect_url = url_for('main.index') if redirect_to_list else None
        logger.debug(f"Returning task_id={task_id}, redirect_url={redirect_url}")
        return jsonify({
            'success': True,
            'task_id': task_id,
            'redirect_url': redirect_url
        })
    except Exception as e:
        logger.error(f"Error starting generation task: {str(e)}", exc_info=True)
        # Clean up temporary uploaded file if needed
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            logger.debug(f"Cleaning up temporary voice file after error: {voice_path}")
            try:
                os.remove(voice_path)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temporary file {voice_path}: {str(cleanup_error)}")
        return jsonify({'error': f'Error starting task: {str(e)}'}), 500


@main_bp.route('/download/<filename>')
def download(filename):
    """Handle the download of generated audio files"""
    logger.info(f"Download requested for file: {filename} from {request.remote_addr}")
    return send_from_directory(OUTPUT_FOLDER, filename)


@main_bp.route('/routines', methods=['GET'])
def get_routines():
    """Get all routines"""
    logger.info(f"List routines requested from {request.remote_addr}")
    routines = list_routines()
    logger.debug(f"Returning {len(routines)} routines")
    return jsonify(list(routines.values()))


@main_bp.route('/routines/<routine_id>', methods=['GET'])
def get_routine_by_id(routine_id):
    """Get a routine by ID"""
    logger.info(f"Get routine requested for ID: {routine_id} from {request.remote_addr}")
    routine = get_routine(routine_id)
    if not routine:
        logger.warning(f"Routine not found: {routine_id}")
        return jsonify({'error': 'Routine not found'}), 404
    logger.debug(f"Returning routine: {routine_id} - {routine.get('name', 'Unnamed')}")
    return jsonify(routine)


@main_bp.route('/routines/<routine_id>', methods=['DELETE'])
def delete_routine_by_id(routine_id):
    """Delete a routine by ID"""
    logger.info(f"Delete routine requested for ID: {routine_id} from {request.remote_addr}")
    success = delete_routine(routine_id)
    if not success:
        logger.warning(f"Failed to delete routine: {routine_id} - not found")
        return jsonify({'error': 'Routine not found'}), 404
    logger.info(f"Routine deleted: {routine_id}")
    return jsonify({'success': True})


@main_bp.route('/task/<task_id>', methods=['GET'])
def check_task_status(task_id):
    """Check the status of a background task"""
    logger.debug(f"Task status check for ID: {task_id} from {request.remote_addr}")
    task_status = get_task_status(task_id)

    if task_status is None:
        logger.warning(f"Task not found: {task_id}")
        return jsonify({'error': 'Task not found'}), 404

    status = task_status['status']
    logger.debug(f"Task {task_id} status: {status}")

    response = {
        'status': status
    }

    # Include result or error if available
    if status == 'completed' and task_status['result']:
        logger.debug(f"Task {task_id} completed with result: {task_status['result']}")
        response['result'] = task_status['result']

        # Add redirect URL if needed
        redirect_to_list = request.args.get('redirect', 'false') == 'true'
        if redirect_to_list:
            response['result']['redirect_url'] = url_for('main.index')
            logger.debug(f"Adding redirect URL to index page for task {task_id}")
        else:
            routine_id = task_status['result']['routine_id']
            response['result']['redirect_url'] = url_for('main.edit_routine', routine_id=routine_id)
            logger.debug(f"Adding redirect URL to edit routine page for task {task_id}, routine {routine_id}")

    if status == 'failed' and task_status['error']:
        logger.debug(f"Task {task_id} failed with error: {task_status['error']}")
        response['error'] = task_status['error']

    return jsonify(response)
