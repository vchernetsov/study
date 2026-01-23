#!/usr/bin/env python3
"""
Vibration Stand Testing Program
Generates frequency sweeps for vibration testing
"""
import os

from common.ir import IRController
from common.threads import Loop, LoopStep
from common.exceptions import FinishLoop

print("=" * 80)
print("Vibration Stand")
print("=" * 80)
print()

#response = input("Starting sound test (y/N), 3 seconds: ").strip().lower()
#if response == 'y':
#    sweep(100, 300, 3)
#else:
#    sys.exit()
# print()
#response = input("Did you hear a sound? (y/N): ").strip().lower()
#if response == 'y':
#    print("Great! Test completed.")
#else:
#    sys.exit()

ir = IRController()
ir.connect()

try:
    samples = LoopStep.sequence(start_frequency=100, end_frequency=102, step=0.5, duration=10)
    loop = Loop(samples, ir)
    print("\nStarting frequency iteration test...")
    try:
        loop.engage()
    except FinishLoop as e:
        print(f"\n{e}")
    print("Frequency iteration ended.")
except KeyboardInterrupt as e:
    print("\n\nInterrupted by user.")
except Exception as e:
    print(f"\nError: {e}")
finally:
    # Always force exit to avoid portaudio cleanup issues
    os._exit(0)

