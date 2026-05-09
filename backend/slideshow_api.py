#!/usr/bin/env python3
"""
Pi Display Manager - FastAPI Entry Point
Main entry point that imports from service and controller layers.
Modern REST API with FastAPI framework.
"""

import signal
import sys
import uvicorn

# Import FastAPI app
from controllers.controller_fastapi import app

# Import service layer for configuration
from services.service import config, logger, stop_scheduler, stop_slideshow


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("\nReceived signal %d, shutting down...", sig)
    stop_scheduler()
    stop_slideshow()
    logger.info("Pi Display Manager FastAPI service stopped")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        port = config.get("api_port", 8000) if config else 8000
        
        print("=" * 70)
        print("🚀 Pi Display Manager - FastAPI Server")
        print("=" * 70)
        print(f"📡 API Server: http://localhost:{port}")
        print(f"📚 API Docs: http://localhost:{port}/docs")
        print(f"🔍 ReDoc: http://localhost:{port}/redoc")
        print("=" * 70)
        
        uvicorn.run(
            "controllers.controller_fastapi:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            log_level="info",
            access_log=False  # Use our custom logging
        )
    except Exception as e:
        if logger:
            logger.error("Fatal error: %s", str(e))
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
