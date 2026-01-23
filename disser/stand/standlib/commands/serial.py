"""Serial connection commands: disconnect."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..console import StandConsole


def register(console: 'StandConsole') -> None:
    """Register serial commands with console."""
    console.do_disconnect = lambda arg: do_disconnect(console, arg)


def do_disconnect(console: 'StandConsole', arg: str) -> None:
    """Disconnect from serial port."""
    console.serial_handler.disconnect()
