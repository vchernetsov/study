"""Camera operations: time sync and file fetch."""

import datetime
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ConfigManager


class CameraSync:
    """Camera time synchronization using gphoto2."""

    @staticmethod
    def release_gvfs() -> None:
        """Kill gvfs-gphoto2-volume-monitor to release USB."""
        print("  [SYNC] Releasing camera from gvfs...")
        subprocess.run(['pkill', '-f', 'gvfs-gphoto2'], capture_output=True)
        time.sleep(0.5)

    @staticmethod
    def detect_camera() -> Optional[str]:
        """Detect camera via gphoto2. Returns camera name or None."""
        try:
            result = subprocess.run(
                ['gphoto2', '--auto-detect'],
                capture_output=True, text=True, timeout=10
            )
        except FileNotFoundError:
            print("  [SYNC] Error: gphoto2 not installed")
            return None
        except subprocess.TimeoutExpired:
            print("  [SYNC] Error: gphoto2 timeout during detection")
            return None

        lines = result.stdout.strip().split('\n')
        cameras = [line for line in lines[2:] if line.strip()]
        if cameras:
            return cameras[0].strip()
        return None

    @staticmethod
    def sync_time() -> bool:
        """Sync camera time with host. Returns success."""
        CameraSync.release_gvfs()
        print("  [SYNC] Detecting camera via gphoto2...")

        camera = CameraSync.detect_camera()
        if not camera:
            print("  [SYNC] Error: No camera detected on USB")
            return False

        print(f"  [SYNC] Found camera: {camera}")
        host_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"  [SYNC] Host time: {host_time}")
        print("  [SYNC] Setting camera datetime...")

        try:
            # Try setting datetime to now
            print("  [SYNC] Trying: gphoto2 --set-config datetime=now")
            result = subprocess.run(
                ['gphoto2', '--set-config', 'datetime=now'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                print("  [SYNC] Success: Camera time synchronized")
                return True

            # Try alternative: set datetime as unix timestamp
            timestamp = int(time.time())
            print(f"  [SYNC] Trying: gphoto2 --set-config-value /main/settings/datetime={timestamp}")
            result = subprocess.run(
                ['gphoto2', '--set-config-value', f'/main/settings/datetime={timestamp}'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                print("  [SYNC] Success: Camera time synchronized")
                return True

            # Try syncdatetime command
            print("  [SYNC] Trying: gphoto2 --set-config syncdatetime=1")
            result = subprocess.run(
                ['gphoto2', '--set-config', 'syncdatetime=1'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                print("  [SYNC] Success: Camera time synchronized")
                return True

            print("  [SYNC] Error: All methods failed")
            if result.stderr.strip():
                print(f"  [SYNC] Last error: {result.stderr.strip()}")
            return False

        except subprocess.TimeoutExpired:
            print("  [SYNC] Error: Timeout while setting camera time")
            return False


class CameraMount:
    """Find and access mounted camera filesystem."""

    EXTENSIONS = {'.jpg', '.jpeg', '.png', '.cr2', '.cr3', '.nef',
                  '.arw', '.raw', '.dng', '.mp4', '.mov', '.avi'}

    @staticmethod
    def find_mount() -> Optional[Path]:
        """Find mounted camera filesystem with DCIM folder."""
        # Check gvfs first (for PTP/MTP cameras)
        uid = os.getuid()
        gvfs_path = f'/run/user/{uid}/gvfs'
        if os.path.exists(gvfs_path):
            try:
                for mount in os.listdir(gvfs_path):
                    if 'gphoto2' in mount or 'mtp' in mount:
                        mount_path = os.path.join(gvfs_path, mount)
                        if os.path.isdir(mount_path):
                            # Check for DCIM directly or inside subdirs
                            dcim = os.path.join(mount_path, 'DCIM')
                            if os.path.exists(dcim):
                                return Path(mount_path)
                            # Some cameras have storage folders
                            for subdir in os.listdir(mount_path):
                                subpath = os.path.join(mount_path, subdir)
                                if os.path.isdir(subpath):
                                    dcim = os.path.join(subpath, 'DCIM')
                                    if os.path.exists(dcim):
                                        return Path(subpath)
            except PermissionError:
                pass

        # Check common mount points
        media_dirs = ['/media', '/mnt', '/run/media']
        user = os.environ.get('USER', '')

        for base in media_dirs:
            if not os.path.exists(base):
                continue
            # Check /media/USER/ pattern
            user_media = os.path.join(base, user)
            if os.path.exists(user_media):
                for mount in os.listdir(user_media):
                    mount_path = os.path.join(user_media, mount)
                    if os.path.isdir(mount_path):
                        dcim = os.path.join(mount_path, 'DCIM')
                        if os.path.exists(dcim):
                            return Path(mount_path)
            # Check base directly
            for mount in os.listdir(base):
                mount_path = os.path.join(base, mount)
                if os.path.isdir(mount_path):
                    dcim = os.path.join(mount_path, 'DCIM')
                    if os.path.exists(dcim):
                        return Path(mount_path)
        return None

    @staticmethod
    def find_files(camera_path: Path) -> List[Path]:
        """Find all image/video files on camera."""
        files = []
        dcim = camera_path / 'DCIM'
        if dcim.exists():
            for root, dirs, filenames in os.walk(dcim):
                for f in filenames:
                    if os.path.splitext(f)[1].lower() in CameraMount.EXTENSIONS:
                        files.append(Path(root) / f)
        return sorted(files)


class CameraFetch:
    """Fetch and rename files from camera."""

    def __init__(self, config: 'ConfigManager'):
        self._config = config

    def fetch_files(self, output_dir: str = None) -> List[Path]:
        """Copy files from camera to output directory."""
        default_dir = self._config.get('fetch', 'output_dir', fallback='./videos')
        output_dir = output_dir or default_dir

        print("  [FETCH] Searching for mounted camera filesystem...")
        print("  [FETCH] Checking /run/user/*/gvfs, /media, /mnt, /run/media")
        camera_path = CameraMount.find_mount()

        if not camera_path:
            print("  [FETCH] Error: No camera detected")
            print("  [FETCH] Please connect and mount your camera (DCIM folder required)")
            return []

        print(f"  [FETCH] Found camera at: {camera_path}")

        print(f"  [FETCH] Scanning for image/video files in DCIM...")
        camera_files = CameraMount.find_files(camera_path)
        if not camera_files:
            print("  [FETCH] No image/video files found on camera")
            return []

        print(f"  [FETCH] Found {len(camera_files)} files on camera")

        print(f"  [FETCH] Creating output directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
        print(f"  [FETCH] Starting file transfer...")

        copied = []
        for i, src in enumerate(camera_files, 1):
            filename = src.name
            dst = Path(output_dir) / filename
            try:
                size = src.stat().st_size
                size_mb = size / (1024 * 1024)
                print(f"  [FETCH] [{i}/{len(camera_files)}] Copying {filename} ({size_mb:.1f} MB)...")
                shutil.copy2(src, dst)
                copied.append(dst)
            except Exception as e:
                print(f"  [FETCH] Error copying {filename}: {e}")

        if copied:
            print(f"  [FETCH] Transfer complete: {len(copied)} files copied")
        else:
            print("  [FETCH] No files copied")

        return copied

    def load_log_entries(self) -> Dict[datetime.datetime, Tuple[float, str]]:
        """Load timestamp->frequency mappings from log file."""
        log_file = self._config.get('loop', 'log_file', fallback='stand.log')
        print(f"  [FETCH] Loading log file: {log_file}")
        log_entries = {}

        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Format: "YYYY-MM-DD HH:MM:SS: frequency"
                    try:
                        timestamp_str, freq_str = line.rsplit(': ', 1)
                        frequency = float(freq_str)
                        ts = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        ts_clean = timestamp_str.replace(':', '').replace(' ', '').replace('-', '')
                        log_entries[ts] = (frequency, ts_clean)
                    except ValueError:
                        continue
        else:
            print(f"  [FETCH] Warning: Log file not found")

        print(f"  [FETCH] Loaded {len(log_entries)} log entries")
        return log_entries

    def rename_with_log(
        self,
        files: List[Path],
        log_entries: Dict[datetime.datetime, Tuple[float, str]],
        tolerance_secs: int = 5,
        interactive: bool = True
    ) -> Tuple[int, int, int]:
        """Rename files using log entries. Returns (renamed, skipped, deleted)."""
        tolerance = datetime.timedelta(seconds=tolerance_secs)
        print(f"  [FETCH] Matching files by timestamp (tolerance: {tolerance_secs}s)...\n")

        renamed = 0
        skipped = 0
        deleted = 0

        for file_path in files:
            filename = file_path.name

            try:
                file_time = file_path.stat().st_mtime
                file_dt = datetime.datetime.fromtimestamp(file_time)
            except OSError:
                print(f"  [RENAME] {filename}: cannot read file time, skipping")
                skipped += 1
                continue

            # Find matching log entry
            match = None
            for log_ts, (freq, ts_clean) in log_entries.items():
                if abs(file_dt - log_ts) <= tolerance:
                    match = (freq, ts_clean, log_ts)
                    break

            if match:
                freq, ts_clean, log_ts = match
                ext = file_path.suffix
                freq_str = f"{freq:07.2f}"
                new_name = f"{freq_str}-{ts_clean}{ext}"
                new_path = file_path.parent / new_name
                try:
                    os.rename(file_path, new_path)
                    renamed += 1
                    print(f"  [RENAME] {filename} -> {new_name} (matched {log_ts})")
                except OSError as e:
                    print(f"  [RENAME] {filename}: error - {e}")
            elif interactive:
                print(f"\n  [RENAME] {filename}")
                print(f"  [RENAME] File time: {file_dt}")
                print(f"  [RENAME] No matching log entry within {tolerance_secs}s tolerance")
                print(f"  [s]kip  [d]elete  [r]ename manually  [q]uit: ", end='')
                choice = input().strip().lower()

                if choice == 'd':
                    try:
                        os.remove(file_path)
                        deleted += 1
                        print(f"  [RENAME] Deleted {filename}")
                    except OSError as e:
                        print(f"  [RENAME] Error deleting: {e}")
                elif choice == 'r':
                    new_name = input(f"  [RENAME] Enter new filename: ").strip()
                    if new_name:
                        new_path = file_path.parent / new_name
                        try:
                            os.rename(file_path, new_path)
                            renamed += 1
                            print(f"  [RENAME] Renamed to {new_name}")
                        except OSError as e:
                            print(f"  [RENAME] Error renaming: {e}")
                    else:
                        skipped += 1
                        print(f"  [RENAME] Skipped")
                elif choice == 'q':
                    print(f"  [RENAME] Quitting...")
                    break
                else:
                    skipped += 1
                    print(f"  [RENAME] Skipped")
            else:
                skipped += 1

        return renamed, skipped, deleted
