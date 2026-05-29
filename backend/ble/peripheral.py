"""Raspberry Pi BLE GATT peripheral/server implementation."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

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

try:
    from bless import BlessServer
    from bless.backends.characteristic import (
        GATTAttributePermissions,
        GATTCharacteristicProperties,
    )
except ImportError:  # pragma: no cover - import checked at runtime on Pi
    BlessServer = None
    GATTAttributePermissions = None
    GATTCharacteristicProperties = None


CommandHandler = Callable[[str], Optional[str]]


@dataclass
class BleConfig:
    """BLE configuration values for the peripheral."""

    device_name: str = BLE_DEVICE_NAME
    service_uuid: str = BLE_SERVICE_UUID
    write_char_uuid: str = BLE_WRITE_CHAR_UUID
    notify_char_uuid: str = BLE_NOTIFY_CHAR_UUID
    max_payload_bytes: int = 180


class PiBleGattPeripheral:
    """BLE GATT server with one write characteristic and one notify characteristic."""

    def __init__(self, logger: logging.Logger, config: BleConfig, handler: CommandHandler = None):
        self._logger = logger
        self._config = config
        self._command_handler = handler

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._running = False
        self._stop_event = threading.Event()
        self._write_lock = threading.Lock()
        self._last_connected = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """Start BLE peripheral in a dedicated asyncio event loop thread."""
        if self._running:
            self._logger.info("BLE peripheral already running")
            return True

        if BlessServer is None:
            self._logger.error("BLE dependencies missing. Install requirements and restart the service.")
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._thread_main, name="ble-gatt-peripheral", daemon=True)
        self._thread.start()
        self._running = True
        return True

    def stop(self, timeout: float = 8.0) -> None:
        """Stop BLE peripheral and cleanly tear down advertising."""
        if not self._running:
            return

        self._stop_event.set()
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)

        if self._thread:
            self._thread.join(timeout=timeout)

        self._running = False
        self._thread = None
        self._loop = None
        self._server = None
        self._last_connected = False

    def notify(self, message: str) -> None:
        """Queue a notification to connected centrals."""
        if not self._running or not self._loop or not self._loop.is_running():
            return

        asyncio.run_coroutine_threadsafe(self._notify_async(message), self._loop)

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._run_server())
        except Exception as exc:  # pragma: no cover - hardware/runtime dependent
            self._logger.error("BLE peripheral crashed: %s", exc, exc_info=True)
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()

    async def _run_server(self) -> None:
        self._logger.info("Starting BLE peripheral: %s", self._config.device_name)
        self._server = BlessServer(name=self._config.device_name)

        self._server.read_request_func = self._on_read_request
        self._server.write_request_func = self._on_write_request

        await self._server.add_new_service(self._config.service_uuid)
        await self._server.add_new_characteristic(
            self._config.service_uuid,
            self._config.write_char_uuid,
            GATTCharacteristicProperties.write | GATTCharacteristicProperties.write_without_response,
            bytearray(),
            GATTAttributePermissions.writeable,
        )
        await self._server.add_new_characteristic(
            self._config.service_uuid,
            self._config.notify_char_uuid,
            GATTCharacteristicProperties.notify | GATTCharacteristicProperties.read,
            bytearray(b"ready"),
            GATTAttributePermissions.readable,
        )

        await self._server.start()
        self._logger.info(
            "BLE advertising started: service=%s write_char=%s notify_char=%s",
            self._config.service_uuid,
            self._config.write_char_uuid,
            self._config.notify_char_uuid,
        )

        while not self._stop_event.is_set():
            connected = self._is_connected()
            if connected != self._last_connected:
                if connected:
                    self._logger.info("BLE central connected")
                else:
                    self._logger.info("BLE central disconnected")
                self._last_connected = connected
            await asyncio.sleep(1.0)

        await self._shutdown()

    async def _shutdown(self) -> None:
        if self._server is None:
            return
        try:
            await self._server.stop()
            self._logger.info("BLE advertising stopped")
        except Exception as exc:  # pragma: no cover - hardware/runtime dependent
            self._logger.warning("BLE stop warning: %s", exc)

    def _on_read_request(self, characteristic, **kwargs):  # pragma: no cover - hardware callback
        return characteristic.value

    def _on_write_request(self, characteristic, value, **kwargs):  # pragma: no cover - hardware callback
        with self._write_lock:
            raw = bytes(value)
            text = raw.decode("utf-8", errors="replace").strip()

            self._logger.info("BLE RX: %s", text)
            print(f"[BLE RX] {text}", flush=True)

            response = None
            if self._command_handler:
                try:
                    response = self._command_handler(text)
                except Exception as exc:
                    self._logger.error("BLE command handler failed: %s", exc, exc_info=True)
                    response = f"ERROR {exc}"

            if response is None:
                response = f"ACK {text}"

            if response:
                self.notify(response)

    async def _notify_async(self, message: str) -> None:
        if not self._server:
            return

        payload = message.encode("utf-8")[: self._config.max_payload_bytes]
        if not payload:
            return

        try:
            characteristic = self._server.get_characteristic(self._config.notify_char_uuid)
            characteristic.value = bytearray(payload)
            await self._server.update_value(self._config.service_uuid, self._config.notify_char_uuid)
            self._logger.info("BLE TX: %s", payload.decode("utf-8", errors="replace"))
        except Exception as exc:  # pragma: no cover - hardware/runtime dependent
            self._logger.warning("BLE notify failed: %s", exc)

    def _is_connected(self) -> bool:
        if not self._server:
            return False

        state = getattr(self._server, "is_connected", False)
        try:
            return bool(state() if callable(state) else state)
        except Exception:
            return False
