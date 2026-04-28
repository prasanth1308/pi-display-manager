#!/usr/bin/env python3
"""
Lightweight REST API for controlling image slideshow on Raspberry Pi using fbi.
Runs as a background service.
"""

import os
import json
import subprocess
import signal
import sys
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Global state
slideshow_process = None
config = {}
api_port = 8000
logger = None


def setup_logging():
    """Configure logging to file and console"""
    global logger
    log_file = Path(__file__).parent / "slideshow_api.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.json"""
    global config
    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path) as f:
            config = json.load(f)
        if logger:
            logger.info("Configuration loaded from %s", config_path)
    except FileNotFoundError:
        msg = f"Config file not found at {config_path}"
        if logger:
            logger.error(msg)
        else:
            print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in config: {e}"
        if logger:
            logger.error(msg)
        else:
            print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)


def get_images():
    """Get list of image files from the configured folder"""
    image_folder = Path(config.get("image_folder", "/home/larokiaraj/pi"))
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

    if not image_folder.exists():
        return []

    images = sorted([
        str(f) for f in image_folder.iterdir()
        if f.suffix.lower() in image_extensions
    ])
    return images


def clear_framebuffer():
    """Clear the framebuffer to remove any lingering images"""
    try:
        framebuffer = config.get("framebuffer", "/dev/fb0")
        logger.info("Clearing framebuffer: %s", framebuffer)
        subprocess.run(
            ["dd", "if=/dev/zero", f"of={framebuffer}"],
            capture_output=True,
            timeout=2
        )
        logger.info("Framebuffer cleared successfully")
    except subprocess.TimeoutExpired:
        logger.warning("Framebuffer clear timed out")
    except Exception as e:
        logger.warning("Failed to clear framebuffer: %s", str(e))


def start_slideshow():
    """Start the slideshow using fbi"""
    global slideshow_process

    if slideshow_process is not None:
        logger.info("Slideshow already running - start request ignored")
        return {"status": "slideshow_running", "message": "Slideshow is already running"}

    images = get_images()
    if not images:
        logger.error("No images found in folder: %s", config.get("image_folder"))
        return {"status": "error", "message": "No images found in folder"}

    try:
        delay = config.get("delay", 5)
        framebuffer = config.get("framebuffer", "/dev/fb0")

        # Build fbi command to work without VT switching and from SSH
        # Using --vt 0 disables VT switching for systems without CONFIG_VT support
        cmd = [
            "fbi",
            "-t", str(delay),         # Time delay between images
            "-a",                      # Auto-advance
            "--noverbose",             # Suppress console output (prevents flashing)
            "-d", framebuffer,         # Specify framebuffer device
            "-T", "1",                 # Use VT 1 (even though switching is disabled)
        ] + images

        cmd_str = " ".join(cmd)
        logger.info("Starting slideshow with command: %s", cmd_str)
        logger.info("Images: %d files from %s", len(images), config.get("image_folder"))

        # Set up environment variables for framebuffer access
        env = os.environ.copy()
        env['FRAMEBUFFER'] = framebuffer
        
        # Open log file for fbi stderr
        fbi_log = Path(__file__).parent / "fbi_error.log"
        with open(fbi_log, "a") as f:
            f.write(f"\n=== Starting fbi at {__import__('datetime').datetime.now()} ===\n")

        with open(fbi_log, "a") as f:
            slideshow_process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=f,
                stderr=f,
                env=env                     # Pass environment with FRAMEBUFFER set
                # NOT using start_new_session so fbi is killed when parent stops
            )
        logger.info("Slideshow process started (PID: %d)", slideshow_process.pid)
        return {"status": "started", "message": "Slideshow started", "image_count": len(images)}
    except FileNotFoundError:
        logger.error("fbi package not installed")
        return {"status": "error", "message": "fbi package not installed"}
    except Exception as e:
        logger.error("Failed to start slideshow: %s", str(e))
        return {"status": "error", "message": str(e)}


def stop_slideshow():
    """Stop the slideshow and kill all fbi processes"""
    global slideshow_process

    if slideshow_process is None:
        logger.info("Stop requested but slideshow not running")
        # Still try to clean up any orphaned processes and clear framebuffer
        try:
            subprocess.run(["pkill", "-9", "fbi"], capture_output=True)
            logger.info("Killed any orphaned fbi processes")
        except Exception as e:
            logger.error("Error running pkill: %s", str(e))
        
        # Clear the framebuffer
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

    # Kill any remaining fbi processes
    try:
        subprocess.run(["pkill", "-9", "fbi"], capture_output=True)
        logger.info("Killed all fbi processes")
    except Exception as e:
        logger.error("Error running pkill: %s", str(e))

    # Clear the framebuffer to remove lingering images
    clear_framebuffer()

    return {"status": "stopped", "message": "Slideshow stopped"}


def get_status():
    """Get current slideshow status"""
    images = get_images()
    return {
        "running": slideshow_process is not None,
        "image_count": len(images),
        "image_folder": config.get("image_folder"),
        "delay": config.get("delay"),
        "framebuffer": config.get("framebuffer")
    }


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the REST API"""

    def do_GET(self):
        """Handle GET requests"""
        response = None
        status = 200

        logger.info("API Request: %s from %s", self.path, self.client_address[0])

        if self.path == "/start":
            response = start_slideshow()
        elif self.path == "/stop":
            response = stop_slideshow()
        elif self.path == "/status":
            response = get_status()
        elif self.path == "/clear":
            clear_framebuffer()
            response = {"status": "ok", "message": "Framebuffer cleared"}
        elif self.path == "/health":
            response = {"status": "ok"}
            logger.info("Health check OK")
        else:
            response = {
                "status": "error",
                "message": "Unknown endpoint",
                "available_endpoints": ["/start", "/stop", "/status", "/clear", "/health"]
            }
            status = 404
            logger.warning("Unknown endpoint requested: %s", self.path)

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
    logger.info("Slideshow API service stopped")
    sys.exit(0)


def run_server():
    """Start the HTTP server"""
    global api_port

    api_port = config.get("api_port", 8000)
    image_folder = config.get("image_folder", "/home/larokiaraj/pi")
    framebuffer = config.get("framebuffer", "/dev/fb0")
    delay = config.get("delay", 5)

    logger.info("=== Slideshow API Service Started ===")
    logger.info("Configuration:")
    logger.info("  Image Folder: %s", image_folder)
    logger.info("  API Port: %d", api_port)
    logger.info("  Slide Delay: %d seconds", delay)
    logger.info("  Framebuffer: %s", framebuffer)

    server = HTTPServer(("0.0.0.0", api_port), APIHandler)
    logger.info("HTTP server listening on 0.0.0.0:%d", api_port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        setup_logging()
        load_config()
        run_server()
    except Exception as e:
        if logger:
            logger.error("Fatal error: %s", str(e))
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
