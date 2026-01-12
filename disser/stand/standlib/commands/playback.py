"""Playback commands: sound, ir, test."""

from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd

if TYPE_CHECKING:
    from ..console import StandConsole


def register(console: 'StandConsole') -> None:
    """Register playback commands with console."""
    console.do_sound = lambda arg: do_sound(console, arg)
    console.do_ir = lambda arg: do_ir(console, arg)
    console.do_test = lambda arg: do_test(console, arg)


def do_sound(console: 'StandConsole', arg: str) -> None:
    """Generate and play a sine wave sound. Usage: sound [frequency] [duration]

    Examples:
      sound              # Use defaults from config
      sound 440          # 440 Hz with default duration
      sound 880 0.5      # 880 Hz for 0.5 seconds
    """
    args = arg.split()
    frequency = float(args[0]) if args else console.config_manager.getfloat('sound', 'frequency')
    duration = float(args[1]) if len(args) > 1 else console.config_manager.getfloat('sound', 'duration')
    sample_rate = console.config_manager.getint('sound', 'sample_rate')

    try:
        print(f"  [SOUND] Generating sine wave: {frequency} Hz, {duration}s, {sample_rate} sample rate")
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        wave = 0.5 * np.sin(2 * np.pi * frequency * t)
        print(f"  [SOUND] Playing audio...")
        sd.play(wave, sample_rate)
        sd.wait()
        print(f"  [SOUND] Playback complete")
    except Exception as e:
        print(f"  [SOUND] Error: {e}")


def do_ir(console: 'StandConsole', arg: str) -> None:
    """Engage the IR lamp by sending command from config to Arduino."""
    if not console.serial_handler.is_connected:
        print("  Error: Not connected.")
        return
    try:
        port = console.config_manager.serial_port
        print(f"  [IR] Sending command to {port}")
        if console.serial_handler.send_ir_command():
            print(f"  [IR] Command sent successfully")
        else:
            print(f"  [IR] Error: Write failed")
    except Exception as e:
        print(f"  [IR] Error: {e}")


def do_test(console: 'StandConsole', arg: str) -> None:
    """Test Arduino connection by sending IR command and playing confirmation sound."""
    if not console.serial_handler.is_connected:
        print("  Error: Not connected.")
        return
    try:
        port = console.config_manager.serial_port
        print(f"  [TEST] Sending IR command to {port}")
        if console.serial_handler.send_test_command():
            print(f"  [TEST] Command sent successfully")
            print(f"  [TEST] Playing confirmation sound")
            do_sound(console, "")
        else:
            print(f"  [TEST] Error: Write failed")
    except Exception as e:
        print(f"  [TEST] Error: {e}")
