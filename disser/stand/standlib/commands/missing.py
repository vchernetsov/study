"""Missing frequencies detection and rerun commands."""

import datetime
import os
import re
import threading
import time
from pathlib import Path
from typing import List, Set, TYPE_CHECKING

import numpy as np
import sounddevice as sd

if TYPE_CHECKING:
    from ..console import StandConsole


def register(console: 'StandConsole') -> None:
    """Register missing frequency commands with console."""
    console.do_missing = lambda arg: do_missing(console, arg)
    console.do_rerun = lambda arg: do_rerun(console, arg)


def get_captured_frequencies(videos_dir: str) -> Set[float]:
    """Extract frequencies from video filenames in directory."""
    frequencies = set()
    pattern = re.compile(r'^(\d+\.\d+)-')

    if not os.path.exists(videos_dir):
        return frequencies

    for filename in os.listdir(videos_dir):
        match = pattern.match(filename)
        if match:
            try:
                freq = float(match.group(1))
                frequencies.add(freq)
            except ValueError:
                pass

    return frequencies


def get_expected_frequencies(start: float, end: float, step: float) -> Set[float]:
    """Generate set of expected frequencies."""
    frequencies = set()
    freq = start
    while freq <= end + 0.0001:  # Small epsilon for float comparison
        frequencies.add(round(freq, 2))
        freq += step
    return frequencies


def find_missing_frequencies(console: 'StandConsole') -> List[float]:
    """Find frequencies that are expected but not captured."""
    videos_dir = console.config_manager.get('fetch', 'output_dir', fallback='./videos')
    start_freq = console.config_manager.getfloat('loop', 'start_frequency', fallback=0.0)
    max_freq = console.config_manager.getfloat('loop', 'max_frequency', fallback=400.0)
    step = console.config_manager.getfloat('loop', 'step', fallback=0.5)

    captured = get_captured_frequencies(videos_dir)
    expected = get_expected_frequencies(start_freq, max_freq, step)

    missing = expected - captured
    return sorted(missing)


def do_missing(console: 'StandConsole', arg: str) -> None:
    """Show frequencies that are missing from fetched videos.

    Compares video files in output directory against expected frequency range.
    Expected range is from start_frequency to max_frequency with step increment.

    Usage: missing
    """
    videos_dir = console.config_manager.get('fetch', 'output_dir', fallback='./videos')
    start_freq = console.config_manager.getfloat('loop', 'start_frequency', fallback=0.0)
    max_freq = console.config_manager.getfloat('loop', 'max_frequency', fallback=400.0)
    step = console.config_manager.getfloat('loop', 'step', fallback=0.5)

    print(f"  Checking {videos_dir} for missing frequencies...")
    print(f"  Expected range: {start_freq} Hz to {max_freq} Hz (step {step})")

    captured = get_captured_frequencies(videos_dir)
    expected = get_expected_frequencies(start_freq, max_freq, step)
    missing = sorted(expected - captured)

    print(f"  Captured: {len(captured)} frequencies")
    print(f"  Expected: {len(expected)} frequencies")
    print(f"  Missing:  {len(missing)} frequencies")

    if missing:
        print(f"\n  Missing frequencies:")
        # Group consecutive ranges
        if len(missing) <= 20:
            for freq in missing:
                print(f"    {freq:.2f} Hz")
        else:
            # Show ranges for large lists
            ranges = []
            start = missing[0]
            prev = missing[0]
            for freq in missing[1:]:
                if abs(freq - prev - step) < 0.01:
                    prev = freq
                else:
                    if start == prev:
                        ranges.append(f"{start:.2f}")
                    else:
                        ranges.append(f"{start:.2f}-{prev:.2f}")
                    start = freq
                    prev = freq
            # Add last range
            if start == prev:
                ranges.append(f"{start:.2f}")
            else:
                ranges.append(f"{start:.2f}-{prev:.2f}")

            print(f"    {', '.join(ranges[:10])} Hz" + (" ..." if len(ranges) > 10 else ""))

        print(f"\n  Use 'rerun' to loop through missing frequencies")
    else:
        print("\n  All frequencies captured!")


def do_rerun(console: 'StandConsole', arg: str) -> None:
    """Run the frequency loop only for missing frequencies.

    Finds frequencies missing from video directory and plays them sequentially,
    triggering IR and logging like the normal loop.

    Usage: rerun
    """
    missing = find_missing_frequencies(console)

    if not missing:
        print("  No missing frequencies found")
        return

    print(f"  Found {len(missing)} missing frequencies to rerun")
    print(f"  First: {missing[0]:.2f} Hz, Last: {missing[-1]:.2f} Hz")

    # Start the rerun loop
    _run_missing_loop(console, missing)


