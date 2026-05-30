#!/usr/bin/env python3
"""macOS BLE GATT central/client for Pi Display Manager."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from pathlib import Path
from typing import Optional

from bleak import BleakClient, BleakError, BleakScanner

try:
    from ble.constants import (
        BLE_DEVICE_NAME,
        BLE_NOTIFY_CHAR_UUID,
        BLE_SERVICE_UUID,
        BLE_WRITE_CHAR_UUID,
    )
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ble.constants import (
        BLE_DEVICE_NAME,
        BLE_NOTIFY_CHAR_UUID,
        BLE_SERVICE_UUID,
        BLE_WRITE_CHAR_UUID,
    )


class MacBleGattClient:
    """Async BLE central with reconnect and notification support."""

    def __init__(
        self,
        logger: logging.Logger,
        device_name: str,
        service_uuid: str,
        write_char_uuid: str,
        notify_char_uuid: str,
        scan_timeout: float = 12.0,
        connect_timeout: float = 15.0,
    ):
        self._logger = logger
        self._device_name = device_name
        self._service_uuid = service_uuid
        self._write_char_uuid = write_char_uuid
        self._notify_char_uuid = notify_char_uuid
        self._scan_timeout = scan_timeout
        self._connect_timeout = connect_timeout

        self._client: Optional[BleakClient] = None
        self._shutdown_event = asyncio.Event()
        self._disconnected_event = asyncio.Event()

    async def run(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                device = await self._discover_device()
                if device is None:
                    self._logger.warning("Pi BLE peripheral not found. Retrying...")
                    await asyncio.sleep(2)
                    continue

                await self._connect(device.address)
                await self._interactive_loop()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.error("Client loop error: %s", exc, exc_info=True)
                await asyncio.sleep(2)
            finally:
                await self._disconnect()

        self._logger.info("BLE client exited")

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        await self._disconnect()

    async def _discover_device(self):
        self._logger.info("Scanning for BLE peripheral '%s'...", self._device_name)

        def _filter(device, adv_data):
            if device.name == self._device_name:
                return True
            advertised_uuids = [u.lower() for u in (adv_data.service_uuids or [])]
            return self._service_uuid.lower() in advertised_uuids

        try:
            return await BleakScanner.find_device_by_filter(_filter, timeout=self._scan_timeout)
        except BleakError as exc:
            self._logger.error("BLE scan failed: %s", exc)
            return None

    async def _connect(self, address: str) -> None:
        self._logger.info("Connecting to %s", address)
        self._disconnected_event.clear()

        self._client = BleakClient(address, disconnected_callback=self._on_disconnected)
        await asyncio.wait_for(self._client.connect(), timeout=self._connect_timeout)
        await self._client.start_notify(self._notify_char_uuid, self._on_notification)
        self._logger.info("Connected and subscribed to notifications")

    async def _disconnect(self) -> None:
        if not self._client:
            return

        try:
            if self._client.is_connected:
                try:
                    await self._client.stop_notify(self._notify_char_uuid)
                except Exception:
                    pass
                await self._client.disconnect()
        finally:
            self._client = None

    async def _interactive_loop(self) -> None:
        if not self._client:
            return

        print("Type commands to send to Pi. Use 'quit' to exit.")

        while not self._shutdown_event.is_set():
            if self._disconnected_event.is_set():
                self._logger.warning("Disconnected. Reconnecting...")
                return

            try:
                command = await asyncio.wait_for(
                    asyncio.to_thread(input, "ble> "),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue

            command = command.strip()
            if not command:
                continue
            if command.lower() in {"quit", "exit"}:
                self._shutdown_event.set()
                return

            await self._send_command(command)

    async def _send_command(self, command: str) -> None:
        if not self._client or not self._client.is_connected:
            self._logger.warning("Command not sent; BLE link is down")
            return

        payload = command.encode("utf-8")
        self._logger.info("Sending command: %s", command)

        # Some BLE stacks/peripherals prefer one write mode over the other.
        # Try write-with-response first, then fallback to write-without-response.
        for response_mode in (True, False):
            try:
                await asyncio.wait_for(
                    self._client.write_gatt_char(self._write_char_uuid, payload, response=response_mode),
                    timeout=4.0,
                )
                self._logger.info("TX (%s): %s", "response" if response_mode else "no-response", command)
                return
            except asyncio.TimeoutError:
                self._logger.warning(
                    "Write timeout (%s) for command: %s",
                    "response" if response_mode else "no-response",
                    command,
                )
            except Exception as exc:
                self._logger.warning(
                    "Write failed (%s): %s",
                    "response" if response_mode else "no-response",
                    exc,
                )

        self._logger.error("Command send failed in both write modes: %s", command)

    def _on_disconnected(self, _client):
        self._logger.warning("BLE disconnected callback received")
        self._disconnected_event.set()

    def _on_notification(self, _sender, data: bytearray):
        message = bytes(data).decode("utf-8", errors="replace")
        print(f"[PI] {message}", flush=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="macOS BLE GATT client for Pi Display Manager")
    parser.add_argument("--device-name", default=BLE_DEVICE_NAME)
    parser.add_argument("--service-uuid", default=BLE_SERVICE_UUID)
    parser.add_argument("--write-char-uuid", default=BLE_WRITE_CHAR_UUID)
    parser.add_argument("--notify-char-uuid", default=BLE_NOTIFY_CHAR_UUID)
    parser.add_argument("--scan-timeout", type=float, default=12.0)
    parser.add_argument("--connect-timeout", type=float, default=15.0)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


async def _async_main(args) -> None:
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("ble-macos-client")

    client = MacBleGattClient(
        logger=logger,
        device_name=args.device_name,
        service_uuid=args.service_uuid,
        write_char_uuid=args.write_char_uuid,
        notify_char_uuid=args.notify_char_uuid,
        scan_timeout=args.scan_timeout,
        connect_timeout=args.connect_timeout,
    )

    loop = asyncio.get_running_loop()

    def _signal_handler():
        loop.create_task(client.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    await client.run()


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
