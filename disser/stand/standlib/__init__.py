"""Stand - Arduino IR Lamp Controller Console Application."""

from .console import StandConsole
from .state_machine import CommandStateMachine
from .config import ConfigManager

__version__ = '1.0.0'
__all__ = ['StandConsole', 'CommandStateMachine', 'ConfigManager', 'main']


def main():
    """Entry point for the application."""
    import sys
    console = StandConsole()
    try:
        console.cmdloop()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
        sys.exit(0)
