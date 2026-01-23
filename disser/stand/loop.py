#!/usr/bin/env python3
"""
Vibration Stand Testing Program
Generates frequency sweeps for vibration testing
"""
import os
from colored import fg, attr

from common.ir import IRController
from common.threads import Loop, LoopStep
from common.exceptions import FinishLoop
from common.log import Logger
from common.config import Config

print("=" * 80)
print("Vibration Stand")
print("=" * 80)
print()

# Load configuration (create if absent)
config_file = "config.json"
if not os.path.exists(config_file):
    print("Config file not found. Creating default config...")
    config = Config(config_file)
    config.save()
    print(f"Created {config_file}")
else:
    config = Config(config_file)
    print(f"Configuration loaded from {config_file}")

print(f"  Frequency range: {config.get('start_frequency')} - {config.get('end_frequency')} Hz")
print(f"  Step: {config.get('step')} Hz")
print(f"  Sound duration: {config.get('sound_duration')} seconds")
print(f"  Sleep time: {config.get('sleep_time')} seconds")
print(f"  IR delay: {config.get('ir_delay')} seconds")
start_freq = config.get('start_frequency')
if start_freq > 0:
    print(f"  Resuming from: {start_freq} Hz (progress is saved automatically)")
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

logger = Logger(config.get('log_file', 'stand.log'))

try:
    samples = LoopStep.sequence(
        start_frequency=config.get('start_frequency'),
        end_frequency=config.get('end_frequency'),
        step=config.get('step'),
        sound_duration=config.get('sound_duration'),
        sleep_time=config.get('sleep_time'),
        ir_delay=config.get('ir_delay')
    )
    loop = Loop(samples, ir, logger, config)
    print("\nStarting frequency iteration test...")
    try:
        loop.engage()
    except FinishLoop as e:
        print(f"\n{e}")
    print("Frequency iteration ended.")

    # Retry missed frequencies until all are completed
    retry_count = 0
    max_retries = config.get('max_retries')

    while True:
        missed = loop.get_missed_frequencies()
        if not missed:
            print("\nNo missed frequencies. All IR engagements successful!")
            break

        retry_count += 1
        if retry_count > max_retries:
            print(f"\nMax retries ({max_retries}) reached. {len(missed)} frequencies still failed: {fg('red')}{missed}{attr('reset')}")
            break

        print(f"\nRetry attempt {retry_count}: {len(missed)} missed frequencies: {fg('red')}{missed}{attr('reset')}")
        # Create LoopSteps for missed frequencies
        missed_steps = LoopStep.list([
            {"frequency": freq}
            for freq in missed
        ], sound_duration=config.get('sound_duration'), sleep_time=config.get('sleep_time'), ir_delay=config.get('ir_delay'))
        loop = Loop(missed_steps, ir, logger, config)
        print("Starting retry loop...")
        try:
            loop.engage()
        except FinishLoop as e:
            print(f"\n{e}")
            break
        print("Retry loop ended.")
except KeyboardInterrupt as e:
    print("\n\nInterrupted by user.")
except Exception as e:
    print(f"\nError: {e}")
finally:
    # Always force exit to avoid portaudio cleanup issues
    os._exit(0)