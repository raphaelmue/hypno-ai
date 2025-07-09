import json
import logging
import os
import threading
import time
import uuid

from app.audio import generate_audio
from app.models.routine import add_routine, update_routine, get_routine

# Create a directory to store task data
TASKS_FOLDER = os.path.join('app', 'static', 'tasks')
os.makedirs(TASKS_FOLDER, exist_ok=True)

# Initialize logger
logger = logging.getLogger(__name__)
logger.info(f"Task system initialized with task folder: {TASKS_FOLDER}")

# Helper functions for task persistence
def _get_task_file_path(task_id):
    """Get the file path for a task's data"""
    return os.path.join(TASKS_FOLDER, f"{task_id}.json")

def _save_task(task_id, task_data):
    """Save task data to a file"""
    file_path = _get_task_file_path(task_id)
    try:
        with open(file_path, 'w') as f:
            json.dump(task_data, f)
        logger.debug(f"Task {task_id} saved to {file_path}")
    except Exception as e:
        logger.error(f"Error saving task {task_id} to {file_path}: {str(e)}")
        raise

def _load_task(task_id):
    """Load task data from a file"""
    file_path = _get_task_file_path(task_id)
    if not os.path.exists(file_path):
        logger.debug(f"Task file not found: {file_path}")
        return None
    try:
        with open(file_path, 'r') as f:
            task_data = json.load(f)
        logger.debug(f"Task {task_id} loaded from {file_path}")
        return task_data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error loading task {task_id}: {str(e)}")
        return None
    except IOError as e:
        logger.error(f"IO error loading task {task_id}: {str(e)}")
        return None

def generate_audio_task(task_id, text, language, voice_path, routine_name, routine_id=None, voice_type=None, voice_id=None, num_threads=4):
    """
    Background task to generate audio from text

    Args:
        task_id (str): ID of the task
        text (str): Text to convert to audio
        language (str): Language code
        voice_path (str): Path to the voice sample file
        routine_name (str): Name of the routine
        routine_id (str, optional): ID of the routine if updating an existing one
        voice_type (str, optional): Type of voice (sample or upload)
        voice_id (str, optional): ID of the sample voice if using a sample
        num_threads (int, optional): Number of threads to use for audio generation
    """
    start_time = time.time()
    logger.info(f"Starting background task {task_id} for routine '{routine_name}' with {num_threads} threads")

    try:
        # Load current task data
        task_data = _load_task(task_id)
        if not task_data:
            logger.error(f"Task data not found for task {task_id}")
            return

        # Update task status to processing
        logger.info(f"Task {task_id} status updated to 'processing'")
        task_data['status'] = 'processing'
        _save_task(task_id, task_data)

        # Generate the audio file
        logger.info(f"Generating audio for task {task_id} with {len(text)} characters of text")
        output_filename = generate_audio(text, language, voice_path, routine_name=routine_name, num_threads=num_threads)
        logger.info(f"Audio generation completed for task {task_id}, output file: {output_filename}")

        # Clean up temporary uploaded file if needed
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            logger.debug(f"Cleaning up temporary voice file: {voice_path}")
            os.remove(voice_path)

        # Store or update the routine
        if routine_id and get_routine(routine_id):
            # Update existing routine
            logger.info(f"Updating existing routine {routine_id} for task {task_id}")
            routine = update_routine(
                routine_id,
                output_filename=output_filename,
                name=routine_name,
                text=text,
                language=language,
                voice_type=voice_type,
                voice_id=voice_id
            )
            logger.info(f"Routine {routine_id} updated successfully")
        else:
            # Create new routine
            logger.info(f"Creating new routine for task {task_id}")
            routine = add_routine(
                name=routine_name,
                text=text,
                language=language,
                voice_type=voice_type,
                voice_id=voice_id,
                output_filename=output_filename
            )
            logger.info(f"New routine created with ID {routine['id']}")

        # Update task status to completed with result
        logger.info(f"Task {task_id} completed successfully")
        task_data['status'] = 'completed'
        task_data['result'] = {
            'routine_id': routine['id'],
            'name': routine['name'],
            'filename': output_filename,
            'download_url': f'/download/{output_filename}'
        }
        _save_task(task_id, task_data)

        total_time = time.time() - start_time
        logger.info(f"Task {task_id} completed in {total_time:.2f} seconds")

    except Exception as e:
        # Log the error
        logger.error(f"Error in task {task_id}: {str(e)}", exc_info=True)

        # Load current task data
        task_data = _load_task(task_id)
        if task_data:
            # Update task status to failed with error message
            logger.info(f"Updating task {task_id} status to 'failed'")
            task_data['status'] = 'failed'
            task_data['error'] = str(e)
            _save_task(task_id, task_data)
        else:
            logger.error(f"Could not update task {task_id} status to 'failed': task data not found")

        # Clean up temporary uploaded file if needed
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            logger.debug(f"Cleaning up temporary voice file after error: {voice_path}")
            try:
                os.remove(voice_path)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temporary file {voice_path}: {str(cleanup_error)}")

        total_time = time.time() - start_time
        logger.error(f"Task {task_id} failed after {total_time:.2f} seconds")

