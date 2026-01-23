"""
Sounds module
"""

import numpy as np
import sounddevice as sd


def sweep(start_frequency, end_frequency, duration, fade_seconds=2, sample_rate=44100):
    """
    Generate and play a frequency sweep (chirp)

    Args:
        start_frequency: Starting frequency in Hz
        end_frequency: Ending frequency in Hz
        duration: Duration in seconds
        sample_rate: Sample rate in Hz (default 44100)
        fade_seconds: Time in seconds to fade-in and fade-out (default=2).
    """
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    frequency = np.linspace(start_frequency, end_frequency, len(t))
    phase = 2 * np.pi * np.cumsum(frequency) / sample_rate
    wave = np.sin(phase)

    # Apply fade-in and fade-out to remove clicks
    fade_samples = int(fade_seconds * sample_rate)
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    wave[:fade_samples] *= fade_in
    wave[-fade_samples:] *= fade_out

    sd.play(wave, sample_rate)
    sd.wait()
