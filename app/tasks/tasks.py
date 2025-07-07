import os
import uuid
import threading
from app.audio import generate_audio
from app.models.routine import add_routine, update_routine, get_routine

# Dictionary to store task status
# Format: {task_id: {'status': 'pending|processing|completed|failed', 'result': {...}, 'error': '...'}}
tasks = {}

def generate_audio_task(task_id, text, language, voice_path, routine_name, routine_id=None, voice_type=None, voice_id=None):
    """
    Background task to generate audio from text
    """
    try:
        # Update task status to processing
        tasks[task_id]['status'] = 'processing'
        
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
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['result'] = {
            'routine_id': routine['id'],
            'name': routine['name'],
            'filename': output_filename,
            'download_url': f'/download/{output_filename}'
        }
    except Exception as e:
        # Update task status to failed with error message
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
        
        # Clean up temporary uploaded file if needed
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            os.remove(voice_path)

def start_task(text, language, voice_path, routine_name, routine_id=None, voice_type=None, voice_id=None):
    """
    Start a new background task and return the task ID
    """
    task_id = str(uuid.uuid4())
    
    # Initialize task status
    tasks[task_id] = {
        'status': 'pending',
        'result': None,
        'error': None
    }
    
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
    if task_id not in tasks:
        return None
    
    return tasks[task_id]

def clean_old_tasks():
    """
    Remove completed and failed tasks that are older than a certain threshold
    This would be called periodically to prevent memory leaks
    """
    # This is a placeholder for a more sophisticated implementation
    # In a real application, you would track task creation time and remove old tasks
    pass