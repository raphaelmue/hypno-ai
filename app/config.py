import os

from app.models.settings import settings

# Application configuration
# Use absolute paths for compatibility
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# Get settings from the settings singleton
DATA_DIR = settings.get_data_dir()
OUTPUT_FOLDER = settings.get_output_folder()
AUDIO_GENERATION_THREADS = settings.get('audio_threads', 4)
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg'}

# Define paths for voices
# Built-in voices are packaged with the app
BUILTIN_VOICES_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'voices')
# User voices are stored in ~/voices/
USER_VOICES_FOLDER = os.path.join(os.path.expanduser("~"), 'voices')
# Ensure user voices directory exists
os.makedirs(USER_VOICES_FOLDER, exist_ok=True)

# Sample voices (built-in, pre-loaded)
SAMPLE_VOICES = {
    'male1': {'name': 'Male Voice 1', 'path': os.path.join(BUILTIN_VOICES_FOLDER, 'de-male-calm.mp3')}
}

# Available languages
LANGUAGES = {
    'en': 'English',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish',
    'it': 'Italian',
    'ja': 'Japanese',
    'zh': 'Chinese',
}

# Logging configuration
# Store logs in the data directory where other app data is stored
LOGS_FOLDER = os.path.join(DATA_DIR, 'logs')
os.makedirs(LOGS_FOLDER, exist_ok=True)

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'filename': os.path.join(LOGS_FOLDER, 'hypno-ai.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'encoding': 'utf8'
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'ERROR',
            'formatter': 'detailed',
            'filename': os.path.join(LOGS_FOLDER, 'error.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'encoding': 'utf8'
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': True
        },
        # App-specific loggers inherit from root logger
        # No need to duplicate handlers
    }
}
