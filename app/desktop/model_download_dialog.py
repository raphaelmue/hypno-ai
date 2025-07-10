import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QDialogButtonBox, QMessageBox
)

from app.tts_model.model import get_model_status, start_model_download, is_model_downloaded, get_model_dir


class ModelDownloadDialog(QDialog):
    """Dialog for downloading the TTS model"""

    # Signal emitted when the model download is complete
    download_complete = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing ModelDownloadDialog")

        # Set up dialog properties
        self.setWindowTitle("TTS Model Download")
        self.setMinimumWidth(500)
        self.setMinimumHeight(200)

        # Create the main layout
        self.layout = QVBoxLayout(self)

        # Create the info label
        self.info_label = QLabel(
            "The text-to-speech model is required for generating audio. "
            "Please download it before using the application."
        )
        self.info_label.setWordWrap(True)
        self.layout.addWidget(self.info_label)

        # Create the model location label
        self.location_label = QLabel(f"Model will be downloaded to: {get_model_dir()}")
        self.location_label.setWordWrap(True)
        self.layout.addWidget(self.location_label)

        # Create the progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        # Create the status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label)

        # Create the button layout
        self.button_layout = QHBoxLayout()

        # Download button
        self.download_button = QPushButton("Download Model")
        self.download_button.clicked.connect(self.start_download)
        self.button_layout.addWidget(self.download_button)

        # Skip button (for development/testing)
        self.skip_button = QPushButton("Skip (Not Recommended)")
        self.skip_button.clicked.connect(self.skip_download)
        self.button_layout.addWidget(self.skip_button)

        # Add the button layout to the main layout
        self.layout.addLayout(self.button_layout)

        # Create the button box
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Close).setEnabled(False)
        self.layout.addWidget(self.button_box)

        # Set up a timer to check the download status
        from PyQt6.QtCore import QTimer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_download_status)

        # Check if the model is already downloaded
        self.check_initial_status()

        self.logger.info("ModelDownloadDialog initialized")

    def check_initial_status(self):
        """Check if the model is already downloaded"""
        if is_model_downloaded():
            self.status_label.setText("Model is already downloaded.")
            self.download_button.setText("Re-download Model")
            self.button_box.button(QDialogButtonBox.StandardButton.Close).setEnabled(True)
            self.skip_button.setEnabled(False)

            # Update info label for re-download case
            self.info_label.setText(
                "The text-to-speech model is already downloaded. "
                "You can re-download it if needed."
            )
        else:
            self.status_label.setText("Model is not downloaded.")

    def start_download(self):
        """Start downloading the model"""
        self.logger.info("Starting model download")

        # Update UI
        self.download_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting download...")

        # Reset the info label to the downloading state
        self.info_label.setText(
            "The text-to-speech model is required for generating audio. "
            "Please wait while the model is being downloaded."
        )

        # Start the download
        start_model_download()

        # Start the timer to check the download status
        self.timer.start(1000)  # Check every second

    def check_download_status(self):
        """Check the status of the model download"""
        status = get_model_status()

        if status['status'] == 'downloading':
            # Update progress (since we don't have actual progress, use a simple animation)
            current_value = self.progress_bar.value()
            if current_value < 95:  # Don't go to 100% until it's actually done
                self.progress_bar.setValue(current_value + 1)
            self.status_label.setText("Downloading model... This may take a few minutes.")

        elif status['status'] == 'downloaded':
            # Download complete
            self.progress_bar.setValue(100)
            self.status_label.setText("Model downloaded successfully!")
            self.timer.stop()
            self.button_box.button(QDialogButtonBox.StandardButton.Close).setEnabled(True)
            self.download_complete.emit()

        elif status['status'] == 'failed':
            # Download failed
            self.progress_bar.setVisible(False)
            self.status_label.setText(f"Download failed: {status['error']}")
            self.download_button.setEnabled(True)
            self.skip_button.setEnabled(True)
            self.timer.stop()

    def skip_download(self):
        """Skip the model download (not recommended)"""
        self.logger.warning("User chose to skip model download")

        # Show a warning message
        reply = QMessageBox.warning(
            self,
            "Skip Model Download",
            "The application requires the TTS model to generate audio. "
            "Without it, you won't be able to generate audio files.\n\n"
            "Are you sure you want to skip the download?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.accept()
