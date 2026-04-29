#!/usr/bin/env python3
"""
Pi Display Manager - REST API for managing image slideshows with playlist support.
Runs as a background service on Raspberry Pi.
"""

import os
import json
import subprocess
import signal
import sys
import logging
import shutil
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Global state
slideshow_process = None
video_process = None
config = {}
playlists_db = {}
current_playlist = None
download_status = {}  # Track video download status
api_port = 8000
logger = None
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PLAYLISTS_DIR = DATA_DIR / "playlists"
VIDEOS_DIR = DATA_DIR / "videos"
UPLOADS_DIR = DATA_DIR / "uploads"
PLAYLISTS_DB_FILE = BASE_DIR / "playlists.json"
STATIC_DIR = BASE_DIR / "static"


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
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create default playlist if it doesn't exist
    default_playlist_dir = PLAYLISTS_DIR / "default"
    default_playlist_dir.mkdir(exist_ok=True)
    
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
                "playlists": {
                    "default": {
                        "name": "Default Playlist",
                        "id": "default",
                        "created": "2024-01-01T00:00:00",
                        "image_count": 0
                    }
                },
                "active_playlist": None
            }
            save_playlists_db()
        logger.info("Playlists database loaded")
    except Exception as e:
        logger.error("Failed to load playlists database: %s", e)
        playlists_db = {"playlists": {}, "active_playlist": None}


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

    if slideshow_process is not None:
        logger.info("Slideshow already running - start request ignored")
        return {"status": "error", "message": "Slideshow is already running"}

    # Use provided playlist or active playlist from db
    if playlist_id is None:
        playlist_id = playlists_db.get("active_playlist")
    
    if playlist_id is None:
        playlist_id = "default"
    
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

    return {"status": "stopped", "message": "Slideshow stopped"}


