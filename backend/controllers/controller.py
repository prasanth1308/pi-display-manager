"""
Pi Display Manager - Flask Controller
Lightweight REST API with Flask framework.
"""

from flask import Flask, request, jsonify, send_file, redirect, make_response
from functools import wraps
from pathlib import Path
import uuid
import threading

# Import authentication
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).parent.parent))

from services.auth import authenticate_user, validate_session, destroy_session

# Import service layer module
import services.service as service

# Import service functions directly
from services.service import (
    # Core functions
    setup_logging, ensure_directories, load_config, load_playlists_db,
    
    # Service functions
    get_status, start_slideshow, stop_slideshow, clear_framebuffer,
    list_playlists, create_playlist, update_playlist, delete_playlist,
    get_playlist_images_list, get_playlist_videos_list,
    upload_image, delete_image, delete_video,
    skip_image, unskip_image,
    parse_multipart_form_data, parse_multipart_form_data_streaming,
    download_youtube_video, downscale_video_to_1080p,
    start_video_playback, stop_video_playback, get_playlist_videos, save_playlists_db,
    
    # Idle screen
    get_idle_config, save_idle_config, start_idle_screen, stop_idle_screen,
    
    # Scheduler
    load_schedules_db, list_schedules, get_schedule, create_schedule,
    update_schedule, delete_schedule, stop_scheduler, start_scheduler,
)

# ═══════════════════════════════════════════════════════════════════════════
# Initialize Flask App
# ═══════════════════════════════════════════════════════════════════════════

# Flask app will be configured after initialization
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024  # 5GB max upload

# ═══════════════════════════════════════════════════════════════════════════
# Authentication Decorator
# ═══════════════════════════════════════════════════════════════════════════

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = request.cookies.get('session_token')
        
        if not session_token:
            return jsonify({
                "status": "error",
                "message": "Unauthorized. Please login."
            }), 401
        
        user_info = validate_session(session_token)
        if not user_info:
            return jsonify({
                "status": "error",
                "message": "Invalid or expired session. Please login."
            }), 401
        
        # Pass user_info to the route function
        return f(user_info=user_info, *args, **kwargs)
    
    return decorated_function

# ═══════════════════════════════════════════════════════════════════════════
# Authentication Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    session_token = request.cookies.get('session_token')
    if session_token:
        user_info = validate_session(session_token)
        if user_info:
            return jsonify({"authenticated": True, "user": user_info})
    return jsonify({"authenticated": False})

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({
            "status": "error",
            "message": "Username and password required"
        }), 400
    
    success, result = authenticate_user(username, password)
    
    if success:
        response = make_response(jsonify({
            "status": "success",
            "message": "Login successful",
            "user": {"username": username}
        }))
        response.set_cookie(
            'session_token',
            result,
            httponly=True,
            samesite='Strict',
            max_age=3600
        )
        return response
    else:
        return jsonify({
            "status": "error",
            "message": result
        }), 401

@app.route('/api/auth/logout', methods=['GET'])
def logout():
    """User logout"""
    session_token = request.cookies.get('session_token')
    if session_token:
        destroy_session(session_token)
    
    response = make_response(jsonify({
        "status": "success",
        "message": "Logged out successfully"
    }))
    response.set_cookie('session_token', '', expires=0)
    return response

# ═══════════════════════════════════════════════════════════════════════════
# Playlist Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/playlists', methods=['GET'])
@require_auth
def get_playlists(user_info):
    """List all playlists"""
    return jsonify({"status": "success", "playlists": list_playlists()})

@app.route('/api/playlists/create', methods=['POST'])
@require_auth
def create_new_playlist(user_info):
    """Create a new playlist"""
    data = request.get_json()
    name = data.get('name')
    ptype = data.get('type', 'image')
    delay = data.get('delay', 5)
    
    return jsonify(create_playlist(name, ptype, delay))

@app.route('/api/playlists/<playlist_id>', methods=['PUT'])
@require_auth
def update_existing_playlist(user_info, playlist_id):
    """Update playlist settings"""
    data = request.get_json()
    name = data.get('name')
    delay = data.get('delay')
    
    return jsonify(update_playlist(playlist_id, name, delay))

@app.route('/api/playlists/<playlist_id>', methods=['DELETE'])
@require_auth
def delete_existing_playlist(user_info, playlist_id):
    """Delete a playlist"""
    return jsonify(delete_playlist(playlist_id))

@app.route('/api/playlists/<playlist_id>/images', methods=['GET'])
@require_auth
def get_images(user_info, playlist_id):
    """Get images in a playlist"""
    return jsonify(get_playlist_images_list(playlist_id))

