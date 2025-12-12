#!/usr/bin/env python3
"""
Stand - A console application with command interface using state machine transitions.
"""

import cmd
import configparser
from collections import deque
import os
import readline
import sys
import threading
import time

import numpy as np
import serial
import sounddevice as sd
from transitions import Machine

CONFIG_FILE = 'stand.conf'


class CommandStateMachine:
    """State machine managing command execution states."""

    states = ['idle', 'ready', 'running', 'paused', 'stopped']

    def __init__(self):
        self.machine = Machine(
            model=self,
            states=CommandStateMachine.states,
            initial='idle',
            auto_transitions=False,
        )

        # Define transitions
        self.machine.add_transition(trigger='initialize', source='idle', dest='ready')
        self.machine.add_transition(trigger='start', source='ready', dest='running')
        self.machine.add_transition(trigger='pause', source='running', dest='paused')
        self.machine.add_transition(trigger='resume', source=['paused', 'stopped'], dest='running')
        self.machine.add_transition(trigger='stop', source=['running', 'paused'], dest='stopped')
        self.machine.add_transition(trigger='reset', source='*', dest='idle')

    def on_enter_idle(self):
        print("  [State] Entered idle state")

    def on_enter_ready(self):
        print("  [State] System initialized and ready")

    def on_enter_running(self):
        print("  [State] Execution started")

    def on_enter_paused(self):
        print("  [State] Execution paused")

    def on_enter_stopped(self):
        print("  [State] Execution stopped")


