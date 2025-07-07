import os

# Flask app configuration
UPLOAD_FOLDER = os.path.join('app', 'static', 'voices')
OUTPUT_FOLDER = os.path.join('static', 'output')
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
