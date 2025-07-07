import os
import json
import uuid
from datetime import datetime
from app.config import OUTPUT_FOLDER

# Path to the JSON file where routines will be stored
ROUTINES_FILE = os.path.join('app', 'data', 'routines.json')

# Ensure the data directory exists
os.makedirs(os.path.dirname(ROUTINES_FILE), exist_ok=True)

# In-memory storage for routines
_routines = {}

def load_routines():
    """Load routines from the JSON file"""
    global _routines
    if os.path.exists(ROUTINES_FILE):
        try:
            with open(ROUTINES_FILE, 'r') as f:
                _routines = json.load(f)
        except (json.JSONDecodeError, IOError):
            _routines = {}
    return _routines

def save_routines():
    """Save routines to the JSON file"""
    with open(ROUTINES_FILE, 'w') as f:
        json.dump(_routines, f, indent=2)

def get_routine(routine_id):
    """Get a routine by ID"""
    routines = load_routines()
    return routines.get(routine_id)

def list_routines():
    """List all routines"""
    routines = load_routines()
    return routines

def add_routine(name, text, language, voice_type, voice_id=None, output_filename=None):
    """Add a new routine or update an existing one"""
    routines = load_routines()
    
    # Generate a unique ID if this is a new routine
    routine_id = str(uuid.uuid4())
    
    # Create the routine object
    routine = {
        'id': routine_id,
        'name': name,
        'text': text,
        'language': language,
        'voice_type': voice_type,
        'voice_id': voice_id,
        'output_filename': output_filename,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    # Add to the in-memory dictionary
    routines[routine_id] = routine
    
    # Save to the JSON file
    save_routines()
    
    return routine

def update_routine(routine_id, output_filename=None, **kwargs):
    """Update an existing routine"""
    routines = load_routines()
    
    if routine_id not in routines:
        return None
    
    # Update the specified fields
    for key, value in kwargs.items():
        if key in routines[routine_id]:
            routines[routine_id][key] = value
    
    # Update the output filename if provided
    if output_filename:
        routines[routine_id]['output_filename'] = output_filename
    
    # Update the updated_at timestamp
    routines[routine_id]['updated_at'] = datetime.now().isoformat()
    
    # Save to the JSON file
    save_routines()
    
    return routines[routine_id]

def delete_routine(routine_id):
    """Delete a routine by ID"""
    routines = load_routines()
    
    if routine_id not in routines:
        return False
    
    # Delete the audio file if it exists
    output_filename = routines[routine_id].get('output_filename')
    if output_filename:
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass  # Ignore errors when deleting the file
    
    # Remove from the in-memory dictionary
    del routines[routine_id]
    
    # Save to the JSON file
    save_routines()
    
    return True

# Initialize by loading routines from the file
load_routines()