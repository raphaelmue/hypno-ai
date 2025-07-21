import logging

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QMessageBox, QFrame,
    QStackedWidget, )

from app.desktop.model_download_dialog import ModelDownloadDialog
from app.desktop.routine_editor import RoutineEditorWidget
from app.desktop.routines_list import RoutinesListWidget
from app.desktop.settings_dialog import SettingsDialog
from app.tts_model.tts_model import is_model_downloaded


class MainWindow(QMainWindow):
    """Main window for the Hypno-AI desktop application"""

    def __init__(self):
        super().__init__()

        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing MainWindow")

        # Set up window properties
        self.setWindowTitle("Hypno-AI")
        self.setMinimumSize(QSize(1000, 800))

        # Create the menu bar
        self.setup_menu_bar()

        # Create the central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create the header with buttons
        self.setup_header()

        # Create the main content area with splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)

        # Create the left panel (routines list)
        self.left_panel = QFrame()
        self.left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.left_panel.setMinimumWidth(300)
        self.left_panel_layout = QVBoxLayout(self.left_panel)

        # Create the routines list
        self.routines_list = RoutinesListWidget(self)
        self.left_panel_layout.addWidget(self.routines_list)

        # Create the right panel (stacked widget for details/editor)
        self.right_panel = QFrame()
        self.right_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.right_panel_layout = QVBoxLayout(self.right_panel)

        # Create the stacked widget for the right panel
        self.right_stacked_widget = QStackedWidget()
        self.right_panel_layout.addWidget(self.right_stacked_widget)

        # Create a welcome/placeholder widget
        self.welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(self.welcome_widget)
        welcome_label = QLabel("Select a routine from the list or create a new one")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(welcome_label)

        # Create the routine editor widget
        self.routine_editor = RoutineEditorWidget(self)

        # Add widgets to the stacked widget
        self.right_stacked_widget.addWidget(self.welcome_widget)
        self.right_stacked_widget.addWidget(self.routine_editor)

        # Add panels to the splitter
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([300, 700])  # Set initial sizes

        # Connect signals
        self.routines_list.new_routine_requested.connect(self.create_new_routine)
        self.routines_list.edit_routine_requested.connect(self.edit_routine)
        self.routines_list.routine_selected.connect(self.on_routine_selected)
        self.routine_editor.save_completed.connect(self.on_routine_saved)
        self.routine_editor.cancel_requested.connect(self.on_edit_cancelled)

        # Set up status bar
        self.statusBar().showMessage("Ready")

        # Check if the TTS model is downloaded and show the download dialog if needed
        self.check_tts_model()

        self.logger.info("MainWindow initialized")

    def setup_header(self):
        """Set up the header with title and action buttons"""
        header_layout = QHBoxLayout()

        # Title
        title_label = QLabel("Hypnosis Audio Generator")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        header_layout.addWidget(title_label)

        # Add spacer to push buttons to the right
        header_layout.addStretch()

        # Create action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)  # Consistent spacing between buttons

        # Create button
        self.create_button = QPushButton("Create")
        self.create_button.setMinimumWidth(100)  # Consistent button width
        self.create_button.clicked.connect(self.create_new_routine)
        button_layout.addWidget(self.create_button)

        # Delete button (initially disabled)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setMinimumWidth(100)  # Consistent button width
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected_routine)
        button_layout.addWidget(self.delete_button)

        # Regenerate button (initially disabled)
        self.regenerate_button = QPushButton("Regenerate")
        self.regenerate_button.setMinimumWidth(100)  # Consistent button width
        self.regenerate_button.setEnabled(False)
        self.regenerate_button.clicked.connect(self.regenerate_selected_routine)
        button_layout.addWidget(self.regenerate_button)

        # Add button layout to header
        header_layout.addLayout(button_layout)

        # Add the header to the main layout
        self.main_layout.addLayout(header_layout)

    def create_new_routine(self):
        """Open the routine editor for creating a new routine"""
        self.logger.info("Creating new routine")
        self.routine_editor.clear()
        self.right_stacked_widget.setCurrentWidget(self.routine_editor)

    def edit_routine(self, routine_id):
        """Open the routine editor for editing an existing routine"""
        self.logger.info(f"Editing routine: {routine_id}")
        self.routine_editor.load_routine(routine_id)
        self.right_stacked_widget.setCurrentWidget(self.routine_editor)

    def on_routine_saved(self):
        """Handle routine save completion"""
        self.logger.info("Routine saved")
        self.routines_list.refresh()
        # Keep the routine editor open after saving (don't switch to welcome widget)
        # self.right_stacked_widget.setCurrentWidget(self.welcome_widget)
        self.statusBar().showMessage("Routine saved successfully", 3000)

    def on_edit_cancelled(self):
        """Handle routine edit cancellation"""
        self.logger.info("Routine edit cancelled")
        self.right_stacked_widget.setCurrentWidget(self.welcome_widget)

    def delete_selected_routine(self):
        """Delete the selected routine"""
        if hasattr(self, 'selected_routine_id') and self.selected_routine_id:
            self.logger.info(f"Deleting routine: {self.selected_routine_id}")

            # Confirm deletion
            reply = QMessageBox.question(
                self, 
                "Confirm Deletion",
                "Are you sure you want to delete this routine?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                from app.models.routine import delete_routine
                success = delete_routine(self.selected_routine_id)
                if success:
                    self.logger.info(f"Routine deleted: {self.selected_routine_id}")
                    self.selected_routine_id = None
                    self.delete_button.setEnabled(False)
                    self.regenerate_button.setEnabled(False)
                    self.routines_list.refresh()
                    self.right_stacked_widget.setCurrentWidget(self.welcome_widget)
                    self.statusBar().showMessage("Routine deleted successfully", 3000)
                else:
                    self.logger.error(f"Failed to delete routine: {self.selected_routine_id}")
                    QMessageBox.warning(self, "Error", "Failed to delete routine.")

    def regenerate_selected_routine(self):
        """Regenerate the selected routine"""
        if hasattr(self, 'selected_routine_id') and self.selected_routine_id:
            self.logger.info(f"Regenerating routine: {self.selected_routine_id}")
            self.edit_routine(self.selected_routine_id)

    def on_routine_selected(self, routine_id):
        """Handle routine selection"""
        self.logger.info(f"Routine selected: {routine_id}")
        self.selected_routine_id = routine_id
        self.delete_button.setEnabled(True)
        self.regenerate_button.setEnabled(True)
        # Open the routine in the editor
        self.edit_routine(routine_id)

    def setup_menu_bar(self):
        """Set up the menu bar"""
        self.logger.info("Setting up menu bar")

        # Create the menu bar
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        # New routine action
        new_action = QAction("&New Routine", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.create_new_routine)
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menu_bar.addMenu("&Tools")

        # Settings action
        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self.show_settings_dialog)
        tools_menu.addAction(settings_action)

        # Download TTS Model action
        download_model_action = QAction("&Download TTS Model", self)
        download_model_action.triggered.connect(lambda: self.check_tts_model(force_show=True))
        tools_menu.addAction(download_model_action)


        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        # About action
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_settings_dialog(self):
        """Show the settings dialog"""
        self.logger.info("Showing settings dialog")
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.exec()


    def show_about_dialog(self):
        """Show the about dialog"""
        self.logger.info("Showing about dialog")
        QMessageBox.about(
            self,
            "About Hypno-AI",
            "Hypno-AI\n\n"
            "A tool for generating hypnosis audio files.\n\n"
            "Version 1.0.0"
        )

    def on_settings_changed(self):
        """Handle settings changed signal"""
        self.logger.info("Settings changed")
        # Refresh the UI to reflect the new settings
        self.routines_list.refresh()

    def check_tts_model(self, force_show=False):
        """Check if the TTS model is downloaded and show the download dialog if needed

        Args:
            force_show (bool): If True, show the dialog even if the model is already downloaded
        """
        self.logger.info("Checking if TTS model is downloaded")

        if not is_model_downloaded() or force_show:
            self.logger.info("TTS model not downloaded or force_show=True, showing download dialog")
            dialog = ModelDownloadDialog(self)
            dialog.exec()
        else:
            self.logger.info("TTS model is already downloaded")

    def closeEvent(self, event):
        """Handle window close event"""
        self.logger.info("Application closing")
        event.accept()
