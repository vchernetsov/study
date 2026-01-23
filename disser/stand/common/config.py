"""
Configuration module for vibration stand tests
"""

import json
import os


class Config:
    """Configuration loader for loop parameters"""

    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.data = self._load_config()

    def _load_config(self):
        """Load configuration from file"""
        if not os.path.exists(self.config_file):
            # Return default configuration
            return self._default_config()

        with open(self.config_file, 'r') as f:
            return json.load(f)

    def _default_config(self):
        """Default configuration"""
        return {
            "start_frequency": 0,
            "end_frequency": 300,
            "step": 0.5,
            "sound_duration": 20,
            "sleep_time": 10,
            "ir_delay": 10,
            "fade_seconds": 2,
            "max_retries": 10,
            "log_file": "stand.log"
        }

    def get(self, key, default=None):
        """Get configuration value"""
        return self.data.get(key, default)

    def set(self, key, value):
        """Set configuration value and save to file"""
        self.data[key] = value
        self.save()

    def save(self):
        """Save current configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def save_default(self):
        """Save default configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self._default_config(), f, indent=4)
