"""
Pi Display Manager - Controller Layer
Handles HTTP requests and routes them to appropriate service functions.
"""

import json
import uuid
import threading
import tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import signal
import sys

# Import authentication module
from auth import (
    authenticate_user, validate_session, destroy_session, 
    require_auth, cleanup_expired_sessions
)

# Import service layer functions and state
from service import (
    # Core functions
    setup_logging, ensure_directories, load_config, load_playlists_db,

    # State variables
    logger, config, playlists_db, download_status, upload_status,
    slideshow_process, video_process, STATIC_DIR, IDLE_DIR, PLAYLISTS_DIR,
    DATA_DIR, UPLOADS_DIR,

    # Service functions
    get_status, start_slideshow, stop_slideshow, clear_framebuffer,
    list_playlists, create_playlist, update_playlist, delete_playlist,
    get_playlist_images_list, get_playlist_videos_list,
    upload_image, upload_video, delete_image, delete_video,
    skip_image, unskip_image,
    parse_multipart_form_data, parse_multipart_form_data_streaming,
    download_youtube_video,
    start_video_playback, stop_video_playback, get_playlist_videos,

    # Idle screen
    get_idle_config, save_idle_config, start_idle_screen, stop_idle_screen,

    # Scheduler
    load_schedules_db, list_schedules, get_schedule, create_schedule,
    update_schedule, delete_schedule, stop_scheduler,
)


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the REST API"""

    def do_GET(self):
        """Handle GET requests"""
        from service import logger, playlists_db, download_status, video_process, slideshow_process
        
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        response = None
        status = 200
        content_type = "application/json"

        # Skip logging for status endpoint to avoid log clutter
        if path != "/api/status":
            logger.info("GET %s from %s", path, self.client_address[0])

        # Public endpoints (no auth required)
        if path == "/login.html" or path == "/login":
            self.serve_static_file("login.html")
            return
        elif path == "/api/auth/status":
            # Check if user is authenticated
            cookie_header = self.headers.get('Cookie', '')
            session_token = None
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('session_token='):
                    session_token = cookie.split('=', 1)[1]
                    break
            
            user_info = validate_session(session_token)
            if user_info:
                response = {"authenticated": True, "user": user_info}
            else:
                response = {"authenticated": False}
            self.send_json_response(response, 200)
            return
        elif path == "/api/auth/logout":
            # Handle logout
            cookie_header = self.headers.get('Cookie', '')
            session_token = None
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('session_token='):
                    session_token = cookie.split('=', 1)[1]
                    break
            
            if session_token:
                destroy_session(session_token)
            
            response = {"status": "success", "message": "Logged out successfully"}
            self.send_json_response(response, 200)
            return

        # Serve static files (requires auth)
        if path == "/" or path == "/index.html":
            # Check authentication before serving main page
            cookie_header = self.headers.get('Cookie', '')
            session_token = None
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('session_token='):
                    session_token = cookie.split('=', 1)[1]
                    break
            
            user_info = validate_session(session_token)
            if not user_info:
                # Redirect to login
                self.send_response(302)
                self.send_header('Location', '/login.html')
                self.end_headers()
                return
            
            self.serve_static_file("index.html")
            return
        elif path.startswith("/frontend/"):
            self.serve_static_file(path[10:])  # Remove "/frontend/" prefix
            return

        # Protected API endpoints (require authentication)
        cookie_header = self.headers.get('Cookie', '')
        session_token = None
        for cookie in cookie_header.split(';'):
            cookie = cookie.strip()
            if cookie.startswith('session_token='):
                session_token = cookie.split('=', 1)[1]
                break
        
        user_info = validate_session(session_token)
        if not user_info:
            response = {"status": "error", "message": "Unauthorized. Please login."}
            self.send_json_response(response, 401)
            return
        
        # Store current user for logging
        self.current_user = user_info

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
            download_id = path.split("/")[3]
            if download_id in download_status:
                response = download_status[download_id]
            else:
                response = {"status": "not_found", "message": "Download not found"}
        elif path.startswith("/api/upload/"):
            # Get upload status
            upload_id = path.split("/")[3]
            if upload_id in upload_status:
                response = upload_status[upload_id]
            else:
                response = {"status": "not_found", "message": "Upload not found"}
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
            video_stopped = False
            slideshow_stopped = False
            
            if video_process is not None:
                response = stop_video_playback()
                video_stopped = True
            
            if slideshow_process is not None:
                response = stop_slideshow()
                slideshow_stopped = True
            
            if not video_stopped and not slideshow_stopped:
                # Nothing was running, but clean up anyway
                response = stop_slideshow()  # This will clean up framebuffer
            
            if video_stopped or slideshow_stopped:
                response = {
                    "status": "stopped",
                    "message": "Playback stopped",
                    "video_stopped": video_stopped,
                    "slideshow_stopped": slideshow_stopped
                }
        elif path == "/api/clear":
            clear_framebuffer()
            response = {"status": "success", "message": "Framebuffer cleared"}
        elif path == "/api/idle-config":
            response = get_idle_config()
        elif path == "/api/schedules":
            response = list_schedules()
        elif path.startswith("/api/schedules/"):
            schedule_id = path.split("/")[3]
            s = get_schedule(schedule_id)
            response = s if s else {"status": "error", "message": "Not found"}
            status = 200 if s else 404
        elif path == "/api/health":
            response = {"status": "ok"}
        elif path.startswith("/data/idle/"):
            # Serve idle background image for browser preview
            filename = path[len("/data/idle/"):]
            filename = unquote(filename)
            self.serve_file_from_dir(IDLE_DIR, filename)
            return
        elif path.startswith("/data/playlists/"):
            # Serve playlist images for browser preview
            # Format: /data/playlists/{playlist_id}/{filename}
            parts = path[len("/data/playlists/"):].split("/", 1)
            if len(parts) == 2:
                playlist_id, filename = parts
                filename = unquote(filename)
                playlist_dir = PLAYLISTS_DIR / playlist_id
                self.serve_file_from_dir(playlist_dir, filename)
            else:
                response = {"status": "error", "message": "Invalid path"}
                self.send_json_response(response, 404)
            return
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
        from service import logger
        
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        response = None
        status = 200

        # Skip logging for status endpoint to avoid log clutter
        if path != "/api/status":
            logger.info("POST %s from %s", path, self.client_address[0])

        try:
            # Public endpoints (no auth required)
            if path == "/api/auth/login":
                # Handle login
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                username = data.get('username', '')
                password = data.get('password', '')
                
                success, result = authenticate_user(username, password)
                
                if success:
                    # Set session cookie
                    response = {
                        "status": "success",
                        "message": "Login successful",
                        "user": {
                            "username": username
                        }
                    }
                    
                    # Send response with cookie
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Set-Cookie', f'session_token={result}; Path=/; HttpOnly; SameSite=Strict; Max-Age=3600')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                    return
                else:
                    response = {"status": "error", "message": result}
                    status = 401
                    self.send_json_response(response, status)
                    return
            
            # Protected endpoints (require authentication)
            cookie_header = self.headers.get('Cookie', '')
            session_token = None
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('session_token='):
                    session_token = cookie.split('=', 1)[1]
                    break
            
            user_info = validate_session(session_token)
            if not user_info:
                response = {"status": "error", "message": "Unauthorized. Please login."}
                self.send_json_response(response, 401)
                return
            
            # Store current user for logging
            self.current_user = user_info
            
            if path == "/api/playlists/create":
                # Create new playlist
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                name = data.get("name", "Untitled Playlist")
                playlist_type = data.get("type", "image")  # "image" or "video"
                delay = data.get("delay", 5)  # Default 5 seconds
                response = create_playlist(name, playlist_type, delay)
            
            elif path.startswith("/api/playlists/") and "/upload" in path:
                # Upload file to playlist (image or video)
                playlist_id = path.split("/")[3]
                content_type = self.headers.get('Content-Type', '')
                
                if 'multipart/form-data' in content_type:
                    content_length = int(self.headers.get('Content-Length', 0))
                    
                    # Check if content length suggests a video (>10MB = likely video)
                    # Use streaming for large files to avoid RAM exhaustion
                    if content_length > 10 * 1024 * 1024:  # 10MB threshold
                        # Generate upload ID for progress tracking
                        upload_id = str(uuid.uuid4())[:8]
                        
                        # Stream directly to temp file
                        temp_file = tempfile.NamedTemporaryFile(delete=False, dir=str(UPLOADS_DIR))
                        temp_path = Path(temp_file.name)
                        temp_file.close()
                        
                        file_info = parse_multipart_form_data_streaming(
                            content_type,
                            self.rfile,
                            content_length,
                            temp_path,
                            upload_id  # Pass upload ID for progress tracking
                        )
                        
                        # The streaming parser consumes the entire request stream
                        # including boundaries and headers, so no draining needed
                        
                        if file_info and file_info.get('filename'):
                            filename = file_info['filename']
                            file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                            
                            # Should be a video based on size
                            video_extensions = ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm']
                            if file_ext in video_extensions:
                                response = upload_video(
                                    playlist_id,
                                    str(temp_path),
                                    filename
                                )
                                # Add upload_id to response for frontend tracking
                                if response.get('status') == 'success':
                                    response['upload_id'] = upload_id
                            else:
                                # Large non-video file - treat as image but warn
                                # Read temp file (still in memory but unavoidable for images)
                                try:
                                    with open(temp_path, 'rb') as f:
                                        file_data = f.read()
                                    temp_path.unlink()
                                    response = upload_image(
                                        playlist_id,
                                        file_data,
                                        filename
                                    )
                                except Exception as e:
                                    if temp_path.exists():
                                        temp_path.unlink()
                                    response = {"status": "error", "message": f"Failed to process file: {str(e)}"}
                        else:
                            response = {"status": "error", "message": "No valid file uploaded"}
                    else:
                        # Small file - use in-memory parsing (original method)
                        body = self.rfile.read(content_length)
                        file_info = parse_multipart_form_data(content_type, body)
                        
                        if file_info and file_info.get('filename') and file_info.get('data'):
                            filename = file_info['filename']
                            file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                            
                            video_extensions = ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm']
                            if file_ext in video_extensions:
                                # Small video - write to temp file then move
                                temp_file = tempfile.NamedTemporaryFile(delete=False, dir=str(UPLOADS_DIR))
                                temp_file.write(file_info['data'])
                                temp_path = Path(temp_file.name)
                                temp_file.close()
                                
                                response = upload_video(
                                    playlist_id,
                                    str(temp_path),
                                    filename
                                )
                            else:
                                response = upload_image(
                                    playlist_id,
                                    file_info['data'],
                                    filename
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
                    # Check if playlist already has a video
                    existing_videos = get_playlist_videos(playlist_id)
                    if existing_videos:
                        response = {
                            "status": "error", 
                            "message": "Playlist already contains a video. Please remove the existing video before downloading another one."
                        }
                    else:
                        # Start download in background thread
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
            
            elif path.startswith("/api/playlists/") and "/images/" in path and "/skip" in path:
                # Skip an image in playlist
                # Format: /api/playlists/{id}/images/{filename}/skip
                parts = path.split("/")
                playlist_id = parts[3]
                filename = parts[5]
                response = skip_image(playlist_id, filename)
            
            elif path == "/api/schedules":
                content_length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(content_length))
                result = create_schedule(
                    data["name"], data["playlist_id"], data["cron"],
                    data.get("enabled", True)
                )
                response = result
                status = 201

            elif path == "/api/idle-config":
                content_length = int(self.headers.get("Content-Length", 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode("utf-8"))
                cfg = save_idle_config(data)
                stop_idle_screen()
                if cfg.get("enabled") and cfg.get("image_path"):
                    start_idle_screen()
                response = cfg

            elif path == "/api/idle-config/upload":
                content_type_hdr = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in content_type_hdr:
                    response = {"status": "error", "message": "Expected multipart/form-data"}
                else:
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    file_info = parse_multipart_form_data(content_type_hdr, body, expected_field="file")
                    if file_info and file_info.get("filename") and file_info.get("data"):
                        from pathlib import Path as _Path
                        ext = _Path(file_info["filename"]).suffix.lower()
                        dest = IDLE_DIR / f"idle_bg{ext}"
                        dest.write_bytes(file_info["data"])
                        response = {"status": "success", "image_path": str(dest)}
                    else:
                        response = {"status": "error", "message": "No valid file found in request"}

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
        from service import logger
        
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        response = None
        status = 200

        # Skip logging for status endpoint to avoid log clutter
        if path != "/api/status":
            logger.info("DELETE %s from %s", path, self.client_address[0])

        try:
            # Protected endpoints (require authentication)
            cookie_header = self.headers.get('Cookie', '')
            session_token = None
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('session_token='):
                    session_token = cookie.split('=', 1)[1]
                    break
            
            user_info = validate_session(session_token)
            if not user_info:
                response = {"status": "error", "message": "Unauthorized. Please login."}
                self.send_json_response(response, 401)
                return
            
            # Store current user for logging
            self.current_user = user_info
            
            if path.startswith("/api/playlists/") and "/images/" in path and "/skip" in path:
                # Unskip an image in playlist
                # Format: /api/playlists/{id}/images/{filename}/skip
                parts = path.split("/")
                playlist_id = parts[3]
                filename = parts[5]
                response = unskip_image(playlist_id, filename)
            
            elif path.startswith("/api/playlists/") and "/images/" in path:
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

            elif path.startswith("/api/schedules/"):
                schedule_id = path.split("/")[3]
                ok = delete_schedule(schedule_id)
                response = {"status": "ok" if ok else "error"}
                status = 200 if ok else 404

            else:
                response = {"status": "error", "message": "Unknown DELETE endpoint"}
                status = 404

        except Exception as e:
            logger.error("DELETE request error: %s", str(e))
            response = {"status": "error", "message": str(e)}
            status = 500

        self.send_json_response(response, status)

    def do_PUT(self):
        """Handle PUT requests"""
        from service import logger

        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Skip logging for status endpoint to avoid log clutter
        if path != "/api/status":
            logger.info("PUT %s from %s", path, self.client_address[0])

        try:
            # Protected endpoints (require authentication)
            cookie_header = self.headers.get('Cookie', '')
            session_token = None
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if cookie.startswith('session_token='):
                    session_token = cookie.split('=', 1)[1]
                    break
            
            user_info = validate_session(session_token)
            if not user_info:
                response = {"status": "error", "message": "Unauthorized. Please login."}
                self.send_json_response(response, 401)
                return
            
            if path.startswith("/api/playlists/"):
                # Update playlist settings
                playlist_id = path.split("/")[3]
                content_length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(content_length))
                result = update_playlist(
                    playlist_id,
                    name=data.get("name"),
                    delay=data.get("delay")
                )
                self.send_json_response(result)
            elif path.startswith("/api/schedules/"):
                schedule_id = path.split("/")[3]
                content_length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(content_length))
                result = update_schedule(schedule_id, data)
                if result:
                    self.send_json_response(result)
                else:
                    self.send_json_response({"status": "error", "message": "Not found"}, 404)
            else:
                self.send_json_response({"status": "error", "message": "Unknown PUT endpoint"}, 404)
        except Exception as e:
            logger.error("PUT request error: %s", e)
            self.send_json_response({"status": "error", "message": str(e)}, 500)

    def serve_file_from_dir(self, directory, filename):
        """Serve a file from an arbitrary directory."""
        from service import logger
        from pathlib import Path as _Path

        file_path = _Path(directory) / filename
        if not file_path.exists():
            self.send_error(404, "File not found")
            return

        content_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }
        content_type = content_types.get(file_path.suffix.lower(), "application/octet-stream")
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.error("Error serving file %s: %s", file_path, e)
            self.send_error(500, "Internal server error")

    def serve_static_file(self, filename):
        """Serve a static file"""
        from service import STATIC_DIR, logger
        
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
    from service import logger
    logger.info("Received signal %d, shutting down...", sig)
    stop_scheduler()
    stop_slideshow()
    logger.info("Pi Display Manager API service stopped")
    sys.exit(0)


def run_server():
    """Start the HTTP server"""
    from service import config, logger, api_port, DATA_DIR, PLAYLISTS_DIR
    
    port = config.get("api_port", 8000)
    delay = config.get("delay", 5)

    logger.info("=== Pi Display Manager API Service Started ===")
    logger.info("Configuration:")
    logger.info("  API Port: %d", port)
    logger.info("  Slide Delay: %d seconds", delay)
    logger.info("  Data Directory: %s", DATA_DIR)
    logger.info("  Playlists Directory: %s", PLAYLISTS_DIR)

    server = ThreadingHTTPServer(("0.0.0.0", port), APIHandler)
    server.daemon_threads = True  # Allow threads to be killed on shutdown
    logger.info("HTTP server listening on 0.0.0.0:%d (multi-threaded)", port)
    logger.info("Web interface: http://localhost:%d", port)

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
        from service import logger
        if logger:
            logger.error("Fatal error: %s", str(e))
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
