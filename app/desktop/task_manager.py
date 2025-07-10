import logging
import os
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from app.audio import generate_audio
from app.models.routine import add_routine, update_routine, get_routine


class TaskManager(QObject):
    """
    Manager for background tasks in the desktop application.
    Handles audio generation tasks and provides signals for task status updates.
    """

    # Define signals
    task_started = pyqtSignal()
    task_progress = pyqtSignal(int, str)  # progress percentage, message
    task_completed = pyqtSignal(dict)  # result dictionary
    task_failed = pyqtSignal(str)  # error message

    def __init__(self):
        super().__init__()

        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing TaskManager")

        # Initialize variables
        self.current_task = None
        self.cancel_requested = False

        self.logger.info("TaskManager initialized")

    def is_task_running(self):
        """Check if a task is currently running"""
        return self.current_task is not None and self.current_task.is_alive()

    def cancel_task(self):
        """Request cancellation of the current task"""
        if self.is_task_running():
            self.logger.info("Task cancellation requested")
            self.cancel_requested = True

    def start_task(self, text, language, voice_path, routine_name, routine_id=None, voice_type=None, voice_id=None):
        """
        Start a new audio generation task in a background thread

        Args:
            text (str): Text to convert to audio
            language (str): Language code
            voice_path (str): Path to the voice sample file
            routine_name (str): Name of the routine
            routine_id (str, optional): ID of the routine if updating an existing one
            voice_type (str, optional): Type of voice (sample or upload)
            voice_id (str, optional): ID of the sample voice if using a sample
        """
        self.logger.info(f"Starting task for routine '{routine_name}'")

        # Reset cancellation flag
        self.cancel_requested = False

        # Create and start the task thread
        self.current_task = threading.Thread(
            target=self._run_task,
            args=(text, language, voice_path, routine_name, routine_id, voice_type, voice_id)
        )
        self.current_task.daemon = True
        self.current_task.start()

        # Emit the task started signal
        self.task_started.emit()

        self.logger.info(f"Task thread started for routine '{routine_name}'")

    def _cleanup_temp_file(self, voice_type, voice_path):
        """
        Clean up temporary voice file if needed

        Args:
            voice_type (str): Type of voice (sample or upload)
            voice_path (str): Path to the voice sample file
        """
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            self.logger.debug(f"Cleaning up temporary voice file: {voice_path}")
            try:
                os.remove(voice_path)
            except Exception as e:
                self.logger.error(f"Error cleaning up temporary file: {str(e)}")

    def _check_cancellation(self, message):
        """
        Check if task cancellation was requested

        Args:
            message (str): Message to log if cancelled

        Returns:
            bool: True if task was cancelled, False otherwise
        """
        if self.cancel_requested:
            self.logger.info(message)
            self.task_failed.emit("Task cancelled")
            return True
        return False

    def _run_task(self, text, language, voice_path, routine_name, routine_id=None, voice_type=None, voice_id=None):
        """
        Run the audio generation task in a background thread

        Args:
            text (str): Text to convert to audio
            language (str): Language code
            voice_path (str): Path to the voice sample file
            routine_name (str): Name of the routine
            routine_id (str, optional): ID of the routine if updating an existing one
            voice_type (str, optional): Type of voice (sample or upload)
            voice_id (str, optional): ID of the sample voice if using a sample
        """
        self.logger.info(f"Running task for routine '{routine_name}'")

        try:
            # Update progress
            self.task_progress.emit(20, "Preparing to generate audio...")

            # Check for cancellation
            if self._check_cancellation("Task cancelled before audio generation"):
                return

            # Generate the audio file
            self.logger.info(f"Generating audio for routine '{routine_name}'")
            self.task_progress.emit(30, "Generating audio...")

            # Define a progress callback function
            def progress_callback(percent, message):
                self.task_progress.emit(percent, message)

            output_filename = generate_audio(
                text=text,
                language=language,
                voice_path=voice_path,
                routine_name=routine_name,
                progress_callback=progress_callback
            )

            self.logger.info(f"Audio generation completed: {output_filename}")
            self.task_progress.emit(70, "Audio generation completed. Saving routine...")

            # Check for cancellation
            if self._check_cancellation("Task cancelled after audio generation"):
                return

            # Clean up temporary uploaded file if needed
            self._cleanup_temp_file(voice_type, voice_path)

            # Store or update the routine
            if routine_id and get_routine(routine_id):
                # Update existing routine
                self.logger.info(f"Updating existing routine {routine_id}")
                routine = update_routine(
                    routine_id,
                    output_filename=output_filename,
                    name=routine_name,
                    text=text,
                    language=language,
                    voice_type=voice_type,
                    voice_id=voice_id
                )
                self.logger.info(f"Routine {routine_id} updated successfully")
            else:
                # Create new routine
                self.logger.info(f"Creating new routine")
                routine = add_routine(
                    name=routine_name,
                    text=text,
                    language=language,
                    voice_type=voice_type,
                    voice_id=voice_id,
                    output_filename=output_filename
                )
                self.logger.info(f"New routine created with ID {routine['id']}")

            # Update progress
            self.task_progress.emit(90, "Finalizing...")

            # Check for cancellation
            if self._check_cancellation("Task cancelled after routine save"):
                return

            # Prepare result
            result = {
                'routine_id': routine['id'],
                'name': routine['name'],
                'filename': output_filename
            }

            # Emit the task completed signal
            self.task_progress.emit(100, "Task completed successfully")
            self.task_completed.emit(result)

            self.logger.info(f"Task completed successfully for routine '{routine_name}'")

        except Exception as e:
            # Log the error
            self.logger.error(f"Error in task: {str(e)}", exc_info=True)

            # Clean up temporary uploaded file if needed
            self._cleanup_temp_file(voice_type, voice_path)

            # Emit the task failed signal
            self.task_failed.emit(str(e))
