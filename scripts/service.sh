#!/usr/bin/env bash
# ── Pi Display Manager — Service Control Script ─────────────────────────────
# Convenient wrapper for systemd service management

set -euo pipefail

SERVICE_NAME="pi-display"

case "${1:-}" in
  start)
    echo "Starting $SERVICE_NAME service..."
    sudo systemctl start "$SERVICE_NAME"
    echo "✓ Service started"
    ;;
  stop)
    echo "Stopping $SERVICE_NAME service..."
    sudo systemctl stop "$SERVICE_NAME"
    echo "✓ Service stopped"
    ;;
  restart)
    echo "Restarting $SERVICE_NAME service..."
    sudo systemctl restart "$SERVICE_NAME"
    echo "✓ Service restarted"
    ;;
  status)
    sudo systemctl status "$SERVICE_NAME"
    ;;
  enable)
    echo "Enabling $SERVICE_NAME service (start on boot)..."
    sudo systemctl enable "$SERVICE_NAME"
    echo "✓ Service will start automatically on boot"
    ;;
  disable)
    echo "Disabling $SERVICE_NAME service (no auto-start)..."
    sudo systemctl disable "$SERVICE_NAME"
    echo "✓ Service will not start automatically on boot"
    ;;
  logs)
    echo "Showing logs (Ctrl+C to exit)..."
    sudo journalctl -u "$SERVICE_NAME" -f
    ;;
  *)
    echo "Pi Display Manager - Service Control"
    echo ""
    echo "Usage: $0 {start|stop|restart|status|enable|disable|logs}"
    echo ""
    echo "Commands:"
    echo "  start    - Start the service now"
    echo "  stop     - Stop the service now"
    echo "  restart  - Restart the service now"
    echo "  status   - Show service status"
    echo "  enable   - Enable auto-start on boot"
    echo "  disable  - Disable auto-start on boot"
    echo "  logs     - View live service logs"
    exit 1
    ;;
esac
