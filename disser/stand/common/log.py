"""
Logging module for vibration stand tests
"""

import os
from datetime import datetime


class Logger:
    """Logger for IR engagement events"""

    def __init__(self, log_file="stand.log"):
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

    def load_entries(self):
        """
        Load log entries from log file

        Returns:
            List of dictionaries with 'timestamp', 'frequency', and 'raw_line' keys
        """
        entries = []
        if not os.path.exists(self.log_file):
            return entries

        with open(self.log_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Format: timestamp-frequency
                parts = line.rsplit('-', 1)
                if len(parts) == 2:
                    timestamp_str = parts[0]
                    frequency = parts[1]
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        entries.append({
                            'timestamp': timestamp,
                            'frequency': frequency,
                            'raw_line': line
                        })
                    except ValueError:
                        continue
        return entries

    def find_matching_entry(self, target_time, tolerance_seconds=5):
        """
        Find log entry closest to target time within ±tolerance_seconds

        Args:
            target_time: datetime object to match
            tolerance_seconds: maximum allowed time difference (default: 5)

        Returns:
            Tuple of (best_match, signed_diff) where:
            - best_match is the matching log entry dict or None
            - signed_diff is the time difference in seconds (positive if target is after log entry)
        """
        entries = self.load_entries()
        if not target_time or not entries:
            return None, None

        best_match = None
        min_abs_diff = tolerance_seconds + 1
        signed_diff = 0

        for entry in entries:
            # Signed difference: target_time - log_time
            diff = (target_time - entry['timestamp']).total_seconds()
            abs_diff = abs(diff)
            if abs_diff < min_abs_diff:
                min_abs_diff = abs_diff
                signed_diff = diff
                best_match = entry

        if min_abs_diff <= tolerance_seconds:
            return best_match, signed_diff
        return None, None
