"""
Pi Display Manager - Service Layer
Contains business logic for managing slideshows, playlists, and video playback.
"""

import os
import json
import subprocess
import sys
import logging
import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
import yt_dlp

# Global state
slideshow_process = None
video_process = None
config = {}
playlists_db = {}
current_playlist = None
download_status = {}  # Track video download status
api_port = 8000
logger = None
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PLAYLISTS_DIR = DATA_DIR / "playlists"
VIDEOS_DIR = DATA_DIR / "videos"
UPLOADS_DIR = DATA_DIR / "uploads"
IDLE_DIR = DATA_DIR / "idle"
PLAYLISTS_DB_FILE = BASE_DIR / "playlists.json"
IDLE_CONFIG_FILE = BASE_DIR / "idle_config.json"
STATIC_DIR = BASE_DIR / "frontend"

# Idle screen state
idle_process = None
idle_thread = None
idle_stop_event = threading.Event()

# Font search paths — Linux (Pi OS) first, then macOS dev fallbacks
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


def setup_logging():
    """Configure logging to file and console"""
    global logger
    log_file = BASE_DIR / "slideshow_api.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)


def ensure_directories():
    """Create necessary directories if they don't exist"""
    PLAYLISTS_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    IDLE_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Directory structure ensured")


def load_config():
    """Load configuration from config.json"""
    global config
    config_path = BASE_DIR / "config.json"
    try:
        with open(config_path) as f:
            config = json.load(f)
        logger.info("Configuration loaded from %s", config_path)
    except FileNotFoundError:
        logger.warning("Config file not found, using defaults")
        config = {
            "api_port": 8000,
            "delay": 5,
            "framebuffer": "/dev/fb0"
        }
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in config: %s", e)
        sys.exit(1)


def load_playlists_db():
    """Load playlists database"""
    global playlists_db
    try:
        if PLAYLISTS_DB_FILE.exists():
            with open(PLAYLISTS_DB_FILE) as f:
                playlists_db = json.load(f)
        else:
            playlists_db = {
                "playlists": {},
                "active_playlist": None
            }
            save_playlists_db()
        logger.info("Playlists database loaded")
    except Exception as e:
        logger.error("Failed to load playlists database: %s", e)
        playlists_db = {"playlists": {}, "active_playlist": None}


# ── Idle Screen ───────────────────────────────────────────────────────────────

def get_idle_config():
    """Return the current idle config dict."""
    try:
        if IDLE_CONFIG_FILE.exists():
            return json.loads(IDLE_CONFIG_FILE.read_text())
    except Exception:
        pass
    return {"image_path": None, "custom_text": "", "enabled": False}


def load_idle_config():
    """Load idle config and apply to the player."""
    cfg = get_idle_config()
    if cfg.get("enabled") and cfg.get("image_path"):
        logger.info("Idle screen configured: %s", cfg["image_path"])
    return cfg


def save_idle_config(data):
    """Persist idle config and return the saved dict."""
    cfg = {
        "image_path": data.get("image_path"),
        "custom_text": data.get("custom_text", ""),
        "enabled": bool(data.get("enabled", True)),
    }
    IDLE_CONFIG_FILE.write_text(json.dumps(cfg))
    logger.info("Idle config saved")
    return cfg


def _get_display_size():
    """Read framebuffer resolution from sysfs. Falls back to 1920x1080."""
    try:
        text = Path("/sys/class/graphics/fb0/virtual_size").read_text().strip()
        w, h = map(int, text.split(","))
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    return 1920, 1080


