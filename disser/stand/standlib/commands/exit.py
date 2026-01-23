"""Exit commands: quit, exit."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..console import StandConsole


def register(console: 'StandConsole') -> None:
    """Register exit commands with console."""
    console.do_quit = lambda arg: do_quit(console, arg)
    console.do_exit = lambda arg: do_quit(console, arg)


def do_quit(console: 'StandConsole', arg: str) -> bool:
    """Exit the console."""
    console.worker_manager.stop(save=False)
    console.serial_handler.disconnect()
    print("Goodbye!")
    return True
