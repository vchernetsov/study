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

    def default(self, line: str) -> None:
        """Handle unknown commands."""
        print(f"Unknown command: {line}")
        print("Type 'help' for available commands.")

    def emptyline(self) -> None:
        """Do nothing on empty input."""
        pass

    def completenames(self, text, *ignored):
        """Override to include dynamically registered commands."""
        dotext = 'do_' + text
        # Include both class and instance attributes
        names = [name for name in dir(self) if name.startswith(dotext)]
        return [name[3:] for name in names]
