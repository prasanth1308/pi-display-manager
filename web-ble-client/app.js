const el = {
  deviceName: document.getElementById("deviceName"),
  serviceUuid: document.getElementById("serviceUuid"),
  writeUuid: document.getElementById("writeUuid"),
  notifyUuid: document.getElementById("notifyUuid"),
  connectBtn: document.getElementById("connectBtn"),
  disconnectBtn: document.getElementById("disconnectBtn"),
  sendBtn: document.getElementById("sendBtn"),
  commandInput: document.getElementById("commandInput"),
  quickButtons: Array.from(document.querySelectorAll("button.quick")),
  status: document.getElementById("status"),
  logs: document.getElementById("logs"),
  clearLogsBtn: document.getElementById("clearLogsBtn"),
};

const state = {
  device: null,
  server: null,
  writeChar: null,
  notifyChar: null,
};

const encoder = new TextEncoder();
const decoder = new TextDecoder();

if (window.location.protocol === "file:") {
  const msg = "Opened via file://. Use a local server: python3 -m http.server 9000 and open http://localhost:9000/web-ble-client/";
  setTimeout(() => {
    setStatus("Use http://localhost (not file://)", "err");
    log(`ERROR: ${msg}`);
    alert(msg);
  }, 0);
}

function now() {
  return new Date().toLocaleTimeString();
}

function log(message) {
  el.logs.textContent += `[${now()}] ${message}\n`;
  el.logs.scrollTop = el.logs.scrollHeight;
}

function setStatus(message, type = "warn") {
  el.status.textContent = message;
  el.status.classList.remove("ok", "warn", "err");
  el.status.classList.add(type);
}

function setConnectedUi(connected) {
  el.connectBtn.disabled = connected;
  el.disconnectBtn.disabled = !connected;
  el.sendBtn.disabled = !connected;
  el.quickButtons.forEach((btn) => {
    btn.disabled = !connected;
  });
}

function normalizeUuid(value) {
  return String(value || "").trim().toLowerCase();
}

async function connect() {
  if (window.location.protocol === "file:") {
    setStatus("Blocked on file://. Open via localhost.", "err");
    log("ERROR: Web Bluetooth requires localhost/HTTPS for reliable behavior.");
    return;
  }

  if (!navigator.bluetooth) {
    setStatus("Web Bluetooth is not available in this browser.", "err");
    log("ERROR: navigator.bluetooth is unavailable.");
    return;
  }

  const deviceName = el.deviceName.value.trim();
  const serviceUuid = normalizeUuid(el.serviceUuid.value);
  const writeUuid = normalizeUuid(el.writeUuid.value);
  const notifyUuid = normalizeUuid(el.notifyUuid.value);

  try {
    setStatus("Opening BLE device chooser...", "warn");
    log(`Requesting BLE device (name=${deviceName}, service=${serviceUuid})`);

    const device = await navigator.bluetooth.requestDevice({
      filters: [{ name: deviceName }],
      optionalServices: [serviceUuid],
    });

    device.addEventListener("gattserverdisconnected", onDisconnected);

    const server = await device.gatt.connect();
    const service = await server.getPrimaryService(serviceUuid);

    const writeChar = await service.getCharacteristic(writeUuid);
    const notifyChar = await service.getCharacteristic(notifyUuid);

    await notifyChar.startNotifications();
    notifyChar.addEventListener("characteristicvaluechanged", onNotification);

    state.device = device;
    state.server = server;
    state.writeChar = writeChar;
    state.notifyChar = notifyChar;

    setConnectedUi(true);
    setStatus(`Connected to ${device.name || "BLE device"}`, "ok");
    log("Connected and notifications enabled.");
  } catch (error) {
    setStatus("Connection failed", "err");
    log(`ERROR: ${error?.message || error}`);
    await disconnect();
  }
}

async function disconnect() {
  try {
    if (state.notifyChar) {
      try {
        state.notifyChar.removeEventListener("characteristicvaluechanged", onNotification);
        await state.notifyChar.stopNotifications();
      } catch {
        // ignore cleanup failure
      }
    }

    if (state.device?.gatt?.connected) {
      state.device.gatt.disconnect();
    }
  } finally {
    if (state.device) {
      state.device.removeEventListener("gattserverdisconnected", onDisconnected);
    }
    state.device = null;
    state.server = null;
    state.writeChar = null;
    state.notifyChar = null;
    setConnectedUi(false);
    setStatus("Disconnected", "warn");
    log("Disconnected.");
  }
}

function onDisconnected() {
  log("Device disconnected.");
  setStatus("Disconnected", "warn");
  setConnectedUi(false);
  state.server = null;
  state.writeChar = null;
  state.notifyChar = null;
}

function onNotification(event) {
  const value = event.target.value;
  const bytes = new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  const message = decoder.decode(bytes);
  log(`[PI] ${message}`);
}

async function sendCommand(rawCommand) {
  const command = (rawCommand ?? el.commandInput.value).trim();
  if (!command) {
    return;
  }

  if (!state.writeChar) {
    setStatus("Not connected", "err");
    log("ERROR: command not sent because write characteristic is unavailable.");
    return;
  }

  const payload = encoder.encode(command);
  log(`[WEB->PI] ${command}`);

  try {
    if (state.writeChar.writeValueWithResponse) {
      await state.writeChar.writeValueWithResponse(payload);
      log("Command sent using writeValueWithResponse.");
    } else {
      await state.writeChar.writeValue(payload);
      log("Command sent using writeValue.");
    }
  } catch (error) {
    log(`ERROR: send failed (${error?.message || error}).`);
  }

  el.commandInput.value = "";
  el.commandInput.focus();
}

el.connectBtn.addEventListener("click", () => {
  void connect();
});

el.disconnectBtn.addEventListener("click", () => {
  void disconnect();
});

el.sendBtn.addEventListener("click", () => {
  void sendCommand();
});

el.commandInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    void sendCommand();
  }
});

el.quickButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    void sendCommand(btn.dataset.cmd || "");
  });
});

el.clearLogsBtn.addEventListener("click", () => {
  el.logs.textContent = "";
});

setConnectedUi(false);
setStatus("Disconnected", "warn");
log("Ready. Click Connect to start BLE session.");
