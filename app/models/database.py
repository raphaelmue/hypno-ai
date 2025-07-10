import sqlite3
from datetime import datetime

from app.models.settings import settings

# Define the database file
DB_FILE = settings.get_db_file()

def get_db_connection():
    """Get a connection to the SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def init_db():
    """Initialize the database schema using Alembic migrations"""
    # Import here to avoid circular imports
    from app.models.migrations import run_migrations

    # Run migrations to ensure the database schema is up to date
    run_migrations()

def get_routine(routine_id):
    """Get a routine by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM routines WHERE id = ?", (routine_id,))
    routine = cursor.fetchone()

    conn.close()

    if routine:
        return dict(routine)
    return None

def list_routines():
    """List all routines"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM routines")
    routines = cursor.fetchall()

    conn.close()

    # Convert to dictionary with routine_id as key
    result = {}
    for routine in routines:
        routine_dict = dict(routine)
        result[routine_dict['id']] = routine_dict

    return result

def add_routine(name, text, language, voice_type, voice_id=None, output_filename=None, routine_id=None):
    """Add a new routine"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Use provided ID or generate a new one
    from uuid import uuid4
    if routine_id is None:
        routine_id = str(uuid4())

    now = datetime.now().isoformat()

    cursor.execute('''
    INSERT INTO routines (id, name, text, language, voice_type, voice_id, output_filename, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (routine_id, name, text, language, voice_type, voice_id, output_filename, now, now))

    conn.commit()
    conn.close()

    return get_routine(routine_id)

def update_routine(routine_id, **kwargs):
    """Update an existing routine"""
    routine = get_routine(routine_id)
    if not routine:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    # Update only the fields that are provided
    updates = []
    values = []

    for key, value in kwargs.items():
        if key in routine and key != 'id':  # Don't update the ID
            updates.append(f"{key} = ?")
            values.append(value)

    # Always update the updated_at timestamp
    updates.append("updated_at = ?")
    values.append(datetime.now().isoformat())

    # Add the routine_id for the WHERE clause
    values.append(routine_id)

    # Execute the update query
    cursor.execute(f'''
    UPDATE routines
    SET {", ".join(updates)}
    WHERE id = ?
    ''', values)

    conn.commit()
    conn.close()

    return get_routine(routine_id)

def delete_routine(routine_id):
    """Delete a routine by ID"""
    routine = get_routine(routine_id)
    if not routine:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM routines WHERE id = ?", (routine_id,))

    conn.commit()
    conn.close()

    return True

# Initialize the database when this module is imported
init_db()
