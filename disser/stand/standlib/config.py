"""Thread-safe configuration manager."""

import configparser
import os
import threading
from typing import Any, List, Tuple


DEFAULT_CONFIG = {
    'serial': {
        'port': '/dev/ttyUSB0',
        'baudrate': '115200',
        'baudrates': '9600,19200,38400,57600,115200'
    },
    'commands': {
        'ir_engage': '!r\\n'
    },
    'sound': {
        'frequency': '440',
        'duration': '1.0',
        'sample_rate': '44100'
    },
    'loop': {
        'current_frequency': '1.0',
        'max_frequency': '150.0',
        'step': '0.25',
        'duration': '1.0',
        'ir_delay': '10.0',
        'loop_sleep': '5.0',
        'max_loops_per_run': '250',
        'log_file': 'stand.log'
    },
    'fetch': {
        'output_dir': './videos',
        'tolerance': '10'
    }
}


class ConfigManager:
    """Thread-safe configuration management."""

    def __init__(self, config_file: str = 'stand.conf'):
        self._lock = threading.RLock()
        self._config = configparser.ConfigParser()
        self.config_file = config_file
        self.loaded = False

    def load(self) -> bool:
        """Load config from file, creating default if missing."""
        with self._lock:
            if os.path.exists(self.config_file):
                self._config.read(self.config_file)
                self.loaded = True
                print(f"  Loaded config from {self.config_file}")
                return True
            else:
                self._create_default()
                self.loaded = True
                return True

    def _create_default(self) -> None:
        """Create default configuration."""
        for section, values in DEFAULT_CONFIG.items():
            self._config[section] = values
        self.save()
        print(f"  Created default config: {self.config_file}")

    def save(self) -> None:
        """Thread-safe save to file."""
        with self._lock:
            with open(self.config_file, 'w') as f:
                self._config.write(f)

    def get(self, section: str, key: str, fallback: Any = None) -> str:
        """Thread-safe get with fallback."""
        with self._lock:
            return self._config.get(section, key, fallback=fallback)

    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        """Thread-safe get integer."""
        with self._lock:
            return self._config.getint(section, key, fallback=fallback)

    def getfloat(self, section: str, key: str, fallback: float = 0.0) -> float:
        """Thread-safe get float."""
        with self._lock:
            return self._config.getfloat(section, key, fallback=fallback)

    def set(self, section: str, key: str, value: str) -> None:
        """Thread-safe set value."""
        with self._lock:
            if not self._config.has_section(section):
                self._config.add_section(section)
            self._config.set(section, key, value)

    def sections(self) -> List[str]:
        """Get all section names."""
        with self._lock:
            return self._config.sections()

    def items(self, section: str) -> List[Tuple[str, str]]:
        """Get all items in a section."""
        with self._lock:
            return list(self._config.items(section))

    def options(self, section: str) -> List[str]:
        """Get all option names in a section."""
        with self._lock:
            return self._config.options(section)

    def has_section(self, section: str) -> bool:
        """Check if section exists."""
        with self._lock:
            return self._config.has_section(section)

    def has_option(self, section: str, key: str) -> bool:
        """Check if option exists."""
        with self._lock:
            return self._config.has_option(section, key)

    def add_section(self, section: str) -> None:
        """Add a new section."""
        with self._lock:
            if not self._config.has_section(section):
                self._config.add_section(section)

    # Convenience properties
    @property
    def serial_port(self) -> str:
        """Get serial port from config."""
        return self.get('serial', 'port', fallback='/dev/ttyUSB0')

    @property
    def baudrate(self) -> int:
        """Get baudrate from config."""
        return self.getint('serial', 'baudrate', fallback=115200)

    @property
    def ir_command(self) -> bytes:
        """Get IR command as bytes."""
        cmd_str = self.get('commands', 'ir_engage', fallback='!r\\n')
        return cmd_str.encode().decode('unicode_escape').encode()
