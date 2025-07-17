"""
File-based implementation of the task management system.
This module provides a TaskManager class that uses file-based persistence for task progress notifications.
"""

import json
import logging
import os
import time
from typing import Any, Dict, Optional

from app.tasks.base_task_manager import BaseTaskManager, TaskProgressNotifier


# Create a directory to store task data
TASKS_FOLDER = os.path.join('app', 'static', 'tasks')
os.makedirs(TASKS_FOLDER, exist_ok=True)


class FileTaskProgressNotifier(TaskProgressNotifier):
    """
    Implementation of TaskProgressNotifier that uses file-based persistence.
    """
    
    def __init__(self):
        """Initialize the notifier"""
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing FileTaskProgressNotifier")
    
    def _get_task_file_path(self, task_id: str) -> str:
        """
        Get the file path for a task's data.
        
        Args:
            task_id: ID of the task
            
        Returns:
            str: Path to the task file
        """
        return os.path.join(TASKS_FOLDER, f"{task_id}.json")
    
    def _save_task(self, task_id: str, task_data: Dict[str, Any]) -> None:
        """
        Save task data to a file.
        
        Args:
            task_id: ID of the task
            task_data: Task data to save
        """
        file_path = self._get_task_file_path(task_id)
        try:
            with open(file_path, 'w') as f:
                json.dump(task_data, f)
            self.logger.debug(f"Task {task_id} saved to {file_path}")
        except Exception as e:
            self.logger.error(f"Error saving task {task_id} to {file_path}: {str(e)}")
            raise
    
    def _load_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Load task data from a file.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Dict[str, Any] or None: Task data if found, None otherwise
        """
        file_path = self._get_task_file_path(task_id)
        if not os.path.exists(file_path):
            self.logger.debug(f"Task file not found: {file_path}")
            return None
        try:
            with open(file_path, 'r') as f:
                task_data = json.load(f)
            self.logger.debug(f"Task {task_id} loaded from {file_path}")
            return task_data
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error loading task {task_id}: {str(e)}")
            return None
        except IOError as e:
            self.logger.error(f"IO error loading task {task_id}: {str(e)}")
            return None
    
    def notify_started(self, task_id: str) -> None:
        """
        Notify that a task has started.
        
        Args:
            task_id: ID of the task
        """
        self.logger.debug(f"Task {task_id} started")
        
        # Initialize task status
        task_data = {
            'status': 'processing',
            'result': None,
            'error': None,
            'created_at': time.time(),
            'progress': {
                'percent': 0,
                'message': 'Task started'
            }
        }
        
        # Save task data to file
        self._save_task(task_id, task_data)
    
    def notify_progress(self, task_id: str, percent: int, message: str) -> None:
        """
        Notify about task progress.
        
        Args:
            task_id: ID of the task
            percent: Progress percentage (0-100)
            message: Progress message
        """
        self.logger.debug(f"Task {task_id} progress: {percent}% - {message}")
        
        # Load current task data
        task_data = self._load_task(task_id)
        if not task_data:
            self.logger.error(f"Task data not found for task {task_id}")
            return
        
        # Update progress
        task_data['progress'] = {
            'percent': percent,
            'message': message
        }
        
        # Save updated task data
        self._save_task(task_id, task_data)
    
    def notify_completed(self, task_id: str, result: Dict[str, Any]) -> None:
        """
        Notify that a task has completed successfully.
        
        Args:
            task_id: ID of the task
            result: Result data
        """
        self.logger.debug(f"Task {task_id} completed with result: {result}")
        
        # Load current task data
        task_data = self._load_task(task_id)
        if not task_data:
            self.logger.error(f"Task data not found for task {task_id}")
            return
        
        # Update task status to completed with result
        task_data['status'] = 'completed'
        task_data['result'] = result
        task_data['progress'] = {
            'percent': 100,
            'message': 'Task completed successfully'
        }
        
        # Save updated task data
        self._save_task(task_id, task_data)
    
    def notify_failed(self, task_id: str, error: str) -> None:
        """
        Notify that a task has failed.
        
        Args:
            task_id: ID of the task
            error: Error message
        """
        self.logger.debug(f"Task {task_id} failed with error: {error}")
        
        # Load current task data
        task_data = self._load_task(task_id)
        if not task_data:
            self.logger.error(f"Task data not found for task {task_id}")
            return
        
        # Update task status to failed with error message
        task_data['status'] = 'failed'
        task_data['error'] = error
        task_data['progress'] = {
            'percent': 0,
            'message': f'Task failed: {error}'
        }
        
        # Save updated task data
        self._save_task(task_id, task_data)


class TaskManager(BaseTaskManager):
    """
    File-based implementation of BaseTaskManager.
    Uses file-based persistence for task progress notifications.
    """
    
    def __init__(self):
        """Initialize the task manager"""
        # Create a notifier
        self.notifier = FileTaskProgressNotifier()
        
        # Initialize the base class
        super().__init__(self.notifier)
        
        self.logger.info("File-based TaskManager initialized")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Dict[str, Any] or None: Task data if found, None otherwise
        """
        return self.notifier._load_task(task_id)


def clean_old_tasks() -> int:
    """
    Remove completed and failed tasks that are older than a certain threshold.
    This would be called periodically to prevent disk space issues.
    
    Returns:
        int: Number of removed task files
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting cleanup of old task files")
    removed_count = 0
    error_count = 0
    
    # Get all task files
    task_files = [f for f in os.listdir(TASKS_FOLDER) if f.endswith('.json')]
    logger.info(f"Found {len(task_files)} task files to check")
    
    for filename in task_files:
        file_path = os.path.join(TASKS_FOLDER, filename)
        try:
            # Check if the file is older than 24 hours
            file_age = os.path.getmtime(file_path)
            age_in_hours = (time.time() - file_age) / 3600
            
            if age_in_hours > 24:  # 24 hours
                logger.debug(f"Removing old task file: {filename} (age: {age_in_hours:.1f} hours)")
                os.remove(file_path)
                removed_count += 1
        except (OSError, IOError) as e:
            logger.error(f"Error checking/removing task file {filename}: {str(e)}")
            error_count += 1
            continue
    
    logger.info(f"Task cleanup completed: removed {removed_count} files, encountered {error_count} errors")
    return removed_count


# Create a singleton instance of the task manager
_task_manager = None


def get_task_manager() -> TaskManager:
    """
    Get the singleton instance of the task manager.
    
    Returns:
        TaskManager: The task manager instance
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


def start_task(text: str, language: str, voice_path: str, routine_name: str, 
              routine_id: Optional[str] = None, voice_type: Optional[str] = None, 
              voice_id: Optional[str] = None, num_threads: int = 4) -> str:
    """
    Start a new background task and return the task ID.
    
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
    task_manager = get_task_manager()
    return task_manager.start_task(
        text=text,
        language=language,
        voice_path=voice_path,
        routine_name=routine_name,
        routine_id=routine_id,
        voice_type=voice_type,
        voice_id=voice_id,
        num_threads=num_threads
    )


def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the status of a task.
    
    Args:
        task_id: ID of the task
        
    Returns:
        Dict[str, Any] or None: Task data if found, None otherwise
    """
    task_manager = get_task_manager()
    return task_manager.get_task_status(task_id)