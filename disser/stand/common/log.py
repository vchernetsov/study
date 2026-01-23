"""
Logging module for vibration stand tests
"""

from datetime import datetime

LOG_FILE = "stand.log"

class Logger:
    """Logger for IR engagement events"""

    def __init__(self, log_file=LOG_FILE):
        self.log_file = log_file

    def log_ir_engage(self, frequency):
        """
        Log IR engagement event

        Args:
            frequency: The frequency at which IR was engaged
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"{timestamp}-{frequency}\n"
        with open(self.log_file, 'a') as f:
            f.write(log_line)
