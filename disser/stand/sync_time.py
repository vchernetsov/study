#!/usr/bin/env python3
"""
Time Synchronization Utility
Synchronizes Nikon 1 V1 camera time with host computer time at the next whole minute
"""

import time
from datetime import datetime
from common.camera import NikonCamera


def wait_for_next_minute():
    """Wait until the next whole minute starts"""
    now = datetime.now()

    # Calculate seconds until next minute
    seconds_to_wait = 60 - now.second - (now.microsecond / 1000000.0)

    print(f"Current time: {now.strftime('%H:%M:%S.%f')[:-3]}")
    print(f"Waiting {seconds_to_wait:.3f} seconds until next minute...")

    # Sleep until next minute
    time.sleep(seconds_to_wait)

    sync_time = datetime.now()
    print(f"Sync triggered at: {sync_time.strftime('%H:%M:%S.%f')[:-3]}")
    return sync_time


def sync_camera_time(camera: NikonCamera):
    """Synchronize camera time via USB"""
    print("\n[SYNC] Synchronizing camera time via USB...")
    result = camera.sync_time()
    if result:
        print("[SYNC] Camera time synchronized successfully!")
        return True
    else:
        print("[SYNC] Failed to synchronize camera time.")
        return False


def main():
    print("=" * 80)
    print("Nikon 1 V1 Camera Time Synchronization")
    print("=" * 80)
    print()

    # Connect to camera
    camera = NikonCamera()
    if not camera.connect():
        print("[ERROR] Could not connect to camera. Make sure:")
        print("  1. Camera is connected via USB")
        print("  2. Camera is turned on")
        print("  3. gphoto2 is installed (sudo apt install gphoto2)")
        return 1

    try:
        # Wait for next minute
        sync_time = wait_for_next_minute()

        # Send sync command
        success = sync_camera_time(camera)

        if success:
            print(f"\n[SUCCESS] Camera time synchronized at {sync_time.strftime('%H:%M:00')}")
            return 0
        else:
            print("\n[FAILED] Camera time synchronization failed")
            return 1

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Time sync cancelled by user")
        return 1
    finally:
        camera.disconnect()


if __name__ == '__main__':
    exit(main())
