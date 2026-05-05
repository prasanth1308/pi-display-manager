#!/usr/bin/env python3
"""
Pi Display Manager - REST API Entry Point
Main entry point that imports from service and controller layers.
"""

import signal
import sys

# Import service layer for initialization
from service import (
    setup_logging, ensure_directories, load_config, load_playlists_db, logger,
    load_idle_config, start_idle_screen,
)

# Import controller for server execution
from controller import run_server, signal_handler


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        setup_logging()
        ensure_directories()
        load_config()
        load_playlists_db()
        cfg = load_idle_config()
        if cfg.get("enabled") and cfg.get("image_path"):
            start_idle_screen()
        run_server()
    except Exception as e:
        if logger:
            logger.error("Fatal error: %s", str(e))
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