@app.route('/api/playlists/<playlist_id>/videos', methods=['GET'])
@require_auth
def get_videos(user_info, playlist_id):
    """Get videos in a playlist"""
    return jsonify(get_playlist_videos_list(playlist_id))

@app.route('/api/playlists/<playlist_id>/upload', methods=['POST'])
@require_auth
def upload_content(user_info, playlist_id):
    """Upload image or video to playlist"""
    # Check if playlist exists
    if playlist_id not in service.playlists_db["playlists"]:
        return jsonify({"status": "error", "message": "Playlist not found"}), 404
    
    # Check for existing videos in video playlists
    playlist_type = service.playlists_db["playlists"][playlist_id].get("type", "image")
    if playlist_type == "video":
        existing_videos = get_playlist_videos(playlist_id)
        if existing_videos:
            return jsonify({
                "status": "error",
                "message": "Playlist already contains a video. Delete the existing video first."
            }), 400
    
    # Get content type and length
    content_type = request.content_type
    content_length = request.content_length
    
    if not content_type or 'multipart/form-data' not in content_type:
        return jsonify({"status": "error", "message": "Content must be multipart/form-data"}), 400
    
    # Large file handling (>10MB)
    if content_length and content_length > 10 * 1024 * 1024:
        upload_id = str(uuid.uuid4())[:8]
        playlist_dir = service.VIDEOS_DIR / playlist_id
        playlist_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        temp_dest = playlist_dir / f".uploading_{upload_id}.tmp"
        
        try:
            # Stream upload
            file_info = parse_multipart_form_data_streaming(
                content_type,
                request.stream,
                content_length,
                temp_dest,
                upload_id
            )
            
            if file_info and file_info.get('filename'):
                filename = file_info['filename']
                file_ext = Path(filename).suffix.lower()
                
                valid_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
                if file_ext not in valid_extensions:
                    temp_dest.unlink()
                    return jsonify({"status": "error", "message": "Invalid video file type"}), 400
                
                # Rename to final path
                final_path = playlist_dir / filename
                counter = 1
                while final_path.exists():
                    name_stem = Path(filename).stem
                    final_path = playlist_dir / f"{name_stem}_{counter}{file_ext}"
                    counter += 1
                
                temp_dest.rename(final_path)
                final_path.chmod(0o644)
                
                # Update database
                videos = get_playlist_videos(playlist_id)
                service.playlists_db["playlists"][playlist_id]["video_count"] = len(videos)
                save_playlists_db()
                
                # Start background downscaling
                thread = threading.Thread(
                    target=downscale_video_to_1080p,
                    args=(final_path, upload_id),
                    daemon=True
                )
                thread.start()
                
                return jsonify({
                    "status": "success",
                    "message": "Video uploaded successfully",
                    "filename": final_path.name,
                    "upload_id": upload_id,
                    "downscale_id": upload_id
                })
            else:
                if temp_dest.exists():
                    temp_dest.unlink()
                return jsonify({"status": "error", "message": "No valid file uploaded"}), 400
                
        except Exception as e:
            if temp_dest.exists():
                temp_dest.unlink()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    else:
        # Small file (<10MB) - use request.data
        body = request.get_data()
        expected_field = "video" if playlist_type == "video" else "image"
        file_info = parse_multipart_form_data(content_type, body, expected_field)
        
        if not file_info or not file_info.get('filename') or not file_info.get('data'):
            return jsonify({"status": "error", "message": "No valid file uploaded"}), 400
        
        filename = file_info['filename']
        file_ext = Path(filename).suffix.lower()
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        
        if file_ext in video_extensions:
            playlist_dir = service.VIDEOS_DIR / playlist_id
            playlist_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            final_path = playlist_dir / filename
            counter = 1
            while final_path.exists():
                name_stem = Path(filename).stem
                final_path = playlist_dir / f"{name_stem}_{counter}{file_ext}"
                counter += 1
            
            final_path.write_bytes(file_info['data'])
            final_path.chmod(0o644)
            
            downscale_id = str(uuid.uuid4())[:8]
            
            # Update database
            videos = get_playlist_videos(playlist_id)
            service.playlists_db["playlists"][playlist_id]["video_count"] = len(videos)
            save_playlists_db()
            
            # Background downscaling
            thread = threading.Thread(
                target=downscale_video_to_1080p,
                args=(final_path, downscale_id),
                daemon=True
            )
            thread.start()
            
            return jsonify({
                "status": "success",
                "message": "Video uploaded successfully",
                "filename": final_path.name,
                "downscale_id": downscale_id
            })
        else:
            result = upload_image(playlist_id, file_info['data'], filename)
            return jsonify(result)

