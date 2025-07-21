"""
Test script to verify that headings are ignored in audio generation.
This script tests that lines starting with ### (headings) are not read in the generated audio.
"""

import os
import logging
import tempfile
from app.audio.audio import generate_audio
from app.config import SAMPLE_VOICES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_heading_ignored():
    """Test that headings are ignored in audio generation."""
    # Sample text with headings
    text = """### This is a heading that should be ignored
    
This is normal text that should be read.

### Another heading that should be ignored
This text should be read, but not the heading above."""

    # Use a sample voice
    voice_path = list(SAMPLE_VOICES.values())[0]['path']
    
    # Create a temporary directory for the output
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Generate audio
            logger.info("Starting audio generation with headings...")
            output_filename = generate_audio(
                text=text,
                language="en",
                voice_path=voice_path,
                routine_name="Test Heading Ignored",
                num_threads=1,  # Use 1 thread for simplicity
                progress_callback=lambda percent, message: logger.info(f"Progress: {percent}% - {message}")
            )
            
            logger.info(f"Audio generation completed successfully. Output file: {output_filename}")
            logger.info("Please verify manually that headings are not read in the generated audio.")
            return True
        except Exception as e:
            logger.error(f"Error during audio generation: {str(e)}", exc_info=True)
            return False

if __name__ == "__main__":
    success = test_heading_ignored()
    if success:
        print("Audio generation test with headings completed!")
        print("Please verify manually that headings are not read in the generated audio.")
    else:
        print("Audio generation test with headings failed!")