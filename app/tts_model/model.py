"""
TTS model management module.
Handles downloading, checking, and loading the TTS model.
"""

import logging
import os
import threading

from TTS.api import TTS

from app.models.settings import settings

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

def get_model_dir():
    """
    Get the directory where the TTS model should be stored and set the TTS_HOME environment variable.

    Returns:
        str: Path to the model directory
    """
    # Set the model directory to a subdirectory of the app's data directory
    model_dir = os.path.join(settings.get_data_dir(), "tts_model")

    # Ensure the directory exists
    os.makedirs(model_dir, exist_ok=True)

    # Set the TTS_HOME environment variable
    os.environ["TTS_HOME"] = model_dir
    logger.info(f"Set TTS_HOME environment variable to: {model_dir}")

    return model_dir

def is_model_downloaded():
    """
    Check if the TTS model is already downloaded by checking for the existence of model files.

    Returns:
        bool: True if the model is downloaded, False otherwise.
    """
    # Get the model directory
    model_dir = get_model_dir()
    logger.debug(f"Checking if model {MODEL_NAME} is downloaded in {model_dir}")

    # For XTTS model, check for the existence of required files
    if "xtts" in MODEL_NAME:
        # Required files for XTTS model
        required_files = ["model.pth", "config.json", "vocab.json", "speakers_xtts.pth"]

        # Check if all required files exist
        all_files_exist = all(os.path.exists(os.path.join(model_dir, "tts", MODEL_NAME.replace("/", "--"), file)) for file in required_files)

        if all_files_exist:
            logger.debug(f"Model {MODEL_NAME} is downloaded (all required files exist)")
            return True
        else:
            # Log which files are missing
            missing_files = [file for file in required_files if not os.path.exists(os.path.join(model_dir, file))]
            logger.debug(f"Model {MODEL_NAME} is not downloaded (missing files: {missing_files})")
            return False
    else:
        # For other models, check for the existence of model.pth and config.json
        model_file_exists = any(os.path.exists(os.path.join(model_dir, file)) 
                               for file in ["model.pth", "model_file.pth", "model_file.pth.tar", "checkpoint.pth"])
        config_file_exists = os.path.exists(os.path.join(model_dir, "config.json"))

        if model_file_exists and config_file_exists:
            logger.debug(f"Model {MODEL_NAME} is downloaded (model file and config file exist)")
            return True
        else:
            logger.debug(f"Model {MODEL_NAME} is not downloaded (model file or config file missing)")
            return False

def get_model_status():
    """
    Get the current status of the TTS model.

    Returns:
        dict: A dictionary containing the model status.
    """
    # Update the status if the model is downloaded but status doesn't reflect it
    if model_status['status'] != 'downloaded' and is_model_downloaded():
        model_status['status'] = 'downloaded'
        model_status['error'] = None

    return model_status

def download_model_task():
    """
    Background task to download the TTS model.
    """
    try:
        # Update model status to downloading
        model_status['status'] = 'downloading'
        model_status['error'] = None

        # Set the model directory environment variable
        model_dir = get_model_dir()
        os.environ["COQUI_TTS_MODELS_DIR"] = os.environ["TTS_HOME"]

        # Download the model
        tts = TTS(MODEL_NAME)

        # Update model status to downloaded
        model_status['status'] = 'downloaded'
    except Exception as e:
        # Update model status to failed with error message
        model_status['status'] = 'failed'
        model_status['error'] = str(e)

def start_model_download(force=True):
    """
    Start downloading the TTS model in a background thread.

    Args:
        force (bool): If True, allow re-downloading even if the model is already downloaded.
                     Default is True to allow manual re-download.

    Returns:
        bool: True if the download was started, False otherwise.
    """
    current_status = get_model_status()

    # Don't start download if it's already downloading
    if current_status['status'] == 'downloading':
        logger.info("Model download already in progress")
        return False

    # Don't start download if it's already downloaded and force is False
    if current_status['status'] == 'downloaded' and not force:
        logger.info("Model already downloaded and force is False")
        return False

    # If we're re-downloading, reset the status
    if current_status['status'] == 'downloaded' and force:
        logger.info("Forcing re-download of model")
        model_status['status'] = 'not_downloaded'

    # Start the download in a background thread
    thread = threading.Thread(target=download_model_task)
    thread.daemon = True  # Thread will exit when the main program exits
    thread.start()
    logger.info("Started model download thread")

    return True

def get_tts_model():
    """
    Get the TTS model instance. If the model is not downloaded, it will return None.

    Returns:
        TTS or None: The TTS model instance if downloaded, None otherwise.
    """
    if get_model_status()['status'] == 'downloaded':
        try:
            # Set the model directory environment variable
            model_dir = get_model_dir()
            os.environ["COQUI_TTS_MODELS_DIR"] = os.environ["TTS_HOME"]

            return TTS(MODEL_NAME)
        except Exception:
            return None
    return None
