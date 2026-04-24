"""
DisplayPlayer — lite version.

Pi OS (Linux):
  Images → fbi  (framebuffer, no X11 needed)
  Videos → cvlc (VLC CLI)

macOS (dev/testing):
  Both   → open (opens in Preview / QuickTime for testing only)
"""

import logging
import os
import platform
import subprocess
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

IS_LINUX = platform.system() == "Linux"


def _kill_all_fbi():
    """Kill any existing fbi processes to ensure clean framebuffer access."""
    if not IS_LINUX:
        return
    
    try:
        # Find all fbi processes
        result = subprocess.run(
            ["pgrep", "-x", "fbi"],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            logger.info(f"Killing {len(pids)} existing fbi process(es)")
            
            for pid in pids:
                try:
                    subprocess.run(["kill", "-9", pid], timeout=1)
                except Exception as e:
                    logger.warning(f"Failed to kill fbi process {pid}: {e}")
    except Exception as e:
        logger.warning(f"Error checking for fbi processes: {e}")


def _build_cmd(paths: list[str], file_type: str, duration: float = 10.0) -> list[str]:
    """
    Build command for playing media file(s).
    
    For images on Linux, fbi supports multiple files in one command,
    creating a slideshow with automatic transitions.
    """
    if IS_LINUX:
        if file_type == "image":
            # fbi: framebuffer image viewer — no X11 required
            # -d /dev/fb0 : explicitly use framebuffer device (required for service)
            # -a    : auto-scale to screen
            # -t <sec> : display each image for <sec> seconds
            # -noverbose : suppress status output
            # -1 : show once (loop through all images once then exit)
            # Multiple paths create a slideshow
            return ["fbi", "-d", "/dev/fb0", "-a", "-t", str(int(duration)), "-noverbose"] + paths
        else:
            # cvlc: VLC without GUI (single video at a time)
            # --vout fb : framebuffer output (no X11)
            # --play-and-exit : quit when video ends
            return [
                "cvlc",
                "--fullscreen",
                "--vout", "fb",
                "--no-osd",
                "--play-and-exit",
                "--quiet",
                paths[0],  # Videos played one at a time
            ]
    else:
        # macOS — just open with the default app (Preview / QuickTime)
        # Used for development/testing only; not fullscreen
        # Note: macOS 'open' doesn't support multiple files as slideshow
        return ["open", paths[0]]


class DisplayPlayer:
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()   # set = paused
        self._next_event = threading.Event()

        self._lock = threading.Lock()
        self._status = {
            "is_playing": False,
            "is_paused": False,
            "current_file": None,
            "current_index": 0,
            "total_items": 0,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play_file(self, file_path: str, file_type: str, duration: float = 10.0):
        items = [{"path": file_path, "type": file_type, "duration": duration}]
        self.play_playlist(items, loop=False)

    def play_playlist(self, items: list[dict], loop: bool = True):
        """
        items: [{"path": str, "type": "image"|"video", "duration": float}, ...]
        """
        self._stop()
        if not items:
            return

        self._stop_event.clear()
        self._pause_event.clear()
        self._next_event.clear()

        self._thread = threading.Thread(
            target=self._run_playlist,
            args=(items, loop),
            daemon=True,
            name="playlist-thread",
        )
        self._thread.start()

    def pause(self):
        self._pause_event.set()
        with self._lock:
            self._status["is_paused"] = True
        logger.info("Paused")

    def resume(self):
        self._pause_event.clear()
        with self._lock:
            self._status["is_paused"] = False
        logger.info("Resumed")

    def next(self):
        self._next_event.set()
        logger.info("Next item")

    def stop(self):
        self._stop()
        logger.info("Stopped")

    def get_status(self) -> dict:
        with self._lock:
            return dict(self._status)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _stop(self):
        self._stop_event.set()
        self._pause_event.clear()
        self._next_event.set()      # unblock any waiting loop

        self._kill_process()
        _kill_all_fbi()  # Ensure all fbi processes are killed

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

        self._thread = None
        with self._lock:
            self._status.update(
                is_playing=False, is_paused=False, current_file=None,
                current_index=0, total_items=0,
            )

    def _run_playlist(self, items: list[dict], loop: bool):
        with self._lock:
            self._status.update(is_playing=True, total_items=len(items))

        index = 0
        while not self._stop_event.is_set():
            # Group consecutive images with same duration into batches
            batch, batch_size = self._get_next_batch(items, index)
            self._next_event.clear()

            # Update status to first item in batch
            with self._lock:
                self._status["current_file"] = batch[0]["path"]
                self._status["current_index"] = index + 1

            is_image_batch = batch[0]["type"] == "image" and len(batch) > 1
            
            if is_image_batch and IS_LINUX:
                # Play all images in batch as fbi slideshow
                self._play_image_batch(batch)
                # fbi will handle timing, just wait for completion
                self._wait_for_process_or_signal()
            elif batch[0]["type"] == "image" and IS_LINUX:
                # Single image on Linux - still use fbi
                self._play_image_batch(batch)  # Works for single image too
                self._wait_for_process_or_signal()
            else:
                # Single item (video or macOS fallback)
                self._play_item(batch[0])
                
                if batch[0]["type"] == "video":
                    self._wait_for_process_or_signal()
                else:
                    # macOS - manually wait
                    self._wait_duration(batch[0].get("duration", 10.0))

            if self._stop_event.is_set():
                break

            index = (index + batch_size) % len(items)
            if not loop and index == 0:
                break

        self._kill_process()
        _kill_all_fbi()  # Final cleanup
        with self._lock:
            self._status.update(
                is_playing=False, is_paused=False,
                current_file=None, current_index=0,
            )

    def _get_next_batch(self, items: list[dict], start_index: int) -> tuple[list[dict], int]:
        """
        Group consecutive images with the same duration into a batch.
        Returns (batch_items, batch_size).
        """
        if start_index >= len(items):
            return [items[0]], 1
            
        first_item = items[start_index]
        
        # If it's a video or not Linux, return single item
        if first_item["type"] != "image" or not IS_LINUX:
            return [first_item], 1
        
        # Batch consecutive images with same duration
        batch = [first_item]
        target_duration = first_item.get("duration", 10.0)
        
        for i in range(start_index + 1, len(items)):
            item = items[i]
            # Stop batching if we hit a video or different duration
            if item["type"] != "image" or item.get("duration", 10.0) != target_duration:
                break
            batch.append(item)
        
        return batch, len(batch)

    def _play_image_batch(self, batch: list[dict]):
        """Play multiple images as a slideshow using fbi."""
        self._kill_process()
        _kill_all_fbi()  # Kill any stray fbi processes
        
        paths = [item["path"] for item in batch]
        duration = batch[0].get("duration", 10.0)
        cmd = _build_cmd(paths, "image", duration)
        
        logger.info("Starting fbi slideshow with %d images (%.1fs each)", len(batch), duration)
        logger.debug(f"fbi command: {' '.join(cmd)}")
        
        try:
            self._process = subprocess.Popen(
                cmd,
                env={**os.environ},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.debug(f"fbi process started with PID {self._process.pid}")
        except FileNotFoundError:
            logger.warning("Command not found: %s — skipping (dev mode?)", cmd[0])
            self._process = None
        except Exception as e:
            logger.error(f"Failed to start fbi: {e}")
            self._process = None

    def _play_item(self, item: dict):
        self._kill_process()
        # Kill any stray fbi processes if we're about to play an image
        if item.get("type", "image") == "image":
            _kill_all_fbi()
        cmd = _build_cmd([item["path"]], item.get("type", "image"), item.get("duration", 10.0))
        try:
            self._process = subprocess.Popen(
                cmd,
                env={**os.environ},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning("Command not found: %s — skipping (dev mode?)", cmd[0])
            self._process = None

    def _wait_duration(self, duration: float):
        elapsed = 0.0
        interval = 0.1
        while elapsed < duration:
            if self._stop_event.is_set() or self._next_event.is_set():
                return
            if not self._pause_event.is_set():
                elapsed += interval
            time.sleep(interval)

    def _wait_for_process_or_signal(self):
        while True:
            if self._stop_event.is_set() or self._next_event.is_set():
                logger.debug("Wait interrupted by signal")
                return
            if self._process is None or self._process.poll() is not None:
                if self._process and self._process.returncode is not None:
                    logger.debug(f"Process exited with code {self._process.returncode}")
                    # Log any errors from stderr
                    if self._process.returncode != 0 and self._process.stderr:
                        try:
                            stderr = self._process.stderr.read().decode('utf-8', errors='ignore')
                            if stderr.strip():
                                logger.warning(f"Process stderr: {stderr.strip()}")
                        except Exception:
                            pass
                # Small delay to ensure framebuffer is released
                time.sleep(0.1)
                return
            time.sleep(0.2)

    def _kill_process(self):
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None


player = DisplayPlayer()
