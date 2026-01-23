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
    # Generate samples (use exact integer sample count)
    num_samples = int(sample_rate * duration)
    t = np.arange(num_samples, dtype=np.float64) / sample_rate

    # For pure tone (start == end), use simple phase calculation
    if start_frequency == end_frequency:
        phase = 2 * np.pi * start_frequency * t
    else:
        # For sweep, use linear chirp formula
        # phase(t) = 2π * (f0*t + (f1-f0)*t²/(2*duration))
        phase = 2 * np.pi * (start_frequency * t + (end_frequency - start_frequency) * t**2 / (2 * duration))

    # Generate pure sine wave
    wave = np.sin(phase)

    # Scale to 80% amplitude to prevent clipping
    wave *= 0.8

    # Apply smooth fade using raised cosine (Hann window) instead of linear
    # This is smoother and introduces less distortion
    fade_samples = int(fade_seconds * sample_rate)
    if fade_samples > 0:
        # Fade in: raised cosine (first half of Hann window)
        fade_in = 0.5 * (1 - np.cos(np.pi * np.arange(fade_samples) / fade_samples))
        wave[:fade_samples] *= fade_in

        # Fade out: raised cosine (second half of Hann window)
        fade_out = 0.5 * (1 + np.cos(np.pi * np.arange(fade_samples) / fade_samples))
        wave[-fade_samples:] *= fade_out

    sd.play(wave, sample_rate)
    sd.wait()
