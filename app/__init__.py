from flask import Flask

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Import configuration
    from app.config import MAX_CONTENT_LENGTH
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    
    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    return app