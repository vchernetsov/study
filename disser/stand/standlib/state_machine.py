"""State machine for command execution states."""

import threading
from typing import List

from transitions import Machine


class CommandStateMachine:
    """Thread-safe state machine managing command execution states."""

    states: List[str] = ['idle', 'ready', 'running', 'paused', 'stopped']

    def __init__(self):
        self._lock = threading.RLock()
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

    @property
    def current_state(self) -> str:
        """Thread-safe state access."""
        with self._lock:
            return self.state

    def get_triggers(self, state: str = None) -> List[str]:
        """Get available triggers from current or specified state."""
        with self._lock:
            target_state = state if state else self.state
            return self.machine.get_triggers(target_state)

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
