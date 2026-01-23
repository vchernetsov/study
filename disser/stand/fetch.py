#!/usr/bin/env python3
"""
Fetch Photos from Camera
Downloads all photos from Nikon 1 V1 to raw folder
"""

import os
import sys
from common.camera import NikonCamera


def main():
    print("=" * 80)
    print("Fetch Photos from Camera")
    print("=" * 80)
    print()

    # Create raw folder if it doesn't exist
    raw_folder = "raw"
    if not os.path.exists(raw_folder):
        os.makedirs(raw_folder)
        print(f"[INFO] Created folder: {raw_folder}/")

    # Connect to camera
    camera = NikonCamera()
    if not camera.connect():
        print("[ERROR] Could not connect to camera")
        return 1

    try:
        print(f"\n[FETCH] Downloading all files to {raw_folder}/...")

        success = camera.download_all(raw_folder)

        if success:
            print(f"\n[SUCCESS] All files downloaded to {raw_folder}/")
            return 0
        else:
            print("\n[FAILED] Failed to download files")
            return 1

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Download cancelled by user")
        return 1
    finally:
        camera.disconnect()


if __name__ == '__main__':
    exit(main())
