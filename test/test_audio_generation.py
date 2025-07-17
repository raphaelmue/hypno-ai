"""
Test script to verify the audio generation functionality.
This script tests the audio generation with a simple text that includes empty segments.
"""

import os
import logging
import tempfile
from app.audio.audio import generate_audio
from app.config import SAMPLE_VOICES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_audio_generation():
    """Test audio generation with a text that includes empty segments."""
    # Sample text with line breaks and [break] tags
    text = """This is a test.
    
This is a new paragraph after a line break.
[break]
This is after a break tag."""

    # Use a sample voice
    voice_path = list(SAMPLE_VOICES.values())[0]['path']
    
    # Create a temporary directory for the output
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Generate audio
            logger.info("Starting audio generation...")
            output_filename = generate_audio(
                text=text,
                language="en",
                voice_path=voice_path,
                routine_name="Test Audio Generation",
                num_threads=1,  # Use 1 thread for simplicity
                progress_callback=lambda percent, message: logger.info(f"Progress: {percent}% - {message}")
            )
            
            logger.info(f"Audio generation completed successfully. Output file: {output_filename}")
            return True
        except Exception as e:
            logger.error(f"Error during audio generation: {str(e)}", exc_info=True)
            return False

if __name__ == "__main__":
    success = test_audio_generation()
    if success:
        print("Audio generation test passed!")
    else:
        print("Audio generation test failed!")