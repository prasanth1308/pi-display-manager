// ── Wi-Fi notification response accumulator ─────────────────────────────────
const wifiResponse = {
  resolve: null,
  reject: null,
  timer: null,
  buffer: "",

  // Called by onNotification for every incoming message.
  // Returns true if the message was consumed by a pending wifi command.
  feed(message) {
    if (!this.resolve) return false;
    this.buffer += (this.buffer ? "\n" : "") + message;
    if (
      this.buffer.startsWith("WIFI_LIST ") ||
      this.buffer.startsWith("WIFI_LIST_PAGE ") ||
      this.buffer.startsWith("WIFI_CONNECTED ") ||
      this.buffer.startsWith("WIFI_FORGOTTEN ") ||
      this.buffer.startsWith("ERROR ")
    ) {
      clearTimeout(this.timer);
      const cb = this.resolve;
      const captured = this.buffer;
      this.resolve = null;
      this.reject = null;
      this.buffer = "";
      cb(captured);
    }
    return true;
  },

  // Send a command and wait up to `timeoutMs` for the notification response.
  async send(rawCommand, timeoutMs = 12000) {
    if (this.resolve) {
      throw new Error("Another Wi-Fi request is already in progress");
    }

    return new Promise((resolve, reject) => {
      this.resolve = resolve;
      this.reject = reject;
      this.buffer = "";
      this.timer = setTimeout(() => {
        this.resolve = null;
        this.reject = null;
        this.buffer = "";
        reject(new Error("Timed out waiting for Wi-Fi response"));
      }, timeoutMs);

      sendCommand(rawCommand, { keepInput: true })
        .catch((err) => {
          clearTimeout(this.timer);
          this.resolve = null;
          this.reject = null;
          this.buffer = "";
          reject(err instanceof Error ? err : new Error(String(err)));
        });
    });
  },
};

// ── DOM references ────────────────────────────────────────────────────────────
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
  // Wi-Fi
  wifiListBtn: document.getElementById("wifiListBtn"),
  wifiConnectBtn: document.getElementById("wifiConnectBtn"),
  wifiForgetBtn: document.getElementById("wifiForgetBtn"),
  wifiSsidInput: document.getElementById("wifiSsidInput"),
  wifiPasswordInput: document.getElementById("wifiPasswordInput"),
  wifiForgetInput: document.getElementById("wifiForgetInput"),
  wifiList: document.getElementById("wifiList"),
  wifiStatus: document.getElementById("wifiStatus"),
  connectedSsid: document.getElementById("connectedSsid"),
  wifiTogglePw: document.getElementById("wifiTogglePw"),
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
  // Wi-Fi buttons
  el.wifiListBtn.disabled = !connected;
  el.wifiConnectBtn.disabled = !connected;
  el.wifiForgetBtn.disabled = !connected;
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
  // Route Wi-Fi responses to the accumulator first
  if (
    message.startsWith("WIFI_LIST ") ||
    message.startsWith("WIFI_LIST_PAGE ") ||
    message.startsWith("WIFI_CONNECTED ") ||
    message.startsWith("WIFI_FORGOTTEN ") ||
    (wifiResponse.resolve && message.startsWith("ERROR "))
  ) {
    wifiResponse.feed(message);
  }
  log(`[PI] ${message}`);
}

