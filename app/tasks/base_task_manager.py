"""
Base task management system for audio generation tasks.
This module provides a unified task management system that can be used by different interfaces.
"""

import logging
import os
import threading
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Union

from app.audio import generate_audio
from app.models.routine import add_routine, update_routine, get_routine


class TaskProgressNotifier(ABC):
    """
    Abstract base class for task progress notification.
    Different interfaces can implement this class to handle progress notifications differently.
    """
    
    @abstractmethod
    def notify_started(self, task_id: str) -> None:
        """Notify that a task has started"""
        pass
        
    @abstractmethod
    def notify_progress(self, task_id: str, percent: int, message: str) -> None:
        """Notify about task progress"""
        pass
        
    @abstractmethod
    def notify_completed(self, task_id: str, result: Dict[str, Any]) -> None:
        """Notify that a task has completed successfully"""
        pass
        
    @abstractmethod
    def notify_failed(self, task_id: str, error: str) -> None:
        """Notify that a task has failed"""
        pass


class BaseTaskManager:
    """
    Base class for task management.
    Handles the common functionality for managing audio generation tasks.
    """
    
    def __init__(self, progress_notifier: TaskProgressNotifier):
        """
        Initialize the task manager.
        
        Args:
            progress_notifier: An instance of TaskProgressNotifier for handling progress notifications
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing BaseTaskManager")
        
        # Store the progress notifier
        self.progress_notifier = progress_notifier
        
        # Initialize variables
        self.current_task = None
        self.cancel_requested = False
        
        self.logger.info("BaseTaskManager initialized")
    
    def is_task_running(self) -> bool:
        """
        Check if a task is currently running.
        
        Returns:
            bool: True if a task is running, False otherwise
        """
        return self.current_task is not None and self.current_task.is_alive()
    
    def cancel_task(self) -> None:
        """Request cancellation of the current task"""
        if self.is_task_running():
            self.logger.info("Task cancellation requested")
            self.cancel_requested = True
    
    def start_task(self, text: str, language: str, voice_path: str, routine_name: str, 
                  routine_id: Optional[str] = None, voice_type: Optional[str] = None, 
                  voice_id: Optional[str] = None, num_threads: int = 4) -> str:
        """
        Start a new audio generation task in a background thread.
        
        Args:
            text: Text to convert to audio
            language: Language code
            voice_path: Path to the voice sample file
            routine_name: Name of the routine
            routine_id: ID of the routine if updating an existing one
            voice_type: Type of voice (sample or upload)
            voice_id: ID of the sample voice if using a sample
            num_threads: Number of threads to use for audio generation
            
        Returns:
            str: ID of the created task
        """
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        self.logger.info(f"Starting task {task_id} for routine '{routine_name}'")
        
        # Reset cancellation flag
        self.cancel_requested = False
        
        # Create and start the task thread
        self.current_task = threading.Thread(
            target=self._run_task,
            args=(task_id, text, language, voice_path, routine_name, routine_id, voice_type, voice_id, num_threads)
        )
        self.current_task.daemon = True
        self.current_task.start()
        
        # Notify that the task has started
        self.progress_notifier.notify_started(task_id)
        
        self.logger.info(f"Task thread started for routine '{routine_name}'")
        return task_id
    
    def _cleanup_temp_file(self, voice_type: Optional[str], voice_path: str) -> None:
        """
        Clean up temporary voice file if needed.
        
        Args:
            voice_type: Type of voice (sample or upload)
            voice_path: Path to the voice sample file
        """
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            self.logger.debug(f"Cleaning up temporary voice file: {voice_path}")
            try:
                os.remove(voice_path)
            except Exception as e:
                self.logger.error(f"Error cleaning up temporary file: {str(e)}")
    
    def _check_cancellation(self, task_id: str, message: str) -> bool:
        """
        Check if task cancellation was requested.
        
        Args:
            task_id: ID of the task
            message: Message to log if cancelled
            
        Returns:
            bool: True if task was cancelled, False otherwise
        """
        if self.cancel_requested:
            self.logger.info(message)
            self.progress_notifier.notify_failed(task_id, "Task cancelled")
            # Reset the current task to None to properly clean up the task state
            self.current_task = None
            # Reset the cancellation flag
            self.cancel_requested = False
            return True
        return False
    
    def _run_task(self, task_id: str, text: str, language: str, voice_path: str, 
                 routine_name: str, routine_id: Optional[str] = None, 
                 voice_type: Optional[str] = None, voice_id: Optional[str] = None,
                 num_threads: int = 4) -> None:
        """
        Run the audio generation task in a background thread.
        
        Args:
            task_id: ID of the task
            text: Text to convert to audio
            language: Language code
            voice_path: Path to the voice sample file
            routine_name: Name of the routine
            routine_id: ID of the routine if updating an existing one
            voice_type: Type of voice (sample or upload)
            voice_id: ID of the sample voice if using a sample
            num_threads: Number of threads to use for audio generation
        """
        self.logger.info(f"Running task {task_id} for routine '{routine_name}'")
        
        try:
            # Update progress
            self._update_progress(task_id, 0, "Preparing to generate audio...")
            
            # Check for cancellation
            if self._check_cancellation(task_id, "Task cancelled before audio generation"):
                return
            
            # Generate the audio file
            self.logger.info(f"Generating audio for routine '{routine_name}'")
            self._update_progress(task_id, 0, "Generating audio...")
            
            # Define a progress callback function
            def progress_callback(percent, message):
                self._update_progress(task_id, percent, message)
                # Check for cancellation during audio generation
                return not self.cancel_requested
            
            # Generate the audio
            output_filename = self._generate_audio(text, language, voice_path, routine_name, num_threads, progress_callback)
            
            self.logger.info(f"Audio generation completed: {output_filename}")
            self._update_progress(task_id, 100, "Audio generation completed. Saving routine...")
            
            # Check for cancellation
            if self._check_cancellation(task_id, "Task cancelled after audio generation"):
                return
            
            # Clean up temporary uploaded file if needed
            self._cleanup_temp_file(voice_type, voice_path)
            
            # Store or update the routine
            routine = self._save_routine(routine_id, output_filename, routine_name, text, language, voice_type, voice_id)
            
            # Update progress
            self._update_progress(task_id, 90, "Finalizing...")
            
            # Check for cancellation
            if self._check_cancellation(task_id, "Task cancelled after routine save"):
                return
            
            # Prepare result
            result = {
                'routine_id': routine['id'],
                'name': routine['name'],
                'filename': output_filename
            }
            
            # Notify that the task has completed
            self._update_progress(task_id, 100, "Task completed successfully")
            self.progress_notifier.notify_completed(task_id, result)
            
            self.logger.info(f"Task completed successfully for routine '{routine_name}'")
            
        except Exception as e:
            # Log the error
            self.logger.error(f"Error in task: {str(e)}", exc_info=True)
            
            # Clean up temporary uploaded file if needed
            self._cleanup_temp_file(voice_type, voice_path)
            
            # Notify that the task has failed
            self.progress_notifier.notify_failed(task_id, str(e))
    
    def _update_progress(self, task_id: str, percent: int, message: str) -> None:
        """
        Update task progress.
        
        Args:
            task_id: ID of the task
            percent: Progress percentage (0-100)
            message: Progress message
        """
        self.progress_notifier.notify_progress(task_id, percent, message)
    
    def _generate_audio(self, text: str, language: str, voice_path: str, 
                       routine_name: str, num_threads: int,
                       progress_callback: Callable[[int, str], bool]) -> str:
        """
        Generate audio from text.
        
        Args:
            text: Text to convert to audio
            language: Language code
            voice_path: Path to the voice sample file
            routine_name: Name of the routine
            num_threads: Number of threads to use for audio generation
            progress_callback: Callback function for progress updates
            
        Returns:
            str: Filename of the generated audio
        """
        return generate_audio(
            text=text,
            language=language,
            voice_path=voice_path,
            routine_name=routine_name,
            num_threads=num_threads,
            progress_callback=progress_callback
        )
    
    def _save_routine(self, routine_id: Optional[str], output_filename: str, 
                     routine_name: str, text: str, language: str,
                     voice_type: Optional[str], voice_id: Optional[str]) -> Dict[str, Any]:
        """
        Save or update a routine.
        
        Args:
            routine_id: ID of the routine if updating an existing one
            output_filename: Filename of the generated audio
            routine_name: Name of the routine
            text: Text content of the routine
            language: Language code
            voice_type: Type of voice (sample or upload)
            voice_id: ID of the sample voice if using a sample
            
        Returns:
            Dict[str, Any]: The saved routine data
        """
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
        
        return routine