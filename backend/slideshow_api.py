#!/usr/bin/env python3
"""
Pi Display Manager - Flask Entry Point
Main entry point that imports from service and controller layers.
Lightweight REST API with Flask framework.
"""

import signal
import sys

# Import Flask app
from controllers.controller import app, initialize_app

# Import service layer for configuration
from services.service import config, logger, stop_scheduler, stop_slideshow


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("\nReceived signal %d, shutting down...", sig)
    stop_scheduler()
    stop_slideshow()
    logger.info("Pi Display Manager Flask service stopped")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize application
        initialize_app()
        
        port = config.get("api_port", 80) if config else 80
        
        print("=" * 70)
        print("🚀 Pi Display Manager - Flask Server")
        print("=" * 70)
        print(f"📡 API Server: http://localhost:{port}")
        print("=" * 70)
        
        app.run(
            host="0.0.0.0",
            port=port,
            threaded=True,
            debug=False
        )
    except Exception as e:
        if logger:
            logger.error("Fatal error: %s", str(e))
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
