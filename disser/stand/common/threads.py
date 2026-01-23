"""
Threading utilities for vibration stand control
"""

import threading
import time
from datetime import datetime, timedelta
from typing import List
from colored import fg, attr
from common.sounds import sweep
from common.exceptions import FinishLoop
from common.utils import format_duration
from common.ir import IRController
from common.log import Logger


class LoopStep:
    def __init__(self, frequency, sound_duration=20, sleep_time=10, ir_delay=5):
        self.frequency = frequency
        self.sound_duration = sound_duration
        self.sleep_time = sleep_time
        self.ir_delay = ir_delay

    def sleep(self):
        print (f'[INFO]: Sleeping for {self.sleep_time} seconds. Meanwhile you can stop process by Ctrl+C gracefully.')
        time.sleep(self.sleep_time)

    def engage(self, ir: IRController, logger: Logger, config, missed_frequencies: list, missed_lock: threading.Lock, estimation):
        print (estimation)
        sweep_thread = self.sweep_thread(self.frequency, self.sound_duration, config)
        ir_thread = self.ir_thread(ir, logger, config, missed_frequencies, missed_lock, self.ir_delay)
        try:
            sweep_thread.join()
            ir_thread.join()
        except KeyboardInterrupt:
            raise FinishLoop("Loop interrupted during sweep")
        self.sleep()

    def sweep_thread(self, frequency, sound_duration, config):
        fade_seconds = config.get('fade_seconds', 2)
        thread = threading.Thread(
            target=sweep,
            args=(frequency, frequency, sound_duration, fade_seconds)
        )
        thread.daemon = True
        thread.start()
        return thread

    def ir_thread(self, ir: IRController, logger: Logger, config, missed_frequencies: list, missed_lock: threading.Lock, ir_delay):
        def delayed_engage():
            time.sleep(ir_delay)
            result = ir.engage()
            if result:
                logger.log_ir_engage(self.frequency)
                config.set('start_frequency', self.frequency)
            else:
                print(fg('red') + "[IR THREAD] WARNING: IR engage failed, not logged." + attr('reset'))
                with missed_lock:
                    missed_frequencies.append(self.frequency)

        thread = threading.Thread(target=delayed_engage)
        thread.daemon = True
        thread.start()
        return thread

    def estimation(self, steps_remain):
        seconds = steps_remain * (self.sound_duration + self.sleep_time)
        finish_time = datetime.now() + timedelta(seconds=seconds)
        duration_str = format_duration(seconds)
        finish_str = finish_time.strftime("%H:%M:%S")
        return f"[SWEEP]: Frequency - {self.frequency} Hz\t|ETA: {duration_str} | Finish at: {finish_str} | Steps remain: {steps_remain}"

    @staticmethod
    def sequence(start_frequency, end_frequency, step, sound_duration):
        result = []
        frequency = start_frequency
        while frequency <= end_frequency:
            result.append(LoopStep(frequency, sound_duration=sound_duration))
            frequency += step
        return result

    @staticmethod
    def list(iterable, sound_duration):
        result = []
        for x in iterable:
            result.append(LoopStep(sound_duration=sound_duration, **x))
        return result

    def __str__(self):
        return f"Step {self.frequency} Hz"


class Loop:

    def __init__(self, iterable: List[LoopStep], ir: IRController, logger: Logger, config=None):
        self.iterable = iterable
        self.ir = ir
        self.logger = logger
        self.config = config
        self.missed_frequencies = []
        self.missed_lock = threading.Lock()

    def engage(self):
        for idx, x in enumerate(self.iterable):
            steps_remain = len(self.iterable) - idx - 1
            estimation = x.estimation(steps_remain)
            try:
                x.engage(self.ir, self.logger, self.config, self.missed_frequencies, self.missed_lock, estimation)
            except FinishLoop:
                raise
            except KeyboardInterrupt:
                raise FinishLoop("Loop interrupted")
            except Exception as e:
                print(f"Sweep error: {e}")
                break

    def get_missed_frequencies(self):
        """Return list of frequencies where IR engagement failed or was skipped"""
        with self.missed_lock:
            return list(self.missed_frequencies)
