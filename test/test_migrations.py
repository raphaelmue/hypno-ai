import os
import logging
from app.models.migrations import check_migrations, run_migrations
from app.models.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_migrations():
    """Test the migration system"""
    logger.info("Testing migration system")
    
    # Get the database file path
    db_file = settings.get_db_file()
    logger.info(f"Database file: {db_file}")
    logger.info(f"Database file exists: {os.path.exists(db_file)}")
    
    # Check for pending migrations
    if check_migrations():
        logger.info("Pending migrations found, applying...")
        if run_migrations():
            logger.info("Migrations applied successfully")
        else:
            logger.error("Failed to apply migrations")
    else:
        logger.info("No pending migrations found")
    
    logger.info("Migration test completed")

if __name__ == "__main__":
    test_migrations()