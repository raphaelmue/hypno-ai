import os
import logging
from app.models.routine import get_routine, list_routines, add_routine, update_routine, delete_routine
from app.config import DATA_DIR

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_operations():
    """Test basic database operations"""
    logger.info("Testing database operations")
    
    # Check database file exists
    db_file = os.path.join(DATA_DIR, "hypno-ai.db")
    logger.info(f"Database file: {db_file}")
    logger.info(f"Database file exists: {os.path.exists(db_file)}")
    
    # List all routines
    routines = list_routines()
    logger.info(f"Found {len(routines)} routines in the database")
    
    # Add a test routine
    test_routine = add_routine(
        name="Test Database",
        text="This is a test routine to verify database operations.",
        language="en",
        voice_type="sample",
        voice_id="male1"
    )
    logger.info(f"Added test routine with ID: {test_routine['id']}")
    
    # Get the routine
    retrieved_routine = get_routine(test_routine['id'])
    logger.info(f"Retrieved routine: {retrieved_routine['name']}")
    
    # Update the routine
    updated_routine = update_routine(
        test_routine['id'],
        name="Updated Test Database",
        text="This routine has been updated."
    )
    logger.info(f"Updated routine: {updated_routine['name']}")
    
    # Delete the routine
    deleted = delete_routine(test_routine['id'])
    logger.info(f"Deleted routine: {deleted}")
    
    # Verify deletion
    deleted_routine = get_routine(test_routine['id'])
    logger.info(f"Routine exists after deletion: {deleted_routine is not None}")
    
    logger.info("Database operations test completed")

if __name__ == "__main__":
    test_database_operations()