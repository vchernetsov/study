"""Background worker threads for loop and IR operations."""

import datetime
import readline
import sys
import threading
import time
from collections import deque
from typing import Callable, Optional, TYPE_CHECKING

import numpy as np
import sounddevice as sd

if TYPE_CHECKING:
    from .config import ConfigManager
    from .serial_handler import SerialHandler
    from .state_machine import CommandStateMachine


class OutputPrinter:
    """Thread-safe console output with readline preservation."""

    def __init__(self, prompt: str, lock: threading.Lock):
        self._lock = lock
        self._prompt = prompt

    def print_line(self, message: str) -> None:
        """Print message preserving readline buffer."""
        with self._lock:
            sys.stdout.write(f"\r{message}\n{self._prompt}")
            sys.stdout.flush()
            try:
                line = readline.get_line_buffer()
                if line:
                    sys.stdout.write(line)
                    sys.stdout.flush()
            except Exception:
                pass


def format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    if seconds < 0:
        return "--:--"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_progress(
    frequency: float,
    loop_count: int,
    max_freq: float,
    step: float,
    duration: float,
    loop_sleep: float,
    max_loops_per_run: int
) -> str:
    """Format progress line with timing info."""
    time_per_iter = duration + loop_sleep

    # Loops remaining in current run
    loops_left_run = max_loops_per_run - loop_count

    # Total loops remaining to reach max_freq
    total_loops_left = int((max_freq - frequency) / step) + 1

    # Time calculations
    time_left_run = loops_left_run * time_per_iter
    time_left_total = total_loops_left * time_per_iter

    now = datetime.datetime.now()
    eta_run = now + datetime.timedelta(seconds=time_left_run)
    eta_total = now + datetime.timedelta(seconds=time_left_total)

    progress = (
        f"Run: {loop_count}/{max_loops_per_run} ({format_time(time_left_run)} remaining, ends at {eta_run.strftime('%H:%M')}) | "
        f"Total: {total_loops_left} left ({format_time(time_left_total)} remaining, ends at {eta_total.strftime('%H:%M')})"
    )
    return progress


