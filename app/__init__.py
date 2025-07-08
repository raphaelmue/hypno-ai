from flask import Flask
import subprocess
import logging
import sys

def check_ffmpeg():
    """Check if ffmpeg is installed and available in the PATH"""
    try:
        # Try to run ffmpeg -version to check if it's installed
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        # If ffmpeg is not found or the command fails
        logging.error("""
        -----------------------------------------------------------------------
        ERROR: ffmpeg is not installed or not found in PATH.

        This application requires ffmpeg for audio processing.

        Please install ffmpeg:
        - Windows: Install using Chocolatey (choco install ffmpeg) or download from ffmpeg.org
        - macOS: Install using Homebrew (brew install ffmpeg)
        - Linux: Use your package manager (apt-get, dnf, pacman, etc.)

        After installing, make sure ffmpeg is in your PATH.
        -----------------------------------------------------------------------
        """)
        return False

def create_app():
    """Create and configure the Flask application"""
    # Check if ffmpeg is installed
    check_ffmpeg()

    app = Flask(__name__)

    # Import configuration
    from app.config import MAX_CONTENT_LENGTH
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app