def _write_framebuffer(img, fb_path):
    """
    Write a PIL Image directly to the framebuffer — no external process, no flicker.
    Supports 32bpp BGRA (common on Pi) and 16bpp RGB565.
    Returns True on success.
    """
    try:
        bpp_path = Path("/sys/class/graphics/fb0/bits_per_pixel")
        bpp = int(bpp_path.read_text().strip()) if bpp_path.exists() else 32

        if bpp == 16:
            import array
            rgb = img.convert("RGB")
            buf = array.array("H")
            for r, g, b in rgb.getdata():
                buf.append(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3))
            data = buf.tobytes()
        else:
            # 32bpp BGRA — swap R and B channels
            from PIL import Image as _Img
            r, g, b = img.convert("RGB").split()
            bgra = _Img.merge("RGBA", (b, g, r, _Img.new("L", img.size, 255)))
            data = bgra.tobytes()

        with open(fb_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        logger.warning("Direct framebuffer write failed: %s", e)
        return False


def _sleep_until_next_minute():
    """
    Block until the next minute boundary, waking early if idle_stop_event is set.
    Returns True if interrupted by stop_event.
    """
    now = datetime.now()
    seconds_left = 60 - now.second - now.microsecond / 1_000_000
    deadline = time.monotonic() + seconds_left
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if idle_stop_event.wait(timeout=min(remaining, 1.0)):
            return True  # stop requested
    return False


def generate_idle_image(base_image_path, custom_text):
    """
    Composite base_image_path — fitted letterboxed to the display resolution —
    with a semi-transparent bottom bar showing date+time (right) and
    custom_text (left). Returns the output path, or None on failure.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not installed — idle image has no overlay")
        return base_image_path

    try:
        # ── Fit image to display ──────────────────────────────────────────
        if sys.platform == "linux":
            disp_w, disp_h = _get_display_size()
        else:
            disp_w, disp_h = 1920, 1080  # dev fallback

        canvas = Image.new("RGB", (disp_w, disp_h), (0, 0, 0))
        src = Image.open(base_image_path).convert("RGB")
        src.thumbnail((disp_w, disp_h), Image.LANCZOS)
        canvas.paste(src, ((disp_w - src.width) // 2, (disp_h - src.height) // 2))

        img = canvas
        w, h = disp_w, disp_h

        # ── Overlay bar ───────────────────────────────────────────────────
        bar_h = max(int(h * 0.15), 72)
        overlay = Image.new("RGBA", (w, bar_h), (0, 0, 0, 185))
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

        time_size = max(int(bar_h * 0.52), 32)
        date_size = max(int(bar_h * 0.24), 16)
        custom_size = max(int(bar_h * 0.28), 18)

        time_font = _font(time_size)
        date_font = _font(date_size)
        custom_font = _font(custom_size)

        pad = int(w * 0.025)
        bar_top = h - bar_h
        white = (255, 255, 255)
        black = (0, 0, 0)

        def _draw_text(text, font, x, y):
            draw.text((x + 2, y + 2), text, font=font, fill=black)
            draw.text((x, y), text, font=font, fill=white)

        def _text_size(text, font):
            try:
                bb = draw.textbbox((0, 0), text, font=font)
                return bb[2] - bb[0], bb[3] - bb[1]
            except AttributeError:
                return draw.textsize(text, font=font)

        time_w, time_h_px = _text_size(time_str, time_font)
        date_w, _ = _text_size(date_str, date_font)

        # Right side: clock stacked above date, both right-aligned
        v_block = time_h_px + 4 + date_size
        time_y = bar_top + (bar_h - v_block) // 2
        _draw_text(time_str, time_font, w - pad - time_w, time_y)
        _draw_text(date_str, date_font, w - pad - date_w, time_y + time_h_px + 4)

        # Left side: custom text, vertically centred in bar
        if custom_text:
            _, ct_h = _text_size(custom_text, custom_font)
            _draw_text(custom_text, custom_font, pad, bar_top + (bar_h - ct_h) // 2)

        out_path = "/tmp/pi_display_idle.jpg"
        img.save(out_path, "JPEG", quality=92)
        return out_path

    except Exception as e:
        logger.error("Failed to generate idle image: %s", e)
        return None


def _kill_idle_fbi():
    """Terminate the idle fbi process and kill any stray fbi instances."""
    global idle_process
    if idle_process is not None:
        try:
            idle_process.terminate()
            idle_process.wait(timeout=2)
        except Exception:
            try:
                idle_process.kill()
            except Exception:
                pass
        idle_process = None
    try:
        subprocess.run(["pkill", "-x", "fbi"], capture_output=True)
    except Exception:
        pass


def _run_idle_loop(image_path, custom_text):
    """
    Background thread for the idle screen.

    Strategy (Linux):
      1. Write the composite image directly to /dev/fb0 — instant, zero flicker.
      2. Sleep until the next minute boundary (not a flat 60 s) so the clock
         turns over precisely.
      3. If direct framebuffer write fails (permissions etc.) fall back to fbi.

    On macOS (dev): fbi not available; just regenerates the temp file silently.
    """
    global idle_process

    logger.info("Idle screen thread started")
    framebuffer = config.get("framebuffer", "/dev/fb0")
    is_linux = sys.platform == "linux"

    # Try direct write first; if it fails once, switch to fbi fallback.
    use_direct = is_linux

    # Kill any fbi left over from a previous slideshow before we start
    if is_linux:
        _kill_idle_fbi()

    while not idle_stop_event.is_set():
        idle_img_path = generate_idle_image(image_path, custom_text)

        if idle_img_path and use_direct:
            try:
                from PIL import Image as _Img
                img = _Img.open(idle_img_path)
                if not _write_framebuffer(img, framebuffer):
                    # Direct write failed — fall back to fbi for the rest of the session
                    logger.info("Falling back to fbi for idle screen")
                    use_direct = False
            except Exception as e:
                logger.error("Idle direct-write error: %s", e)
                use_direct = False

        if idle_img_path and not use_direct and is_linux:
            # fbi fallback: kill previous instance, start new one
            _kill_idle_fbi()
            cmd = [
                "fbi", "-T", "1", "-d", framebuffer,
                "--noverbose", "-t", "86400", idle_img_path,
            ]
            try:
                fbi_log = BASE_DIR / "fbi_error.log"
                with open(fbi_log, "a") as f:
                    idle_process = subprocess.Popen(
                        cmd, stdin=subprocess.DEVNULL, stdout=f, stderr=f
                    )
            except FileNotFoundError:
                logger.warning("fbi not found — idle display unavailable")
            except Exception as e:
                logger.error("Failed to start idle fbi: %s", e)

        # Sleep until the clock minute turns over, not a flat interval
        if _sleep_until_next_minute():
            break  # stop_event fired

    _kill_idle_fbi()
    logger.info("Idle screen thread stopped")


def start_idle_screen():
    """Start the idle screen if configured and enabled."""
    global idle_thread, idle_stop_event

    cfg = get_idle_config()
    if not cfg.get("enabled") or not cfg.get("image_path"):
        return

    stop_idle_screen()  # ensure clean state

    idle_stop_event.clear()
    idle_thread = threading.Thread(
        target=_run_idle_loop,
        args=(cfg["image_path"], cfg.get("custom_text", "")),
        daemon=True,
        name="idle-screen",
    )
    idle_thread.start()
    logger.info("Idle screen started")


def stop_idle_screen():
    """Stop the idle screen thread and kill any fbi process it owns."""
    global idle_thread, idle_stop_event

    idle_stop_event.set()
    if idle_thread and idle_thread.is_alive():
        idle_thread.join(timeout=3)
    idle_thread = None
    idle_stop_event = threading.Event()  # reset for next use


# ── Playlists DB ──────────────────────────────────────────────────────────────

def save_playlists_db():
    """Save playlists database"""
    try:
        with open(PLAYLISTS_DB_FILE, 'w') as f:
            json.dump(playlists_db, f, indent=2)
        logger.info("Playlists database saved")
    except Exception as e:
        logger.error("Failed to save playlists database: %s", e)


def get_playlist_images(playlist_id):
    """Get list of image files from a playlist folder"""
    playlist_dir = PLAYLISTS_DIR / playlist_id
    if not playlist_dir.exists():
        return []
    
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
    images = sorted([
        str(f) for f in playlist_dir.iterdir()
        if f.suffix.lower() in image_extensions and f.is_file()
    ])
    return images


def clear_framebuffer():
    """Clear the framebuffer to remove any lingering images"""
    try:
        framebuffer = config.get("framebuffer", "/dev/fb0")
        logger.info("Clearing framebuffer: %s", framebuffer)
        subprocess.run(
            ["dd", "if=/dev/zero", f"of={framebuffer}", "bs=1M", "count=10"],
            capture_output=True,
            timeout=3
        )
        logger.info("Framebuffer cleared successfully")
    except subprocess.TimeoutExpired:
        logger.warning("Framebuffer clear timed out")
    except Exception as e:
        logger.warning("Failed to clear framebuffer: %s", str(e))


def start_slideshow(playlist_id=None):
    """Start the slideshow using fbi"""
    global slideshow_process, current_playlist

    stop_idle_screen()

    if slideshow_process is not None:
        logger.info("Slideshow already running - start request ignored")
        return {"status": "error", "message": "Slideshow is already running"}

    # Use provided playlist or active playlist from db
    if playlist_id is None:
        playlist_id = playlists_db.get("active_playlist")
    
    if playlist_id is None:
        return {"status": "error", "message": "No playlist selected"}
    
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": f"Playlist '{playlist_id}' not found"}

    images = get_playlist_images(playlist_id)
    if not images:
        logger.error("No images found in playlist: %s", playlist_id)
        return {"status": "error", "message": "No images found in playlist"}

    try:
        delay = config.get("delay", 5)
        framebuffer = config.get("framebuffer", "/dev/fb0")

        cmd = [
            "fbi",
            "-t", str(delay),
            "-a",
            "--noverbose",
            "-d", framebuffer,
            "-T", "1",
        ] + images

        logger.info("Starting slideshow with playlist: %s (%d images)", playlist_id, len(images))

        env = os.environ.copy()
        env['FRAMEBUFFER'] = framebuffer
        
        fbi_log = BASE_DIR / "fbi_error.log"
        with open(fbi_log, "a") as f:
            f.write(f"\n=== Starting slideshow at {__import__('datetime').datetime.now()} ===\n")
            f.write(f"Playlist: {playlist_id}\n")

        with open(fbi_log, "a") as f:
            slideshow_process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=f,
                stderr=f,
                env=env
            )
        
        current_playlist = playlist_id
        playlists_db["active_playlist"] = playlist_id
        save_playlists_db()
        
        logger.info("Slideshow started (PID: %d)", slideshow_process.pid)
        return {
            "status": "started",
            "message": "Slideshow started",
            "playlist": playlist_id,
            "image_count": len(images)
        }
    except FileNotFoundError:
        logger.error("fbi package not installed")
        return {"status": "error", "message": "fbi package not installed"}
    except Exception as e:
        logger.error("Failed to start slideshow: %s", str(e))
        return {"status": "error", "message": str(e)}


def stop_slideshow():
    """Stop the slideshow and kill all fbi processes"""
    global slideshow_process, current_playlist

    if slideshow_process is None:
        logger.info("Stop requested but slideshow not running")
        try:
            subprocess.run(["pkill", "-9", "fbi"], capture_output=True)
            logger.info("Killed any orphaned fbi processes")
        except Exception as e:
            logger.error("Error running pkill: %s", str(e))
        
        clear_framebuffer()
        start_idle_screen()
        return {"status": "not_running", "message": "Slideshow is not running (cleaned up framebuffer)"}

    try:
        logger.info("Stopping slideshow (PID: %d)", slideshow_process.pid)
        slideshow_process.terminate()
        slideshow_process.wait(timeout=2)
        logger.info("Slideshow stopped successfully")
    except subprocess.TimeoutExpired:
        logger.warning("Slideshow did not stop gracefully, killing process")
        slideshow_process.kill()
    finally:
        slideshow_process = None
        current_playlist = None

    try:
        subprocess.run(["pkill", "-9", "fbi"], capture_output=True)
        logger.info("Killed all fbi processes")
    except Exception as e:
        logger.error("Error running pkill: %s", str(e))

    clear_framebuffer()
    start_idle_screen()

    return {"status": "stopped", "message": "Slideshow stopped"}


def get_status():
    """Get current slideshow status"""
    active_playlist_id = playlists_db.get("active_playlist")
    image_count = 0
    if active_playlist_id:
        image_count = len(get_playlist_images(active_playlist_id))
    
    return {
        "running": slideshow_process is not None or video_process is not None,
        "current_playlist": current_playlist,
        "active_playlist": active_playlist_id,
        "image_count": image_count,
        "delay": config.get("delay"),
        "framebuffer": config.get("framebuffer"),
        "total_playlists": len(playlists_db.get("playlists", {}))
    }


def create_playlist(name, playlist_type="image"):
    """Create a new playlist"""
    playlist_id = str(uuid.uuid4())[:8]
    
    # Determine base directory based on type
    if playlist_type == "video":
        base_dir = VIDEOS_DIR
    else:
        base_dir = PLAYLISTS_DIR
    
    playlist_dir = base_dir / playlist_id
    playlist_dir.mkdir(exist_ok=True)
    
    playlists_db["playlists"][playlist_id] = {
        "name": name,
        "id": playlist_id,
        "type": playlist_type,
        "created": __import__('datetime').datetime.now().isoformat(),
        "image_count": 0,
        "video_count": 0 if playlist_type == "video" else None
    }
    save_playlists_db()
    
    logger.info("Created %s playlist: %s (ID: %s)", playlist_type, name, playlist_id)
    return {"status": "success", "playlist_id": playlist_id, "message": "Playlist created"}


def delete_playlist(playlist_id):
    """Delete a playlist"""
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": "Playlist not found"}
    
    # Stop playback if this playlist is playing
    if current_playlist == playlist_id:
        if video_process is not None:
            stop_video_playback()
        else:
            stop_slideshow()
    
    # Determine folder based on type
    plist_type = playlists_db["playlists"][playlist_id].get("type", "image")
    if plist_type == "video":
        playlist_dir = VIDEOS_DIR / playlist_id
    else:
        playlist_dir = PLAYLISTS_DIR / playlist_id
    
    # Delete folder
    if playlist_dir.exists():
        shutil.rmtree(playlist_dir)
    
    # Remove from database
    del playlists_db["playlists"][playlist_id]
    
    if playlists_db.get("active_playlist") == playlist_id:
        playlists_db["active_playlist"] = None
    
    save_playlists_db()
    
    logger.info("Deleted playlist: %s", playlist_id)
    return {"status": "success", "message": "Playlist deleted"}


def list_playlists():
    """List all playlists with their details"""
    playlists = []
    for playlist_id, info in playlists_db.get("playlists", {}).items():
        plist_type = info.get("type", "image")
        
        if plist_type == "video":
            videos = get_playlist_videos(playlist_id)
            item_count = len(videos)
        else:
            images = get_playlist_images(playlist_id)
            item_count = len(images)
        
        playlists.append({
            "id": playlist_id,
            "name": info["name"],
            "type": plist_type,
            "image_count": item_count if plist_type == "image" else 0,
            "video_count": item_count if plist_type == "video" else 0,
            "created": info.get("created", ""),
            "is_active": playlists_db.get("active_playlist") == playlist_id,
            "is_playing": current_playlist == playlist_id
        })
    return playlists


def upload_image(playlist_id, file_data, filename):
    """Upload an image to a playlist"""
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": "Playlist not found"}
    
    # Validate file extension
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
    file_ext = Path(filename).suffix.lower()
    if file_ext not in valid_extensions:
        return {"status": "error", "message": "Invalid file type"}
    
    # Save file to playlist folder
    playlist_dir = PLAYLISTS_DIR / playlist_id
    file_path = playlist_dir / filename
    
    # Handle duplicate names
    counter = 1
    while file_path.exists():
        name_stem = Path(filename).stem
        file_path = playlist_dir / f"{name_stem}_{counter}{file_ext}"
        counter += 1
    
    try:
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # Update image count
        playlists_db["playlists"][playlist_id]["image_count"] = len(get_playlist_images(playlist_id))
        save_playlists_db()
        
        logger.info("Uploaded image to playlist %s: %s", playlist_id, file_path.name)
        return {"status": "success", "message": "Image uploaded", "filename": file_path.name}
    except Exception as e:
        logger.error("Failed to upload image: %s", e)
        return {"status": "error", "message": str(e)}


def delete_image(playlist_id, filename):
    """Delete an image from a playlist"""
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": "Playlist not found"}
    
    playlist_dir = PLAYLISTS_DIR / playlist_id
    file_path = playlist_dir / filename
    
    if not file_path.exists():
        return {"status": "error", "message": "Image not found"}
    
    try:
        file_path.unlink()
        
        # Update image count
        playlists_db["playlists"][playlist_id]["image_count"] = len(get_playlist_images(playlist_id))
        save_playlists_db()
        
        logger.info("Deleted image from playlist %s: %s", playlist_id, filename)
        return {"status": "success", "message": "Image deleted"}
    except Exception as e:
        logger.error("Failed to delete image: %s", e)
        return {"status": "error", "message": str(e)}


def delete_video(playlist_id, filename):
    """Delete a video from a video playlist"""
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": "Playlist not found"}
    
    playlist_dir = VIDEOS_DIR / playlist_id
    file_path = playlist_dir / filename
    
    if not file_path.exists():
        return {"status": "error", "message": "Video not found"}
    
    try:
        file_path.unlink()
        
        # Update video count
        playlists_db["playlists"][playlist_id]["video_count"] = len(get_playlist_videos(playlist_id))
        save_playlists_db()
        
        logger.info("Deleted video from playlist %s: %s", playlist_id, filename)
        return {"status": "success", "message": "Video deleted"}
    except Exception as e:
        logger.error("Failed to delete video: %s", e)
        return {"status": "error", "message": str(e)}


def get_playlist_images_list(playlist_id):
    """Get list of images with metadata for a playlist"""
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": "Playlist not found"}
    
    playlist_dir = PLAYLISTS_DIR / playlist_id
    images = []
    
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
    for file_path in sorted(playlist_dir.iterdir()):
        if file_path.suffix.lower() in image_extensions and file_path.is_file():
            stat = file_path.stat()
            images.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "type": "image"
            })
    
    return {"status": "success", "playlist_id": playlist_id, "images": images}


def get_playlist_videos_list(playlist_id):
    """Get list of videos with metadata for a video playlist"""
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": "Playlist not found"}
    
    playlist_dir = VIDEOS_DIR / playlist_id
    videos = []
    
    video_extensions = {".mp4", ".mkv", ".avi", ".webm", ".mov"}
    for file_path in sorted(playlist_dir.iterdir()):
        if file_path.suffix.lower() in video_extensions and file_path.is_file():
            stat = file_path.stat()
            duration = get_video_duration(file_path)
            videos.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "duration": duration,
                "type": "video"
            })
    
    return {"status": "success", "playlist_id": playlist_id, "videos": videos}


def parse_multipart_form_data(content_type, body, expected_field="image"):
    """Parse multipart/form-data without using deprecated cgi module"""
    try:
        # Extract boundary from content type
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part.split('=', 1)[1].strip('"')
                break
        
        if not boundary:
            return None
        
        # Split body by boundary
        boundary_bytes = ('--' + boundary).encode()
        parts = body.split(boundary_bytes)
        
        for part in parts:
            if not part or part == b'--\r\n' or part == b'--':
                continue
            
            # Split headers and content
            try:
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue
                
                headers_data = part[:header_end]
                content = part[header_end + 4:]
                
                # Remove trailing \r\n
                if content.endswith(b'\r\n'):
                    content = content[:-2]
                
                # Parse headers
                headers_str = headers_data.decode('utf-8', errors='ignore')
                filename = None
                field_name = None
                
                for line in headers_str.split('\r\n'):
                    if line.startswith('Content-Disposition:'):
                        # Extract filename and field name
                        for param in line.split(';'):
                            param = param.strip()
                            if 'filename=' in param:
                                filename = param.split('=', 1)[1].strip('"')
                            elif 'name=' in param:
                                field_name = param.split('=', 1)[1].strip('"')
                
                if field_name == expected_field and filename and content:
                    return {'filename': filename, 'data': content}
            
            except Exception as e:
                logger.error("Error parsing multipart section: %s", e)
                continue
        
        return None
    
    except Exception as e:
        logger.error("Error parsing multipart form data: %s", e)
        return None


# Video-related functions

def get_video_duration(video_path):
    """Get video duration using ffprobe (part of VLC)"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            duration = float(result.stdout.strip())
            return int(duration)
        return None
    except Exception as e:
        logger.error("Failed to get video duration: %s", e)
        return None


def is_youtube_url(url):
    """Check if URL is a valid YouTube URL"""
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com']
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in youtube_domains)
    except:
        return False