class LoopWorker:
    """Background worker for frequency sweep loop."""

    def __init__(
        self,
        config: 'ConfigManager',
        state_machine: 'CommandStateMachine',
        ir_trigger_event: threading.Event,
        stop_event: threading.Event,
        printer: OutputPrinter,
        on_pause: Optional[Callable] = None,
    ):
        self._config = config
        self._state_machine = state_machine
        self._ir_trigger = ir_trigger_event
        self._stop_event = stop_event
        self._printer = printer
        self._on_pause = on_pause
        self._thread: Optional[threading.Thread] = None
        self._save_on_stop = True
        self.history: deque = deque(maxlen=10)

    def start(self, save_on_stop: bool = True) -> None:
        """Start loop worker thread."""
        self._save_on_stop = save_on_stop
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop loop worker."""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    @property
    def is_running(self) -> bool:
        """Check if worker is active."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """Main loop implementation."""
        sample_rate = self._config.getint('sound', 'sample_rate', fallback=44100)
        max_freq = self._config.getfloat('loop', 'max_frequency', fallback=400.0)
        step = self._config.getfloat('loop', 'step', fallback=0.25)
        duration = self._config.getfloat('loop', 'duration', fallback=1.0)
        loop_sleep = self._config.getfloat('loop', 'loop_sleep', fallback=10.0)
        max_loops_per_run = self._config.getint('loop', 'max_loops_per_run', fallback=250)
        loop_count = 0

        while not self._stop_event.is_set():
            frequency = self._config.getfloat('loop', 'current_frequency', fallback=1.0)

            if frequency > max_freq:
                print(f"  Loop completed (reached {max_freq} Hz)")
                break

            if loop_count >= max_loops_per_run:
                print(f"  Loop paused after {max_loops_per_run} iterations (use 'resume' to continue)")
                try:
                    self._state_machine.pause()
                except Exception:
                    pass
                if self._on_pause:
                    self._on_pause()
                break

            try:
                self.history.append(f"{frequency:.1f} Hz")

                # Format progress info
                progress = format_progress(
                    frequency, loop_count, max_freq, step,
                    duration, loop_sleep, max_loops_per_run
                )

                self._printer.print_line(f"  ♪ {frequency:.2f} Hz | {progress}")

                # Signal IR thread that iteration started
                self._ir_trigger.set()

                # Streaming audio playback
                phase = [0.0]
                total_samples = int(sample_rate * duration)
                samples_played = [0]

                def audio_callback(outdata, frames, time_info, status):
                    if self._stop_event.is_set():
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
                    while samples_played[0] < total_samples and not self._stop_event.is_set():
                        time.sleep(0.1)

                if self._stop_event.is_set():
                    break

                # Increment and save frequency
                frequency += step
                self._config.set('loop', 'current_frequency', str(frequency))
                if self._save_on_stop:
                    self._config.save()

                # Delay message
                self._printer.print_line(f"  zzz sleeping {loop_sleep:.0f}s...")

                # Interruptible sleep
                sleep_iterations = int(loop_sleep * 10)
                for _ in range(sleep_iterations):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)

                loop_count += 1

            except Exception as e:
                print(f"  Loop error: {e}")
                break


class IRWorker:
    """Background worker for IR commands synchronized with loop."""

    def __init__(
        self,
        config: 'ConfigManager',
        serial_handler: 'SerialHandler',
        state_machine: 'CommandStateMachine',
        ir_trigger_event: threading.Event,
        stop_event: threading.Event,
        printer: OutputPrinter,
    ):
        self._config = config
        self._serial = serial_handler
        self._state_machine = state_machine
        self._ir_trigger = ir_trigger_event
        self._stop_event = stop_event
        self._printer = printer
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start IR worker thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop IR worker."""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None

    @property
    def is_running(self) -> bool:
        """Check if worker is active."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """IR worker loop."""
        while not self._stop_event.is_set():
            # Wait for signal from sound loop
            self._ir_trigger.wait()
            if self._stop_event.is_set():
                break
            self._ir_trigger.clear()

            # Wait before sending IR
            ir_delay = self._config.getfloat('loop', 'ir_delay', fallback=10.0)
            time.sleep(ir_delay)
            if self._stop_event.is_set():
                break

            # Send IR command
            if self._serial.is_connected:
                try:
                    cmd = self._config.ir_command
                    success = self._serial.write(cmd)
                    if success:
                        frequency = self._config.getfloat('loop', 'current_frequency', fallback=0)
                        # Log IR command only if properly initialized
                        if self._state_machine.state != 'running':
                            return

                        log_file = self._config.get('loop', 'log_file', fallback='stand.log')
                        try:
                            with open(log_file, 'a') as f:
                                f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {frequency:.1f}\n")
                        except Exception:
                            pass
                        self._printer.print_line(f"  -> IR sent @ {frequency:.2f} Hz")
                    else:
                        self._printer.print_line(f"  !! IR error: write failed")
                except Exception as e:
                    self._printer.print_line(f"  !! IR error: {e}")
            else:
                self._printer.print_line(f"  !! IR skipped (not connected)")


class WorkerManager:
    """Coordinates loop and IR workers lifecycle."""

    def __init__(
        self,
        config: 'ConfigManager',
        serial_handler: 'SerialHandler',
        state_machine: 'CommandStateMachine',
        output_lock: threading.Lock,
        prompt: str,
    ):
        self._config = config
        self._serial = serial_handler
        self._state_machine = state_machine
        self._stop_event = threading.Event()
        self._ir_trigger = threading.Event()
        self._printer = OutputPrinter(prompt, output_lock)

        self._loop_worker = LoopWorker(
            config=config,
            state_machine=state_machine,
            ir_trigger_event=self._ir_trigger,
            stop_event=self._stop_event,
            printer=self._printer,
        )

        self._ir_worker = IRWorker(
            config=config,
            serial_handler=serial_handler,
            state_machine=state_machine,
            ir_trigger_event=self._ir_trigger,
            stop_event=self._stop_event,
            printer=self._printer,
        )

    def start(self, save_on_stop: bool = True) -> None:
        """Start both workers."""
        # Stop any existing workers first
        self.stop(save=True)

        # Reset events
        self._stop_event.clear()
        self._ir_trigger.clear()

        # Start workers
        self._loop_worker.start(save_on_stop=save_on_stop)
        self._ir_worker.start()

    def stop(self, save: bool = True) -> None:
        """Stop both workers."""
        if self._loop_worker.is_running or self._ir_worker.is_running:
            self._loop_worker._save_on_stop = save
            self._stop_event.set()
            self._ir_trigger.set()  # Wake up IR thread
            self._loop_worker.stop()
            self._ir_worker.stop()

    @property
    def loop_history(self) -> deque:
        """Get loop history."""
        return self._loop_worker.history

    @property
    def is_running(self) -> bool:
        """Check if workers are running."""
        return self._loop_worker.is_running
