import json
import logging
import os


class Settings:
    """Class to manage application settings"""
    
    # Default settings
    DEFAULT_SETTINGS = {
        'data_dir': os.path.join(os.path.expanduser("~"), "hypno-ai"),
        'default_language': 'en',
        'audio_threads': 4,
    }
    
    def __init__(self):
        """Initialize settings"""
        self.logger = logging.getLogger(__name__)
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.settings_file = None
        self.load_settings()
    
    def load_settings(self):
        """Load settings from the settings file"""
        # First try to load from the user's home directory
        home_settings_file = os.path.join(os.path.expanduser("~"), ".hypno-ai-settings.json")
        
        # Then try to load from the application directory
        app_settings_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "settings.json")
        
        # Try to load from the home directory first, then the application directory
        if os.path.exists(home_settings_file):
            self.settings_file = home_settings_file
        elif os.path.exists(app_settings_file):
            self.settings_file = app_settings_file
        else:
            # If no settings file exists, create one in the home directory
            self.settings_file = home_settings_file
            self.save_settings()
            return
        
        try:
            with open(self.settings_file, 'r') as f:
                loaded_settings = json.load(f)
                # Update settings with loaded values
                self.settings.update(loaded_settings)
                self.logger.info(f"Settings loaded from {self.settings_file}")
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Error loading settings: {str(e)}")
            # If there's an error, use default settings and save them
            self.save_settings()
    
    def save_settings(self):
        """Save settings to the settings file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            self.logger.info(f"Settings saved to {self.settings_file}")
            return True
        except IOError as e:
            self.logger.error(f"Error saving settings: {str(e)}")
            return False
    
    def get(self, key, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)
    
    def set(self, key, value):
        """Set a setting value"""
        self.settings[key] = value
        return self.save_settings()
    
    def get_data_dir(self):
        """Get the data directory"""
        data_dir = self.get('data_dir')
        # Ensure the directory exists
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    
    def set_data_dir(self, data_dir):
        """Set the data directory"""
        # Validate the directory
        if not os.path.isdir(data_dir):
            try:
                os.makedirs(data_dir, exist_ok=True)
            except OSError:
                self.logger.error(f"Could not create directory: {data_dir}")
                return False
        
        # Set the new data directory
        return self.set('data_dir', data_dir)
    
    def get_upload_folder(self):
        """Get the upload folder"""
        upload_folder = os.path.join(self.get_data_dir(), 'voices')
        os.makedirs(upload_folder, exist_ok=True)
        return upload_folder
    
    def get_output_folder(self):
        """Get the output folder"""
        output_folder = os.path.join(self.get_data_dir(), 'output')
        os.makedirs(output_folder, exist_ok=True)
        return output_folder
    
    def get_db_file(self):
        """Get the database file path"""
        return os.path.join(self.get_data_dir(), "hypno-ai.db")

# Create a singleton instance
settings = Settings()