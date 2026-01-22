"""Command module initialization and registration."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..console import StandConsole


def register_commands(console: 'StandConsole') -> None:
    """Register all command modules with console."""
    from . import state, loop, playback, missing

    state.register(console)
    loop.register(console)
    playback.register(console)
    missing.register(console)
