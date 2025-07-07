from app.config import ALLOWED_EXTENSIONS

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS