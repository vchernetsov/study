"""
Camera control module for Nikon 1 V1 via USB
"""

import subprocess
from datetime import datetime


class NikonCamera:
    """Controls Nikon 1 V1 camera via gphoto2"""

    def __init__(self):
        self.connected = False
        self.killed_processes = []

    def _kill_gvfs(self):
        """Kill gvfs-gphoto2-volume-monitor to release camera"""
        import time
        try:
            print("[CAMERA] Stopping gvfs processes...")

            # Check which processes are running before killing
            result = subprocess.run(['pgrep', 'gvfs-gphoto2-volume-monitor'], capture_output=True)
            if result.returncode == 0:
                self.killed_processes.append('gvfs-gphoto2-volume-monitor')

            result = subprocess.run(['pgrep', 'gvfsd'], capture_output=True)
            if result.returncode == 0:
                self.killed_processes.append('gvfsd')

            # Kill gvfs-gphoto2-volume-monitor
            subprocess.run(['pkill', '-9', 'gvfs-gphoto2-volume-monitor'], capture_output=True, timeout=2)
            time.sleep(0.3)
            subprocess.run(['pkill', '-9', 'gvfs-gphoto2-volume-monitor'], capture_output=True, timeout=2)

            # Also kill gvfsd if present
            subprocess.run(['pkill', '-9', 'gvfsd'], capture_output=True, timeout=2)

            # Give it more time to release the device
            time.sleep(1)
            return True
        except Exception as e:
            print(f"[CAMERA] Warning: Could not kill gvfs process: {e}")
            return False

    def _restore_gvfs(self):
        """Restore gvfs processes that were killed"""
        if not self.killed_processes:
            return

        try:
            print("[CAMERA] Restoring gvfs processes...")
            # Restart gvfs daemon - it will auto-spawn the volume monitor
            if 'gvfsd' in self.killed_processes or 'gvfs-gphoto2-volume-monitor' in self.killed_processes:
                subprocess.run(['gvfsd'], capture_output=True, timeout=2)
                print("[CAMERA] gvfs processes restored")
            self.killed_processes = []
        except Exception as e:
            print(f"[CAMERA] Warning: Could not restore gvfs processes: {e}")

    def connect(self):
        """Check if camera is connected"""
        # First, kill gvfs process that might block access
        self._kill_gvfs()

        try:
            result = subprocess.run(
                ['gphoto2', '--auto-detect'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and 'usb' in result.stdout.lower():
                print("[CAMERA] Nikon camera detected via USB")
                self.connected = True
                return True
            else:
                print("[CAMERA] No camera detected")
                # Restore processes if connection failed
                self._restore_gvfs()
                return False
        except FileNotFoundError:
            print("[CAMERA] ERROR: gphoto2 not found. Please install: sudo apt install gphoto2")
            self._restore_gvfs()
            return False
        except Exception as e:
            print(f"[CAMERA] ERROR: {e}")
            self._restore_gvfs()
            return False

    def sync_time(self):
        """Synchronize camera time with host time"""
        if not self.connected:
            print("[CAMERA] WARNING: Camera not connected")
            return False

        success = False
        try:
            # Kill gvfs again (it may have respawned)
            self._kill_gvfs()

            # Get current time - use Unix timestamp for Nikon
            now = datetime.now()
            timestamp = int(now.timestamp())

            print(f"[CAMERA] Setting camera time to: {now.strftime('%Y-%m-%d %H:%M:%S')}")

            # Try setting time using timestamp
            result = subprocess.run(
                ['gphoto2', '--set-config', f'/main/settings/datetime={timestamp}'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                print("[CAMERA] Time synchronized successfully")
                success = True
            else:
                # If that fails, try alternative method
                print("[CAMERA] Trying alternative method...")
                result = subprocess.run(
                    ['gphoto2', '--set-config-index', '/main/settings/datetime=0'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    print("[CAMERA] Time synchronized successfully")
                    success = True
                else:
                    print(f"[CAMERA] Failed to sync time: {result.stderr}")
                    success = False

        except Exception as e:
            print(f"[CAMERA] ERROR syncing time: {e}")
            success = False
        finally:
            # Always restore gvfs processes, even on failure
            self._restore_gvfs()

        return success

    def download_all(self, target_folder):
        """Download all files from camera to target folder"""
        if not self.connected:
            print("[CAMERA] WARNING: Camera not connected")
            return False

        success = False
        try:
            # Kill gvfs again (it may have respawned)
            self._kill_gvfs()

            # Change to target directory
            import os
            original_dir = os.getcwd()
            os.chdir(target_folder)

            print(f"[CAMERA] Downloading all files from camera...")
            print("-" * 80)

            # Don't capture output - let it stream to terminal for progress
            result = subprocess.run(
                ['gphoto2', '--get-all-files', '--skip-existing'],
                timeout=300  # 5 minutes timeout
            )

            print("-" * 80)

            # Change back to original directory
            os.chdir(original_dir)

            if result.returncode == 0:
                print(f"[CAMERA] Download completed successfully")
                success = True
            else:
                print(f"[CAMERA] Download completed with errors (return code: {result.returncode})")
                success = False

        except Exception as e:
            print(f"[CAMERA] ERROR downloading files: {e}")
            success = False
        finally:
            # Always restore gvfs processes, even on failure
            self._restore_gvfs()

        return success

    def disconnect(self):
        """Disconnect from camera and restore gvfs processes"""
        self.connected = False
        self._restore_gvfs()
        print("[CAMERA] Disconnected")
