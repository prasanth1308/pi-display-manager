# Web BLE Client (HTML + JS)

This folder contains a plain HTML/JS Web Bluetooth client that can send commands to the Pi BLE GATT server and receive notifications.

## Files

- `index.html`: UI
- `styles.css`: styles
- `app.js`: Web Bluetooth client logic

## Requirements

- Chromium-based browser with Web Bluetooth support (Chrome/Edge recommended)
- HTTPS origin, or localhost
- User gesture for device selection (click Connect)
- Pi service advertising BLE and reachable over Bluetooth

## Run locally

You need to serve this folder via a local HTTP server (do not open directly with `file://`).

From repo root:

```bash
python3 -m http.server 9000
```

Open:

```text
http://localhost:9000/web-ble-client/
```

If you open `index.html` directly from Finder (file://), modern browsers can block script loading and Web Bluetooth access.

## Host on GitHub Pages (recommended)

This repo now includes a Pages workflow at `.github/workflows/pages.yml`.

### One-time setup in GitHub

1. Open repository settings.
2. Go to `Settings -> Pages`.
3. Under **Build and deployment**, select **Source: GitHub Actions**.

### Deploy

1. Commit and push changes to branch `feat/blegatt`.
2. Wait for workflow **Deploy Web BLE Client to GitHub Pages** to complete.
3. Open the Pages URL from workflow output.

Expected URL pattern:

```text
https://prasanth1308.github.io/pi-display-manager/
```

## Usage

1. Click Connect.
2. In chooser, select `PiDisplayManager`.
3. Send commands like:
   - `ping`
   - `status`
   - `stop`
   - `default-start`
   - `start <playlist_id>`
4. View responses in Logs.

## Troubleshooting

- If Connect button does nothing: ensure browser supports Web Bluetooth and page is on localhost/HTTPS.
- If connected but no response: verify UUIDs match Pi config.
- If device not listed: check Pi service logs and Bluetooth adapter state
