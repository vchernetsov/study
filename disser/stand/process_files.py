#!/usr/bin/env python3
"""
Process Files from Raw to Processed
Renames files based on frequency and datetime, moves to processed/ folder
"""

import os
import shutil
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


def process_files():
    """Process all files from raw/ to processed/ with renaming"""
    raw_folder = "raw"
    processed_folder = "processed"
    config = Config()
    log_file = config.get('log_file', 'stand.log')

    # Check raw folder exists
    if not os.path.exists(raw_folder):
        print(f"{fg('red')}[ERROR] Folder '{raw_folder}/' not found{attr('reset')}")
        return 1

    # Create processed folder if it doesn't exist
    if not os.path.exists(processed_folder):
        os.makedirs(processed_folder)
        print(f"[INFO] Created folder: {processed_folder}/")

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

    print("=" * 100)
    print(f"{'Original Filename':<40} {'New Filename':<40} {'Status'}")
    print("=" * 100)

    processed_count = 0
    skipped_count = 0

    for filename in files:
        filepath = os.path.join(raw_folder, filename)

        # Get file extension
        _, ext = os.path.splitext(filename)

        # Get creation time from metadata
        creation_time = get_video_metadata(filepath)

        if not creation_time:
            print(f"{filename:<40} {fg('yellow')}SKIPPED (no metadata){attr('reset'):<40}")
            skipped_count += 1
            continue

        # Find matching log entry (with ±5 seconds tolerance)
        match, time_diff = logger.find_matching_entry(creation_time, tolerance_seconds=5)

        if not match:
            print(f"{filename:<40} {fg('yellow')}SKIPPED (no log match){attr('reset'):<40}")
            skipped_count += 1
            continue

        # Create new filename: <frequency>-<datetime>.<extension>
        # Format: 100.5-2026-01-23_21-05-00.MOV
        datetime_str = creation_time.strftime("%Y-%m-%d_%H-%M-%S")
        new_filename = f"{match['frequency']}-{datetime_str}{ext}"
        new_filepath = os.path.join(processed_folder, new_filename)

        # Check if destination file already exists
        if os.path.exists(new_filepath):
            print(f"{filename:<40} {fg('red')}SKIPPED (already exists){attr('reset'):<40}")
            skipped_count += 1
            continue

        # Move and rename file
        try:
            shutil.move(filepath, new_filepath)
            print(f"{filename:<40} {new_filename:<40} {fg('green')}✓{attr('reset')}")
            processed_count += 1
        except Exception as e:
            print(f"{filename:<40} {fg('red')}ERROR: {e}{attr('reset'):<40}")
            skipped_count += 1

    print("=" * 100)
    print(f"Total files: {len(files)}, Processed: {processed_count}, Skipped: {skipped_count}")
    print()

    return 0


def main():
    print("=" * 80)
    print("Process Files from Raw to Processed")
    print("=" * 80)
    print()

    return process_files()


if __name__ == '__main__':
    exit(main())
