import os
import pytest
import logging
from app.models.routine import get_routine, list_routines, add_routine, update_routine, delete_routine
from app.config import DATA_DIR

# Configure logging
logger = logging.getLogger(__name__)

@pytest.fixture
def test_routine_data():
    """Fixture providing test routine data"""
    return {
        "name": "Test Database",
        "text": "This is a test routine to verify database operations.",
        "language": "en",
        "voice_type": "sample",
        "voice_id": "male1"
    }

@pytest.fixture
def cleanup_test_routines():
    """Fixture to clean up test routines after tests"""
    # Setup - nothing to do here
    yield
    # Teardown - clean up any test routines
    routines = list_routines()
    for routine_id, routine in routines.items():
        if routine['name'].startswith('Test Database') or routine['name'].startswith('Updated Test Database'):
            delete_routine(routine_id)
            logger.info(f"Cleaned up test routine: {routine_id}")

def test_database_file_exists():
    """Test that the database file exists"""
    db_file = os.path.join(DATA_DIR, "hypno-ai.db")
    assert os.path.exists(db_file), f"Database file does not exist: {db_file}"

def test_list_routines():
    """Test listing routines"""
    routines = list_routines()
    assert isinstance(routines, dict), "list_routines should return a dictionary"
    # We can't assert the exact number as it may vary, but we can check the structure
    if routines:
        # Get the first routine from the dictionary
        first_routine_id = next(iter(routines))
        first_routine = routines[first_routine_id]
        assert 'id' in first_routine, "Routine should have an 'id' field"
        assert 'name' in first_routine, "Routine should have a 'name' field"

def test_add_routine(test_routine_data, cleanup_test_routines):
    """Test adding a routine"""
    # Add a test routine
    test_routine = add_routine(**test_routine_data)
    
    # Verify the routine was added
    assert test_routine is not None, "add_routine should return the added routine"
    assert 'id' in test_routine, "Added routine should have an 'id' field"
    assert test_routine['name'] == test_routine_data['name'], "Added routine should have the correct name"
    
    # Clean up is handled by the cleanup_test_routines fixture

def test_get_routine(test_routine_data, cleanup_test_routines):
    """Test getting a routine"""
    # Add a test routine
    test_routine = add_routine(**test_routine_data)
    
    # Get the routine
    retrieved_routine = get_routine(test_routine['id'])
    
    # Verify the routine was retrieved
    assert retrieved_routine is not None, "get_routine should return the routine"
    assert retrieved_routine['id'] == test_routine['id'], "Retrieved routine should have the correct ID"
    assert retrieved_routine['name'] == test_routine_data['name'], "Retrieved routine should have the correct name"
    
    # Clean up is handled by the cleanup_test_routines fixture

def test_update_routine(test_routine_data, cleanup_test_routines):
    """Test updating a routine"""
    # Add a test routine
    test_routine = add_routine(**test_routine_data)
    
    # Update the routine
    updated_name = "Updated Test Database"
    updated_text = "This routine has been updated."
    updated_routine = update_routine(
        test_routine['id'],
        name=updated_name,
        text=updated_text
    )
    
    # Verify the routine was updated
    assert updated_routine is not None, "update_routine should return the updated routine"
    assert updated_routine['id'] == test_routine['id'], "Updated routine should have the same ID"
    assert updated_routine['name'] == updated_name, "Updated routine should have the updated name"
    assert updated_routine['text'] == updated_text, "Updated routine should have the updated text"
    
    # Verify the update persisted
    retrieved_routine = get_routine(test_routine['id'])
    assert retrieved_routine['name'] == updated_name, "Update should persist in the database"
    assert retrieved_routine['text'] == updated_text, "Update should persist in the database"
    
    # Clean up is handled by the cleanup_test_routines fixture

def test_delete_routine(test_routine_data, cleanup_test_routines):
    """Test deleting a routine"""
    # Add a test routine
    test_routine = add_routine(**test_routine_data)
    
    # Delete the routine
    deleted = delete_routine(test_routine['id'])
    
    # Verify the routine was deleted
    assert deleted is True, "delete_routine should return True on success"
    
    # Verify the deletion persisted
    deleted_routine = get_routine(test_routine['id'])
    assert deleted_routine is None, "Deleted routine should not be retrievable"
    
    # No need for cleanup since we deleted the routine