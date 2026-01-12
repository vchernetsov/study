"""Loop control commands: sweep."""

import sys
import time
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd

if TYPE_CHECKING:
    from ..console import StandConsole


def register(console: 'StandConsole') -> None:
    """Register loop commands with console."""
    console.do_sweep = lambda arg: do_sweep(console, arg)


def do_sweep(console: 'StandConsole', arg: str) -> None:
    """Sweep from 1 Hz to max frequency with smooth chirp. Usage: sweep [max_freq] [duration]

    Examples:
      sweep              # Use defaults from config
      sweep 200          # Sweep to 200 Hz with default duration
      sweep 300 30       # Sweep to 300 Hz in 30 seconds
    """
    args = arg.split()
    sample_rate = console.config_manager.getint('sound', 'sample_rate', fallback=44100)
    min_freq = 1.0
    max_freq = float(args[0]) if args else console.config_manager.getfloat('sweep', 'max_frequency')
    total_duration = float(args[1]) if len(args) > 1 else console.config_manager.getfloat('sweep', 'duration')

    print(f"  Sweeping {min_freq} Hz -> {max_freq} Hz in {total_duration:.0f} seconds")
    print(f"  Press Ctrl+C to stop")

    # Streaming state
    phase = [0.0]
    sample_idx = [0]
    total_samples = int(sample_rate * total_duration)

    def callback(outdata, frames, time_info, status):
        for i in range(frames):
            inst_freq = min_freq + (max_freq - min_freq) * (sample_idx[0] + i) / total_samples
            phase[0] += 2 * np.pi * inst_freq / sample_rate
            outdata[i] = 0.5 * np.sin(phase[0])
        sample_idx[0] += frames
        if sample_idx[0] >= total_samples:
            raise sd.CallbackStop()

    try:
        with sd.OutputStream(samplerate=sample_rate, channels=1, callback=callback, blocksize=2048):
            while sample_idx[0] < total_samples:
                current_freq = min_freq + (max_freq - min_freq) * sample_idx[0] / total_samples
                sys.stdout.write(f"\r  {current_freq:.1f} Hz  ")
                sys.stdout.flush()
                time.sleep(0.5)
        print(f"\n  Sweep complete")
    except KeyboardInterrupt:
        print("\n  Sweep interrupted")
    except Exception as e:
        print(f"\n  Sweep error: {e}")