def start_task(text, language, voice_path, routine_name, routine_id=None, voice_type=None, voice_id=None, num_threads=4):
    """
    Start a new background task and return the task ID

    Args:
        text (str): Text to convert to audio
        language (str): Language code
        voice_path (str): Path to the voice sample file
        routine_name (str): Name of the routine
        routine_id (str, optional): ID of the routine if updating an existing one
        voice_type (str, optional): Type of voice (sample or upload)
        voice_id (str, optional): ID of the sample voice if using a sample
        num_threads (int, optional): Number of threads to use for audio generation

    Returns:
        str: ID of the created task
    """
    task_id = str(uuid.uuid4())
    logger.info(f"Creating new task {task_id} for routine '{routine_name}' with {num_threads} threads")

    # Log task parameters
    logger.debug(f"Task {task_id} parameters: language={language}, voice_type={voice_type}, " +
                f"voice_id={voice_id}, routine_id={routine_id}, text_length={len(text)}")

    # Initialize task status
    task_data = {
        'status': 'pending',
        'result': None,
        'error': None,
        'created_at': str(uuid.uuid1())  # Use uuid1 for timestamp-based ordering
    }

    # Save task data to file
    _save_task(task_id, task_data)
    logger.info(f"Task {task_id} initialized with status 'pending'")

    try:
        # Start the task in a background thread
        thread = threading.Thread(
            target=generate_audio_task,
            args=(task_id, text, language, voice_path, routine_name, routine_id, voice_type, voice_id, num_threads)
        )
        thread.daemon = True  # Thread will exit when the main program exits
        thread.start()
        logger.info(f"Background thread started for task {task_id}")
    except Exception as e:
        logger.error(f"Error starting background thread for task {task_id}: {str(e)}", exc_info=True)
        # Update task status to failed
        task_data['status'] = 'failed'
        task_data['error'] = f"Failed to start task: {str(e)}"
        _save_task(task_id, task_data)
        # Re-raise the exception
        raise

    return task_id

def get_task_status(task_id):
    """
    Get the status of a task
    """
    logger.debug(f"Checking status of task {task_id}")
    task_data = _load_task(task_id)

    if task_data:
        logger.debug(f"Task {task_id} status: {task_data.get('status', 'unknown')}")
    else:
        logger.warning(f"Task {task_id} not found")

    return task_data

def clean_old_tasks():
    """
    Remove completed and failed tasks that are older than a certain threshold
    This would be called periodically to prevent disk space issues
    """
    logger.info("Starting cleanup of old task files")
    removed_count = 0
    error_count = 0

    # Get all task files
    task_files = [f for f in os.listdir(TASKS_FOLDER) if f.endswith('.json')]
    logger.info(f"Found {len(task_files)} task files to check")

    for filename in task_files:
        file_path = os.path.join(TASKS_FOLDER, filename)
        try:
            # Check if the file is older than 24 hours
            file_age = os.path.getmtime(file_path)
            age_in_hours = (time.time() - file_age) / 3600

            if age_in_hours > 24:  # 24 hours
                logger.debug(f"Removing old task file: {filename} (age: {age_in_hours:.1f} hours)")
                os.remove(file_path)
                removed_count += 1
        except (OSError, IOError) as e:
            logger.error(f"Error checking/removing task file {filename}: {str(e)}")
            error_count += 1
            continue

    logger.info(f"Task cleanup completed: removed {removed_count} files, encountered {error_count} errors")
    return removed_count
