import logging
import os
import uuid

from PyQt6.QtCore import pyqtSignal, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTextEdit, QComboBox, QRadioButton, QFileDialog,
    QMessageBox, QProgressBar, QGroupBox, QFormLayout, QButtonGroup,
    QApplication
)

from app.config import LANGUAGES, SAMPLE_VOICES, OUTPUT_FOLDER
from app.desktop.task_manager import TaskManager
from app.models.routine import get_routine
from app.utils import allowed_file


class RoutineEditorWidget(QWidget):
    """Widget for creating and editing routines"""

    # Define signals
    save_completed = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing RoutineEditorWidget")

        # Initialize variables
        self.routine_id = None
        self.voice_path = None
        self.output_filename = None
        self.task_manager = TaskManager()

        # Set up the layout
        self.layout = QVBoxLayout(self)

        # Create the form
        self.setup_form()

        # Create the button bar
        self.setup_button_bar()

        # Create the status section
        self.setup_status_section()

        # Create the result section
        self.setup_result_section()

        # Connect task manager signals
        self.task_manager.task_started.connect(self.on_task_started)
        self.task_manager.task_progress.connect(self.on_task_progress)
        self.task_manager.task_completed.connect(self.on_task_completed)
        self.task_manager.task_failed.connect(self.on_task_failed)

        self.logger.info("RoutineEditorWidget initialized")

    def setup_form(self):
        """Set up the form for routine data"""
        form_group = QGroupBox("Routine Information")
        form_layout = QFormLayout()

        # Routine Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter a name for this routine")
        form_layout.addRow("Routine Name:", self.name_input)

        # Hypnosis Script
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Enter your hypnosis script here...")
        self.text_input.setMinimumHeight(200)
        form_layout.addRow("Hypnosis Script:", self.text_input)

        # Help text for script
        help_label = QLabel("Use line breaks for a 2-second pause. Insert [break] where you want a 5-second pause in the audio.")
        help_label.setStyleSheet("color: gray; font-style: italic;")
        form_layout.addRow("", help_label)

        # Language
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        form_layout.addRow("Language:", self.language_combo)

        # Voice Selection
        voice_group = QGroupBox("Voice Selection")
        voice_layout = QVBoxLayout()

        self.voice_type_group = QButtonGroup(self)

        # Sample voice option
        self.sample_voice_radio = QRadioButton("Use sample voice")
        self.sample_voice_radio.setChecked(True)
        self.voice_type_group.addButton(self.sample_voice_radio, 1)
        voice_layout.addWidget(self.sample_voice_radio)

        # Sample voice selector
        self.sample_voice_combo = QComboBox()
        for voice_id, voice in SAMPLE_VOICES.items():
            self.sample_voice_combo.addItem(voice['name'], voice_id)
        voice_layout.addWidget(self.sample_voice_combo)

        # Upload voice option
        self.upload_voice_radio = QRadioButton("Upload your own voice reference")
        self.voice_type_group.addButton(self.upload_voice_radio, 2)
        voice_layout.addWidget(self.upload_voice_radio)

        # Upload voice file selector
        upload_layout = QHBoxLayout()
        self.voice_file_path = QLineEdit()
        self.voice_file_path.setReadOnly(True)
        self.voice_file_path.setPlaceholderText("No file selected")
        upload_layout.addWidget(self.voice_file_path)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.on_browse_clicked)
        upload_layout.addWidget(self.browse_button)

        voice_layout.addLayout(upload_layout)

        # Help text for voice upload
        upload_help = QLabel("Upload a short audio clip (5-10 seconds) of the voice you want to mimic.")
        upload_help.setStyleSheet("color: gray; font-style: italic;")
        voice_layout.addWidget(upload_help)

        voice_group.setLayout(voice_layout)
        form_layout.addRow("", voice_group)

        # Connect radio buttons to enable/disable appropriate controls
        self.sample_voice_radio.toggled.connect(self.on_voice_type_changed)

        form_group.setLayout(form_layout)
        self.layout.addWidget(form_group)

    def setup_button_bar(self):
        """Set up the button bar at the bottom of the form"""
        button_layout = QHBoxLayout()

        # Save button (saves without generating)
        self.save_routine_button = QPushButton("Save")
        self.save_routine_button.clicked.connect(self.on_save_routine_clicked)
        button_layout.addWidget(self.save_routine_button)

        # Generate button
        self.generate_button = QPushButton("Generate Hypnosis Audio")
        self.generate_button.clicked.connect(self.on_generate_clicked)
        button_layout.addWidget(self.generate_button)

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        button_layout.addWidget(self.cancel_button)

        self.layout.addLayout(button_layout)

    def setup_status_section(self):
        """Set up the status section for displaying generation progress"""
        self.status_group = QGroupBox("Generation Status")
        self.status_group.setVisible(False)
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

        self.status_group.setLayout(status_layout)
        self.layout.addWidget(self.status_group)

    def setup_result_section(self):
        """Set up the result section for displaying the generated audio"""
        self.result_group = QGroupBox("Generated Audio")
        self.result_group.setVisible(False)
        result_layout = QVBoxLayout()

        # Success message
        success_label = QLabel("Your hypnosis audio is ready! You can listen to it below or save it to your device.")
        result_layout.addWidget(success_label)

        # Media player
        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        # Audio controls
        audio_layout = QHBoxLayout()

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.on_play_clicked)
        audio_layout.addWidget(self.play_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.on_stop_clicked)
        audio_layout.addWidget(self.stop_button)

        self.save_audio_button = QPushButton("Save Audio to File")
        self.save_audio_button.clicked.connect(self.on_save_clicked)
        audio_layout.addWidget(self.save_audio_button)

        result_layout.addLayout(audio_layout)

        self.result_group.setLayout(result_layout)
        self.layout.addWidget(self.result_group)

    def clear(self):
        """Clear all form fields"""
        self.routine_id = None
        self.voice_path = None
        self.output_filename = None

        self.name_input.clear()
        self.text_input.clear()
        self.language_combo.setCurrentIndex(0)  # Default to first language
        self.sample_voice_radio.setChecked(True)
        self.sample_voice_combo.setCurrentIndex(0)  # Default to first sample voice
        self.voice_file_path.clear()

        self.status_group.setVisible(False)
        self.result_group.setVisible(False)

        self.generate_button.setEnabled(True)

    def load_routine(self, routine_id):
        """Load an existing routine into the form"""
        self.logger.info(f"Loading routine: {routine_id}")

        routine = get_routine(routine_id)
        if not routine:
            self.logger.error(f"Routine not found: {routine_id}")
            QMessageBox.warning(self, "Error", "Routine not found.")
            return

        self.clear()

        self.routine_id = routine_id
        self.output_filename = routine.get('output_filename')

        # Set form values
        self.name_input.setText(routine.get('name', ''))
        self.text_input.setText(routine.get('text', ''))

        # Set language
        language_code = routine.get('language', 'en')
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == language_code:
                self.language_combo.setCurrentIndex(i)
                break

        # Set voice type and selection
        voice_type = routine.get('voice_type', 'sample')
        if voice_type == 'sample':
            self.sample_voice_radio.setChecked(True)
            voice_id = routine.get('voice_id', '')
            for i in range(self.sample_voice_combo.count()):
                if self.sample_voice_combo.itemData(i) == voice_id:
                    self.sample_voice_combo.setCurrentIndex(i)
                    break
        else:
            self.upload_voice_radio.setChecked(True)
            # Can't restore the uploaded file, user will need to re-upload

        # If there's an output file, show the result section
        if self.output_filename:
            self.show_result()

        self.logger.info(f"Routine loaded: {routine_id}")

    def on_voice_type_changed(self, checked):
        """Handle voice type radio button changes"""
        self.sample_voice_combo.setEnabled(self.sample_voice_radio.isChecked())
        self.voice_file_path.setEnabled(self.upload_voice_radio.isChecked())
        self.browse_button.setEnabled(self.upload_voice_radio.isChecked())

    def on_browse_clicked(self):
        """Handle click on the Browse button for voice file selection"""
        self.logger.info("Browse button clicked for voice file selection")

        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Audio Files (*.wav *.mp3 *.ogg)")

        if file_dialog.exec_():
            file_paths = file_dialog.selectedFiles()
            if file_paths:
                file_path = file_paths[0]
                self.logger.info(f"Selected voice file: {file_path}")

                # Validate file extension
                if not allowed_file(file_path):
                    self.logger.warning(f"Invalid file type: {file_path}")
                    QMessageBox.warning(self, "Error", "Invalid file type. Please select a WAV, MP3, or OGG file.")
                    return

                self.voice_path = file_path
                self.voice_file_path.setText(os.path.basename(file_path))

    def on_generate_clicked(self):
        """Handle click on the Generate button"""
        self.logger.info("Generate button clicked")

        # Validate inputs
        name = self.name_input.text().strip()
        text = self.text_input.toPlainText().strip()
        language = self.language_combo.currentData()

        if not text:
            QMessageBox.warning(self, "Error", "Please enter a hypnosis script.")
            return

        # Use a default name if none provided
        if not name:
            name = f"Routine {uuid.uuid4().hex[:8]}"

        # Get voice path based on selection
        voice_type = 'sample' if self.sample_voice_radio.isChecked() else 'upload'
        voice_id = None

        if voice_type == 'sample':
            voice_id = self.sample_voice_combo.currentData()
            voice_path = SAMPLE_VOICES[voice_id]['path']
        else:
            if not self.voice_path:
                QMessageBox.warning(self, "Error", "Please select a voice file.")
                return
            voice_path = self.voice_path

        # Disable the generate button to prevent multiple clicks
        self.generate_button.setEnabled(False)

        # Show the status section
        self.status_group.setVisible(True)
        self.result_group.setVisible(False)

        # Start the generation task
        self.task_manager.start_task(
            text=text,
            language=language,
            voice_path=voice_path,
            routine_name=name,
            routine_id=self.routine_id,
            voice_type=voice_type,
            voice_id=voice_id
        )

    def on_task_started(self):
        """Handle task start"""
        self.logger.info("Audio generation task started")
        self.status_label.setText("Generating your hypnosis audio... This may take a few minutes.")
        self.status_details.setText("Starting the generation process...")
        self.progress_bar.setValue(10)  # Initial progress
        QApplication.processEvents()

    def on_task_progress(self, progress, message):
        """Handle task progress updates"""
        self.logger.debug(f"Audio generation progress: {progress}%, {message}")
        self.progress_bar.setValue(progress)
        self.status_details.setText(message)
        QApplication.processEvents()

    def on_task_completed(self, result):
        """Handle task completion"""
        self.logger.info(f"Audio generation completed: {result}")

        # Update routine ID and output filename
        self.routine_id = result.get('routine_id')
        self.output_filename = result.get('filename')

        # Show the result section
        self.show_result()

        # Hide the status section
        self.status_group.setVisible(False)

        # Re-enable the generate button
        self.generate_button.setEnabled(True)

        # Don't emit the save_completed signal here to keep the routine open after generation

    def on_task_failed(self, error):
        """Handle task failure"""
        self.logger.error(f"Audio generation failed: {error}")

        # Hide the status section
        self.status_group.setVisible(False)

        # Show error message
        QMessageBox.critical(self, "Error", f"Failed to generate audio: {error}")

        # Re-enable the generate button
        self.generate_button.setEnabled(True)

    def show_result(self):
        """Show the result section with the generated audio"""
        if not self.output_filename:
            return

        # Set up the media player
        file_path = os.path.join(OUTPUT_FOLDER, self.output_filename)
        if os.path.exists(file_path):
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self.result_group.setVisible(True)
            self.logger.info(f"Audio file loaded: {file_path}")
        else:
            self.logger.warning(f"Audio file not found: {file_path}")
            QMessageBox.warning(self, "Error", f"Audio file not found: {self.output_filename}")

    def on_play_clicked(self):
        """Handle click on the Play button"""
        self.logger.info("Play button clicked")
        self.player.play()

    def on_stop_clicked(self):
        """Handle click on the Stop button"""
        self.logger.info("Stop button clicked")
        self.player.stop()

    def on_save_routine_clicked(self):
        """Handle click on the Save button (saves routine without generating audio)"""
        self.logger.info("Save routine button clicked")

        # Validate inputs
        name = self.name_input.text().strip()
        text = self.text_input.toPlainText().strip()
        language = self.language_combo.currentData()

        if not text:
            QMessageBox.warning(self, "Error", "Please enter a hypnosis script.")
            return

        # Use a default name if none provided
        if not name:
            name = f"Routine {uuid.uuid4().hex[:8]}"

        # Get voice type and ID based on selection
        voice_type = 'sample' if self.sample_voice_radio.isChecked() else 'upload'
        voice_id = None

        if voice_type == 'sample':
            voice_id = self.sample_voice_combo.currentData()
        else:
            if not self.voice_path:
                QMessageBox.warning(self, "Error", "Please select a voice file.")
                return

        # Save the routine to the database
        try:
            from app.models.routine import add_routine, update_routine, get_routine

            if self.routine_id and get_routine(self.routine_id):
                # Update existing routine
                self.logger.info(f"Updating existing routine {self.routine_id}")
                routine = update_routine(
                    self.routine_id,
                    name=name,
                    text=text,
                    language=language,
                    voice_type=voice_type,
                    voice_id=voice_id
                )
                self.logger.info(f"Routine {self.routine_id} updated successfully")
            else:
                # Create new routine
                self.logger.info(f"Creating new routine")
                routine = add_routine(
                    name=name,
                    text=text,
                    language=language,
                    voice_type=voice_type,
                    voice_id=voice_id
                )
                self.routine_id = routine['id']
                self.logger.info(f"New routine created with ID {routine['id']}")

            # Show success message
            QMessageBox.information(self, "Success", "Routine saved successfully.")

            # Emit the save_completed signal to update the UI
            self.save_completed.emit()

        except Exception as e:
            self.logger.error(f"Error saving routine: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save routine: {str(e)}")

    def on_save_clicked(self):
        """Handle click on the Save Audio button"""
        self.logger.info("Save Audio button clicked")

        if not self.output_filename:
            QMessageBox.warning(self, "Error", "No audio file available.")
            return

        # Get the source file path
        source_path = os.path.join(OUTPUT_FOLDER, self.output_filename)
        if not os.path.exists(source_path):
            QMessageBox.warning(self, "Error", f"Audio file not found: {self.output_filename}")
            return

        # Open file dialog to select destination
        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix("wav")
        file_dialog.setNameFilter("WAV Files (*.wav)")

        suggested_name = self.name_input.text().strip()
        if not suggested_name:
            suggested_name = "hypnosis_routine"

        file_dialog.selectFile(f"{suggested_name}.wav")

        if file_dialog.exec_():
            file_paths = file_dialog.selectedFiles()
            if file_paths:
                dest_path = file_paths[0]
                self.logger.info(f"Saving audio to: {dest_path}")

                try:
                    # Copy the file
                    import shutil
                    shutil.copy2(source_path, dest_path)
                    self.logger.info(f"Audio saved to: {dest_path}")
                    QMessageBox.information(self, "Success", f"Audio saved to: {dest_path}")
                except Exception as e:
                    self.logger.error(f"Error saving audio: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Failed to save audio: {str(e)}")

    def on_cancel_clicked(self):
        """Handle click on the Cancel button"""
        self.logger.info("Cancel button clicked")

        # If a task is running, confirm cancellation
        if self.task_manager.is_task_running():
            reply = QMessageBox.question(
                self, 
                "Confirm Cancellation",
                "A generation task is in progress. Are you sure you want to cancel?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.task_manager.cancel_task()
                self.cancel_requested.emit()

            return

        # Otherwise, just emit the cancel signal
        self.cancel_requested.emit()
