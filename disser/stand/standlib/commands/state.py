"""State machine control commands."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..console import StandConsole


def register(console: 'StandConsole') -> None:
    """Register state commands with console."""
    console.do_state = lambda arg: do_state(console, arg)
    console.do_start = lambda arg: do_start(console, arg)
    console.do_pause = lambda arg: do_pause(console, arg)
    console.do_resume = lambda arg: do_resume(console, arg)
    console.do_stop = lambda arg: do_stop(console, arg)
    console.do_reset = lambda arg: do_reset(console, arg)
    console.do_transitions = lambda arg: do_transitions(console, arg)


def do_state(console: 'StandConsole', arg: str) -> None:
    """Show current state of the state machine."""
    print(f"Current state: {console.state_machine.state}")


def do_start(console: 'StandConsole', arg: str) -> None:
    """Start execution and begin frequency loop (ready -> running)."""
    try:
        console.state_machine.start()
        console.worker_manager.start()
    except Exception:
        print(f"  Error: Cannot start from state '{console.state_machine.state}'")


def do_pause(console: 'StandConsole', arg: str) -> None:
    """Pause execution and stop loop without saving (running -> paused)."""
    try:
        console.worker_manager.stop(save=False)
        console.state_machine.pause()
    except Exception:
        print(f"  Error: Cannot pause from state '{console.state_machine.state}'")


def do_resume(console: 'StandConsole', arg: str) -> None:
    """Resume execution and restart loop (paused/stopped -> running)."""
    try:
        console.state_machine.resume()
        console.worker_manager.start()
    except Exception:
        print(f"  Error: Cannot resume from state '{console.state_machine.state}'")


def do_stop(console: 'StandConsole', arg: str) -> None:
    """Stop execution and loop without saving progress (running/paused -> stopped)."""
    try:
        console.worker_manager.stop(save=False)
        console.state_machine.stop()
    except Exception:
        print(f"  Error: Cannot stop from state '{console.state_machine.state}'")


def do_reset(console: 'StandConsole', arg: str) -> None:
    """Reset the system to idle state."""
    console.state_machine.reset()


def do_transitions(console: 'StandConsole', arg: str) -> None:
    """Show available transitions from current state."""
    current = console.state_machine.state
    triggers = console.state_machine.get_triggers(current)
    if triggers:
        print(f"Available transitions from '{current}':")
        for trigger in triggers:
            print(f"  {trigger}")
    else:
        print(f"No transitions available from '{current}'")
