"""
Pi Display Manager - Controller Layer
Handles HTTP requests and routes them to appropriate service functions.
"""

import json
import uuid
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import signal
import sys

# Import service layer functions and state
from service import (
    # Core functions
    setup_logging, ensure_directories, load_config, load_playlists_db,
    
    # State variables
    logger, config, playlists_db, download_status, 
    slideshow_process, video_process, STATIC_DIR,
    
    # Service functions
    get_status, start_slideshow, stop_slideshow, clear_framebuffer,
    list_playlists, create_playlist, delete_playlist,
    get_playlist_images_list, get_playlist_videos_list,
    upload_image, delete_image, delete_video,
    parse_multipart_form_data, download_youtube_video,
    start_video_playback, stop_video_playback, get_playlist_videos
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

        logger.info("GET %s from %s", path, self.client_address[0])

        # Serve static files
        if path == "/" or path == "/index.html":
            self.serve_static_file("index.html")
            return
        elif path.startswith("/frontend/"):
            self.serve_static_file(path[10:])  # Remove "/frontend/" prefix
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
            download_id = path.split("/")[3]
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
        from service import logger
        
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

    server = HTTPServer(("0.0.0.0", port), APIHandler)
    logger.info("HTTP server listening on 0.0.0.0:%d", port)
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
