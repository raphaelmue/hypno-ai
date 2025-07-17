import os
import pytest
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import the necessary modules
from app.config import BUILTIN_VOICES_FOLDER, USER_VOICES_FOLDER, SAMPLE_VOICES

def test_builtin_voices_folder_exists():
    """Test that the built-in voices folder exists"""
    assert os.path.exists(BUILTIN_VOICES_FOLDER), f"Built-in voices folder does not exist: {BUILTIN_VOICES_FOLDER}"
    assert os.path.isdir(BUILTIN_VOICES_FOLDER), f"Built-in voices path is not a directory: {BUILTIN_VOICES_FOLDER}"

def test_user_voices_folder_exists():
    """Test that the user voices folder exists"""
    assert os.path.exists(USER_VOICES_FOLDER), f"User voices folder does not exist: {USER_VOICES_FOLDER}"
    assert os.path.isdir(USER_VOICES_FOLDER), f"User voices path is not a directory: {USER_VOICES_FOLDER}"

def test_builtin_voices_folder_has_files():
    """Test that the built-in voices folder has files"""
    if os.path.exists(BUILTIN_VOICES_FOLDER):
        files = os.listdir(BUILTIN_VOICES_FOLDER)
        assert len(files) > 0, f"Built-in voices folder is empty: {BUILTIN_VOICES_FOLDER}"
        
        # Log the files for informational purposes
        for file in files:
            logger.info(f"Built-in voice file: {file}")

def test_sample_voices_configured():
    """Test that the sample voices are correctly configured"""
    assert len(SAMPLE_VOICES) > 0, "No sample voices configured"
    
    for voice_id, voice in SAMPLE_VOICES.items():
        # Check that each sample voice has the required fields
        assert 'name' in voice, f"Sample voice {voice_id} missing 'name' field"
        assert 'path' in voice, f"Sample voice {voice_id} missing 'path' field"
        
        # Check that the voice file exists
        voice_path = voice['path']
        assert os.path.exists(voice_path), f"Sample voice file does not exist: {voice_path}"
        assert os.path.isfile(voice_path), f"Sample voice path is not a file: {voice_path}"