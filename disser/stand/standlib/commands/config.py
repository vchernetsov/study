"""Configuration commands: config, set."""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..console import StandConsole


def register(console: 'StandConsole') -> None:
    """Register config commands with console."""
    console.do_config = lambda arg: do_config(console, arg)
    console.do_set = lambda arg: do_set(console, arg)
    console.complete_set = lambda text, line, begidx, endidx: complete_set(console, text, line, begidx, endidx)


def do_config(console: 'StandConsole', arg: str) -> None:
    """Show current configuration."""
    print("Current configuration:")
    for section in console.config_manager.sections():
        print(f"  [{section}]")
        for key, value in console.config_manager.items(section):
            print(f"    {key} = {value}")


def do_set(console: 'StandConsole', arg: str) -> None:
    """Set configuration value. Usage: set <section>.<key> <value>

    Examples:
      set serial.port /dev/ttyACM0
      set serial.baudrate 115200
      set commands.ir_engage !r\\n
    """
    if not console.config_manager.loaded:
        print("  Warning: Config not loaded yet.")

    args = arg.split(None, 1)
    if len(args) < 2:
        print("  Usage: set <section>.<key> <value>")
        print("  Example: set serial.port /dev/ttyUSB0")
        return

    key_path, value = args
    if '.' not in key_path:
        print("  Error: Key must be in format <section>.<key>")
        print("  Example: set serial.port /dev/ttyUSB0")
        return

    section, key = key_path.split('.', 1)

    if not console.config_manager.has_section(section):
        console.config_manager.add_section(section)
        print(f"  Created new section [{section}]")

    console.config_manager.set(section, key, value)
    console.config_manager.save()
    print(f"  Set {section}.{key} = {value}")


def complete_set(console: 'StandConsole', text: str, line: str, begidx: int, endidx: int) -> List[str]:
    """Autocomplete for set command."""
    args = line.split()
    if len(args) == 1 or (len(args) == 2 and not line.endswith(' ')):
        # Complete section.key
        options = []
        for section in console.config_manager.sections():
            for key in console.config_manager.options(section):
                options.append(f"{section}.{key}")
        return [opt for opt in options if opt.startswith(text)]
    elif len(args) >= 2:
        # Complete value based on key
        key_path = args[1]
        if '.' in key_path:
            section, key = key_path.split('.', 1)
            options = []
            # Add current value as option
            if console.config_manager.has_option(section, key):
                current = console.config_manager.get(section, key)
                options.append(current)
            # Add context-specific suggestions
            if key == 'port':
                import serial.tools.list_ports
                options.extend([p.device for p in serial.tools.list_ports.comports()])
            elif key in ('frequency', 'current_frequency'):
                options.extend(['1.0', '10.0', '50.0', '100.0', '200.0', '400.0'])
            elif key == 'max_frequency':
                options.extend(['100.0', '200.0', '400.0', '480.0', '1000.0'])
            elif key == 'step':
                options.extend(['0.1', '0.2', '0.5', '1.0', '2.0', '5.0'])
            elif key == 'duration':
                options.extend(['1.0', '5.0', '10.0', '20.0', '30.0', '60.0'])
            elif key in ('ir_delay', 'loop_sleep'):
                options.extend(['5.0', '10.0', '15.0', '20.0', '30.0'])
            elif key == 'max_loops_per_run':
                options.extend(['50', '100', '200', '500', '1000'])
            elif key == 'sample_rate':
                options.extend(['22050', '44100', '48000', '96000'])
            elif key == 'log_file':
                options.extend(['stand.log', 'experiment.log'])
            return [opt for opt in options if opt.startswith(text)]
    return []
