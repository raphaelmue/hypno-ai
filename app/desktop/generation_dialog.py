import logging
import os
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QGroupBox, QTextEdit, QApplication, QMessageBox
)

class CollapsibleSection(QGroupBox):
    """A collapsible section widget that can be expanded or collapsed."""

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self.on_toggle)

        # Main layout
        self.main_layout = QVBoxLayout(self)

        # Content widget
        self.content = QVBoxLayout()
        self.main_layout.addLayout(self.content)

        # Initially collapsed
        self.setFlat(True)
        self.content_visible = False
        self.update_collapse_state()

    def on_toggle(self, checked):
        """Handle toggle event."""
        self.content_visible = checked
        self.update_collapse_state()

    def update_collapse_state(self):
        """Update the visibility of content based on collapse state."""
        for i in range(self.content.count()):
            item = self.content.itemAt(i)
            if item.widget():
                item.widget().setVisible(self.content_visible)

    def addWidget(self, widget):
        """Add a widget to the content layout."""
        self.content.addWidget(widget)
        widget.setVisible(self.content_visible)


class GenerationDialog(QDialog):
    """Dialog for generating audio with progress and log display."""

    def __init__(self, parent=None, task_manager=None):
        super().__init__(parent)

        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing GenerationDialog")

        # Store task manager
        self.task_manager = task_manager

        # Set window properties
        self.setWindowTitle("Generating Audio")
        self.setMinimumSize(QSize(500, 300))

        # Set up the layout
        self.layout = QVBoxLayout(self)

        # Create the status section
        self.setup_status_section()

        # Create the log section
        self.setup_log_section()

        # Create the button bar
        self.setup_button_bar()

        # Connect task manager signals
        if self.task_manager:
            self.task_manager.task_started.connect(self.on_task_started)
            self.task_manager.task_progress.connect(self.on_task_progress)
            self.task_manager.task_completed.connect(self.on_task_completed)
            self.task_manager.task_failed.connect(self.on_task_failed)

        self.logger.info("GenerationDialog initialized")

    def setup_status_section(self):
        """Set up the status section for displaying generation progress."""
        status_layout = QVBoxLayout()

        # Status message
        self.status_label = QLabel("Generating your hypnosis audio... This may take a few minutes.")
        status_layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)

        # Status details
        self.status_details = QLabel("Starting the generation process...")
        self.status_details.setStyleSheet("color: gray; font-style: italic;")
        status_layout.addWidget(self.status_details)

        self.layout.addLayout(status_layout)

    def setup_log_section(self):
        """Set up the collapsible log section."""
        self.log_section = CollapsibleSection("Log", self)

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        self.log_section.addWidget(self.log_text)

        self.layout.addWidget(self.log_section)

    def setup_button_bar(self):
        """Set up the button bar."""
        button_layout = QHBoxLayout()

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        button_layout.addWidget(self.cancel_button)

        # Spacer
        button_layout.addStretch()

        # Close button (initially disabled)
        self.close_button = QPushButton("Close")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)

        self.layout.addLayout(button_layout)

    def start_generation(self, text, language, voice_path, routine_name, routine_id=None, voice_type=None, voice_id=None):
        """Start the generation process."""
        self.logger.info("Starting generation process")

        # Log the parameters
        self.add_log_message(f"Starting generation with parameters:")
        self.add_log_message(f"- Routine name: {routine_name}")
        self.add_log_message(f"- Language: {language}")
        self.add_log_message(f"- Voice type: {voice_type}")
        self.add_log_message(f"- Text length: {len(text)} characters")

        # Start the task
        self.task_manager.start_task(
            text=text,
            language=language,
            voice_path=voice_path,
            routine_name=routine_name,
            routine_id=routine_id,
            voice_type=voice_type,
            voice_id=voice_id
        )

    def on_task_started(self):
        """Handle task start."""
        self.logger.info("Audio generation task started")
        self.status_label.setText("Generating your hypnosis audio... This may take a few minutes.")
        self.status_details.setText("Starting the generation process...")
        self.progress_bar.setValue(10)  # Initial progress
        self.add_log_message("Generation task started")
        QApplication.processEvents()

    def on_task_progress(self, progress, message):
        """Handle task progress updates."""
        self.logger.debug(f"Audio generation progress: {progress}%, {message}")
        self.progress_bar.setValue(progress)
        self.status_details.setText(message)
        self.add_log_message(f"Progress {progress}%: {message}")
        QApplication.processEvents()

    def on_task_completed(self, result):
        """Handle task completion."""
        self.logger.info(f"Audio generation completed: {result}")

        # Update UI
        self.status_label.setText("Generation completed successfully!")
        self.progress_bar.setValue(100)
        self.status_details.setText("Your hypnosis audio is ready.")

        # Log the result
        self.add_log_message("Generation completed successfully")
        self.add_log_message(f"Output filename: {result.get('filename')}")

        # Enable close button and disable cancel button
        self.close_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        # Store the result for retrieval by the parent
        self.result = result

    def on_task_failed(self, error):
        """Handle task failure."""
        self.logger.error(f"Audio generation failed: {error}")

        # Update UI
        self.status_label.setText("Generation failed!")
        self.status_details.setText(f"Error: {error}")

        # Log the error
        self.add_log_message(f"ERROR: Generation failed: {error}")

        # Enable close button and disable cancel button
        self.close_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        # Set result to None
        self.result = None

    def on_cancel_clicked(self):
        """Handle cancel button click."""
        self.logger.info("Cancel button clicked, showing confirmation dialog")

        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Cancellation",
            "Are you sure you want to cancel the generation process?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info("Generation cancellation confirmed by user")

            # Cancel the task
            if self.task_manager and self.task_manager.is_task_running():
                self.task_manager.cancel_task()
                self.add_log_message("Generation cancelled by user")

            # Close the dialog
            self.reject()
        else:
            self.logger.info("Generation cancellation declined by user")
            self.add_log_message("Cancellation declined, continuing generation")

    def add_log_message(self, message):
        """Add a message to the log."""
        self.log_text.append(message)
        # Scroll to the bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def get_result(self):
        """Get the generation result."""
        return getattr(self, 'result', None)
