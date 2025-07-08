import os
import uuid
import json
import time
import threading
from app.audio import generate_audio
from app.models.routine import add_routine, update_routine, get_routine

# Create a directory to store task data
TASKS_FOLDER = os.path.join('app', 'static', 'tasks')
os.makedirs(TASKS_FOLDER, exist_ok=True)

# Helper functions for task persistence
def _get_task_file_path(task_id):
    """Get the file path for a task's data"""
    return os.path.join(TASKS_FOLDER, f"{task_id}.json")

def _save_task(task_id, task_data):
    """Save task data to a file"""
    file_path = _get_task_file_path(task_id)
    with open(file_path, 'w') as f:
        json.dump(task_data, f)

def _load_task(task_id):
    """Load task data from a file"""
    file_path = _get_task_file_path(task_id)
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

def generate_audio_task(task_id, text, language, voice_path, routine_name, routine_id=None, voice_type=None, voice_id=None):
    """
    Background task to generate audio from text
    """
    try:
        # Load current task data
        task_data = _load_task(task_id)
        if not task_data:
            return

        # Update task status to processing
        task_data['status'] = 'processing'
        _save_task(task_id, task_data)

        # Generate the audio file
        output_filename = generate_audio(text, language, voice_path, routine_name=routine_name)

        # Clean up temporary uploaded file if needed
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            os.remove(voice_path)

        # Store or update the routine
        if routine_id and get_routine(routine_id):
            # Update existing routine
            routine = update_routine(
                routine_id,
                output_filename=output_filename,
                name=routine_name,
                text=text,
                language=language,
                voice_type=voice_type,
                voice_id=voice_id
            )
        else:
            # Create new routine
            routine = add_routine(
                name=routine_name,
                text=text,
                language=language,
                voice_type=voice_type,
                voice_id=voice_id,
                output_filename=output_filename
            )

        # Update task status to completed with result
        task_data['status'] = 'completed'
        task_data['result'] = {
            'routine_id': routine['id'],
            'name': routine['name'],
            'filename': output_filename,
            'download_url': f'/download/{output_filename}'
        }
        _save_task(task_id, task_data)
    except Exception as e:
        # Load current task data
        task_data = _load_task(task_id)
        if task_data:
            # Update task status to failed with error message
            task_data['status'] = 'failed'
            task_data['error'] = str(e)
            _save_task(task_id, task_data)

        # Clean up temporary uploaded file if needed
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            os.remove(voice_path)

def start_task(text, language, voice_path, routine_name, routine_id=None, voice_type=None, voice_id=None):
    """
    Start a new background task and return the task ID
    """
    task_id = str(uuid.uuid4())

    # Initialize task status
    task_data = {
        'status': 'pending',
        'result': None,
        'error': None,
        'created_at': str(uuid.uuid1())  # Use uuid1 for timestamp-based ordering
    }

    # Save task data to file
    _save_task(task_id, task_data)

    # Start the task in a background thread
    thread = threading.Thread(
        target=generate_audio_task,
        args=(task_id, text, language, voice_path, routine_name, routine_id, voice_type, voice_id)
    )
    thread.daemon = True  # Thread will exit when the main program exits
    thread.start()

    return task_id

def get_task_status(task_id):
    """
    Get the status of a task
    """
    return _load_task(task_id)

def clean_old_tasks():
    """
    Remove completed and failed tasks that are older than a certain threshold
    This would be called periodically to prevent disk space issues
    """
    # Get all task files
    for filename in os.listdir(TASKS_FOLDER):
        if filename.endswith('.json'):
            file_path = os.path.join(TASKS_FOLDER, filename)
            try:
                # Check if the file is older than 24 hours
                file_age = os.path.getmtime(file_path)
                if (time.time() - file_age) > 86400:  # 24 hours in seconds
                    os.remove(file_path)
            except (OSError, IOError):
                continue
