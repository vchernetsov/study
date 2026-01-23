"""Help commands: help."""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..console import StandConsole


def register(console: 'StandConsole') -> None:
    """Register help commands with console."""
    console.do_help = lambda arg: do_help(console, arg)
    console.complete_help = lambda text, line, begidx, endidx: complete_help(console, text, line, begidx, endidx)


def do_help(console: 'StandConsole', arg: str) -> None:
    """Show help for commands. Usage: help [command]"""
    if arg:
        try:
            func = getattr(console, 'do_' + arg)
            print(f"\n  {arg}: {func.__doc__}\n")
        except AttributeError:
            print(f"  Unknown command: {arg}")
        return

    print("""
Stand - Arduino IR Lamp Controller
===================================
(Auto-connects to Arduino on startup using config settings)

CONFIGURATION:
  config        Display current configuration from stand.conf.

  set <section>.<key> <value>
                Set a configuration value and save to stand.conf.
                Examples: set serial.port /dev/ttyACM0
                          set serial.baudrate 115200
                          set commands.ir_engage !r\\n

SERIAL CONNECTION:
  disconnect    Close the serial connection to Arduino.

  test          Send IR command to Arduino and play confirmation sound.

DEVICE CONTROL:
  ir            Engage the IR lamp by sending command to Arduino.

  sound [freq] [duration]
                Generate and play a sine wave sound.
                Examples: sound              # Use defaults from config
                          sound 440          # 440 Hz with default duration
                          sound 880 0.5      # 880 Hz for 0.5 seconds

STATE MACHINE (controls frequency loop):
  state         Show current state of the system.
                States: idle, ready, running, paused, stopped

  transitions   List available state transitions from current state.

  start         Start frequency loop (ready -> running)
                Plays 1 Hz -> 400 Hz, incrementing by 0.1 Hz each second.
                Frequency saved to config after each cycle.

  pause         Pause loop without saving (running -> paused)

  resume        Resume loop from current frequency (paused/stopped -> running)

  stop          Stop loop without saving (running/paused -> stopped)

  reset         Reset state to idle (from any state)

CAMERA:
  sync          Sync camera time with host computer using gphoto2.

  fetch [dir]   Fetch photos from mounted camera filesystem and rename.
                Copies from DCIM folder to ./photos/ by default, then
                prompts to rename as <frequency>-<timestamp>.<extension>

  missing       Show frequencies missing from fetched videos.
                Compares files in output directory against expected range.

  rerun         Loop through only the missing frequencies.
                Plays sound and triggers IR for each missing frequency.

OTHER:
  help [cmd]    Show this help or help for specific command.
  quit, exit    Exit the application.

TYPICAL WORKFLOW:
  1. test                  # Verify connection (plays sound)
  2. sync                  # Sync camera time (optional)
  3. ir                    # Engage IR lamp
  4. start                 # Start frequency sweep loop
  5. pause / resume        # Control loop as needed
  6. stop                  # Stop without saving progress

CONFIG FILE (stand.conf):
  [serial]
  port = /dev/ttyUSB0      # Default serial port
  baudrate = 9600          # Serial baud rate

  [commands]
  ir_engage = !r\\n         # Command to engage IR lamp

  [sound]
  frequency = 440          # Default frequency in Hz
  duration = 1.0           # Default duration in seconds
  sample_rate = 44100      # Audio sample rate

  [loop]
  current_frequency = 1.0  # Current/resume frequency
  max_frequency = 400.0    # Maximum frequency
  step = 0.1               # Frequency increment per cycle
  duration = 1.0           # Duration of each tone
""")


def complete_help(console: 'StandConsole', text: str, line: str, begidx: int, endidx: int) -> List[str]:
    """Autocomplete for help command."""
    commands = [name[3:] for name in dir(console) if name.startswith('do_')]
    return [cmd for cmd in commands if cmd.startswith(text)]
