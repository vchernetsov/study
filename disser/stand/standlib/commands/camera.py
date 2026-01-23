"""Camera commands: sync, fetch."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..console import StandConsole


def register(console: 'StandConsole') -> None:
    """Register camera commands with console."""
    console.do_sync = lambda arg: do_sync(console, arg)
    console.do_fetch = lambda arg: do_fetch(console, arg)


def do_sync(console: 'StandConsole', arg: str) -> None:
    """Sync camera time with host computer."""
    from ..camera import CameraSync
    CameraSync.sync_time()


def do_fetch(console: 'StandConsole', arg: str) -> None:
    """Fetch photos from mounted camera and optionally rename using log entries.

    Copies all files from connected camera filesystem to ./videos/ directory,
    then prompts to rename files based on stand.log entries.
    Naming format: <frequency>-<timestamp>.<extension>

    Usage: fetch [output_dir]
      fetch              # Copies to ./videos/
      fetch ./my_videos  # Copies to ./my_videos/
    """
    output_dir = arg.strip() if arg.strip() else None
    copied_files = console.camera_fetch.fetch_files(output_dir)
    if copied_files:
        log_entries = console.camera_fetch.load_log_entries()
        tolerance_secs = console.config_manager.getint('fetch', 'tolerance', fallback=5)
        renamed, skipped, deleted = console.camera_fetch.rename_with_log(
            copied_files, log_entries, tolerance_secs, interactive=True
        )
        print(f"\n  [FETCH] Complete: {renamed} renamed, {skipped} skipped, {deleted} deleted")