async function sendCommand(rawCommand, options = {}) {
  const keepInput = Boolean(options.keepInput);
  const command = (rawCommand ?? el.commandInput.value).trim();
  if (!command) {
    throw new Error("Command is empty");
  }

  if (!state.writeChar) {
    setStatus("Not connected", "err");
    log("ERROR: command not sent because write characteristic is unavailable.");
    throw new Error("Not connected");
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
    throw (error instanceof Error ? error : new Error(String(error)));
  }

  if (!keepInput) {
    el.commandInput.value = "";
    el.commandInput.focus();
  }
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

// ── Wi-Fi UI logic ─────────────────────────────────────────────────────────────

function setWifiStatus(msg, isError = false) {
  el.wifiStatus.textContent = msg;
  el.wifiStatus.className = "wifi-status " + (isError ? "err" : (msg ? "ok" : ""));
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function signalBars(dbm) {
  // dbm typically -30 (best) to -90 (worst); some drivers return 0-100 pct
  const pct = dbm > 0 ? dbm : Math.max(0, Math.min(100, (dbm + 90) * 100 / 60));
  if (pct > 75) return "████";
  if (pct > 50) return "███░";
  if (pct > 25) return "██░░";
  return "█░░░";
}

function renderNetworks(networks) {
  el.wifiList.innerHTML = "";
  el.wifiList.style.display = networks.length ? "block" : "none";
  el.connectedSsid.style.display = "none";

  for (const net of networks) {
    const row = document.createElement("div");
    row.className = "wifi-row" + (net.connected ? " wifi-row--connected" : "");

    const badge = net.connected ? ` <span class="wifi-badge">connected</span>` : "";
    const signal = net.signal !== null && net.signal !== undefined
      ? `<span class="wifi-signal" title="${net.signal} dBm">${signalBars(net.signal)}</span>`
      : "";

    row.innerHTML =
      `<span class="wifi-ssid">${escapeHtml(net.ssid)}${badge}</span>` +
      signal +
      `<button class="wifi-pick" data-ssid="${escapeHtml(net.ssid)}">Select</button>`;
    el.wifiList.appendChild(row);

    if (net.connected) {
      el.connectedSsid.textContent = "\u2713 " + net.ssid;
      el.connectedSsid.style.display = "inline-block";
    }
  }

  el.wifiList.querySelectorAll(".wifi-pick").forEach((btn) => {
    btn.addEventListener("click", () => {
      el.wifiSsidInput.value = btn.dataset.ssid;
      document.getElementById("wifiConnectDetails").open = true;
      el.wifiPasswordInput.focus();
    });
  });
}

el.wifiListBtn.addEventListener("click", async () => {
  setWifiStatus("Scanning\u2026");
  el.wifiListBtn.disabled = true;
  try {
    const networks = [];

    let reply = await wifiResponse.send("wifi-list", 20000);
    if (!reply.startsWith("WIFI_LIST_PAGE ")) {
      setWifiStatus(reply, true);
      return;
    }

    while (reply.startsWith("WIFI_LIST_PAGE ")) {
      const payload = JSON.parse(reply.slice("WIFI_LIST_PAGE ".length));
      const items = Array.isArray(payload.i) ? payload.i : [];

      for (const item of items) {
        networks.push({
          ssid: item.s || "",
          signal: item.g,
          connected: !!item.c,
        });
      }

      if (payload.d) {
        break;
      }

      reply = await wifiResponse.send(`wifi-list-page ${payload.n}`, 12000);
      if (reply.startsWith("ERROR ")) {
        setWifiStatus(reply, true);
        return;
      }
    }

    renderNetworks(networks);
    setWifiStatus(networks.length + " network(s) found");
  } catch (e) {
    setWifiStatus(e.message, true);
  } finally {
    el.wifiListBtn.disabled = !state.writeChar;
  }
});

el.wifiConnectBtn.addEventListener("click", async () => {
  const ssid = el.wifiSsidInput.value.trim();
  const pw = el.wifiPasswordInput.value;
  if (!ssid) { setWifiStatus("Enter an SSID", true); return; }
  if (!pw)   { setWifiStatus("Enter a password", true); return; }

  setWifiStatus("Connecting\u2026");
  el.wifiConnectBtn.disabled = true;
  try {
    const cmd = `wifi-connect ${JSON.stringify(ssid)} ${JSON.stringify(pw)}`;
    const reply = await wifiResponse.send(cmd, 35000);
    if (reply.startsWith("WIFI_CONNECTED")) {
      setWifiStatus("Connected to " + ssid);
      el.wifiPasswordInput.value = "";
    } else {
      setWifiStatus(reply, true);
    }
  } catch (e) {
    setWifiStatus(e.message, true);
  } finally {
    el.wifiConnectBtn.disabled = !state.writeChar;
  }
});

el.wifiForgetBtn.addEventListener("click", async () => {
  const ssid = el.wifiForgetInput.value.trim();
  if (!ssid) { setWifiStatus("Enter the SSID to forget", true); return; }
  if (!confirm(`Forget Wi-Fi network "${ssid}"?`)) return;

  setWifiStatus("Forgetting\u2026");
  el.wifiForgetBtn.disabled = true;
  try {
    const reply = await wifiResponse.send(`wifi-forget ${JSON.stringify(ssid)}`, 12000);
    if (reply.startsWith("WIFI_FORGOTTEN")) {
      setWifiStatus("Forgotten: " + ssid);
      el.wifiForgetInput.value = "";
    } else {
      setWifiStatus(reply, true);
    }
  } catch (e) {
    setWifiStatus(e.message, true);
  } finally {
    el.wifiForgetBtn.disabled = !state.writeChar;
  }
});

el.wifiTogglePw.addEventListener("click", () => {
  const isPassword = el.wifiPasswordInput.type === "password";
  el.wifiPasswordInput.type = isPassword ? "text" : "password";
  el.wifiTogglePw.textContent = isPassword ? "\u{1F648}" : "\u{1F441}\uFE0F";
});

// ── Bootstrap ──────────────────────────────────────────────────────────────────
setConnectedUi(false);
setStatus("Disconnected", "warn");
log("Ready. Click Connect to start BLE session.");
