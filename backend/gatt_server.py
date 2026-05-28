#!/usr/bin/env python3
"""Pi Display Manager BLE GATT server.

Provides a simple BLE service with three characteristics:
1) Wi-Fi Scan (read): Returns visible SSIDs as JSON.
2) Wi-Fi Connect (write): Accepts JSON payload with credentials.
3) Status (read/notify): Returns latest operation status.

Write payload examples:
{"ssid":"MyWiFi","password":"secret"}
{"ssid":"OpenWiFi"}
"""

import json
import logging
import signal
import subprocess
import sys
import threading
import time
from typing import List

from bluezero import adapter, peripheral


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("gatt_server")

SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
WIFI_SCAN_UUID = "12345678-1234-5678-1234-56789abcdef1"
WIFI_CONNECT_UUID = "12345678-1234-5678-1234-56789abcdef2"
STATUS_UUID = "12345678-1234-5678-1234-56789abcdef3"
LOCAL_NAME = "Pi3A-GATT"

MAX_CHUNK = 480
status_lock = threading.Lock()
status_text = "idle"


def _set_status(message: str) -> None:
    global status_text
    with status_lock:
        status_text = message
    log.info("STATUS: %s", message)


def _get_status() -> str:
    with status_lock:
        return status_text


def _decode_value(value) -> str:
    """Decode a BlueZ write value to text safely."""
    try:
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).decode("utf-8", errors="ignore")
        if isinstance(value, list):
            return bytes(value).decode("utf-8", errors="ignore")
        return str(value)
    except Exception:
        return ""


def _scan_wifi() -> List[dict]:
    networks = []
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"],
            capture_output=True,
            text=True,
            timeout=18,
            check=False,
        )
        if result.returncode != 0:
            return []

        by_ssid = {}
        for line in result.stdout.splitlines():
            parts = line.split(":")
            if len(parts) < 3:
                continue
            ssid = parts[0].strip()
            if not ssid:
                continue

            try:
                quality = int(parts[1])
            except Exception:
                quality = 0
            secure = bool(parts[2].strip())
            signal_dbm = int((quality / 2) - 100)

            existing = by_ssid.get(ssid)
            if existing is None or signal_dbm > existing["signal_dbm"]:
                by_ssid[ssid] = {
                    "ssid": ssid,
                    "quality": quality,
                    "signal_dbm": signal_dbm,
                    "secure": secure,
                }

        networks = sorted(by_ssid.values(), key=lambda x: x["signal_dbm"], reverse=True)
    except Exception as exc:
        log.warning("Wi-Fi scan failed: %s", exc)
    return networks


def _wifi_scan_read():
    """Read callback for Wi-Fi scan characteristic."""
    data = {
        "status": "ok",
        "networks": _scan_wifi(),
    }
    payload = json.dumps(data, separators=(",", ":"))
    if len(payload) > MAX_CHUNK:
        payload = payload[: MAX_CHUNK - 1]
    return payload.encode("utf-8")


def _status_read():
    payload = json.dumps({"status": _get_status()})
    if len(payload) > MAX_CHUNK:
        payload = payload[: MAX_CHUNK - 1]
    return payload.encode("utf-8")


def _connect_worker(ssid: str, password: str) -> None:
    _set_status(f"connecting:{ssid}")

    cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        cmd.extend(["password", password])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
        if result.returncode == 0:
            _set_status(f"connected:{ssid}")
        else:
            err = (result.stderr or result.stdout or "connect_failed").strip().replace("\n", " ")
            _set_status(f"error:{err[:180]}")
    except Exception as exc:
        _set_status(f"error:{str(exc)[:180]}")


def _wifi_connect_write(value, _options):
    """Write callback for Wi-Fi connect characteristic."""
    raw = _decode_value(value).strip()
    if not raw:
        _set_status("error:empty_payload")
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _set_status("error:invalid_json")
        return

    ssid = str(payload.get("ssid", "")).strip()
    password = str(payload.get("password", ""))

    if not ssid:
        _set_status("error:ssid_required")
        return

    t = threading.Thread(target=_connect_worker, args=(ssid, password), daemon=True)
    t.start()


def _get_adapter_address() -> str:
    adapters = list(adapter.Adapter.available())
    if not adapters:
        raise RuntimeError("No BLE adapter found")
    return adapters[0].address


def main() -> int:
    _set_status("starting")

    try:
        adapter_addr = _get_adapter_address()
    except Exception as exc:
        log.error("Bluetooth adapter unavailable: %s", exc)
        return 1

    ble = peripheral.Peripheral(
        adapter_addr=adapter_addr,
        local_name=LOCAL_NAME,
        appearance=0,
    )

    ble.add_service(srv_id=1, uuid=SERVICE_UUID, primary=True)

    ble.add_characteristic(
        srv_id=1,
        chr_id=1,
        uuid=WIFI_SCAN_UUID,
        value=[],
        notifying=False,
        flags=["read"],
        read_callback=_wifi_scan_read,
    )

    ble.add_characteristic(
        srv_id=1,
        chr_id=2,
        uuid=WIFI_CONNECT_UUID,
        value=[],
        notifying=False,
        flags=["write"],
        write_callback=_wifi_connect_write,
    )

    ble.add_characteristic(
        srv_id=1,
        chr_id=3,
        uuid=STATUS_UUID,
        value=[],
        notifying=True,
        flags=["read", "notify"],
        read_callback=_status_read,
    )

    def _shutdown(_sig, _frm):
        _set_status("stopping")
        try:
            ble.stop()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    _set_status("ready")
    log.info("Starting GATT server as %s on %s", LOCAL_NAME, adapter_addr)
    ble.publish()

    # Keep process alive for signal handling while Bluezero main loop runs.
    while True:
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
