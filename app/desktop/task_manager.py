"""
This module re-exports the TaskManager class from qt_task_manager.py.
It is kept for backward compatibility with existing code.
"""

import logging

# Set up logging
logger = logging.getLogger(__name__)
logger.info("Importing TaskManager from qt_task_manager.py for backward compatibility")
