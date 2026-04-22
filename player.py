"""
DisplayPlayer — controls mpv subprocess for fullscreen media playback.

Playback runs in a background thread that iterates playlist items.
Control signals (pause/resume/next/stop) use threading.Event flags.
"""

import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Set DISPLAY for X11 — mpv needs this to render on the TV
DISPLAY_ENV = {"DISPLAY": ":0"}


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
        """Play a single file immediately."""
        items = [{"path": file_path, "type": file_type, "duration": duration}]
        self.play_playlist(items, loop=False)

    def play_playlist(self, items: list[dict], loop: bool = True):
        """
        Play a list of items.
        Each item: {"path": str, "type": "image"|"video"|"presentation", "duration": float}
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
        logger.info("Playback paused")

    def resume(self):
        self._pause_event.clear()
        with self._lock:
            self._status["is_paused"] = False
        logger.info("Playback resumed")

    def next(self):
        self._next_event.set()
        logger.info("Skip to next item")

    def stop(self):
        self._stop()
        logger.info("Playback stopped")

    def get_status(self) -> dict:
        with self._lock:
            return dict(self._status)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _stop(self):
        self._stop_event.set()
        self._pause_event.clear()  # unblock any waiting loop
        self._next_event.set()     # unblock wait loop

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

            # Wait for item duration (or next/stop signal)
            if item["type"] == "video":
                # For video, wait until mpv exits naturally or signal fires
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
                is_playing=False, is_paused=False, current_file=None,
                current_index=0,
            )

    def _play_item(self, item: dict):
        """Launch mpv for a single item."""
        self._kill_process()

        path = item["path"]
        file_type = item.get("type", "image")

        cmd = [
            "mpv",
            "--fullscreen",
            "--no-terminal",
            "--really-quiet",
        ]

        if file_type == "video":
            cmd.append(path)
        else:
            # Images and presentation slides
            cmd += ["--no-audio", path]

        import os
        env = {**os.environ, **DISPLAY_ENV}

        try:
            self._process = subprocess.Popen(cmd, env=env)
        except FileNotFoundError:
            logger.warning("mpv not found — running in dev mode, skipping playback")
            self._process = None

    def _wait_duration(self, duration: float):
        """Wait for duration seconds, respecting pause and next/stop events."""
        elapsed = 0.0
        interval = 0.1
        while elapsed < duration:
            if self._stop_event.is_set() or self._next_event.is_set():
                return
            if not self._pause_event.is_set():
                elapsed += interval
            time.sleep(interval)

    def _wait_for_process_or_signal(self):
        """Wait until mpv exits or a control signal fires."""
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


# Module-level singleton used by routers and scheduler
player = DisplayPlayer()
