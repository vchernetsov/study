"""Thread-safe serial port handler."""

import threading
from typing import Optional, TYPE_CHECKING

import serial

if TYPE_CHECKING:
    from .config import ConfigManager


class SerialHandler:
    """Thread-safe serial port management."""

    def __init__(self, config: 'ConfigManager'):
        self._lock = threading.Lock()
        self._port: Optional[serial.Serial] = None
        self._config = config

    @property
    def is_connected(self) -> bool:
        """Check if port is open."""
        with self._lock:
            return self._port is not None and self._port.is_open

    @property
    def port(self) -> Optional[serial.Serial]:
        """Get the serial port object."""
        return self._port

    def connect(self, port: str = None, baudrate: int = None) -> bool:
        """Connect to serial port. Returns success status."""
        with self._lock:
            port = port or self._config.serial_port
            baudrate = baudrate or self._config.baudrate

            if self._port and self._port.is_open:
                self._port.close()

            try:
                print(f"  [SERIAL] Opening port {port} at {baudrate} baud...")
                self._port = serial.Serial(port, baudrate, timeout=1)
                print(f"  [SERIAL] Connected successfully")
                return True
            except serial.SerialException as e:
                print(f"  [SERIAL] Warning: Could not connect to {port}: {e}")
                return False

    def disconnect(self) -> None:
        """Close serial connection."""
        with self._lock:
            if self._port and self._port.is_open:
                port = self._config.serial_port
                print(f"  [SERIAL] Closing connection to {port}...")
                self._port.close()
                print(f"  [SERIAL] Disconnected")
            else:
                print("  [SERIAL] Not connected")

    def reconnect(self) -> bool:
        """Reconnect using current config."""
        with self._lock:
            port = self._config.serial_port
            baudrate = self._config.baudrate

            if self._port and self._port.is_open:
                print(f"  [SERIAL] Closing existing connection...")
                self._port.close()

            try:
                print(f"  [SERIAL] Opening port {port} at {baudrate} baud...")
                self._port = serial.Serial(port, baudrate, timeout=1)
                print(f"  [SERIAL] Reconnected successfully")
                return True
            except serial.SerialException as e:
                print(f"  [SERIAL] Error: {e}")
                return False

    def write(self, data: bytes) -> bool:
        """Thread-safe write. Returns success status."""
        with self._lock:
            if not self._port or not self._port.is_open:
                return False
            try:
                self._port.write(data)
                return True
            except serial.SerialException:
                return False

    def readline(self, timeout: float = 1.0) -> Optional[str]:
        """Thread-safe read line."""
        with self._lock:
            if not self._port or not self._port.is_open:
                return None
            try:
                old_timeout = self._port.timeout
                self._port.timeout = timeout
                line = self._port.readline().decode().strip()
                self._port.timeout = old_timeout
                return line
            except serial.SerialException:
                return None

    def reset_input_buffer(self) -> None:
        """Clear input buffer."""
        with self._lock:
            if self._port and self._port.is_open:
                self._port.reset_input_buffer()

    def send_ir_command(self) -> bool:
        """Send IR command from config. Returns success."""
        cmd = self._config.ir_command
        return self.write(cmd)

    def send_test_command(self) -> bool:
        """Send IR command as test. Returns success."""
        return self.send_ir_command()
