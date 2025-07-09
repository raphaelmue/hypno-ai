"""
TTS model management module.
Handles downloading, checking, and loading the TTS model.
"""

import os
import threading
import logging
import time
from TTS.api import TTS

# Initialize logger
logger = logging.getLogger(__name__)

# Dictionary to store model status
# Format: {'status': 'not_downloaded|downloading|downloaded|failed', 'error': '...'}
model_status = {
    'status': 'not_downloaded',
    'error': None
}

# Model information
MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
MODEL_TASK = "downloading TTS model"
MAX_VERIFICATION_ATTEMPTS = 5  # Maximum number of attempts to verify download
VERIFICATION_DELAY = 2  # Seconds to wait between verification attempts

def is_model_downloaded():
    """
    Check if the TTS model is already downloaded.

    Returns:
        bool: True if the model is downloaded, False otherwise.
    """
    try:
        # Try to initialize TTS with the model to check if it's downloaded
        # This will raise an exception if the model is not downloaded
        logger.debug(f"Checking if model {MODEL_NAME} is downloaded")
        tts = TTS(MODEL_NAME, progress_bar=False)
        logger.debug(f"Model {MODEL_NAME} is downloaded and initialized successfully")
        return True
    except Exception as e:
        logger.debug(f"Model {MODEL_NAME} is not downloaded: {str(e)}")
        return False

def get_model_status():
    """
    Get the current status of the TTS model.

    Returns:
        dict: A dictionary containing the model status.
    """
    logger.debug(f"Getting model status, current status: {model_status['status']}")

    # Update the status if the model is downloaded but status doesn't reflect it
    if model_status['status'] != 'downloaded' and is_model_downloaded():
        logger.info(f"Model {MODEL_NAME} is downloaded but status was {model_status['status']}, updating to 'downloaded'")
        model_status['status'] = 'downloaded'
        model_status['error'] = None

    logger.debug(f"Returning model status: {model_status['status']}")
    return model_status

def download_model_task():
    """
    Background task to download the TTS model.
    """
    start_time = time.time()
    logger.info(f"Starting download of model {MODEL_NAME}")

    try:
        # Update model status to downloading
        model_status['status'] = 'downloading'
        model_status['error'] = None
        logger.info(f"Model status updated to 'downloading'")

        # Attempt to download the model
        logger.debug(f"Initializing TTS with model {MODEL_NAME} to trigger download")
        tts = TTS(MODEL_NAME)
        logger.debug(f"TTS initialization completed, now verifying download")

        # Verify that the model is actually downloaded
        # The TTS initialization might return before the download is complete
        verified = False
        attempts = 0

        while not verified and attempts < MAX_VERIFICATION_ATTEMPTS:
            attempts += 1
            logger.debug(f"Verification attempt {attempts}/{MAX_VERIFICATION_ATTEMPTS}")

            if is_model_downloaded():
                verified = True
                logger.info(f"Model download verified after {attempts} attempts")
            else:
                logger.debug(f"Model not yet fully downloaded, waiting {VERIFICATION_DELAY} seconds before next check")
                time.sleep(VERIFICATION_DELAY)

        if verified:
            # Update model status to downloaded
            model_status['status'] = 'downloaded'
            download_time = time.time() - start_time
            logger.info(f"Model {MODEL_NAME} download completed and verified in {download_time:.2f} seconds")
        else:
            # If we couldn't verify the download after multiple attempts
            model_status['status'] = 'failed'
            model_status['error'] = "Download verification failed after multiple attempts"
            logger.error(f"Failed to verify model download after {MAX_VERIFICATION_ATTEMPTS} attempts")

    except Exception as e:
        # Update model status to failed with error message
        model_status['status'] = 'failed'
        model_status['error'] = str(e)
        logger.error(f"Error downloading model {MODEL_NAME}: {str(e)}", exc_info=True)

def start_model_download():
    """
    Start downloading the TTS model in a background thread.

    Returns:
        bool: True if the download was started, False if it's already downloaded or downloading.
    """
    logger.info(f"Request to start model {MODEL_NAME} download")
    current_status = get_model_status()

    # Don't start download if it's already downloaded or downloading
    if current_status['status'] in ['downloaded', 'downloading']:
        logger.info(f"Model download not started: current status is '{current_status['status']}'")
        return False

    # Start the download in a background thread
    logger.info(f"Starting model download in background thread")
    thread = threading.Thread(target=download_model_task)
    thread.daemon = True  # Thread will exit when the main program exits
    thread.start()
    logger.debug(f"Background thread started for model download")

    return True

def get_tts_model():
    """
    Get the TTS model instance. If the model is not downloaded, it will return None.

    Returns:
        TTS or None: The TTS model instance if downloaded, None otherwise.
    """
    logger.debug("Request to get TTS model instance")
    status = get_model_status()['status']

    if status == 'downloaded':
        try:
            logger.debug(f"Model status is 'downloaded', creating TTS instance")
            tts = TTS(MODEL_NAME)
            logger.info(f"TTS model instance created successfully")
            return tts
        except Exception as e:
            logger.error(f"Error creating TTS model instance: {str(e)}")
            return None
    else:
        logger.warning(f"Cannot create TTS model instance: model status is '{status}', not 'downloaded'")
        return None
