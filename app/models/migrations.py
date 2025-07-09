import os
import logging
import alembic.config
from alembic import command
from app.models.settings import settings

# Set up logging
logger = logging.getLogger(__name__)

# This module provides functions for managing database migrations using Alembic.
# It is used by the application to ensure that the database schema is up to date.
# 
# The main functions are:
# - check_migrations(): Check if there are any pending migrations
# - run_migrations(): Apply any pending migrations
# - create_migration(message): Create a new migration script
#
# For more information on how to use Alembic, see the README.md file in the migrations directory.

def get_alembic_config():
    """Get the Alembic configuration"""
    # Get the path to the alembic.ini file
    alembic_ini = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'alembic.ini')

    # Create the Alembic configuration
    config = alembic.config.Config(alembic_ini)

    # Override the SQLAlchemy URL with the actual database file path
    db_file = settings.get_db_file()
    db_url = f"sqlite:///{db_file}"
    config.set_main_option("sqlalchemy.url", db_url)

    return config

def check_migrations():
    """Check if there are any pending migrations"""
    logger.info("Checking for pending database migrations")
    config = get_alembic_config()

    # Get the current revision
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(config)

    # Get the database revision
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    db_file = settings.get_db_file()
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url)

    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()

    # Get the head revision
    head_rev = script.get_current_head()

    # Check if we need to upgrade
    if current_rev != head_rev:
        logger.info(f"Database needs migration from {current_rev} to {head_rev}")
        return True

    logger.info("Database is up to date")
    return False

def run_migrations():
    """Run database migrations"""
    logger.info("Running database migrations")
    config = get_alembic_config()

    try:
        # Run the upgrade to the latest version
        command.upgrade(config, "head")
        logger.info("Database migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error running database migrations: {str(e)}")
        return False

def create_migration(message):
    """Create a new migration script"""
    logger.info(f"Creating new migration: {message}")
    config = get_alembic_config()

    try:
        # Create a new revision
        command.revision(config, message=message, autogenerate=True)
        logger.info("Migration script created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating migration script: {str(e)}")
        return False
