"""Command module initialization and registration."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..console import StandConsole


def register_commands(console: 'StandConsole') -> None:
    """Register all command modules with console."""
    from . import state, loop, playback, missing, serial, camera, config, help, exit

    state.register(console)
    loop.register(console)
    playback.register(console)
    missing.register(console)
    serial.register(console)
    camera.register(console)
    config.register(console)
    help.register(console)
    exit.register(console)
