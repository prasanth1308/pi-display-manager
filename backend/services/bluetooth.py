"""
Pi Display Manager - Bluetooth Service
RFCOMM server that listens for commands from a paired Bluetooth client
and returns JSON responses.

Protocol (newline-delimited JSON):
  Client → Pi : {"command": "getWifiList"}\n
  Pi → Client : {"status": "ok",    "data": [...]}\n
               or {"status": "error", "message": "..."}\n

Supported commands:
  getWifiList   – scan & return nearby Wi-Fi networks
  getConnectedWifi – return the currently connected Wi-Fi SSID/details
  connectWifi   – connect to a Wi-Fi network  {"command":"connectWifi","ssid":"...","password":"..."}
  getStatus     – return Pi display-manager status snapshot
  ping          – health check, returns {"status":"ok","data":"pong"}
"""

import json
import logging
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)

# ── UUID must match what the client advertises when searching ──────────────
SERVICE_UUID = "00001101-0000-1000-8000-00805F9B34FB"  # standard SPP UUID
SERVICE_NAME = "PiDisplayManager"
RFCOMM_PORT  = 1   # channel 1; use bluetooth.PORT_ANY for auto-assign

_server_thread: threading.Thread | None = None
_stop_event = threading.Event()


# ═══════════════════════════════════════════════════════════════════════════
# Command handlers
# ═══════════════════════════════════════════════════════════════════════════

def _cmd_ping(_payload: dict) -> dict:
    return {"status": "ok", "data": "pong"}