class StandConsole(cmd.Cmd):
    """Interactive console for Stand application."""

    intro = "Welcome to Stand console. Type 'help' for available commands.\n"
    prompt = "stand> "

    def __init__(self, config_file=CONFIG_FILE):
        super().__init__()
        self.state_machine = CommandStateMachine()
        self.serial_port = None
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.config_loaded = False
        self.loop_thread = None
        self.loop_stop_event = threading.Event()
        self.loop_save_on_stop = True
        self.loop_history = deque(maxlen=10)
        self.output_lock = threading.Lock()
        # Auto-init and connect on startup
        self._auto_init()
        self._auto_connect()

    def _auto_init(self):
        """Initialize system on startup."""
        self._load_config()
        try:
            self.state_machine.initialize()
        except Exception:
            pass

    def _auto_connect(self):
        """Connect to Arduino on startup."""
        port = self._get_serial_port()
        baudrate = self._get_baudrate()
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            print(f"  Connected to {port} at {baudrate} baud")
        except serial.SerialException as e:
            print(f"  Warning: Could not connect to {port}: {e}")

    def _load_config(self):
        """Load settings from config file."""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            self.config_loaded = True
            print(f"  Loaded config from {self.config_file}")
        else:
            self._create_default_config()
            self.config_loaded = True

    def _create_default_config(self):
        """Create default config file."""
        self.config['serial'] = {
            'port': '/dev/ttyUSB0',
            'baudrate': '9600',
            'baudrates': '9600,19200,38400,57600,115200'
        }
        self.config['commands'] = {
            'ir_engage': '!r\\n',
            'test': '!t\\n'
        }
        self.config['sound'] = {
            'frequency': '440',
            'duration': '1.0',
            'sample_rate': '44100'
        }
        self.config['loop'] = {
            'current_frequency': '1.0',
            'min_frequency': '1.0',
            'max_frequency': '400.0',
            'step': '0.1',
            'duration': '1.0'
        }
        self._save_config()
        print(f"  Created default config: {self.config_file}")

    def _save_config(self):
        """Save current settings to config file."""
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def _get_serial_port(self):
        return self.config.get('serial', 'port', fallback='/dev/ttyUSB0')

    def _get_baudrate(self):
        return self.config.getint('serial', 'baudrate', fallback=9600)

    def _get_ir_command(self):
        cmd_str = self.config.get('commands', 'ir_engage', fallback='!r\\n')
        print (f"'{cmd_str}'")
        return cmd_str.encode().decode('unicode_escape').encode()

    def _get_test_command(self):
        cmd_str = self.config.get('commands', 'test', fallback='!t\\n')
        return cmd_str.encode().decode('unicode_escape').encode()

    def do_state(self, arg):
        """Show current state of the state machine."""
        print(f"Current state: {self.state_machine.state}")

    def _start_loop(self):
        """Internal method to start the loop thread."""
        # Stop any existing loop first
        self._stop_loop(save=True)
        # Reset and start fresh
        self.loop_stop_event.clear()
        self.loop_save_on_stop = True
        self.loop_thread = threading.Thread(target=self._loop_worker, daemon=True)
        self.loop_thread.start()

    def _stop_loop(self, save=True):
        """Internal method to stop the loop thread."""
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_save_on_stop = save
            self.loop_stop_event.set()
            # Don't call sd.stop() - let the current playback finish naturally
            # The thread checks loop_stop_event after each sd.wait()
            self.loop_thread.join(timeout=5)
        self.loop_thread = None

    def do_start(self, arg):
        """Start execution and begin frequency loop (ready -> running)."""
        try:
            self.state_machine.start()
            self._start_loop()
        except Exception as e:
            print(f"  Error: Cannot start from state '{self.state_machine.state}'")

    def do_pause(self, arg):
        """Pause execution and stop loop without saving (running -> paused)."""
        try:
            self._stop_loop(save=False)
            self.state_machine.pause()
        except Exception as e:
            print(f"  Error: Cannot pause from state '{self.state_machine.state}'")

    def do_resume(self, arg):
        """Resume execution and restart loop (paused/stopped -> running)."""
        try:
            self.state_machine.resume()
            self._start_loop()
        except Exception as e:
            print(f"  Error: Cannot resume from state '{self.state_machine.state}'")

    def do_stop(self, arg):
        """Stop execution and loop without saving progress (running/paused -> stopped)."""
        try:
            self._stop_loop(save=False)
            self.state_machine.stop()
        except Exception as e:
            print(f"  Error: Cannot stop from state '{self.state_machine.state}'")

    def do_reset(self, arg):
        """Reset the system to idle state."""
        self.state_machine.reset()

    def do_transitions(self, arg):
        """Show available transitions from current state."""
        current = self.state_machine.state
        triggers = self.state_machine.machine.get_triggers(current)
        if triggers:
            print(f"Available transitions from '{current}':")
            for trigger in triggers:
                print(f"  {trigger}")
        else:
            print(f"No transitions available from '{current}'")

    def do_reconnect(self, arg):
        """Reconnect to Arduino serial port if connection was lost."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        port = self._get_serial_port()
        baudrate = self._get_baudrate()
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            print(f"  Reconnected to {port} at {baudrate} baud")
        except serial.SerialException as e:
            print(f"  Error: {e}")

    def do_disconnect(self, arg):
        """Disconnect from serial port."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print("  Disconnected")
        else:
            print("  Not connected")

    def do_ir(self, arg):
        """Engage the IR lamp by sending command from config to Arduino."""
        if not self.serial_port or not self.serial_port.is_open:
            print("  Error: Not connected. Use 'connect' first.")
            return
        try:
            cmd = self._get_ir_command()
            self.serial_port.write(cmd)
            print("  IR lamp command sent")
        except serial.SerialException as e:
            print(f"  Error: {e}")

    def do_test(self, arg):
        """Test Arduino connection by sending test command, showing response, and playing sound."""
        if not self.serial_port or not self.serial_port.is_open:
            print("  Error: Not connected. Use 'connect' first.")
            return
        try:
            self.serial_port.reset_input_buffer()
            cmd = self._get_test_command()
            self.serial_port.write(cmd)
            response = self.serial_port.readline().decode().strip()
            self.do_sound("")
        except serial.SerialException as e:
            print(f"  Error: {e}")

    def do_sound(self, arg):
        """Generate and play a sine wave sound. Usage: sound [frequency] [duration]

        Examples:
          sound              # Use defaults from config
          sound 440          # 440 Hz with default duration
          sound 880 0.5      # 880 Hz for 0.5 seconds
        """
        args = arg.split()
        frequency = float(args[0]) if args else self.config.getfloat('sound', 'frequency', fallback=440)
        duration = float(args[1]) if len(args) > 1 else self.config.getfloat('sound', 'duration', fallback=1.0)
        sample_rate = self.config.getint('sound', 'sample_rate', fallback=44100)

        try:
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            wave = 0.5 * np.sin(2 * np.pi * frequency * t)
            print(f"  Playing {frequency} Hz for {duration}s...")
            sd.play(wave, sample_rate)
            sd.wait()
            print("  Done")
        except Exception as e:
            print(f"  Error: {e}")

    def _loop_worker(self):
        """Background thread worker for sound loop."""
        sample_rate = self.config.getint('sound', 'sample_rate', fallback=44100)
        max_freq = self.config.getfloat('loop', 'max_frequency', fallback=400.0)
        step = self.config.getfloat('loop', 'step', fallback=0.1)
        duration = self.config.getfloat('loop', 'duration', fallback=1.0)

        while not self.loop_stop_event.is_set():
            frequency = self.config.getfloat('loop', 'current_frequency', fallback=1.0)

            if frequency > max_freq:
                print(f"  Loop completed (reached {max_freq} Hz)")
                break

            try:
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                wave = 0.5 * np.sin(2 * np.pi * frequency * t)
                self.loop_history.append(f"{frequency:.1f} Hz")
                # Print frequency - save current input, print on new line, restore prompt
                with self.output_lock:
                    # Move to new line, print status, then reprint prompt
                    sys.stdout.write(f"\r  ♪ {frequency:.1f} Hz\n{self.prompt}")
                    sys.stdout.flush()
                    # Redisplay any partial input the user has typed
                    try:
                        line = readline.get_line_buffer()
                        if line:
                            sys.stdout.write(line)
                            sys.stdout.flush()
                    except Exception:
                        pass
                sd.play(wave, sample_rate)
                sd.wait()
                time.sleep(0.15)  # Small delay for audio cleanup

                if self.loop_stop_event.is_set():
                    break

                # Increment and save frequency
                frequency += step
                self.config.set('loop', 'current_frequency', str(frequency))
                if self.loop_save_on_stop:
                    self._save_config()

            except Exception as e:
                print(f"  Loop error: {e}")
                break

    def do_loopreset(self, arg):
        """Reset loop frequency to minimum (1 Hz)."""
        min_freq = self.config.getfloat('loop', 'min_frequency', fallback=1.0)
        self.config.set('loop', 'current_frequency', str(min_freq))
        self._save_config()
        print(f"  Loop frequency reset to {min_freq} Hz")

    def do_loopstatus(self, arg):
        """Show current loop status, frequency, and last 10 played frequencies."""
        running = self.loop_thread and self.loop_thread.is_alive()
        frequency = self.config.getfloat('loop', 'current_frequency', fallback=1.0)
        max_freq = self.config.getfloat('loop', 'max_frequency', fallback=400.0)
        step = self.config.getfloat('loop', 'step', fallback=0.1)
        print(f"  Status: {'running' if running else 'stopped'}")
        print(f"  Current: {frequency:.1f} Hz | Max: {max_freq} Hz | Step: {step} Hz")
        if self.loop_history:
            print(f"  History: {' -> '.join(self.loop_history)}")

    def do_config(self, arg):
        """Show current configuration."""
        print("Current configuration:")
        for section in self.config.sections():
            print(f"  [{section}]")
            for key, value in self.config.items(section):
                print(f"    {key} = {value}")

    def do_set(self, arg):
        """Set configuration value. Usage: set <section>.<key> <value>

        Examples:
          set serial.port /dev/ttyACM0
          set serial.baudrate 115200
          set commands.ir_engage !r\\n
        """
        if not self.config_loaded:
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

        if not self.config.has_section(section):
            self.config.add_section(section)
            print(f"  Created new section [{section}]")

        self.config.set(section, key, value)
        self._save_config()
        print(f"  Set {section}.{key} = {value}")

    def complete_set(self, text, line, begidx, endidx):
        """Autocomplete for set command."""
        args = line.split()
        if len(args) == 1 or (len(args) == 2 and not line.endswith(' ')):
            # Complete section.key
            options = []
            for section in self.config.sections():
                for key in self.config.options(section):
                    options.append(f"{section}.{key}")
            return [opt for opt in options if opt.startswith(text)]
        elif len(args) >= 2:
            # Complete value based on key
            key_path = args[1]
            if '.' in key_path:
                section, key = key_path.split('.', 1)
                options = []
                # Add current value as option
                if self.config.has_option(section, key):
                    current = self.config.get(section, key)
                    options.append(current)
                # Add context-specific suggestions
                if key == 'port':
                    import serial.tools.list_ports
                    options.extend([p.device for p in serial.tools.list_ports.comports()])
                elif key == 'baudrate':
                    baudrates_str = self.config.get('serial', 'baudrates', fallback='9600,19200,38400,57600,115200')
                    options.extend(baudrates_str.split(','))
                return [opt for opt in options if opt.startswith(text)]
        return []

    def complete_help(self, text, line, begidx, endidx):
        """Autocomplete for help command."""
        commands = [name[3:] for name in dir(self) if name.startswith('do_')]
        return [cmd for cmd in commands if cmd.startswith(text)]

    def do_quit(self, arg):
        """Exit the console."""
        self._stop_loop(save=False)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        print("Goodbye!")
        return True

    def do_exit(self, arg):
        """Exit the console."""
        return self.do_quit(arg)

    def default(self, line):
        """Handle unknown commands."""
        print(f"Unknown command: {line}")
        print("Type 'help' for available commands.")

    def emptyline(self):
        """Do nothing on empty input."""
        pass

    def do_help(self, arg):
        """Show help for commands. Usage: help [command]"""
        if arg:
            # Show help for specific command
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
  reconnect     Reconnect to Arduino if connection was lost.

  disconnect    Close the serial connection to Arduino.

  test          Send test command to Arduino and play sound on response.

