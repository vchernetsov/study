#!/usr/bin/env python3
"""
Play Sound at Frequency
Simple program to play a tone at specified frequency and duration
"""

import sys
import os
from common.sounds import sweep
from common.config import Config


def main():
    if len(sys.argv) < 3:
        print("Usage: ./play_sound.py <frequency> <duration>")
        print("Example: ./play_sound.py 100 5")
        return 1

    try:
        frequency = float(sys.argv[1])
        duration = float(sys.argv[2])
    except ValueError:
        print("ERROR: Frequency and duration must be numbers")
        return 1

    # Load config for fade_seconds
    config = Config()
    fade_seconds = config.get('fade_seconds', 2)

    print(f"Playing {frequency} Hz for {duration} seconds...")

    try:
        sweep(frequency, frequency, duration, fade_seconds)
        print("Done.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        # Force exit to avoid portaudio cleanup issues
        os._exit(0)


if __name__ == '__main__':
    exit(main())
