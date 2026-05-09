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
upload_status = {}  # Track video upload status
api_port = 8000
logger = None
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PLAYLISTS_DIR = DATA_DIR / "playlists"
VIDEOS_DIR = DATA_DIR / "videos"
IDLE_DIR = DATA_DIR / "idle"
PLAYLISTS_DB_FILE = BASE_DIR / "playlists.json"
IDLE_CONFIG_FILE = BASE_DIR / "idle_config.json"
STATIC_DIR = BASE_DIR / "frontend"

# Idle screen state
idle_process = None
idle_thread = None
idle_stop_event = threading.Event()

# Scheduler state
SCHEDULES_DB_FILE = BASE_DIR / "schedules.json"
schedules_db: list = []
scheduler_thread = None
scheduler_stop_event = threading.Event()

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

        time_size = max(int(bar_h * 0.40), 26)
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
        gap = max(int(bar_h * 0.08), 8)
        v_block = time_h_px + gap + date_size
        time_y = bar_top + (bar_h - v_block) // 2
        _draw_text(time_str, time_font, w - pad - time_w, time_y)
        _draw_text(date_str, date_font, w - pad - date_w, time_y + time_h_px + gap)

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
    subprocess.run(["pkill", "-9", "fbi"], capture_output=True)
    clear_framebuffer()
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


def get_playlist_metadata(playlist_id):
    """Get or create metadata for a playlist (tracks skipped images)"""
    metadata_file = PLAYLISTS_DIR / f"{playlist_id}_metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                return json.load(f)
        except:
            pass
    return {"skipped_images": []}


def save_playlist_metadata(playlist_id, metadata):
    """Save playlist metadata"""
    metadata_file = PLAYLISTS_DIR / f"{playlist_id}_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)


