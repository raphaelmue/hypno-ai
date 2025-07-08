"""
TTS model management module.
Handles downloading, checking, and loading the TTS model.
"""

import os
import threading
from TTS.api import TTS

# Dictionary to store model status
# Format: {'status': 'not_downloaded|downloading|downloaded|failed', 'error': '...'}
model_status = {
    'status': 'not_downloaded',
    'error': None
}

# Model information
MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
MODEL_TASK = "downloading TTS model"

def is_model_downloaded():
    """
    Check if the TTS model is already downloaded.
    
    Returns:
        bool: True if the model is downloaded, False otherwise.
    """
    try:
        # Try to initialize TTS with the model to check if it's downloaded
        # This will raise an exception if the model is not downloaded
        tts = TTS(MODEL_NAME, progress_bar=False)
        return True
    except Exception:
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
        
        # Download the model
        tts = TTS(MODEL_NAME)
        
        # Update model status to downloaded
        model_status['status'] = 'downloaded'
    except Exception as e:
        # Update model status to failed with error message
        model_status['status'] = 'failed'
        model_status['error'] = str(e)

def start_model_download():
    """
    Start downloading the TTS model in a background thread.
    
    Returns:
        bool: True if the download was started, False if it's already downloaded or downloading.
    """
    current_status = get_model_status()
    
    # Don't start download if it's already downloaded or downloading
    if current_status['status'] in ['downloaded', 'downloading']:
        return False
    
    # Start the download in a background thread
    thread = threading.Thread(target=download_model_task)
    thread.daemon = True  # Thread will exit when the main program exits
    thread.start()
    
    return True

def get_tts_model():
    """
    Get the TTS model instance. If the model is not downloaded, it will return None.
    
    Returns:
        TTS or None: The TTS model instance if downloaded, None otherwise.
    """
    if get_model_status()['status'] == 'downloaded':
        try:
            return TTS(MODEL_NAME)
        except Exception:
            return None
    return None