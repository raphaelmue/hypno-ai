import os
import sys
from PyQt6.QtWidgets import QApplication
from app.desktop.main_window import MainWindow
from app.config import UPLOAD_FOLDER, OUTPUT_FOLDER

# Ensure required directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Set environment variable for Coqui TTS
os.environ["COQUI_TOS_AGREED"] = "1"

def main():
    """Main entry point for the desktop application"""
    # Create the Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("Hypnosis Audio Generator")
    app.setStyle("Fusion")  # Use Fusion style for consistent look across platforms

    # Create and show the main window
    main_window = MainWindow()
    main_window.show()

    # Start the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
