"""
IR communication module
"""

import serial

BAUDRATE = 115200
PORT = '/dev/ttyUSB0'

class IRController:
    """Controls IR lamp connected to Arduino"""

    def __init__(self, port=PORT, baudrate=BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self.connection = None

    def connect(self):
        """Connect to Arduino"""
        try:
            self.connection = serial.Serial(self.port, self.baudrate)
        except serial.SerialException as e:
            print(f"[IR] WARNING: Could not connect to {self.port}[{self.baudrate}]: {e}")
            return False
        print("[IR] Connected successfully.")
        return True

    def disconnect(self):
        """Disconnect from Arduino"""
        if self.connection:
            self.connection.close()
            self.connection = None
            print("[IR] Disconnected successfully.")
            return True
        print("[IR] Not disconnected, no connection.")
        return False

    def engage(self):
        """Send engage command to Arduino"""
        if self.connection:
            print("[IR] Engage...")
            self.connection.write(b'!r\n')
            print("[IR] sent.")
            return True
        print("[IR] WARNING: Not connected, no engage.")
        return False