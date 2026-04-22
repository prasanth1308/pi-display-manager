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


def _build_cmd(path: str, file_type: str) -> list[str]:
    if IS_LINUX:
        if file_type == "image":
            # fbi: framebuffer image viewer — no X11 required
            # -T 1  : use virtual terminal 1
            # -a    : auto-scale to screen
            # -1    : show once and exit (we control the loop)
            # -noverbose : suppress status output
            return ["fbi", "-T", "1", "-a", "-1", "-noverbose", path]
        else:
            # cvlc: VLC without GUI
            # --vout fb : framebuffer output (no X11)
            # --play-and-exit : quit when video ends
            return [
                "cvlc",
                "--fullscreen",
                "--vout", "fb",
                "--no-osd",
                "--play-and-exit",
                "--quiet",
                path,
            ]
    else:
        # macOS — just open with the default app (Preview / QuickTime)
        # Used for development/testing only; not fullscreen
        return ["open", path]


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
            item = items[index]
            self._next_event.clear()

            with self._lock:
                self._status["current_file"] = item["path"]
                self._status["current_index"] = index + 1

            self._play_item(item)

            if item["type"] == "video":
                self._wait_for_process_or_signal()
            else:
                self._wait_duration(item.get("duration", 10.0))

            if self._stop_event.is_set():
                break

            index = (index + 1) % len(items)
            if not loop and index == 0:
                break

        self._kill_process()
        with self._lock:
            self._status.update(
                is_playing=False, is_paused=False,
                current_file=None, current_index=0,
            )

    def _play_item(self, item: dict):
        self._kill_process()
        cmd = _build_cmd(item["path"], item.get("type", "image"))
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
                return
            if self._process is None or self._process.poll() is not None:
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
