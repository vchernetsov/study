"""Main console application."""

import cmd
import threading

from .config import ConfigManager
from .state_machine import CommandStateMachine
from .serial_handler import SerialHandler
from .workers import WorkerManager
from .camera import CameraSync, CameraFetch
from .commands import register_commands


class StandConsole(cmd.Cmd):
    """Interactive console for Stand application."""

    intro = "Welcome to Stand console. Type 'help' for available commands.\n"
    prompt = "stand> "

    def __init__(self, config_file: str = 'stand.conf'):
        super().__init__()

        # Core components
        self.config_manager = ConfigManager(config_file)
        self.state_machine = CommandStateMachine()
        self.serial_handler = SerialHandler(self.config_manager)
        self.output_lock = threading.Lock()

        self.worker_manager = WorkerManager(
            config=self.config_manager,
            serial_handler=self.serial_handler,
            state_machine=self.state_machine,
            output_lock=self.output_lock,
            prompt=self.prompt,
        )

        # Camera utilities
        self.camera_fetch = CameraFetch(self.config_manager)

        # Register command modules
        register_commands(self)

        # Auto-initialize
        self._auto_init()

    def _auto_init(self) -> None:
        """Initialize config and connect."""
        self.config_manager.load()
        try:
            self.state_machine.initialize()
        except Exception:
            pass
        self.serial_handler.connect()

    # Serial commands
    def do_disconnect(self, arg: str) -> None:
        """Disconnect from serial port."""
        self.serial_handler.disconnect()

    # Camera commands
    def do_sync(self, arg: str) -> None:
        """Sync camera time with host computer."""
        CameraSync.sync_time()

    def do_fetch(self, arg: str) -> None:
        """Fetch photos from mounted camera and optionally rename using log entries.

        Copies all files from connected camera filesystem to ./videos/ directory,
        then prompts to rename files based on stand.log entries.
        Naming format: <frequency>-<timestamp>.<extension>

        Usage: fetch [output_dir]
          fetch              # Copies to ./videos/
          fetch ./my_videos  # Copies to ./my_videos/
        """
        output_dir = arg.strip() if arg.strip() else None
        copied_files = self.camera_fetch.fetch_files(output_dir)
        if copied_files:
            log_entries = self.camera_fetch.load_log_entries()
            tolerance_secs = self.config_manager.getint('fetch', 'tolerance', fallback=5)
            renamed, skipped, deleted = self.camera_fetch.rename_with_log(
                copied_files, log_entries, tolerance_secs, interactive=True
            )
            print(f"\n  [FETCH] Complete: {renamed} renamed, {skipped} skipped, {deleted} deleted")

    # Config commands
    def do_config(self, arg: str) -> None:
        """Show current configuration."""
        print("Current configuration:")
        for section in self.config_manager.sections():
            print(f"  [{section}]")
            for key, value in self.config_manager.items(section):
                print(f"    {key} = {value}")

    def do_set(self, arg: str) -> None:
        """Set configuration value. Usage: set <section>.<key> <value>

        Examples:
          set serial.port /dev/ttyACM0
          set serial.baudrate 115200
          set commands.ir_engage !r\\n
        """
        if not self.config_manager.loaded:
            print("  Warning: Config not loaded yet.")

        args = arg.split(None, 1)
        if len(args) < 2:
            print("  Usage: set <section>.<key> <value>")
            print("  Example: set serial.port /dev/ttyUSB0")
            return

        key_path, value = args
        if '.' not in key_path:
            print("  Error: Key must be in format <section>.<key>")
            print("  Example: set serial.port /dev/ttyUSB0")
            return

        section, key = key_path.split('.', 1)

        if not self.config_manager.has_section(section):
            self.config_manager.add_section(section)
            print(f"  Created new section [{section}]")

        self.config_manager.set(section, key, value)
        self.config_manager.save()
        print(f"  Set {section}.{key} = {value}")

    def complete_set(self, text, line, begidx, endidx):
        """Autocomplete for set command."""
        args = line.split()
        if len(args) == 1 or (len(args) == 2 and not line.endswith(' ')):
            # Complete section.key
            options = []
            for section in self.config_manager.sections():
                for key in self.config_manager.options(section):
                    options.append(f"{section}.{key}")
            return [opt for opt in options if opt.startswith(text)]
        elif len(args) >= 2:
            # Complete value based on key
            key_path = args[1]
            if '.' in key_path:
                section, key = key_path.split('.', 1)
                options = []
                # Add current value as option
                if self.config_manager.has_option(section, key):
                    current = self.config_manager.get(section, key)
                    options.append(current)
                # Add context-specific suggestions
                if key == 'port':
                    import serial.tools.list_ports
                    options.extend([p.device for p in serial.tools.list_ports.comports()])
                elif key == 'baudrate':
                    baudrates_str = self.config_manager.get('serial', 'baudrates', fallback='9600,19200,38400,57600,115200')
                    options.extend(baudrates_str.split(','))
                elif key in ('frequency', 'current_frequency'):
                    options.extend(['1.0', '10.0', '50.0', '100.0', '200.0', '400.0'])
                elif key == 'max_frequency':
                    options.extend(['100.0', '200.0', '400.0', '480.0', '1000.0'])
                elif key == 'step':
                    options.extend(['0.1', '0.2', '0.5', '1.0', '2.0', '5.0'])
                elif key == 'duration':
                    options.extend(['1.0', '5.0', '10.0', '20.0', '30.0', '60.0'])
                elif key in ('ir_delay', 'loop_sleep'):
                    options.extend(['5.0', '10.0', '15.0', '20.0', '30.0'])
                elif key == 'max_loops_per_run':
                    options.extend(['50', '100', '200', '500', '1000'])
                elif key == 'sample_rate':
                    options.extend(['22050', '44100', '48000', '96000'])
                elif key == 'log_file':
                    options.extend(['stand.log', 'experiment.log'])
                return [opt for opt in options if opt.startswith(text)]
        return []

    def complete_help(self, text, line, begidx, endidx):
        """Autocomplete for help command."""
        commands = [name[3:] for name in dir(self) if name.startswith('do_')]
        return [cmd for cmd in commands if cmd.startswith(text)]

    # Exit commands
    def do_quit(self, arg: str) -> bool:
        """Exit the console."""
        self.worker_manager.stop(save=False)
        self.serial_handler.disconnect()
        print("Goodbye!")
        return True

    def do_exit(self, arg: str) -> bool:
        """Exit the console."""
        return self.do_quit(arg)

    def default(self, line: str) -> None:
        """Handle unknown commands."""
        print(f"Unknown command: {line}")
        print("Type 'help' for available commands.")

    def emptyline(self) -> None:
        """Do nothing on empty input."""
        pass

    def do_help(self, arg: str) -> None:
        """Show help for commands. Usage: help [command]"""
        if arg:
            try:
                func = getattr(self, 'do_' + arg)
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