def get_playlist_images(playlist_id):
    """Get list of image files from a playlist folder (excluding skipped images)"""
    playlist_dir = PLAYLISTS_DIR / playlist_id
    if not playlist_dir.exists():
        return []
    
    # Get metadata to check skipped images
    metadata = get_playlist_metadata(playlist_id)
    skipped_images = set(metadata.get("skipped_images", []))
    
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
    images = sorted([
        str(f) for f in playlist_dir.iterdir()
        if f.suffix.lower() in image_extensions and f.is_file() and f.name not in skipped_images
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
        # Get delay from playlist, fallback to config default
        delay = playlists_db["playlists"][playlist_id].get("delay", config.get("delay", 5))
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
    delay = config.get("delay", 5)  # Default delay
    
    if active_playlist_id and active_playlist_id in playlists_db["playlists"]:
        image_count = len(get_playlist_images(active_playlist_id))
        delay = playlists_db["playlists"][active_playlist_id].get("delay", 5)
    
    return {
        "running": slideshow_process is not None or video_process is not None,
        "current_playlist": current_playlist,
        "active_playlist": active_playlist_id,
        "image_count": image_count,
        "delay": delay,
        "framebuffer": config.get("framebuffer"),
        "total_playlists": len(playlists_db.get("playlists", {}))
    }


def create_playlist(name, playlist_type="image", delay=5):
    """Create a new playlist"""
    playlist_id = str(uuid.uuid4())[:8]
    
    # Determine base directory based on type
    if playlist_type == "video":
        base_dir = VIDEOS_DIR
    else:
        base_dir = PLAYLISTS_DIR
    
    playlist_dir = base_dir / playlist_id
    playlist_dir.mkdir(exist_ok=True, mode=0o755)
    
    playlists_db["playlists"][playlist_id] = {
        "name": name,
        "id": playlist_id,
        "type": playlist_type,
        "created": __import__('datetime').datetime.now().isoformat(),
        "image_count": 0,
        "video_count": 0 if playlist_type == "video" else None,
        "delay": delay
    }
    save_playlists_db()
    
    logger.info("Created %s playlist: %s (ID: %s) with delay: %ds", playlist_type, name, playlist_id, delay)
    return {"status": "success", "playlist_id": playlist_id, "message": "Playlist created"}


def update_playlist(playlist_id, name=None, delay=None):
    """Update playlist settings"""
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": "Playlist not found"}
    
    playlist = playlists_db["playlists"][playlist_id]
    
    if name is not None:
        playlist["name"] = name
    
    if delay is not None:
        playlist["delay"] = delay
    
    save_playlists_db()
    
    logger.info("Updated playlist %s: name=%s, delay=%s", playlist_id, name, delay)
    return {"status": "success", "message": "Playlist updated", "playlist": playlist}


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
            "delay": info.get("delay", 5),
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



def skip_image(playlist_id, filename):
    """Mark an image as skipped in the playlist"""
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": "Playlist not found"}
    
    playlist_dir = PLAYLISTS_DIR / playlist_id
    image_path = playlist_dir / filename
    
    if not image_path.exists():
        return {"status": "error", "message": "Image not found"}
    
    metadata = get_playlist_metadata(playlist_id)
    skipped_images = metadata.get("skipped_images", [])
    
    if filename not in skipped_images:
        skipped_images.append(filename)
        metadata["skipped_images"] = skipped_images
        save_playlist_metadata(playlist_id, metadata)
        logger.info("Image skipped: %s in playlist %s", filename, playlist_id)
    
    return {"status": "success", "message": "Image skipped"}


def unskip_image(playlist_id, filename):
    """Unmark an image as skipped in the playlist"""
    if playlist_id not in playlists_db["playlists"]:
        return {"status": "error", "message": "Playlist not found"}
    
    metadata = get_playlist_metadata(playlist_id)
    skipped_images = metadata.get("skipped_images", [])
    
    if filename in skipped_images:
        skipped_images.remove(filename)
        metadata["skipped_images"] = skipped_images
        save_playlist_metadata(playlist_id, metadata)
        logger.info("Image unskipped: %s in playlist %s", filename, playlist_id)
    
    return {"status": "success", "message": "Image unskipped"}


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
    
    # Get metadata to check skipped images
    metadata = get_playlist_metadata(playlist_id)
    skipped_images = set(metadata.get("skipped_images", []))
    
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
    for file_path in sorted(playlist_dir.iterdir()):
        if file_path.suffix.lower() in image_extensions and file_path.is_file():
            stat = file_path.stat()
            images.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "type": "image",
                "skipped": file_path.name in skipped_images
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


def parse_multipart_form_data_streaming(content_type, file_obj, content_length, output_path, upload_id=None):
    """Parse multipart/form-data by streaming to disk to avoid RAM exhaustion"""
    global upload_status
    
    logger.info("[UPLOAD] Starting streaming upload - content_length: %d bytes (%.2f MB), upload_id: %s", 
                content_length, content_length / (1024 * 1024), upload_id)
    
    try:
        # Initialize upload status
        if upload_id:
            upload_status[upload_id] = {
                "status": "uploading",
                "progress": 0,
                "bytes_written": 0,
                "total_bytes": content_length
            }
        
        # Extract boundary from content type
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part.split('=', 1)[1].strip('"')
                break
        
        if not boundary:
            logger.error("[UPLOAD] No boundary found in Content-Type: %s", content_type)
            if upload_id:
                upload_status[upload_id] = {"status": "error", "message": "Invalid boundary"}
            return None
        
        logger.info("[UPLOAD] Boundary extracted: %s", boundary[:50])
        
        boundary_bytes = ('--' + boundary).encode()
        boundary_len = len(boundary_bytes)
        
        # Buffer for reading chunks
        chunk_size = 8192  # 8KB chunks
        buffer = b''
        filename = None
        in_file_content = False
        out_file = None
        bytes_written = 0
        bytes_read = 0  # Track total bytes consumed from stream
        last_progress_update = 0
        
        logger.info("[UPLOAD] Starting read loop - chunk_size: %d bytes", chunk_size)
        
        try:
            while bytes_read < content_length:
                # Read remaining bytes, capped at chunk size
                to_read = min(chunk_size, content_length - bytes_read)
                chunk = file_obj.read(to_read)
                if not chunk:
                    logger.warning("[UPLOAD] Read returned empty chunk - bytes_read: %d / %d", 
                                  bytes_read, content_length)
                    break
                
                bytes_read += len(chunk)
                buffer += chunk
                
                # Log progress every 10MB
                if bytes_read % (10 * 1024 * 1024) < chunk_size:
                    logger.debug("[UPLOAD] Read progress: %d / %d bytes (%.1f%%)", 
                                bytes_read, content_length, (bytes_read / content_length * 100))
                
                # Look for headers if not yet in file content
                if not in_file_content:
                    header_end = buffer.find(b'\r\n\r\n')
                    if header_end != -1:
                        headers_data = buffer[:header_end]
                        headers_str = headers_data.decode('utf-8', errors='ignore')
                        
                        logger.debug("[UPLOAD] Found headers at position %d: %s", header_end, headers_str[:200])
                        
                        # Extract filename
                        for line in headers_str.split('\r\n'):
                            if 'Content-Disposition:' in line:
                                for param in line.split(';'):
                                    param = param.strip()
                                    if 'filename=' in param:
                                        filename = param.split('=', 1)[1].strip('"')
                                        break
                        
                        if filename:
                            # Start writing file content
                            logger.info("[UPLOAD] Headers parsed - filename: %s, starting file write to: %s", 
                                       filename, output_path)
                            buffer = buffer[header_end + 4:]
                            out_file = open(output_path, 'wb')
                            in_file_content = True
                        else:
                            logger.warning("[UPLOAD] No filename found in headers: %s", headers_str)
                
                # Write file content, checking for boundary
                if in_file_content and out_file:
                    # Check if we have a boundary in buffer
                    boundary_pos = buffer.find(boundary_bytes)
                    if boundary_pos != -1:
                        # Write everything before boundary (minus \r\n)
                        end_pos = boundary_pos - 2 if boundary_pos >= 2 else boundary_pos
                        if end_pos > 0:
                            out_file.write(buffer[:end_pos])
                            bytes_written += end_pos
                        
                        logger.info("[UPLOAD] Boundary detected at position %d - file complete: %d bytes written (%.2f MB)", 
                                   boundary_pos, bytes_written, bytes_written / (1024 * 1024))
                        
                        # Update final progress
                        if upload_id and content_length > 0:
                            upload_status[upload_id].update({
                                "progress": 100,
                                "bytes_written": bytes_written,
                                "status": "complete"
                            })
                        
                        # Clear buffer and continue reading to consume entire request
                        logger.info("[UPLOAD] Continuing to consume remaining stream data...")
                        buffer = b''
                        continue
                    else:
                        # Keep last chunk in buffer in case boundary is split
                        if len(buffer) > boundary_len + 10:
                            write_size = len(buffer) - (boundary_len + 10)
                            out_file.write(buffer[:write_size])
                            bytes_written += write_size
                            buffer = buffer[write_size:]
                            
                            # Update progress every 1%
                            if upload_id and content_length > 0:
                                progress = min(99, int((bytes_written / content_length) * 100))
                                if progress > last_progress_update:
                                    upload_status[upload_id].update({
                                        "progress": progress,
                                        "bytes_written": bytes_written,
                                        "status": "uploading"
                                    })
                                    logger.info("[UPLOAD] Progress: %d%% (%d MB / %d MB)", 
                                               progress, 
                                               bytes_written // (1024 * 1024), 
                                               content_length // (1024 * 1024))
                                    last_progress_update = progress
            
            # Log when loop exits
            logger.info("[UPLOAD] Read loop complete - bytes_read: %d / %d, in_file_content: %s, filename: %s", 
                       bytes_read, content_length, in_file_content, filename)
        
        finally:
            logger.info("[UPLOAD] Closing file - total bytes_read: %d, bytes_written: %d", 
                       bytes_read, bytes_written)
            if out_file:
                out_file.close()
        
        if filename and bytes_written > 0:
            # Mark as complete
            logger.info("[UPLOAD] Upload SUCCESS - filename: %s, size: %d bytes (%.2f MB)", 
                       filename, bytes_written, bytes_written / (1024 * 1024))
            if upload_id:
                upload_status[upload_id] = {
                    "status": "complete",
                    "progress": 100,
                    "bytes_written": bytes_written,
                    "filename": filename
                }
            return {'filename': filename, 'path': str(output_path), 'size': bytes_written}
        
        # Clean up if failed
        logger.warning("[UPLOAD] Upload FAILED - filename: %s, bytes_written: %d", filename, bytes_written)
        if output_path.exists():
            output_path.unlink()
        
        if upload_id:
            upload_status[upload_id] = {"status": "error", "message": "Upload failed"}
        
        return None
    
    except Exception as e:
        logger.error("[UPLOAD] EXCEPTION in streaming parser: %s", e, exc_info=True)
        if output_path and output_path.exists():
            output_path.unlink()
        if upload_id:
            upload_status[upload_id] = {"status": "error", "message": str(e)}
        return None


def parse_multipart_form_data(content_type, body, expected_field="image"):
    """Parse multipart/form-data without using deprecated cgi module (for small files)"""
    logger.info("[PARSE-SMALL] Starting in-memory parser - body size: %d bytes, expected_field: %s", 
               len(body), expected_field)
    
    try:
        # Extract boundary from content type
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part.split('=', 1)[1].strip('"')
                break
        
        if not boundary:
            logger.error("[PARSE-SMALL] No boundary found in Content-Type")
            return None
        
        logger.info("[PARSE-SMALL] Boundary extracted: %s", boundary[:50])
        
        # Split body by boundary
        boundary_bytes = ('--' + boundary).encode()
        parts = body.split(boundary_bytes)
        logger.info("[PARSE-SMALL] Split into %d parts", len(parts))
        
        for part in parts:
            if not part or part == b'--\r\n' or part == b'--':
                continue
            
            logger.debug("[PARSE-SMALL] Processing part of size: %d bytes", len(part))
            
            # Split headers and content
            try:
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    logger.debug("[PARSE-SMALL] No header separator found, skipping part")
                    continue
                
                headers_data = part[:header_end]
                content = part[header_end + 4:]
                
                # Remove trailing \r\n
                if content.endswith(b'\r\n'):
                    content = content[:-2]
                
                logger.debug("[PARSE-SMALL] Content size after trimming: %d bytes", len(content))
                
                # Parse headers
                headers_str = headers_data.decode('utf-8', errors='ignore')
                filename = None
                field_name = None
                
                logger.debug("[PARSE-SMALL] Headers: %s", headers_str[:200])
                
                for line in headers_str.split('\r\n'):
                    if line.startswith('Content-Disposition:'):
                        # Extract filename and field name
                        for param in line.split(';'):
                            param = param.strip()
                            if 'filename=' in param:
                                filename = param.split('=', 1)[1].strip('"')
                            elif 'name=' in param:
                                field_name = param.split('=', 1)[1].strip('"')
                
                logger.info("[PARSE-SMALL] Parsed - field_name: %s, filename: %s, content_len: %d, expected: %s", 
                           field_name, filename, len(content) if content else 0, expected_field)
                
                if field_name == expected_field and filename and content:
                    logger.info("[PARSE-SMALL] SUCCESS - returning file: %s (%d bytes)", filename, len(content))
                    return {'filename': filename, 'data': content}
            
            except Exception as e:
                logger.error("[PARSE-SMALL] Error parsing multipart section: %s", e)
                continue
        
        logger.warning("[PARSE-SMALL] No matching file found after processing all parts")
        return None
    
    except Exception as e:
        logger.error("[PARSE-SMALL] EXCEPTION in parser: %s", e, exc_info=True)
        return None
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


def downscale_video_to_1080p(video_path):
    """Downscale video to 1080p using ffmpeg if resolution is higher"""
    try:
        # Check current resolution using ffprobe
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            str(video_path)
        ]
        
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            logger.warning("[DOWNSCALE] Could not probe video resolution: %s", result.stderr)
            return True  # Skip downscaling but don't fail
        
        # Parse width,height
        resolution = result.stdout.strip().split(',')
        if len(resolution) != 2:
            logger.warning("[DOWNSCALE] Invalid resolution format: %s", result.stdout)
            return True
        
        width, height = int(resolution[0]), int(resolution[1])
        logger.info("[DOWNSCALE] Video resolution: %dx%d", width, height)
        
        # Only downscale if height > 1080 or width > 1920
        if height <= 1080 and width <= 1920:
            logger.info("[DOWNSCALE] Video already at or below 1080p, skipping")
            return True
        
        logger.info("[DOWNSCALE] Downscaling video from %dx%d to 1080p...", width, height)
        
        # Create temp output file
        temp_output = video_path.parent / f".downscaling_{video_path.name}"
        
        # Downscale using ffmpeg with hardware acceleration if available
        ffmpeg_cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vf', 'scale=-2:1080',  # Maintain aspect ratio, height=1080
            '-c:v', 'libx264',  # H.264 codec
            '-preset', 'fast',  # Fast encoding
            '-crf', '23',  # Quality (lower = better, 23 is default)
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-y',  # Overwrite output
            str(temp_output)
        ]
        
        logger.info("[DOWNSCALE] Running: %s", ' '.join(ffmpeg_cmd))
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            logger.error("[DOWNSCALE] ffmpeg failed: %s", result.stderr)
            if temp_output.exists():
                temp_output.unlink()
            return False
        
        # Replace original with downscaled version
        temp_output.replace(video_path)
        logger.info("[DOWNSCALE] Successfully downscaled video to 1080p")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("[DOWNSCALE] Downscaling timed out")
        if temp_output.exists():
            temp_output.unlink()
        return False
    except Exception as e:
        logger.error("[DOWNSCALE] Downscaling failed: %s", str(e))
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
            
            # Downscale to 1080p if needed
            logger.info("[DOWNLOAD] Checking if downscaling needed...")
            downscale_success = downscale_video_to_1080p(new_path)
            if not downscale_success:
                logger.warning("[DOWNLOAD] Downscaling failed, keeping original video")
            
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
                "--vout-filter=croppadd",
                "--croppadd-croptop=0",
                "--croppadd-cropbottom=0",
                "--croppadd-cropleft=0",
                "--croppadd-cropright=0",
                "--width=1920",
                "--height=1080",
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
                "--vout-filter=croppadd",
                "--croppadd-croptop=0",
                "--croppadd-cropbottom=0",
                "--croppadd-cropleft=0",
                "--croppadd-cropright=0",
                "--width=1920",
                "--height=1080",
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


# ── Scheduler ─────────────────────────────────────────────────────────────────

def _cron_field_match(field, value, min_val):
    """Match one 5-field cron token: *, */n, n-m, comma list, or literal."""
    if field == "*":
        return True
    for part in field.split(","):
        if part.startswith("*/"):
            step = int(part[2:])
            if (value - min_val) % step == 0:
                return True
        elif "-" in part:
            lo, hi = map(int, part.split("-", 1))
            if lo <= value <= hi:
                return True
        elif int(part) == value:
            return True
    return False


def _cron_matches(cron, dt):
    """Return True if 5-field cron expression matches the given datetime."""
    parts = cron.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts
    # datetime.weekday(): Mon=0..Sun=6  →  cron dow: Sun=0..Sat=6
    cron_dow = (dt.weekday() + 1) % 7
    return (
        _cron_field_match(minute, dt.minute, 0)
        and _cron_field_match(hour, dt.hour, 0)
        and _cron_field_match(dom, dt.day, 1)
        and _cron_field_match(month, dt.month, 1)
        and _cron_field_match(dow, cron_dow, 0)
    )


def load_schedules_db():
    global schedules_db
    try:
        if SCHEDULES_DB_FILE.exists():
            with open(SCHEDULES_DB_FILE) as f:
                schedules_db = json.load(f)
        else:
            schedules_db = []
        logger.info("Schedules database loaded (%d schedules)", len(schedules_db))
    except Exception as e:
        logger.error("Failed to load schedules database: %s", e)
        schedules_db = []


def save_schedules_db():
    try:
        with open(SCHEDULES_DB_FILE, "w") as f:
            json.dump(schedules_db, f, indent=2)
    except Exception as e:
        logger.error("Failed to save schedules database: %s", e)


def list_schedules():
    return schedules_db


def get_schedule(schedule_id):
    return next((s for s in schedules_db if s["id"] == schedule_id), None)


def create_schedule(name, playlist_id, cron, enabled=True):
    schedule = {
        "id": str(uuid.uuid4()),
        "name": name,
        "playlist_id": playlist_id,
        "cron": cron,
        "enabled": enabled,
    }
    schedules_db.append(schedule)
    save_schedules_db()
    logger.info("Schedule created: %s (%s)", name, cron)
    return schedule


def update_schedule(schedule_id, data):
    schedule = get_schedule(schedule_id)
    if not schedule:
        return None
    for key in ("name", "playlist_id", "cron", "enabled"):
        if key in data:
            schedule[key] = data[key]
    save_schedules_db()
    return schedule


def delete_schedule(schedule_id):
    global schedules_db
    before = len(schedules_db)
    schedules_db = [s for s in schedules_db if s["id"] != schedule_id]
    if len(schedules_db) < before:
        save_schedules_db()
        return True
    return False


def _scheduler_fire_playlist(playlist_id):
    """Stop whatever is playing and start the scheduled playlist."""
    stop_slideshow()
    stop_video_playback()
    playlist = playlists_db.get("playlists", {}).get(playlist_id)
    if not playlist:
        logger.warning("Scheduler: playlist %s not found", playlist_id)
        return
    if playlist.get("type") == "video":
        start_video_playback(playlist_id)
    else:
        start_slideshow(playlist_id)


def _run_scheduler_loop():
    logger.info("Scheduler loop started")
    while not scheduler_stop_event.is_set():
        # Reuse the minute-boundary sleep but driven by the scheduler stop event
        now = datetime.now()
        seconds_left = 60 - now.second - now.microsecond / 1_000_000
        deadline = time.monotonic() + seconds_left
        interrupted = False
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if scheduler_stop_event.wait(timeout=min(remaining, 1.0)):
                interrupted = True
                break
        if interrupted or scheduler_stop_event.is_set():
            break

        now = datetime.now()
        for schedule in list(schedules_db):
            if not schedule.get("enabled"):
                continue
            try:
                if _cron_matches(schedule["cron"], now):
                    logger.info("Scheduler firing: %s", schedule["name"])
                    _scheduler_fire_playlist(schedule["playlist_id"])
                    break  # at most one schedule fires per minute
            except Exception as e:
                logger.error("Scheduler error for '%s': %s", schedule.get("name"), e)

    logger.info("Scheduler loop stopped")


def start_scheduler():
    global scheduler_thread, scheduler_stop_event
    scheduler_stop_event.clear()
    scheduler_thread = threading.Thread(
        target=_run_scheduler_loop, daemon=True, name="scheduler"
    )
    scheduler_thread.start()
    logger.info("Scheduler started")


def stop_scheduler():
    global scheduler_thread
    scheduler_stop_event.set()
    if scheduler_thread and scheduler_thread.is_alive():
        scheduler_thread.join(timeout=5)
    scheduler_thread = None
    logger.info("Scheduler stopped")
