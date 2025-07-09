import os
import logging.config

# Default values
DEFAULT_AUDIO_THREADS = 4

# Environment variables
try:
    AUDIO_GENERATION_THREADS = int(os.environ.get('AUDIO_GENERATION_THREADS', DEFAULT_AUDIO_THREADS))
    # Ensure at least 1 thread
    AUDIO_GENERATION_THREADS = max(1, AUDIO_GENERATION_THREADS)
except (ValueError, TypeError):
    # If the environment variable is not a valid integer, use the default value
    print(f"Warning: Invalid value for AUDIO_GENERATION_THREADS environment variable. Using default value of {DEFAULT_AUDIO_THREADS}.")
    AUDIO_GENERATION_THREADS = DEFAULT_AUDIO_THREADS

# Flask app configuration
# Use absolute paths for Docker/Gunicorn compatibility
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'voices')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'output')
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Sample voices (these would be pre-loaded)
SAMPLE_VOICES = {
    'male1': {'name': 'Male Voice 1', 'path': os.path.join(UPLOAD_FOLDER, 'de-male-calm.mp3')}
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
LOGS_FOLDER = os.path.join(BASE_DIR, 'logs')
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
        'app': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False
        },
        'app.audio': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False
        },
        'app.tasks': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False
        },
        'app.routes': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False
        },
    }
}
