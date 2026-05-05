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
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

IS_LINUX = platform.system() == "Linux"

# Font search paths (Linux first, then macOS fallbacks)
_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
]


def _find_font():
    for p in _FONT_PATHS:
        if Path(p).exists():
            return p
    return None


def _kill_all_fbi():
    """Kill any existing fbi processes to ensure clean framebuffer access."""
    if not IS_LINUX:
        return

    try:
        result = subprocess.run(
            ["pgrep", "-x", "fbi"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            logger.info("Killing %d existing fbi process(es)", len(pids))
            for pid in pids:
                try:
                    subprocess.run(["kill", "-9", pid], timeout=1)
                except Exception as e:
                    logger.warning("Failed to kill fbi process %s: %s", pid, e)
    except Exception as e:
        logger.warning("Error checking for fbi processes: %s", e)


def _build_cmd(paths: list[str], file_type: str, duration: float = 10.0) -> list[str]:
    """
    Build command for playing media file(s).

    For images on Linux, fbi supports multiple files in one command,
    creating a slideshow with automatic transitions.
    """
    if IS_LINUX:
        if file_type == "image":
            delay = int(duration)
            return [
                "fbi",
                "-t", str(delay),
                "-a",
                "--noverbose",
                "-d", "/dev/fb0",
                "-T", "1",
            ] + paths
        else:
            return [
                "cvlc",
                "--fullscreen",
                "--vout", "fb",
                "--no-osd",
                "--play-and-exit",
                "--quiet",
                paths[0],
            ]
    else:
        return ["open", paths[0]]


def _generate_idle_image(base_image_path: str, custom_text: str) -> Optional[str]:
    """
    Composite the base image with a date+time and custom text overlay.
    Returns the path to the generated temp image, or None on failure.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not installed — showing idle image without overlay")
        return base_image_path

    try:
        img = Image.open(base_image_path).convert("RGB")
        w, h = img.size

        # Semi-transparent dark bar at the bottom (25% of height)
        bar_h = max(int(h * 0.25), 80)
        overlay = Image.new("RGBA", (w, bar_h), (0, 0, 0, 180))
        img_rgba = img.convert("RGBA")
        img_rgba.paste(overlay, (0, h - bar_h), overlay)
        img = img_rgba.convert("RGB")

        draw = ImageDraw.Draw(img)
        font_path = _find_font()

        def _font(size):
            if font_path:
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception:
                    pass
            return ImageFont.load_default()

        now = datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%A, %B %d, %Y")

        time_size = max(int(bar_h * 0.50), 32)
        date_size = max(int(bar_h * 0.22), 16)
        custom_size = max(int(bar_h * 0.25), 18)

        time_font = _font(time_size)
        date_font = _font(date_size)
        custom_font = _font(custom_size)

        pad = int(w * 0.03)
        bar_top = h - bar_h
        text_color = (255, 255, 255)
        shadow = (0, 0, 0)

        # Right side: large time, smaller date below
        def _draw_text(text, font, x, y):
            draw.text((x + 2, y + 2), text, font=font, fill=shadow)
            draw.text((x, y), text, font=font, fill=text_color)

        try:
            time_bbox = draw.textbbox((0, 0), time_str, font=time_font)
            time_w = time_bbox[2] - time_bbox[0]
            time_h_px = time_bbox[3] - time_bbox[1]
        except AttributeError:
            time_w, time_h_px = draw.textsize(time_str, font=time_font)

        time_x = w - pad - time_w
        time_y = bar_top + (bar_h - time_h_px) // 2 - int(date_size * 0.6)

        _draw_text(time_str, time_font, time_x, time_y)

        try:
            date_bbox = draw.textbbox((0, 0), date_str, font=date_font)
            date_w = date_bbox[2] - date_bbox[0]
        except AttributeError:
            date_w, _ = draw.textsize(date_str, font=date_font)

        date_x = w - pad - date_w
        date_y = time_y + time_h_px + 4
        _draw_text(date_str, date_font, date_x, date_y)

        # Left side: custom text (vertically centred in bar)
        if custom_text:
            try:
                ct_bbox = draw.textbbox((0, 0), custom_text, font=custom_font)
                ct_h = ct_bbox[3] - ct_bbox[1]
            except AttributeError:
                _, ct_h = draw.textsize(custom_text, font=custom_font)

            ct_y = bar_top + (bar_h - ct_h) // 2
            _draw_text(custom_text, custom_font, pad, ct_y)

        out_path = "/tmp/pi_display_idle.jpg"
        img.save(out_path, "JPEG", quality=92)
        return out_path

    except Exception as e:
        logger.error("Failed to generate idle image: %s", e)
        return base_image_path


class DisplayPlayer:
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._next_event = threading.Event()

        self._lock = threading.Lock()
        self._status = {
            "is_playing": False,
            "is_paused": False,
            "current_file": None,
            "current_index": 0,
            "total_items": 0,
        }

        # Idle screen state
        self._idle_image_path: Optional[str] = None
        self._idle_custom_text: str = ""
        self._idle_thread: Optional[threading.Thread] = None
        self._idle_stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_idle_config(self, image_path: Optional[str], custom_text: str = ""):
        """Configure the idle screen. Pass image_path=None to disable."""
        self._idle_image_path = image_path
        self._idle_custom_text = custom_text

    def show_idle(self):
        """Start the idle screen if idle config is set."""
        if not self._idle_image_path:
            return
        self._stop_idle()
        self._idle_stop_event.clear()
        self._idle_thread = threading.Thread(
            target=self._run_idle,
            daemon=True,
            name="idle-thread",
        )
        self._idle_thread.start()

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
        self.show_idle()

    def get_status(self) -> dict:
        with self._lock:
            return dict(self._status)

    # ------------------------------------------------------------------
    # Internal — idle
    # ------------------------------------------------------------------

    def _stop_idle(self):
        self._idle_stop_event.set()
        if self._idle_thread and self._idle_thread.is_alive():
            self._idle_thread.join(timeout=3)
        self._idle_thread = None

    def _run_idle(self):
        logger.info("Idle screen started")
        while not self._idle_stop_event.is_set():
            idle_path = _generate_idle_image(
                self._idle_image_path, self._idle_custom_text
            )
            if idle_path:
                self._kill_process()
                _kill_all_fbi()
                if IS_LINUX:
                    cmd = [
                        "fbi",
                        "-T", "1",
                        "-d", "/dev/fb0",
                        "--noverbose",
                        "-t", "86400",  # stay for 24 h (we'll kill it on refresh)
                        idle_path,
                    ]
                    try:
                        fbi_log = Path(__file__).parent / "fbi_error.log"
                        with open(fbi_log, "a") as f:
                            self._process = subprocess.Popen(
                                cmd,
                                stdin=subprocess.DEVNULL,
                                stdout=f,
                                stderr=f,
                            )
                    except FileNotFoundError:
                        logger.warning("fbi not found — idle screen unavailable")
                else:
                    try:
                        subprocess.Popen(
                            ["open", idle_path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except Exception:
                        pass

            # Refresh every 60 s to update the clock
            self._idle_stop_event.wait(timeout=60)

        self._kill_process()
        _kill_all_fbi()
        logger.info("Idle screen stopped")

    # ------------------------------------------------------------------
    # Internal — playlist
    # ------------------------------------------------------------------

    def _stop(self):
        self._stop_idle()
        self._stop_event.set()
        self._pause_event.clear()
        self._next_event.set()

        self._kill_process()
        _kill_all_fbi()

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
            batch, batch_size = self._get_next_batch(items, index)
            self._next_event.clear()

            with self._lock:
                self._status["current_file"] = batch[0]["path"]
                self._status["current_index"] = index + 1

            is_image_batch = batch[0]["type"] == "image" and len(batch) > 1

            if is_image_batch and IS_LINUX:
                self._play_image_batch(batch)
                self._wait_for_process_or_signal()
            elif batch[0]["type"] == "image" and IS_LINUX:
                self._play_image_batch(batch)
                self._wait_for_process_or_signal()
            else:
                self._play_item(batch[0])
                if batch[0]["type"] == "video":
                    self._wait_for_process_or_signal()
                else:
                    self._wait_duration(batch[0].get("duration", 10.0))

            if self._stop_event.is_set():
                break

            index = (index + batch_size) % len(items)
            if not loop and index == 0:
                break

        self._kill_process()
        _kill_all_fbi()
        with self._lock:
            self._status.update(
                is_playing=False, is_paused=False,
                current_file=None, current_index=0,
            )

        # Return to idle when a non-looping playlist finishes naturally
        if not self._stop_event.is_set():
            self.show_idle()

    def _get_next_batch(self, items: list[dict], start_index: int) -> tuple[list[dict], int]:
        if start_index >= len(items):
            return [items[0]], 1

        first_item = items[start_index]

        if first_item["type"] != "image" or not IS_LINUX:
            return [first_item], 1

        batch = [first_item]
        target_duration = first_item.get("duration", 10.0)

        for i in range(start_index + 1, len(items)):
            item = items[i]
            if item["type"] != "image" or item.get("duration", 10.0) != target_duration:
                break
            batch.append(item)

        return batch, len(batch)

    def _play_image_batch(self, batch: list[dict]):
        self._kill_process()
        _kill_all_fbi()

        paths = [item["path"] for item in batch]
        duration = batch[0].get("duration", 10.0)
        cmd = _build_cmd(paths, "image", duration)

        logger.info("Starting fbi slideshow with %d images (%.1fs each)", len(batch), duration)

        try:
            fbi_log = Path(__file__).parent / "fbi_error.log"
            with open(fbi_log, "a") as f:
                f.write(f"\n=== Starting fbi at {datetime.now()} ===\n")
            with open(fbi_log, "a") as f:
                self._process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=f,
                    stderr=f,
                )
        except FileNotFoundError:
            logger.warning("Command not found: %s — skipping (dev mode?)", cmd[0])
            self._process = None
        except Exception as e:
            logger.error("Failed to start fbi: %s", e)
            self._process = None

    def _play_item(self, item: dict):
        self._kill_process()
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
                return
            if self._process is None or self._process.poll() is not None:
                if self._process and self._process.returncode not in (None, 0):
                    logger.debug("Process exited with code %d", self._process.returncode)
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