DEVICE CONTROL:
  ir            Engage the IR lamp by sending command to Arduino.
                Command sequence is defined in stand.conf.

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

LOOP UTILITIES:
  loopstatus    Show current loop status and frequency.

  loopreset     Reset loop frequency back to minimum (1 Hz).

OTHER:
  help [cmd]    Show this help or help for specific command.
  quit, exit    Exit the application.

TYPICAL WORKFLOW:
  1. test                  # Verify connection (plays sound)
  2. ir                    # Engage IR lamp
  3. start                 # Start frequency sweep loop
  4. pause / resume        # Control loop as needed
  5. stop                  # Stop without saving progress

CONFIG FILE (stand.conf):
  [serial]
  port = /dev/ttyUSB0      # Default serial port
  baudrate = 9600          # Serial baud rate

  [commands]
  ir_engage = !r\\n         # Command to engage IR lamp
  test = !t\\n              # Test/ping command

  [sound]
  frequency = 440          # Default frequency in Hz
  duration = 1.0           # Default duration in seconds
  sample_rate = 44100      # Audio sample rate

  [loop]
  current_frequency = 1.0  # Current/resume frequency
  min_frequency = 1.0      # Starting frequency
  max_frequency = 400.0    # Maximum frequency
  step = 0.1               # Frequency increment per cycle
  duration = 1.0           # Duration of each tone
""")


def main():
    """Entry point for the application."""
    console = StandConsole()
    try:
        console.cmdloop()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