def _run_missing_loop(console: 'StandConsole', frequencies: List[float]) -> None:
    """Run loop for specific list of frequencies."""
    from ..workers import OutputPrinter, format_time

    sample_rate = console.config_manager.getint('sound', 'sample_rate', fallback=44100)
    duration = console.config_manager.getfloat('loop', 'duration', fallback=1.0)
    loop_sleep = console.config_manager.getfloat('loop', 'loop_sleep', fallback=10.0)
    ir_delay = console.config_manager.getfloat('loop', 'ir_delay', fallback=10.0)
    log_file = console.config_manager.get('loop', 'log_file', fallback='stand.log')

    printer = OutputPrinter(console.prompt, console.output_lock)
    stop_event = threading.Event()
    ir_trigger = threading.Event()

    # Store stop event for external control
    console._rerun_stop_event = stop_event

    def ir_worker():
        """IR worker thread for rerun."""
        while not stop_event.is_set():
            ir_trigger.wait()
            if stop_event.is_set():
                break
            ir_trigger.clear()

            # Wait before sending IR
            time.sleep(ir_delay)
            if stop_event.is_set():
                break

            # Send IR command
            if console.serial_handler.is_connected:
                try:
                    cmd = console.config_manager.ir_command
                    success = console.serial_handler.write(cmd)
                    if success:
                        freq = console.config_manager.getfloat('loop', 'current_frequency', fallback=0)
                        try:
                            with open(log_file, 'a') as f:
                                f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {freq:.1f}\n")
                        except Exception:
                            pass
                        printer.print_line(f"  -> IR sent @ {freq:.2f} Hz")
                except Exception as e:
                    printer.print_line(f"  !! IR error: {e}")
            else:
                printer.print_line(f"  !! IR skipped (not connected)")

    # Start IR thread
    ir_thread = threading.Thread(target=ir_worker, daemon=True)
    ir_thread.start()

    total = len(frequencies)
    time_per_iter = duration + loop_sleep

    try:
        for i, frequency in enumerate(frequencies):
            if stop_event.is_set():
                break

            # Update current frequency in config
            console.config_manager.set('loop', 'current_frequency', str(frequency))

            # Calculate progress
            remaining = total - i
            time_left = remaining * time_per_iter
            eta = datetime.datetime.now() + datetime.timedelta(seconds=time_left)

            progress = f"Rerun: {i+1}/{total} ({format_time(time_left)} remaining, ends at {eta.strftime('%H:%M')})"
            printer.print_line(f"  ♪ {frequency:.2f} Hz | {progress}")

            # Signal IR thread
            ir_trigger.set()

            # Streaming audio playback
            phase = [0.0]
            total_samples = int(sample_rate * duration)
            samples_played = [0]

            def audio_callback(outdata, frames, time_info, status):
                if stop_event.is_set():
                    raise sd.CallbackStop()
                for j in range(frames):
                    if samples_played[0] >= total_samples:
                        outdata[j:] = 0
                        raise sd.CallbackStop()
                    phase[0] += 2 * np.pi * frequency / sample_rate
                    outdata[j] = 0.5 * np.sin(phase[0])
                    samples_played[0] += 1

            with sd.OutputStream(samplerate=sample_rate, channels=1,
                                 callback=audio_callback, blocksize=2048):
                while samples_played[0] < total_samples and not stop_event.is_set():
                    time.sleep(0.1)

            if stop_event.is_set():
                break

            # Sleep between iterations
            printer.print_line(f"  zzz sleeping {loop_sleep:.0f}s...")
            sleep_iterations = int(loop_sleep * 10)
            for _ in range(sleep_iterations):
                if stop_event.is_set():
                    break
                time.sleep(0.1)

        if not stop_event.is_set():
            print(f"\n  Rerun complete! Processed {total} missing frequencies")
        else:
            print(f"\n  Rerun stopped at {frequency:.2f} Hz")

    except KeyboardInterrupt:
        stop_event.set()
        print(f"\n  Rerun interrupted")
    finally:
        stop_event.set()
        ir_trigger.set()  # Wake up IR thread
        ir_thread.join(timeout=2)
        console._rerun_stop_event = None
