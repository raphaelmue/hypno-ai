import os
import uuid

from app.config import OUTPUT_FOLDER
from app.models.database import get_routine as db_get_routine, list_routines as db_list_routines, \
    add_routine as db_add_routine, update_routine as db_update_routine, delete_routine as db_delete_routine


def get_routine(routine_id):
    """Get a routine by ID"""
    return db_get_routine(routine_id)

def list_routines():
    """List all routines"""
    return db_list_routines()

def add_routine(name, text, language, voice_type, voice_id=None, output_filename=None):
    """Add a new routine"""
    # Generate a unique ID
    routine_id = str(uuid.uuid4())

    # Add the routine to the database
    return db_add_routine(
        name=name,
        text=text,
        language=language,
        voice_type=voice_type,
        voice_id=voice_id,
        output_filename=output_filename,
        routine_id=routine_id
    )

def update_routine(routine_id, output_filename=None, **kwargs):
    """Update an existing routine"""
    # If output_filename is provided, add it to kwargs
    if output_filename:
        kwargs['output_filename'] = output_filename

    # Update the routine in the database
    return db_update_routine(routine_id, **kwargs)

def delete_routine(routine_id):
    """Delete a routine by ID"""
    # Get the routine to check if it exists and to get the output_filename
    routine = get_routine(routine_id)

    if not routine:
        return False

    # Delete the audio file if it exists
    output_filename = routine.get('output_filename')
    if output_filename:
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass  # Ignore errors when deleting the file

    # Delete the routine from the database
    return db_delete_routine(routine_id)