def _cmd_get_wifi_list(_payload: dict) -> dict:
    """Scan nearby Wi-Fi networks using nmcli (preferred) or iwlist."""
    try:
        result = subprocess.run(
            [
                "nmcli", "--terse", "--fields",
                "SSID,SIGNAL,SECURITY,CHAN",
                "device", "wifi", "list", "--rescan", "yes",
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            networks = []
            seen: set[str] = set()
            for line in result.stdout.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 4:
                    ssid, signal, security, channel = (
                        parts[0], parts[1], parts[2], parts[3]
                    )
                    if ssid and ssid not in seen:
                        seen.add(ssid)
                        networks.append({
                            "ssid":     ssid,
                            "signal":   int(signal) if signal.isdigit() else 0,
                            "security": security,
                            "channel":  channel,
                        })
            networks.sort(key=lambda n: n["signal"], reverse=True)
            return {"status": "ok", "data": networks}
    except FileNotFoundError:
        pass  # nmcli not available, fall through to iwlist
    except Exception as exc:
        logger.warning("nmcli scan failed: %s", exc)

    # Fallback: iwlist
    try:
        result = subprocess.run(
            ["iwlist", "wlan0", "scan"],
            capture_output=True, text=True, timeout=15,
        )
        networks = []
        seen: set[str] = set()
        current: dict = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Cell "):
                if current.get("ssid") and current["ssid"] not in seen:
                    seen.add(current["ssid"])
                    networks.append(current)
                current = {}
            elif "ESSID:" in line:
                current["ssid"] = line.split('"')[1] if '"' in line else ""
            elif "Signal level=" in line:
                try:
                    sig_part = line.split("Signal level=")[1].split(" ")[0]
                    current["signal"] = int(sig_part.split("/")[0])
                except (IndexError, ValueError):
                    current["signal"] = 0
            elif "Encryption key:" in line:
                current["security"] = "WPA" if "on" in line else "Open"
        if current.get("ssid") and current["ssid"] not in seen:
            networks.append(current)
        networks.sort(key=lambda n: n.get("signal", 0), reverse=True)
        return {"status": "ok", "data": networks}
    except Exception as exc:
        return {"status": "error", "message": f"Wi-Fi scan failed: {exc}"}


def _cmd_get_connected_wifi(_payload: dict) -> dict:
    """Return the currently connected Wi-Fi network details."""
    try:
        result = subprocess.run(
            ["nmcli", "--terse", "--fields",
             "NAME,TYPE,STATE,DEVICE",
             "connection", "show", "--active"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 4 and "wireless" in parts[1]:
                    ssid = parts[0]
                    # get IP
                    ip_result = subprocess.run(
                        ["nmcli", "-t", "-f", "IP4.ADDRESS",
                         "connection", "show", ssid],
                        capture_output=True, text=True, timeout=5,
                    )
                    ip = ""
                    for ip_line in ip_result.stdout.splitlines():
                        if "IP4.ADDRESS" in ip_line:
                            ip = ip_line.split(":")[1].split("/")[0]
                            break
                    return {"status": "ok", "data": {"ssid": ssid, "ip": ip}}
        return {"status": "ok", "data": None}  # not connected
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _cmd_connect_wifi(payload: dict) -> dict:
    """Connect to a Wi-Fi network. Requires 'ssid' (and optionally 'password')."""
    ssid = payload.get("ssid", "").strip()
    password = payload.get("password", "").strip()
    if not ssid:
        return {"status": "error", "message": "'ssid' is required"}
    try:
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if password:
            cmd += ["password", password]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return {"status": "ok", "data": f"Connected to {ssid}"}
        return {"status": "error", "message": result.stderr.strip() or result.stdout.strip()}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _cmd_get_status(_payload: dict) -> dict:
    """Return a lightweight status snapshot of the display manager."""
    try:
        # Import here to avoid circular imports at module load time
        from services.service import get_status  # type: ignore
        status = get_status()
        return {"status": "ok", "data": status}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


_COMMAND_MAP = {
    "ping":             _cmd_ping,
    "getWifiList":      _cmd_get_wifi_list,
    "getConnectedWifi": _cmd_get_connected_wifi,
    "connectWifi":      _cmd_connect_wifi,
    "getStatus":        _cmd_get_status,
}


# ═══════════════════════════════════════════════════════════════════════════
# Request dispatcher
# ═══════════════════════════════════════════════════════════════════════════

def _dispatch(raw: str) -> str:
    """Parse a raw JSON string, run the matching handler, return JSON string."""
    try:
        payload = json.loads(raw.strip())
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "Invalid JSON"})

    command = payload.get("command", "")
    handler = _COMMAND_MAP.get(command)
    if handler is None:
        available = list(_COMMAND_MAP.keys())
        return json.dumps({
            "status":    "error",
            "message":   f"Unknown command: '{command}'",
            "available": available,
        })

    try:
        response = handler(payload)
    except Exception as exc:
        logger.exception("Handler for '%s' raised an exception", command)
        response = {"status": "error", "message": str(exc)}

    return json.dumps(response)


# ═══════════════════════════════════════════════════════════════════════════
# Client connection handler
# ═══════════════════════════════════════════════════════════════════════════

def _handle_client(client_sock, client_addr):
    logger.info("Bluetooth client connected: %s", client_addr)
    buffer = ""
    try:
        while not _stop_event.is_set():
            try:
                chunk = client_sock.recv(1024).decode("utf-8", errors="replace")
            except OSError:
                break
            if not chunk:
                break

            buffer += chunk
            # Process every complete newline-terminated message
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                logger.debug("BT ← %s", line)
                response = _dispatch(line)
                logger.debug("BT → %s", response)
                try:
                    client_sock.send((response + "\n").encode("utf-8"))
                except OSError:
                    return
    finally:
        client_sock.close()
        logger.info("Bluetooth client disconnected: %s", client_addr)


# ═══════════════════════════════════════════════════════════════════════════
# Server loop
# ═══════════════════════════════════════════════════════════════════════════

def _server_loop():
    try:
        import bluetooth  # type: ignore  (pybluez)
    except ImportError as exc:
        logger.error(
            "Bluetooth import failed with %s while using %s. "
            "Verify the service venv with '%s -c "
            "\"import bluetooth; print(bluetooth.__file__)\"'.",
            exc,
            sys.executable,
            sys.executable,
        )
        return

    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", RFCOMM_PORT))
    server_sock.listen(1)

    bluetooth.advertise_service(
        server_sock,
        SERVICE_NAME,
        service_id=SERVICE_UUID,
        service_classes=[SERVICE_UUID, bluetooth.SERIAL_PORT_CLASS],
        profiles=[bluetooth.SERIAL_PORT_PROFILE],
    )

    logger.info(
        "Bluetooth RFCOMM server listening on channel %d (UUID: %s)",
        RFCOMM_PORT, SERVICE_UUID,
    )

    try:
        while not _stop_event.is_set():
            server_sock.settimeout(2.0)
            try:
                client_sock, client_addr = server_sock.accept()
            except bluetooth.BluetoothError:
                continue  # timeout → check stop_event
            t = threading.Thread(
                target=_handle_client,
                args=(client_sock, client_addr),
                daemon=True,
            )
            t.start()
    finally:
        server_sock.close()
        logger.info("Bluetooth RFCOMM server stopped")


# ═══════════════════════════════════════════════════════════════════════════
# Public start / stop API
# ═══════════════════════════════════════════════════════════════════════════

def start_bluetooth_service():
    """Start the Bluetooth RFCOMM server in a background thread."""
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        logger.warning("Bluetooth service is already running")
        return

    _stop_event.clear()
    _server_thread = threading.Thread(target=_server_loop, daemon=True, name="bt-rfcomm")
    _server_thread.start()
    logger.info("Bluetooth service thread started")


def stop_bluetooth_service():
    """Signal the Bluetooth server to stop."""
    _stop_event.set()
    if _server_thread:
        _server_thread.join(timeout=5)
    logger.info("Bluetooth service stopped")
