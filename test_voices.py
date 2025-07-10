import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the necessary modules
from app.config import BUILTIN_VOICES_FOLDER, USER_VOICES_FOLDER, SAMPLE_VOICES

def test_voice_folders():
    """Test that the voice folders are correctly configured"""
    logger.info("Testing voice folder configuration")
    
    # Check that the built-in voices folder exists
    logger.info(f"Built-in voices folder: {BUILTIN_VOICES_FOLDER}")
    logger.info(f"Built-in voices folder exists: {os.path.exists(BUILTIN_VOICES_FOLDER)}")
    
    # Check that the user voices folder exists
    logger.info(f"User voices folder: {USER_VOICES_FOLDER}")
    logger.info(f"User voices folder exists: {os.path.exists(USER_VOICES_FOLDER)}")
    
    # List the contents of the built-in voices folder
    logger.info("Built-in voices:")
    if os.path.exists(BUILTIN_VOICES_FOLDER):
        for file in os.listdir(BUILTIN_VOICES_FOLDER):
            logger.info(f"  - {file}")
    else:
        logger.warning("Built-in voices folder does not exist")
    
    # List the contents of the user voices folder
    logger.info("User voices:")
    if os.path.exists(USER_VOICES_FOLDER):
        for file in os.listdir(USER_VOICES_FOLDER):
            logger.info(f"  - {file}")
    else:
        logger.warning("User voices folder does not exist")
    
    # Check that the sample voices are correctly configured
    logger.info("Sample voices:")
    for voice_id, voice in SAMPLE_VOICES.items():
        logger.info(f"  - {voice_id}: {voice['name']}")
        logger.info(f"    Path: {voice['path']}")
        logger.info(f"    Path exists: {os.path.exists(voice['path'])}")
    
    logger.info("Voice folder test completed")

if __name__ == "__main__":
    test_voice_folders()