import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QComboBox, QSpinBox, QFileDialog, QGroupBox, QFormLayout, QDialogButtonBox,
    QMessageBox
)

from app.config import LANGUAGES
from app.models.settings import settings


class SettingsDialog(QDialog):
    """Dialog for configuring application settings"""
    
    # Signal emitted when settings are changed
    settings_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing SettingsDialog")
        
        # Set up dialog properties
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        
        # Create the main layout
        self.layout = QVBoxLayout(self)
        
        # Create the form layout for settings
        self.create_data_location_group()
        self.create_language_group()
        self.create_performance_group()
        
        # Create the button box
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_settings)
        
        # Add the button box to the layout
        self.layout.addWidget(self.button_box)
        
        # Load current settings
        self.load_settings()
        
        self.logger.info("SettingsDialog initialized")
    
    def create_data_location_group(self):
        """Create the group for data location settings"""
        group = QGroupBox("Data Location")
        layout = QFormLayout()
        
        # Data directory
        self.data_dir_layout = QHBoxLayout()
        self.data_dir_edit = QLineEdit()
        self.data_dir_edit.setReadOnly(True)
        self.data_dir_layout.addWidget(self.data_dir_edit)
        
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_data_dir)
        self.data_dir_layout.addWidget(self.browse_button)
        
        layout.addRow("Data Directory:", self.data_dir_layout)
        
        group.setLayout(layout)
        self.layout.addWidget(group)
    
    def create_language_group(self):
        """Create the group for language settings"""
        group = QGroupBox("Language")
        layout = QFormLayout()
        
        # Default language
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        
        layout.addRow("Default Language:", self.language_combo)
        
        group.setLayout(layout)
        self.layout.addWidget(group)
    
    def create_performance_group(self):
        """Create the group for performance settings"""
        group = QGroupBox("Performance")
        layout = QFormLayout()
        
        # Audio generation threads
        self.threads_spin = QSpinBox()
        self.threads_spin.setMinimum(1)
        self.threads_spin.setMaximum(16)
        
        layout.addRow("Audio Generation Threads:", self.threads_spin)
        
        group.setLayout(layout)
        self.layout.addWidget(group)
    
    def load_settings(self):
        """Load current settings into the dialog"""
        # Data directory
        self.data_dir_edit.setText(settings.get_data_dir())
        
        # Default language
        default_language = settings.get('default_language', 'en')
        index = self.language_combo.findData(default_language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        
        # Audio generation threads
        self.threads_spin.setValue(settings.get('audio_threads', 4))
    
    def browse_data_dir(self):
        """Open a file dialog to select the data directory"""
        current_dir = self.data_dir_edit.text()
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "Select Data Directory",
            current_dir
        )
        
        if dir_path:
            self.data_dir_edit.setText(dir_path)
    
    def apply_settings(self):
        """Apply the settings without closing the dialog"""
        # Get the values from the dialog
        data_dir = self.data_dir_edit.text()
        default_language = self.language_combo.currentData()
        audio_threads = self.threads_spin.value()
        
        # Check if data directory has changed
        old_data_dir = settings.get_data_dir()
        data_dir_changed = data_dir != old_data_dir
        
        # Save the settings
        if data_dir_changed:
            if not settings.set_data_dir(data_dir):
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Could not set data directory to {data_dir}. Please choose a different directory."
                )
                return False
        
        settings.set('default_language', default_language)
        settings.set('audio_threads', audio_threads)
        
        # Emit the settings changed signal
        self.settings_changed.emit()
        
        self.logger.info("Settings applied")
        return True
    
    def accept(self):
        """Apply settings and close the dialog if successful"""
        if self.apply_settings():
            super().accept()
    
    def showEvent(self, event):
        """Called when the dialog is shown"""
        # Reload settings in case they've changed
        self.load_settings()
        super().showEvent(event)