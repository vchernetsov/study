#!/usr/bin/env python3
"""
Stand - A console application with command interface using state machine transitions.
"""

import cmd
import configparser
from collections import deque
import datetime
import glob
import os
import readline
import shutil
import subprocess
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
        self.ir_thread = None
        self.loop_stop_event = threading.Event()
        self.ir_trigger_event = threading.Event()
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
            print(f"  [SERIAL] Opening port {port} at {baudrate} baud...")
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            print(f"  [SERIAL] Connected successfully")
        except serial.SerialException as e:
            print(f"  [SERIAL] Warning: Could not connect to {port}: {e}")

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
            'baudrate': '115200',
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
            'max_frequency': '120.0',
            'step': '0.25',
            'duration': '1.0',
            'ir_delay': '10.0',
            'loop_sleep': '10.0',
            'max_loops_per_run': '250',
            'log_file': 'stand.log'
        }
        self.config['fetch'] = {
            'output_dir': './videos',
            'tolerance': '5'
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
        return self.config.getint('serial', 'baudrate', fallback=115200)

    def _get_ir_command(self):
        cmd_str = self.config.get('commands', 'ir_engage', fallback='!r\\n')
        return cmd_str.encode().decode('unicode_escape').encode()

    def _get_test_command(self):
        cmd_str = self.config.get('commands', 'test', fallback='!t\\n')
        return cmd_str.encode().decode('unicode_escape').encode()

    def do_state(self, arg):
        """Show current state of the state machine."""
        print(f"Current state: {self.state_machine.state}")

    def _start_loop(self):
        """Internal method to start the loop and IR threads."""
        # Stop any existing loop first
        self._stop_loop(save=True)
        # Reset and start fresh
        self.loop_stop_event.clear()
        self.ir_trigger_event.clear()
        self.loop_save_on_stop = True
        self.loop_thread = threading.Thread(target=self._loop_worker, daemon=True)
        self.ir_thread = threading.Thread(target=self._ir_worker, daemon=True)
        self.loop_thread.start()
        self.ir_thread.start()

    def _stop_loop(self, save=True):
        """Internal method to stop the loop and IR threads."""
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_save_on_stop = save
            self.loop_stop_event.set()
            self.ir_trigger_event.set()  # Wake up IR thread so it can exit
            # Don't call sd.stop() - let the current playback finish naturally
            # The thread checks loop_stop_event after each sd.wait()
            self.loop_thread.join(timeout=5)
            self._clear_progress()
        if self.ir_thread and self.ir_thread.is_alive():
            self.ir_thread.join(timeout=2)
        self.loop_thread = None
        self.ir_thread = None

    def _sync_camera_time(self):
        """Sync camera time with host. Returns True if successful."""
        # Kill gvfs-gphoto2-volume-monitor to release USB device
        print("  [SYNC] Releasing camera from gvfs...")
        subprocess.run(['pkill', '-f', 'gvfs-gphoto2'], capture_output=True)
        time.sleep(0.5)

        print("  [SYNC] Detecting camera via gphoto2...")

        # Check if camera is connected
        try:
            result = subprocess.run(
                ['gphoto2', '--auto-detect'],
                capture_output=True, text=True, timeout=10
            )
        except FileNotFoundError:
            print("  [SYNC] Error: gphoto2 not installed")
            return False
        except subprocess.TimeoutExpired:
            print("  [SYNC] Error: gphoto2 timeout during detection")
            return False

        lines = result.stdout.strip().split('\n')
        cameras = [l for l in lines[2:] if l.strip()]
        if not cameras:
            print("  [SYNC] Error: No camera detected on USB")
            return False

        print(f"  [SYNC] Found camera: {cameras[0].strip()}")
        host_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"  [SYNC] Host time: {host_time}")
        print("  [SYNC] Setting camera datetime...")

        # Set camera datetime to current host time
        try:
            # Try setting datetime to now
            print("  [SYNC] Trying: gphoto2 --set-config datetime=now")
            result = subprocess.run(
                ['gphoto2', '--set-config', 'datetime=now'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                print("  [SYNC] Success: Camera time synchronized")
                return True

            # Try alternative: set datetime as unix timestamp
            timestamp = int(time.time())
            print(f"  [SYNC] Trying: gphoto2 --set-config-value /main/settings/datetime={timestamp}")
            result = subprocess.run(
                ['gphoto2', '--set-config-value', f'/main/settings/datetime={timestamp}'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                print("  [SYNC] Success: Camera time synchronized")
                return True

            # Try syncdatetime command
            print("  [SYNC] Trying: gphoto2 --set-config syncdatetime=1")
            result = subprocess.run(
                ['gphoto2', '--set-config', 'syncdatetime=1'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                print("  [SYNC] Success: Camera time synchronized")
                return True

            print(f"  [SYNC] Error: All methods failed")
            if result.stderr.strip():
                print(f"  [SYNC] Last error: {result.stderr.strip()}")
            return False

        except subprocess.TimeoutExpired:
            print("  [SYNC] Error: Timeout while setting camera time")
            return False

    def do_sync(self, arg):
        """Sync camera time with host computer."""
        self._sync_camera_time()

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
        port = self._get_serial_port()
        baudrate = self._get_baudrate()
        if self.serial_port and self.serial_port.is_open:
            print(f"  [SERIAL] Closing existing connection...")
            self.serial_port.close()
        try:
            print(f"  [SERIAL] Opening port {port} at {baudrate} baud...")
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            print(f"  [SERIAL] Reconnected successfully")
        except serial.SerialException as e:
            print(f"  [SERIAL] Error: {e}")

    def do_disconnect(self, arg):
        """Disconnect from serial port."""
        if self.serial_port and self.serial_port.is_open:
            port = self._get_serial_port()
            print(f"  [SERIAL] Closing connection to {port}...")
            self.serial_port.close()
            print(f"  [SERIAL] Disconnected")
        else:
            print("  [SERIAL] Not connected")

    def do_ir(self, arg):
        """Engage the IR lamp by sending command from config to Arduino."""
        if not self.serial_port or not self.serial_port.is_open:
            print("  Error: Not connected. Use 'connect' first.")
            return
        try:
            cmd = self._get_ir_command()
            port = self._get_serial_port()
            print(f"  [IR] Sending command to {port}: {cmd!r}")
            self.serial_port.write(cmd)
            print(f"  [IR] Command sent successfully")
        except serial.SerialException as e:
            print(f"  [IR] Error: {e}")

    def do_test(self, arg):
        """Test Arduino connection by sending test command, showing response, and playing sound."""
        if not self.serial_port or not self.serial_port.is_open:
            print("  Error: Not connected. Use 'connect' first.")
            return
        try:
            port = self._get_serial_port()
            cmd = self._get_test_command()
            print(f"  [TEST] Clearing input buffer on {port}")
            self.serial_port.reset_input_buffer()
            print(f"  [TEST] Sending test command: {cmd!r}")
            self.serial_port.write(cmd)
            print(f"  [TEST] Waiting for response...")
            response = self.serial_port.readline().decode().strip()
            print(f"  [TEST] Response: {response!r}")
            print(f"  [TEST] Playing confirmation sound")
            self.do_sound("")
        except serial.SerialException as e:
            print(f"  [TEST] Error: {e}")

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
            print(f"  [SOUND] Generating sine wave: {frequency} Hz, {duration}s, {sample_rate} sample rate")
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            wave = 0.5 * np.sin(2 * np.pi * frequency * t)
            print(f"  [SOUND] Playing audio...")
            sd.play(wave, sample_rate)
            sd.wait()
            print(f"  [SOUND] Playback complete")
        except Exception as e:
            print(f"  [SOUND] Error: {e}")

    def _format_time(self, seconds):
        """Format seconds as HH:MM:SS or MM:SS."""
        if seconds < 0:
            return "--:--"
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _format_progress(self, frequency, loop_count, max_freq, step, duration, loop_sleep, max_loops_per_run):
        """Format progress line with timing info."""
        time_per_iter = duration + loop_sleep

        # Loops remaining in current run (until max_loops_per_run)
        loops_left_run = max_loops_per_run - loop_count

        # Total loops remaining to reach max_freq
        total_loops_left = int((max_freq - frequency) / step) + 1

        # Time calculations
        time_left_run = loops_left_run * time_per_iter
        time_left_total = total_loops_left * time_per_iter

        now = datetime.datetime.now()
        eta_run = now + datetime.timedelta(seconds=time_left_run)
        eta_total = now + datetime.timedelta(seconds=time_left_total)

        # Format progress line
        progress = (
            f"Run: {loop_count}/{max_loops_per_run} ({self._format_time(time_left_run)} remaining, ends at {eta_run.strftime('%H:%M')}) | "
            f"Total: {total_loops_left} left ({self._format_time(time_left_total)} remaining, ends at {eta_total.strftime('%H:%M')})"
        )
        return progress

    def _clear_progress(self):
        """Clear the progress line (no-op now, kept for compatibility)."""
        pass

    def _loop_worker(self):
        """Background thread worker for sound loop using streaming audio."""
        sample_rate = self.config.getint('sound', 'sample_rate', fallback=44100)
        max_freq = self.config.getfloat('loop', 'max_frequency', fallback=400.0)
        step = self.config.getfloat('loop', 'step', fallback=0.25)
        duration = self.config.getfloat('loop', 'duration', fallback=1.0)
        loop_sleep = self.config.getfloat('loop', 'loop_sleep', fallback=10.0)
        max_loops_per_run = self.config.getint('loop', 'max_loops_per_run', fallback=250)
        loop_count = 0

        while not self.loop_stop_event.is_set():
            frequency = self.config.getfloat('loop', 'current_frequency', fallback=1.0)

            if frequency > max_freq:
                self._clear_progress()
                print(f"  Loop completed (reached {max_freq} Hz)")
                break

            if loop_count >= max_loops_per_run:
                self._clear_progress()
                print(f"  Loop paused after {max_loops_per_run} iterations (use 'resume' to continue)")
                try:
                    self.state_machine.pause()
                except Exception:
                    pass
                break

            try:
                self.loop_history.append(f"{frequency:.1f} Hz")

                # Format progress info
                progress = self._format_progress(frequency, loop_count, max_freq, step, duration, loop_sleep, max_loops_per_run)

                # Print frequency and progress on same line
                with self.output_lock:
                    sys.stdout.write(f"\r  ♪ {frequency:.2f} Hz | {progress}\n{self.prompt}")
                    sys.stdout.flush()
                    try:
                        line = readline.get_line_buffer()
                        if line:
                            sys.stdout.write(line)
                            sys.stdout.flush()
                    except Exception:
                        pass

                # Signal IR thread that iteration started
                self.ir_trigger_event.set()

                # Streaming audio playback to avoid buffer underruns
                phase = [0.0]
                total_samples = int(sample_rate * duration)
                samples_played = [0]

                def audio_callback(outdata, frames, time_info, status):
                    if self.loop_stop_event.is_set():
                        raise sd.CallbackStop()
                    for i in range(frames):
                        if samples_played[0] >= total_samples:
                            outdata[i:] = 0
                            raise sd.CallbackStop()
                        phase[0] += 2 * np.pi * frequency / sample_rate
                        outdata[i] = 0.5 * np.sin(phase[0])
                        samples_played[0] += 1

                with sd.OutputStream(samplerate=sample_rate, channels=1,
                                     callback=audio_callback, blocksize=2048):
                    while samples_played[0] < total_samples and not self.loop_stop_event.is_set():
                        time.sleep(0.1)

                if self.loop_stop_event.is_set():
                    break

                # Increment and save frequency
                frequency += step
                self.config.set('loop', 'current_frequency', str(frequency))
                if self.loop_save_on_stop:
                    self._save_config()

                # Delay between iterations
                with self.output_lock:
                    sys.stdout.write(f"\r  zzz sleeping {loop_sleep:.0f}s...\n{self.prompt}")
                    sys.stdout.flush()
                    try:
                        line = readline.get_line_buffer()
                        if line:
                            sys.stdout.write(line)
                            sys.stdout.flush()
                    except Exception:
                        pass

                # Interruptible sleep
                sleep_iterations = int(loop_sleep * 10)
                for _ in range(sleep_iterations):
                    if self.loop_stop_event.is_set():
                        break
                    time.sleep(0.1)

                loop_count += 1

            except Exception as e:
                self._clear_progress()
                print(f"  Loop error: {e}")
                break

    def _ir_worker(self):
        """Background thread worker for IR commands, synchronized with sound loop."""
        while not self.loop_stop_event.is_set():
            # Wait for signal from sound loop
            self.ir_trigger_event.wait()
            if self.loop_stop_event.is_set():
                break
            self.ir_trigger_event.clear()

            # Wait before sending IR
            ir_delay = self.config.getfloat('loop', 'ir_delay', fallback=10.0)
            time.sleep(ir_delay)
            if self.loop_stop_event.is_set():
                break

            # Send IR command
            if self.serial_port and self.serial_port.is_open:
                try:
                    cmd = self._get_ir_command()
                    self.serial_port.write(cmd)
                    frequency = self.config.getfloat('loop', 'current_frequency', fallback=0)
                    # Log IR command
                    log_file = self.config.get('loop', 'log_file', fallback='stand.log')
                    try:
                        with open(log_file, 'a') as f:
                            f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {frequency:.1f}\n")
                    except Exception:
                        pass
                    with self.output_lock:
                        sys.stdout.write(f"\r  -> IR sent @ {frequency:.2f} Hz\n{self.prompt}")
                        sys.stdout.flush()
                        try:
                            line = readline.get_line_buffer()
                            if line:
                                sys.stdout.write(line)
                                sys.stdout.flush()
                        except Exception:
                            pass
                except serial.SerialException as e:
                    with self.output_lock:
                        sys.stdout.write(f"\r  !! IR error: {e}\n{self.prompt}")
                        sys.stdout.flush()
            else:
                with self.output_lock:
                    sys.stdout.write(f"\r  !! IR skipped (not connected)\n{self.prompt}")
                    sys.stdout.flush()

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
        step = self.config.getfloat('loop', 'step', fallback=0.25)
        print(f"  Status: {'running' if running else 'stopped'}")
        print(f"  Current: {frequency:.2f} Hz | Max: {max_freq} Hz | Step: {step} Hz")
        if self.loop_history:
            print(f"  History: {' -> '.join(self.loop_history)}")

    def do_sweep(self, arg):
        """Sweep from 1 Hz to max frequency with smooth chirp. Usage: sweep [max_freq] [duration]

        Examples:
          sweep              # Use defaults from config
          sweep 200          # Sweep to 200 Hz with default duration
          sweep 300 30       # Sweep to 300 Hz in 30 seconds
        """
        args = arg.split()
        sample_rate = self.config.getint('sound', 'sample_rate', fallback=44100)
        min_freq = 1.0
        max_freq = float(args[0]) if args else self.config.getfloat('sweep', 'max_frequency', fallback=400.0)
        total_duration = float(args[1]) if len(args) > 1 else self.config.getfloat('sweep', 'duration', fallback=60.0)

        print(f"  Sweeping {min_freq} Hz -> {max_freq} Hz in {total_duration:.0f} seconds")
        print(f"  Press Ctrl+C to stop")

        # Streaming state
        phase = [0.0]  # Use list to allow modification in callback
        sample_idx = [0]
        total_samples = int(sample_rate * total_duration)

        def callback(outdata, frames, time_info, status):
            t = np.arange(frames) / sample_rate
            # Current time in the sweep
            current_time = sample_idx[0] / sample_rate
            # Instantaneous frequency at current time (linear sweep)
            freq = min_freq + (max_freq - min_freq) * current_time / total_duration
            # Generate samples with continuous phase
            for i in range(frames):
                inst_freq = min_freq + (max_freq - min_freq) * (sample_idx[0] + i) / total_samples
                phase[0] += 2 * np.pi * inst_freq / sample_rate
                outdata[i] = 0.5 * np.sin(phase[0])
            sample_idx[0] += frames
            # Stop when done
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

    def _find_camera_mount(self):
        """Find mounted camera filesystem."""
        # Check gvfs first (for PTP/MTP cameras)
        uid = os.getuid()
        gvfs_path = f'/run/user/{uid}/gvfs'
        if os.path.exists(gvfs_path):
            try:
                for mount in os.listdir(gvfs_path):
                    if 'gphoto2' in mount or 'mtp' in mount:
                        mount_path = os.path.join(gvfs_path, mount)
                        if os.path.isdir(mount_path):
                            # Check for DCIM directly or inside subdirs
                            dcim = os.path.join(mount_path, 'DCIM')
                            if os.path.exists(dcim):
                                return mount_path
                            # Some cameras have storage folders
                            for subdir in os.listdir(mount_path):
                                subpath = os.path.join(mount_path, subdir)
                                if os.path.isdir(subpath):
                                    dcim = os.path.join(subpath, 'DCIM')
                                    if os.path.exists(dcim):
                                        return subpath
            except PermissionError:
                pass

        # Check common mount points
        media_dirs = ['/media', '/mnt', '/run/media']
        user = os.environ.get('USER', '')

        for base in media_dirs:
            if not os.path.exists(base):
                continue
            # Check /media/USER/ pattern
            user_media = os.path.join(base, user)
            if os.path.exists(user_media):
                for mount in os.listdir(user_media):
                    mount_path = os.path.join(user_media, mount)
                    if os.path.isdir(mount_path):
                        # Look for DCIM folder (standard camera folder)
                        dcim = os.path.join(mount_path, 'DCIM')
                        if os.path.exists(dcim):
                            return mount_path
            # Check base directly
            for mount in os.listdir(base):
                mount_path = os.path.join(base, mount)
                if os.path.isdir(mount_path):
                    dcim = os.path.join(mount_path, 'DCIM')
                    if os.path.exists(dcim):
                        return mount_path
        return None

    def _find_camera_files(self, camera_path):
        """Find all image/video files on camera."""
        extensions = {'.jpg', '.jpeg', '.png', '.cr2', '.cr3', '.nef', '.arw',
                      '.raw', '.dng', '.mp4', '.mov', '.avi'}
        files = []
        dcim = os.path.join(camera_path, 'DCIM')
        if os.path.exists(dcim):
            for root, dirs, filenames in os.walk(dcim):
                for f in filenames:
                    if os.path.splitext(f)[1].lower() in extensions:
                        files.append(os.path.join(root, f))
        return sorted(files)

    def do_fetch(self, arg):
        """Fetch photos from mounted camera and optionally rename using log entries.

        Copies all files from connected camera filesystem to ./videos/ directory,
        then prompts to rename files based on stand.log entries.
        Naming format: <frequency>-<timestamp>.<extension>

        Usage: fetch [output_dir]
          fetch              # Copies to ./videos/
          fetch ./my_videos  # Copies to ./my_videos/
        """
        default_dir = self.config.get('fetch', 'output_dir', fallback='./videos')
        output_dir = arg.strip() if arg.strip() else default_dir

        # Find mounted camera
        print("  [FETCH] Searching for mounted camera filesystem...")
        print("  [FETCH] Checking /run/user/*/gvfs, /media, /mnt, /run/media")
        camera_path = self._find_camera_mount()

        if not camera_path:
            print("  [FETCH] Error: No camera detected")
            print("  [FETCH] Please connect and mount your camera (DCIM folder required)")
            return

        print(f"  [FETCH] Found camera at: {camera_path}")

        # Find files on camera
        print(f"  [FETCH] Scanning for image/video files in DCIM...")
        camera_files = self._find_camera_files(camera_path)
        if not camera_files:
            print("  [FETCH] No image/video files found on camera")
            return

        print(f"  [FETCH] Found {len(camera_files)} files on camera")

        # Create output directory
        print(f"  [FETCH] Creating output directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
        print(f"  [FETCH] Starting file transfer...")

        # Copy files
        copied = []
        for i, src in enumerate(camera_files, 1):
            filename = os.path.basename(src)
            dst = os.path.join(output_dir, filename)
            try:
                size = os.path.getsize(src)
                size_mb = size / (1024 * 1024)
                print(f"  [FETCH] [{i}/{len(camera_files)}] Copying {filename} ({size_mb:.1f} MB)...")
                shutil.copy2(src, dst)
                copied.append(dst)
            except Exception as e:
                print(f"  [FETCH] Error copying {filename}: {e}")

        if not copied:
            print("  [FETCH] No files copied")
            return

        print(f"  [FETCH] Transfer complete: {len(copied)} files copied")

        # Parse log file
        log_file = self.config.get('loop', 'log_file', fallback='stand.log')
        print(f"  [FETCH] Loading log file: {log_file}")
        log_entries = {}
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Format: "YYYY-MM-DD HH:MM:SS: frequency"
                    try:
                        timestamp_str, freq_str = line.rsplit(': ', 1)
                        frequency = float(freq_str)
                        ts = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        ts_clean = timestamp_str.replace(':', '').replace(' ', '').replace('-', '')
                        log_entries[ts] = (frequency, ts_clean)
                    except ValueError:
                        continue
        else:
            print(f"  [FETCH] Warning: Log file not found")

        print(f"  [FETCH] Loaded {len(log_entries)} log entries")
        tolerance_secs = self.config.getint('fetch', 'tolerance', fallback=5)
        print(f"  [FETCH] Matching files by timestamp (tolerance: {tolerance_secs}s)...\n")

        renamed = 0
        skipped = 0
        deleted = 0
        tolerance = datetime.timedelta(seconds=tolerance_secs)

        for file_path in copied:
            filename = os.path.basename(file_path)

            # Get file modification time
            try:
                file_time = os.stat(file_path).st_mtime
                file_dt = datetime.datetime.fromtimestamp(file_time)
            except OSError:
                print(f"  [RENAME] {filename}: cannot read file time, skipping")
                skipped += 1
                continue

            # Find matching log entry
            match = None
            for log_ts, (freq, ts_clean) in log_entries.items():
                if abs(file_dt - log_ts) <= tolerance:
                    match = (freq, ts_clean, log_ts)
                    break

            if match:
                # Auto-rename matched files
                freq, ts_clean, log_ts = match
                ext = os.path.splitext(file_path)[1]
                freq_str = f"{freq:07.2f}"
                new_name = f"{freq_str}-{ts_clean}{ext}"
                new_path = os.path.join(output_dir, new_name)
                try:
                    os.rename(file_path, new_path)
                    renamed += 1
                    print(f"  [RENAME] {filename} -> {new_name} (matched {log_ts})")
                except OSError as e:
                    print(f"  [RENAME] {filename}: error - {e}")
            else:
                # No match - ask user
                print(f"\n  [RENAME] {filename}")
                print(f"  [RENAME] File time: {file_dt}")
                print(f"  [RENAME] No matching log entry within {tolerance_secs}s tolerance")
                print(f"  [s]kip  [d]elete  [r]ename manually  [q]uit: ", end='')
                choice = input().strip().lower()

                if choice == 'd':
                    try:
                        os.remove(file_path)
                        deleted += 1
                        print(f"  [RENAME] Deleted {filename}")
                    except OSError as e:
                        print(f"  [RENAME] Error deleting: {e}")
                elif choice == 'r':
                    new_name = input(f"  [RENAME] Enter new filename: ").strip()
                    if new_name:
                        new_path = os.path.join(output_dir, new_name)
                        try:
                            os.rename(file_path, new_path)
                            renamed += 1
                            print(f"  [RENAME] Renamed to {new_name}")
                        except OSError as e:
                            print(f"  [RENAME] Error renaming: {e}")
                    else:
                        skipped += 1
                        print(f"  [RENAME] Skipped")
                elif choice == 'q':
                    print(f"  [RENAME] Quitting...")
                    break
                else:
                    skipped += 1
                    print(f"  [RENAME] Skipped")

        print(f"\n  [FETCH] Complete: {renamed} renamed, {skipped} skipped, {deleted} deleted")

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
                elif key in ('frequency', 'min_frequency', 'current_frequency'):
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
