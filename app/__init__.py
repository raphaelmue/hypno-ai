from flask import Flask
import logging
import logging.config

def create_app():
    """Create and configure the Flask application"""
    # Set up logging
    from app.config import LOGGING_CONFIG
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(__name__)
    logger.info("Starting Hypno-AI application")

    app = Flask(__name__)

    # Import configuration
    from app.config import MAX_CONTENT_LENGTH
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app
