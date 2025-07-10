import re

import unicodedata

from app.config import ALLOWED_EXTENSIONS


def allowed_file(filename):
    """Check if the uploaded file has an allowed extension"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def slugify(text):
    """
    Convert a string to a URL-friendly slug.
    - Convert to lowercase
    - Remove non-alphanumeric characters
    - Replace spaces with hyphens
    - Remove leading/trailing hyphens
    """
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    # Convert to lowercase
    text = text.lower()
    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    # If empty, use a default
    if not text:
        text = 'routine'
    return text