@app.route('/api/playlists/<playlist_id>/download', methods=['POST'])
@require_auth
def download_video(user_info, playlist_id):
    """Download video from YouTube"""
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({"status": "error", "message": "No URL provided"}), 400
    
    existing_videos = get_playlist_videos(playlist_id)
    if existing_videos:
        return jsonify({
            "status": "error",
            "message": "Playlist already contains a video. Please remove it first."
        }), 400
    
    download_id = str(uuid.uuid4())[:8]
    thread = threading.Thread(
        target=download_youtube_video,
        args=(playlist_id, url, download_id),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        "status": "started",
        "download_id": download_id,
        "message": "Download started"
    })

@app.route('/api/playlists/<playlist_id>/images/<filename>', methods=['DELETE'])
@require_auth
def delete_playlist_image(user_info, playlist_id, filename):
    """Delete an image from playlist"""
    return jsonify(delete_image(playlist_id, filename))

@app.route('/api/playlists/<playlist_id>/videos/<filename>', methods=['DELETE'])
@require_auth
def delete_playlist_video(user_info, playlist_id, filename):
    """Delete a video from playlist"""
    return jsonify(delete_video(playlist_id, filename))

@app.route('/api/playlists/<playlist_id>/images/<filename>/skip', methods=['POST'])
@require_auth
def skip_playlist_image(user_info, playlist_id, filename):
    """Skip an image in playlist"""
    return jsonify(skip_image(playlist_id, filename))

@app.route('/api/playlists/<playlist_id>/images/<filename>/skip', methods=['DELETE'])
@require_auth
def unskip_playlist_image(user_info, playlist_id, filename):
    """Unskip an image in playlist"""
    return jsonify(unskip_image(playlist_id, filename))

# ═══════════════════════════════════════════════════════════════════════════
# Playback Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/status', methods=['GET'])
@require_auth
def playback_status(user_info):
    """Get current playback status"""
    return jsonify(get_status())

@app.route('/api/start', methods=['GET'])
@require_auth
def start_playback(user_info):
    """Start slideshow or video playback"""
    playlist_id = request.args.get('playlist')
    
    if playlist_id and playlist_id in service.playlists_db["playlists"]:
        plist_type = service.playlists_db["playlists"][playlist_id].get("type", "image")
        if plist_type == "video":
            return jsonify(start_video_playback(playlist_id))
        else:
            return jsonify(start_slideshow(playlist_id))
    else:
        return jsonify(start_slideshow(playlist_id))

@app.route('/api/stop', methods=['GET'])
@require_auth
def stop_playback(user_info):
    """Stop all playback"""
    video_stopped = False
    slideshow_stopped = False
    
    if service.video_process is not None:
        response = stop_video_playback()
        video_stopped = True
    
    if service.slideshow_process is not None:
        response = stop_slideshow()
        slideshow_stopped = True
    
    if not video_stopped and not slideshow_stopped:
        response = stop_slideshow()
    
    if video_stopped or slideshow_stopped:
        return jsonify({
            "status": "stopped",
            "message": "Playback stopped",
            "video_stopped": video_stopped,
            "slideshow_stopped": slideshow_stopped
        })
    return jsonify(response)

@app.route('/api/clear', methods=['GET'])
@require_auth
def clear_display(user_info):
    """Clear the framebuffer"""
    clear_framebuffer()
    return jsonify({"status": "success", "message": "Framebuffer cleared"})

# ═══════════════════════════════════════════════════════════════════════════
# Progress Tracking Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/download/<download_id>', methods=['GET'])
@require_auth
def get_download_status(user_info, download_id):
    """Get download progress status"""
    if download_id in service.download_status:
        return jsonify(service.download_status[download_id])
    return jsonify({"status": "error", "message": "Download not found"}), 404

@app.route('/api/downscale/<downscale_id>', methods=['GET'])
@require_auth
def get_downscale_status(user_info, downscale_id):
    """Get downscale progress status"""
    if downscale_id in service.downscale_status:
        return jsonify(service.downscale_status[downscale_id])
    return jsonify({"status": "error", "message": "Downscale not found"}), 404

# ═══════════════════════════════════════════════════════════════════════════
# Idle Screen Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/idle-config', methods=['GET'])
@require_auth
def get_idle_configuration(user_info):
    """Get idle screen configuration"""
    return jsonify(get_idle_config())