def download_youtube_video(playlist_id, video_url, download_id):
    """Download video from YouTube using yt-dlp library with progress tracking"""
    global download_status
    
    if playlist_id not in playlists_db["playlists"]:
        download_status[download_id] = {"status": "error", "message": "Playlist not found"}
        return
    
    if playlists_db["playlists"][playlist_id].get("type") != "video":
        download_status[download_id] = {"status": "error", "message": "Not a video playlist"}
        return
    
    if not is_youtube_url(video_url):
        download_status[download_id] = {"status": "error", "message": "Only YouTube URLs are supported"}
        return
    
    playlist_dir = VIDEOS_DIR / playlist_id
    
    def progress_hook(d):
        """Hook to track download progress"""
        if d['status'] == 'downloading':
            # Extract progress information
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            
            if total > 0:
                progress = (downloaded / total) * 100
                download_status[download_id]["progress"] = progress
            
            # Add speed and ETA
            speed = d.get('speed')
            eta = d.get('eta')
            
            if speed:
                speed_mb = speed / (1024 * 1024)
                download_status[download_id]["speed"] = f"{speed_mb:.2f}MiB/s"
            
            if eta:
                minutes, seconds = divmod(eta, 60)
                download_status[download_id]["eta"] = f"{int(minutes):02d}:{int(seconds):02d}"
        
        elif d['status'] == 'finished':
            download_status[download_id]["progress"] = 100
    
    try:
        download_status[download_id] = {"status": "downloading", "progress": 0, "title": ""}
        logger.info("Starting download from: %s", video_url)
        
        # Generate unique video ID for filename (no spaces)
        video_id = str(uuid.uuid4())[:12]
        
        # Use yt-dlp library to download video in 720p MP4 format
        # Download with original title first, then rename
        output_template = str(playlist_dir / "%(title)s.%(ext)s")
        
        ydl_opts = {
            'format': 'bestvideo[height<=1080][vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[height<=1080]',
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [progress_hook],
        }
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_title = info.get('title', 'Unknown')
            download_status[download_id]["title"] = video_title
        
        # Find the downloaded file (most recently created)
        videos = [f for f in playlist_dir.iterdir() if f.suffix.lower() in {'.mp4', '.mkv', '.avi', '.webm'}]
        if videos:
            video_file = max(videos, key=lambda f: f.stat().st_mtime)
            
            # Rename to custom ID (no spaces)
            new_filename = f"{video_id}.mp4"
            new_path = playlist_dir / new_filename
            video_file.rename(new_path)
            
            duration = get_video_duration(new_path)
            
            download_status[download_id] = {
                "status": "completed",
                "progress": 100,
                "filename": new_filename,
                "duration": duration,
                "title": video_title,
                "message": "Download completed"
            }
            
            # Update playlist video count
            playlist_videos = get_playlist_videos(playlist_id)
            playlists_db["playlists"][playlist_id]["video_count"] = len(playlist_videos)
            save_playlists_db()
            
            logger.info("Download completed: %s (renamed to %s)", video_title, new_filename)
        else:
            download_status[download_id] = {"status": "error", "message": "Download completed but file not found"}
    
    except Exception as e:
        error_msg = str(e)
        download_status[download_id] = {"status": "error", "message": error_msg}
        logger.error("Download error: %s", e)


