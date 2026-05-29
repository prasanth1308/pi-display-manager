#!/usr/bin/env python3
"""Standalone BLE GATT peripheral server for Raspberry Pi."""

from __future__ import annotations

import argparse
import logging
import signal
import time
from pathlib import Path

try:
    from ble.constants import (
        BLE_DEVICE_NAME,
        BLE_NOTIFY_CHAR_UUID,
        BLE_SERVICE_UUID,
        BLE_WRITE_CHAR_UUID,
    )
    from ble.peripheral import BleConfig, PiBleGattPeripheral
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ble.constants import (
        BLE_DEVICE_NAME,
        BLE_NOTIFY_CHAR_UUID,
        BLE_SERVICE_UUID,
        BLE_WRITE_CHAR_UUID,
    )
    from ble.peripheral import BleConfig, PiBleGattPeripheral


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone BLE GATT peripheral for Raspberry Pi")
    parser.add_argument("--device-name", default=BLE_DEVICE_NAME)
    parser.add_argument("--service-uuid", default=BLE_SERVICE_UUID)
    parser.add_argument("--write-char-uuid", default=BLE_WRITE_CHAR_UUID)
    parser.add_argument("--notify-char-uuid", default=BLE_NOTIFY_CHAR_UUID)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("ble-pi-server")

    config = BleConfig(
        device_name=args.device_name,
        service_uuid=args.service_uuid,
        write_char_uuid=args.write_char_uuid,
        notify_char_uuid=args.notify_char_uuid,
    )

    def _handler(command: str) -> str:
        logger.info("RX command: %s", command)
        print(f"[BLE RX] {command}", flush=True)
        return f"ACK {command}"

    peripheral = PiBleGattPeripheral(logger=logger, config=config, handler=_handler)

    should_exit = False

    def _stop(*_args):
        nonlocal should_exit
        should_exit = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    if not peripheral.start():
        raise SystemExit(1)

    logger.info("BLE peripheral started. Press Ctrl+C to stop.")
    try:
        while not should_exit:
            time.sleep(0.25)
    finally:
        peripheral.stop()
        logger.info("BLE peripheral stopped")


if __name__ == "__main__":
    main()