@app.route('/api/idle-config', methods=['POST'])
@require_auth
def save_idle_configuration(user_info):
    """Save idle screen configuration"""
    data = request.get_json()
    cfg = save_idle_config(data)
    stop_idle_screen()
    if cfg.get("enabled") and cfg.get("image_path"):
        start_idle_screen()
    return jsonify(cfg)

@app.route('/api/idle-config/upload', methods=['POST'])
@require_auth
def upload_idle_background(user_info):
    """Upload idle screen background image"""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400
    
    ext = Path(file.filename).suffix.lower()
    dest = service.IDLE_DIR / f"idle_bg{ext}"
    file.save(str(dest))
    
    return jsonify({"status": "success", "image_path": str(dest)})

# ═══════════════════════════════════════════════════════════════════════════
# Scheduler Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/schedules', methods=['GET'])
@require_auth
def get_schedules(user_info):
    """List all schedules"""
    return jsonify(list_schedules())

@app.route('/api/schedules/<schedule_id>', methods=['GET'])
@require_auth
def get_schedule_by_id(user_info, schedule_id):
    """Get a specific schedule"""
    s = get_schedule(schedule_id)
    if not s:
        return jsonify({"status": "error", "message": "Schedule not found"}), 404
    return jsonify(s)

@app.route('/api/schedules', methods=['POST'])
@require_auth
def create_new_schedule(user_info):
    """Create a new schedule"""
    data = request.get_json()
    return jsonify(create_schedule(
        data.get('name'),
        data.get('playlist_id'),
        data.get('cron'),
        data.get('enabled', True)
    ))

@app.route('/api/schedules/<schedule_id>', methods=['PUT'])
@require_auth
def update_existing_schedule(user_info, schedule_id):
    """Update a schedule"""
    data = request.get_json()
    result = update_schedule(schedule_id, data)
    if not result:
        return jsonify({"status": "error", "message": "Schedule not found"}), 404
    return jsonify(result)

@app.route('/api/schedules/<schedule_id>', methods=['DELETE'])
@require_auth
def delete_existing_schedule(user_info, schedule_id):
    """Delete a schedule"""
    ok = delete_schedule(schedule_id)
    if not ok:
        return jsonify({"status": "error", "message": "Schedule not found"}), 404
    return jsonify({"status": "ok"})

# ═══════════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check"""
    return jsonify({"status": "ok"})

# ═══════════════════════════════════════════════════════════════════════════
# Static File Serving
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/')
@app.route('/index.html')
def serve_index():
    """Serve main application page"""
    session_token = request.cookies.get('session_token')
    user_info = validate_session(session_token)
    if not user_info:
        return redirect('/login.html')
    return send_file(service.STATIC_DIR / "index.html")

@app.route('/login.html')
@app.route('/login')
def serve_login():
    """Serve login page"""
    return send_file(service.STATIC_DIR / "login.html")

# Serve static files from frontend
@app.route('/frontend/<path:filename>')
def serve_static(filename):
    """Serve static frontend files"""
    return send_file(service.STATIC_DIR / filename)

# Serve data files (with authentication)
@app.route('/data/idle/<filename>')
@require_auth
def serve_idle_file(user_info, filename):
    """Serve idle screen images"""
    file_path = service.IDLE_DIR / filename
    if not file_path.exists():
        return jsonify({"status": "error", "message": "File not found"}), 404
    return send_file(file_path)

@app.route('/data/playlists/<playlist_id>/<filename>')
@require_auth
def serve_playlist_file(user_info, playlist_id, filename):
    """Serve playlist images/videos"""
    file_path = service.PLAYLISTS_DIR / playlist_id / filename
    if not file_path.exists():
        return jsonify({"status": "error", "message": "File not found"}), 404
    return send_file(file_path)

# ═══════════════════════════════════════════════════════════════════════════
# Application Initialization
# ═══════════════════════════════════════════════════════════════════════════

def initialize_app():
    """Initialize application on startup"""
    setup_logging()
    ensure_directories()
    load_config()
    load_playlists_db()
    
    # Configure Flask static folder after service initialization
    app.static_folder = str(service.STATIC_DIR)
    
    # Load idle config
    cfg = get_idle_config()
    if cfg.get("enabled") and cfg.get("image_path"):
        start_idle_screen()
    
    # Start scheduler
    load_schedules_db()
    start_scheduler()
    
    service.logger.info("=== Pi Display Manager Flask Started ===")
    service.logger.info("API running on http://localhost:%d", service.config.get("api_port", 8000))

# ═══════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    initialize_app()
    port = service.config.get("api_port", 8000) if service.config else 8000
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
