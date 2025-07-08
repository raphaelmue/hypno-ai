import os
from app import create_app

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    # In production, bind to all interfaces and disable debug mode
    os.environ["COQUI_TOS_AGREED"] = "1"
    app.run(port=5000, debug=False)
