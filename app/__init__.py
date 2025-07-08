from flask import Flask
import threading

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Import configuration
    from app.config import MAX_CONTENT_LENGTH
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    # Check if TTS model is downloaded and start download if needed
    from app.tts_model.model import is_model_downloaded, start_model_download
    if not is_model_downloaded():
        # Start model download in a background thread after a short delay
        # to allow the application to start up first
        def delayed_model_download():
            import time
            time.sleep(5)  # Wait 5 seconds before starting the download
            start_model_download()

        thread = threading.Thread(target=delayed_model_download)
        thread.daemon = True
        thread.start()

    return app
