import os
import logging
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QSettings, QSize

from app.desktop.routines_list import RoutinesListWidget
from app.desktop.routine_editor import RoutineEditorWidget
from app.config import LANGUAGES

class MainWindow(QMainWindow):
    """Main window for the Hypno-AI desktop application"""

    def __init__(self):
        super().__init__()

        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing MainWindow")

        # Set up window properties
        self.setWindowTitle("Hypno-AI")
        self.setMinimumSize(QSize(900, 700))

        # Create the central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create the header
        self.setup_header()

        # Create the tab widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        # Create the routines list tab
        self.routines_list = RoutinesListWidget(self)
        self.tab_widget.addTab(self.routines_list, "Routines")

        # Create the routine editor tab (initially hidden)
        self.routine_editor = RoutineEditorWidget(self)
        self.editor_tab_index = self.tab_widget.addTab(self.routine_editor, "Create/Edit Routine")
        self.tab_widget.setTabVisible(self.editor_tab_index, False)

        # Connect signals
        self.routines_list.new_routine_requested.connect(self.create_new_routine)
        self.routines_list.edit_routine_requested.connect(self.edit_routine)
        self.routine_editor.save_completed.connect(self.on_routine_saved)
        self.routine_editor.cancel_requested.connect(self.on_edit_cancelled)

        # Set up status bar
        self.statusBar().showMessage("Ready")

        self.logger.info("MainWindow initialized")

    def setup_header(self):
        """Set up the header with title and logo"""
        header_layout = QHBoxLayout()

        # Title
        title_label = QLabel("Hypnosis Audio Generator")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        header_layout.addWidget(title_label)

        # Add the header to the main layout
        self.main_layout.addLayout(header_layout)

    def create_new_routine(self):
        """Open the routine editor tab for creating a new routine"""
        self.logger.info("Creating new routine")
        self.routine_editor.clear()
        self.tab_widget.setTabVisible(self.editor_tab_index, True)
        self.tab_widget.setCurrentIndex(self.editor_tab_index)

    def edit_routine(self, routine_id):
        """Open the routine editor tab for editing an existing routine"""
        self.logger.info(f"Editing routine: {routine_id}")
        self.routine_editor.load_routine(routine_id)
        self.tab_widget.setTabVisible(self.editor_tab_index, True)
        self.tab_widget.setCurrentIndex(self.editor_tab_index)

    def on_routine_saved(self):
        """Handle routine save completion"""
        self.logger.info("Routine saved")
        self.routines_list.refresh()
        self.tab_widget.setCurrentIndex(0)  # Switch back to routines list
        self.tab_widget.setTabVisible(self.editor_tab_index, False)
        self.statusBar().showMessage("Routine saved successfully", 3000)

    def on_edit_cancelled(self):
        """Handle routine edit cancellation"""
        self.logger.info("Routine edit cancelled")
        self.tab_widget.setCurrentIndex(0)  # Switch back to routines list
        self.tab_widget.setTabVisible(self.editor_tab_index, False)

    def closeEvent(self, event):
        """Handle window close event"""
        self.logger.info("Application closing")
        event.accept()
