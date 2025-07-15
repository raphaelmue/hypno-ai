import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from app.config import USER_VOICES_FOLDER, OUTPUT_FOLDER
from app.desktop.main_window import MainWindow
from app.models.migrations import check_migrations, run_migrations

# Get logger
logger = logging.getLogger(__name__)

# Ensure required directories exist
os.makedirs(USER_VOICES_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Set environment variable for Coqui TTS
os.environ["COQUI_TOS_AGREED"] = "1"

# Check for and apply database migrations
try:
    if check_migrations():
        logger.info("Database migrations needed, applying...")
        if run_migrations():
            logger.info("Database migrations applied successfully")
        else:
            logger.error("Failed to apply database migrations")
    else:
        logger.info("Database schema is up to date")
except Exception as e:
    logger.error(f"Error checking or applying database migrations: {str(e)}")
    logger.exception("Migration error details:")

def main():
    """Main entry point for the desktop application"""
    # Log that we're starting the main application
    logger.info("Starting Hypno-AI desktop application")

    # Create the Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("Hypnosis Audio Generator")
    app.setStyle("Fusion")  # Use Fusion style for consistent look across platforms

    # Create and show the main window
    main_window = MainWindow()
    main_window.show()

    # Start the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
