"""
Qt-specific implementation of the task management system.
This module provides a TaskManager class that uses PyQt signals for task progress notifications.
"""

import logging
from typing import Any, Dict

from PyQt6.QtCore import QObject, pyqtSignal

from app.tasks.base_task_manager import BaseTaskManager, TaskProgressNotifier


class QtTaskProgressNotifier(QObject):
    """
    Implementation of TaskProgressNotifier interface that uses PyQt signals.
    This class implements the TaskProgressNotifier interface without inheriting from it
    to avoid metaclass conflicts between QObject and ABC.
    """
    
    # Define signals
    task_started = pyqtSignal()
    task_progress = pyqtSignal(int, str)  # progress percentage, message
    task_completed = pyqtSignal(dict)  # result dictionary
    task_failed = pyqtSignal(str)  # error message
    
    def __init__(self):
        """Initialize the notifier"""
        QObject.__init__(self)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing QtTaskProgressNotifier")
    
    def notify_started(self, task_id: str) -> None:
        """
        Notify that a task has started.
        
        Args:
            task_id: ID of the task
        """
        self.logger.debug(f"Task {task_id} started")
        self.task_started.emit()
    
    def notify_progress(self, task_id: str, percent: int, message: str) -> None:
        """
        Notify about task progress.
        
        Args:
            task_id: ID of the task
            percent: Progress percentage (0-100)
            message: Progress message
        """
        self.logger.debug(f"Task {task_id} progress: {percent}% - {message}")
        self.task_progress.emit(percent, message)
    
    def notify_completed(self, task_id: str, result: Dict[str, Any]) -> None:
        """
        Notify that a task has completed successfully.
        
        Args:
            task_id: ID of the task
            result: Result data
        """
        self.logger.debug(f"Task {task_id} completed with result: {result}")
        self.task_completed.emit(result)
    
    def notify_failed(self, task_id: str, error: str) -> None:
        """
        Notify that a task has failed.
        
        Args:
            task_id: ID of the task
            error: Error message
        """
        self.logger.debug(f"Task {task_id} failed with error: {error}")
        self.task_failed.emit(error)


class TaskManager(BaseTaskManager):
    """
    Qt-specific implementation of BaseTaskManager.
    Uses PyQt signals for task progress notifications.
    """
    
    def __init__(self):
        """Initialize the task manager"""
        # Create a notifier
        self.notifier = QtTaskProgressNotifier()
        
        # Initialize the base class
        super().__init__(self.notifier)
        
        self.logger.info("Qt TaskManager initialized")
    
    # Expose the signals from the notifier
    @property
    def task_started(self):
        return self.notifier.task_started
    
    @property
    def task_progress(self):
        return self.notifier.task_progress
    
    @property
    def task_completed(self):
        return self.notifier.task_completed
    
    @property
    def task_failed(self):
        return self.notifier.task_failed