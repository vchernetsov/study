#!/usr/bin/env python3
"""
List Files and Match with Log Entries
Shows files from raw/ directory with their creation time and matched log entries
"""

import os
import subprocess
from datetime import datetime
from colored import fg, attr
from common.log import Logger
from common.config import Config


def get_video_metadata(filepath):
    """Extract creation time from video file metadata"""
    try:
        result = subprocess.run(
            ['exiftool', '-CreateDate', '-s3', filepath],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Parse exiftool output: "YYYY:MM:DD HH:MM:SS"
            timestamp_str = result.stdout.strip()
            try:
                return datetime.strptime(timestamp_str, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                return None
        return None
    except FileNotFoundError:
        print(f"{fg('red')}[ERROR] exiftool not found. Install: sudo apt install libimage-exiftool-perl{attr('reset')}")
        return None
    except Exception as e:
        print(f"{fg('red')}[ERROR] Failed to read metadata: {e}{attr('reset')}")
        return None


def list_files_with_log():
    """List all files in raw/ directory with their log matches"""
    raw_folder = "raw"
    config = Config()
    log_file = config.get('log_file', 'stand.log')

    if not os.path.exists(raw_folder):
        print(f"{fg('red')}[ERROR] Folder '{raw_folder}/' not found{attr('reset')}")
        return 1

    # Load log entries
    print(f"[INFO] Loading log entries from {log_file}...")
    logger = Logger(log_file)
    log_entries = logger.load_entries()
    print(f"[INFO] Found {len(log_entries)} log entries")
    print(f"[INFO] Using time tolerance: ±5 seconds")
    print()

    # List all files in raw folder
    files = sorted([f for f in os.listdir(raw_folder) if os.path.isfile(os.path.join(raw_folder, f))])

    if not files:
        print(f"{fg('yellow')}[WARNING] No files found in {raw_folder}/{attr('reset')}")
        return 0

    print("=" * 110)
    print(f"{'Filename':<40} {'Creation Time':<20} {'Frequency (Hz)':<15} {'Time Diff':<12} {'Match'}")
    print("=" * 110)

    matched_count = 0
    for filename in files:
        filepath = os.path.join(raw_folder, filename)

        # Get creation time from metadata
        creation_time = get_video_metadata(filepath)

        if creation_time:
            creation_str = creation_time.strftime("%Y-%m-%d %H:%M:%S")

            # Find matching log entry (with ±5 seconds tolerance)
            match, time_diff = logger.find_matching_entry(creation_time, tolerance_seconds=5)

            if match:
                diff_str = f"{time_diff:+.1f}s"
                print(f"{filename:<40} {creation_str:<20} {match['frequency']:<15} {diff_str:<12} {fg('green')}✓{attr('reset')}")
                matched_count += 1
            else:
                print(f"{filename:<40} {creation_str:<20} {fg('red')}NO MATCH{attr('reset'):<15} {'-':<12} {fg('red')}✗{attr('reset')}")
        else:
            print(f"{filename:<40} {fg('yellow')}NO METADATA{attr('reset'):<20} {fg('yellow')}-{attr('reset'):<15} {'-':<12} {fg('yellow')}?{attr('reset')}")

    print("=" * 110)
    print(f"Total files: {len(files)}, Matched: {matched_count}, Unmatched: {len(files) - matched_count}")
    print(f"Note: Matching uses ±5 seconds time tolerance")
    print()

    return 0


def main():
    print("=" * 80)
    print("File List with Log Matching")
    print("=" * 80)
    print()

    return list_files_with_log()


if __name__ == '__main__':
    exit(main())