def get_status():
    """Get current slideshow status"""
    active_playlist_id = playlists_db.get("active_playlist")
    image_count = 0
    if active_playlist_id:
        image_count = len(get_playlist_images(active_playlist_id))
    
    return {
        "running": slideshow_process is not None,
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
    if playlist_id == "default":
        return {"status": "error", "message": "Cannot delete default playlist"}
    
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


def parse_multipart_form_data(content_type, body):
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
                
                if field_name == 'image' and filename and content:
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
    """Download video from YouTube using yt-dlp with progress tracking"""
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
    
    try:
        download_status[download_id] = {"status": "downloading", "progress": 0, "title": ""}
        logger.info("Starting download from: %s", video_url)
        
        # Use yt-dlp to download video in 720p MP4 format with progress
        output_template = str(playlist_dir / "%(title)s.%(ext)s")
        
        # Start the download process with real-time output
        process = subprocess.Popen(
            [
                "yt-dlp",
                "-f", "best[height<=720][ext=mp4]/best[height<=720]/best",
                "--merge-output-format", "mp4",
                "--newline",  # Force newline for each progress line
                "--no-colors",  # Remove color codes
                "-o", output_template,
                video_url
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Read output line by line and parse progress
        import re
        video_title = "Video"
        
        for line in process.stdout:
            line = line.strip()
            
            # Extract video title
            if "[download] Destination:" in line:
                try:
                    # Extract filename from path
                    match = re.search(r'Destination: (.+?)\.(mp4|mkv|webm)', line)
                    if match:
                        path = Path(match.group(1))
                        video_title = path.name
                        download_status[download_id]["title"] = video_title
                except:
                    pass
            
            # Parse download progress: [download]  45.2% of 123.45MiB at 1.23MiB/s ETA 00:34
            if "[download]" in line and "%" in line:
                try:
                    # Extract percentage
                    match = re.search(r'(\d+\.?\d*)%', line)
                    if match:
                        progress = float(match.group(1))
                        download_status[download_id]["progress"] = progress
                        
                        # Extract speed and ETA if available
                        speed_match = re.search(r'at\s+([\d.]+\w+/s)', line)
                        eta_match = re.search(r'ETA\s+(\d+:\d+)', line)
                        
                        if speed_match:
                            download_status[download_id]["speed"] = speed_match.group(1)
                        if eta_match:
                            download_status[download_id]["eta"] = eta_match.group(1)
                except Exception as e:
                    logger.warning("Error parsing progress: %s", e)
        
        # Wait for process to complete
        return_code = process.wait(timeout=600)
        result = type('obj', (object,), {'returncode': return_code, 'stderr': ''})
        
        if result.returncode == 0:
            # Find the downloaded file
            videos = [f for f in playlist_dir.iterdir() if f.suffix.lower() in {'.mp4', '.mkv', '.avi', '.webm'}]
            if videos:
                video_file = max(videos, key=lambda f: f.stat().st_mtime)
                duration = get_video_duration(video_file)
                
                download_status[download_id] = {
                    "status": "completed",
                    "progress": 100,
                    "filename": video_file.name,
                    "duration": duration,
                    "message": "Download completed"
                }
                
                # Update playlist video count
                playlist_videos = get_playlist_videos(playlist_id)
                playlists_db["playlists"][playlist_id]["video_count"] = len(playlist_videos)
                save_playlists_db()
                
                logger.info("Download completed: %s", video_file.name)
            else:
                download_status[download_id] = {"status": "error", "message": "Download completed but file not found"}
        else:
            download_status[download_id] = {"status": "error", "message": "Download failed"}
            logger.error("Download failed with code: %s", result.returncode)
    
    except subprocess.TimeoutExpired:
        download_status[download_id] = {"status": "error", "message": "Download timed out"}
        logger.error("Download timed out")
        try:
            process.kill()
        except:
            pass
    except Exception as e:
        download_status[download_id] = {"status": "error", "message": str(e)}
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
        
        # VLC command for fullscreen looped playback on framebuffer
        cmd = [
            "cvlc",  # Console VLC
            "--fullscreen",
            "--loop",
            "--no-video-title-show",
            "--no-audio",  # Disable audio for Pi display
            video_path
        ]
        
        logger.info("Starting video playback: %s", Path(video_path).name)
        
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
    
    return {"status": "stopped", "message": "Video playback stopped"}


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the REST API"""

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        response = None
        status = 200
        content_type = "application/json"

        logger.info("GET %s from %s", path, self.client_address[0])

        # Serve static files
        if path == "/" or path == "/index.html":
            self.serve_static_file("index.html")
            return
        elif path.startswith("/static/"):
            self.serve_static_file(path[8:])  # Remove "/static/" prefix
            return

        # API endpoints
        if path == "/api/status":
            response = get_status()
        elif path == "/api/playlists":
            response = {"status": "success", "playlists": list_playlists()}
        elif path.startswith("/api/playlists/") and "/images" in path:
            # Get images for a playlist
            playlist_id = path.split("/")[3]
            response = get_playlist_images_list(playlist_id)
        elif path.startswith("/api/playlists/") and "/videos" in path:
            # Get videos for a playlist
            playlist_id = path.split("/")[3]
            response = get_playlist_videos_list(playlist_id)
        elif path.startswith("/api/download/"):
            # Get download status
            download_id = path.split("/")[2]
            if download_id in download_status:
                response = download_status[download_id]
            else:
                response = {"status": "not_found", "message": "Download not found"}
        elif path == "/api/start":
            playlist_id = query.get("playlist", [None])[0]
            if playlist_id and playlist_id in playlists_db["playlists"]:
                plist_type = playlists_db["playlists"][playlist_id].get("type", "image")
                if plist_type == "video":
                    response = start_video_playback(playlist_id)
                else:
                    response = start_slideshow(playlist_id)
            else:
                response = start_slideshow(playlist_id)
        elif path == "/api/stop":
            # Stop both image and video playback
            if video_process is not None:
                response = stop_video_playback()
            else:
                response = stop_slideshow()
        elif path == "/api/clear":
            clear_framebuffer()
            response = {"status": "success", "message": "Framebuffer cleared"}
        elif path == "/api/health":
            response = {"status": "ok"}
        else:
            response = {
                "status": "error",
                "message": "Unknown endpoint",
                "available_endpoints": [
                    "/api/status", "/api/playlists", "/api/start", "/api/stop", 
                    "/api/clear", "/api/health", "/api/download/{id}"
                ]
            }
            status = 404

        self.send_json_response(response, status)

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        response = None
        status = 200

        logger.info("POST %s from %s", path, self.client_address[0])

        try:
            if path == "/api/playlists/create":
                # Create new playlist
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                name = data.get("name", "Untitled Playlist")
                playlist_type = data.get("type", "image")  # "image" or "video"
                response = create_playlist(name, playlist_type)
            
            elif path.startswith("/api/playlists/") and "/upload" in path:
                # Upload image to playlist
                playlist_id = path.split("/")[3]
                content_type = self.headers.get('Content-Type', '')
                
                if 'multipart/form-data' in content_type:
                    # Read the entire body
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length)
                    
                    # Parse multipart data
                    file_info = parse_multipart_form_data(content_type, body)
                    
                    if file_info and file_info.get('filename') and file_info.get('data'):
                        response = upload_image(
                            playlist_id,
                            file_info['data'],
                            file_info['filename']
                        )
                    else:
                        response = {"status": "error", "message": "No valid file uploaded"}
                else:
                    response = {"status": "error", "message": "Content must be multipart/form-data"}
            
            elif path.startswith("/api/playlists/") and "/download" in path:
                # Download video from YouTube
                playlist_id = path.split("/")[3]
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                video_url = data.get("url", "")
                
                if not video_url:
                    response = {"status": "error", "message": "No URL provided"}
                else:
                    # Start download in background thread
                    import threading
                    download_id = str(uuid.uuid4())[:8]
                    thread = threading.Thread(
                        target=download_youtube_video,
                        args=(playlist_id, video_url, download_id)
                    )
                    thread.daemon = True
                    thread.start()
                    response = {
                        "status": "started",
                        "download_id": download_id,
                        "message": "Download started"
                    }
            
            else:
                response = {"status": "error", "message": "Unknown POST endpoint"}
                status = 404

        except Exception as e:
            logger.error("POST request error: %s", str(e))
            response = {"status": "error", "message": str(e)}
            status = 500

        self.send_json_response(response, status)

    def do_DELETE(self):
        """Handle DELETE requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        response = None
        status = 200

        logger.info("DELETE %s from %s", path, self.client_address[0])

        try:
            if path.startswith("/api/playlists/") and "/images/" in path:
                # Delete image from playlist
                parts = path.split("/")
                playlist_id = parts[3]
                filename = parts[5]
                response = delete_image(playlist_id, filename)
            
            elif path.startswith("/api/playlists/") and "/videos/" in path:
                # Delete video from playlist
                parts = path.split("/")
                playlist_id = parts[3]
                filename = parts[5]
                response = delete_video(playlist_id, filename)
            
            elif path.startswith("/api/playlists/"):
                # Delete playlist
                playlist_id = path.split("/")[3]
                response = delete_playlist(playlist_id)
            
            else:
                response = {"status": "error", "message": "Unknown DELETE endpoint"}
                status = 404

        except Exception as e:
            logger.error("DELETE request error: %s", str(e))
            response = {"status": "error", "message": str(e)}
            status = 500

        self.send_json_response(response, status)

    def serve_static_file(self, filename):
        """Serve a static file"""
        file_path = STATIC_DIR / filename
        
        if not file_path.exists():
            self.send_error(404, "File not found")
            return
        
        # Determine content type
        content_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif'
        }
        
        ext = file_path.suffix.lower()
        content_type = content_types.get(ext, 'text/plain')
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.error("Error serving static file: %s", e)
            self.send_error(500, "Internal server error")

    def send_json_response(self, response, status=200):
        """Send a JSON response"""
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Received signal %d, shutting down...", sig)
    stop_slideshow()
    logger.info("Pi Display Manager API service stopped")
    sys.exit(0)


def run_server():
    """Start the HTTP server"""
    global api_port

    api_port = config.get("api_port", 8000)
    delay = config.get("delay", 5)

    logger.info("=== Pi Display Manager API Service Started ===")
    logger.info("Configuration:")
    logger.info("  API Port: %d", api_port)
    logger.info("  Slide Delay: %d seconds", delay)
    logger.info("  Data Directory: %s", DATA_DIR)
    logger.info("  Playlists Directory: %s", PLAYLISTS_DIR)

    server = HTTPServer(("0.0.0.0", api_port), APIHandler)
    logger.info("HTTP server listening on 0.0.0.0:%d", api_port)
    logger.info("Web interface: http://localhost:%d", api_port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        setup_logging()
        ensure_directories()
        load_config()
        load_playlists_db()
        run_server()
    except Exception as e:
        if logger:
            logger.error("Fatal error: %s", str(e))
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