def get_playlist_videos(playlist_id):
    """Get list of video files from a video playlist folder"""
    playlist_dir = VIDEOS_DIR / playlist_id
    if not playlist_dir.exists():
        return []
    
    video_extensions = {".mp4", ".mkv", ".avi", ".webm", ".mov"}
    videos = sorted([
        str(f) for f in playlist_dir.iterdir()
        if f.suffix.lower() in video_extensions and f.is_file()
    ])
    return videos


def start_video_playback(playlist_id):
    """Start video playback using VLC in loop mode"""
    global video_process, current_playlist

    stop_idle_screen()

    if video_process is not None:
        logger.info("Video already playing - start request ignored")
        return {"status": "error", "message": "Video is already playing"}
    
    videos = get_playlist_videos(playlist_id)
    if not videos:
        logger.error("No videos found in playlist: %s", playlist_id)
        return {"status": "error", "message": "No videos found in playlist"}
    
    if len(videos) > 1:
        return {"status": "error", "message": "Only one video per playlist is supported"}
    
    try:
        video_path = videos[0]
        
        # Determine which user to run VLC as
        # If running as root, run as larokiaraj user using sudo
        current_user = os.getenv('USER', os.getenv('LOGNAME', 'root'))
        
        if current_user == 'root' or os.geteuid() == 0:
            # Run as larokiaraj user using sudo
            cmd = [
                "sudo", "-u", "larokiaraj",
                "cvlc",
                "--fullscreen",
                "--avcodec-hw=mmal",
                "--network-caching=1000",
                "--loop",
                "--no-video-title-show",
                "--no-audio",
                video_path
            ]
        else:
            # Not root, run VLC normally
            cmd = [
                "cvlc",
                "--fullscreen",
                 "--avcodec-hw=mmal",
                "--network-caching=1000",
                "--loop",
                "--no-video-title-show",
                "--no-audio",
                video_path
            ]
        
        logger.info("Starting video playback: %s", Path(video_path).name)
        logger.info("VLC command: %s", ' '.join(cmd))
        
        vlc_log = BASE_DIR / "vlc_error.log"
        with open(vlc_log, "a") as f:
            f.write(f"\n=== Starting video playback at {__import__('datetime').datetime.now()} ===\n")
            f.write(f"Video: {video_path}\n")
        
        with open(vlc_log, "a") as f:
            video_process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=f,
                stderr=f
            )
        
        current_playlist = playlist_id
        playlists_db["active_playlist"] = playlist_id
        save_playlists_db()
        
        logger.info("Video playback started (PID: %d)", video_process.pid)
        return {
            "status": "started",
            "message": "Video playback started",
            "playlist": playlist_id,
            "video": Path(video_path).name
        }
    except FileNotFoundError:
        logger.error("VLC not installed")
        return {"status": "error", "message": "VLC not installed"}
    except Exception as e:
        logger.error("Failed to start video playback: %s", str(e))
        return {"status": "error", "message": str(e)}


def stop_video_playback():
    """Stop video playback and kill all VLC processes"""
    global video_process, current_playlist
    
    if video_process is None:
        logger.info("Stop requested but video not playing")
        try:
            subprocess.run(["pkill", "-9", "vlc"], capture_output=True)
            logger.info("Killed any orphaned VLC processes")
        except Exception as e:
            logger.error("Error running pkill: %s", str(e))
        
        return {"status": "not_running", "message": "Video is not playing"}
    
    try:
        logger.info("Stopping video playback (PID: %d)", video_process.pid)
        video_process.terminate()
        video_process.wait(timeout=2)
        logger.info("Video stopped successfully")
    except subprocess.TimeoutExpired:
        logger.warning("Video did not stop gracefully, killing process")
        video_process.kill()
    finally:
        video_process = None
        current_playlist = None
    
    try:
        subprocess.run(["pkill", "-9", "vlc"], capture_output=True)
        logger.info("Killed all VLC processes")
    except Exception as e:
        logger.error("Error running pkill: %s", str(e))

    start_idle_screen()
    return {"status": "stopped", "message": "Video playback stopped"}
