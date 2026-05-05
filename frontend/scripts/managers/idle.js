/**
 * IdleManager
 * Handles idle screen configuration: upload background image,
 * set custom text, and save/apply the config.
 */

const IdleManager = {
  _imagePath: null,

  async load() {
    try {
      const cfg = await API.getIdleConfig();
      if (!cfg) return;

      document.getElementById("idle-enabled").checked = !!cfg.enabled;
      document.getElementById("idle-custom-text").value = cfg.custom_text || "";

      if (cfg.image_path) {
        this._imagePath = cfg.image_path;
        this._showPreview(cfg.image_path);
      }
    } catch (e) {
      console.error("Failed to load idle config:", e);
    }
  },

  _showPreview(imagePath) {
    const wrap = document.getElementById("idle-preview-wrap");
    const img = document.getElementById("idle-preview-img");
    // Build preview URL from stored path, e.g. "data/idle/idle_bg.jpg"
    const filename = imagePath.replace(/^.*[/\\]/, "");
    img.src = `/data/idle/${filename}`;
    wrap.style.display = "block";
    document.getElementById("idle-upload-hint").style.display = "none";
  },

  async uploadBackground(file) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch("/api/idle-config/upload", {
        method: "POST",
        body: fd,
      });
      const data = await res.json();
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Upload failed");
      }
      this._imagePath = data.image_path;
      this._showPreview(data.image_path);
      UI.showToast("Background image uploaded", TOAST_TYPES.SUCCESS);
    } catch (e) {
      UI.showToast(`Upload failed: ${e.message}`, TOAST_TYPES.ERROR);
    }
  },

  async save() {
    const enabled = document.getElementById("idle-enabled").checked;
    const customText = document.getElementById("idle-custom-text").value.trim();
    const statusEl = document.getElementById("idle-save-status");

    if (enabled && !this._imagePath) {
      UI.showToast("Upload a background image first", TOAST_TYPES.ERROR);
      return;
    }

    try {
      await API.saveIdleConfig({
        enabled,
        image_path: this._imagePath,
        custom_text: customText,
      });
      statusEl.textContent = "Saved ✓";
      setTimeout(() => (statusEl.textContent = ""), 3000);
      UI.showToast("Idle screen settings saved", TOAST_TYPES.SUCCESS);
    } catch (e) {
      UI.showToast(`Save failed: ${e.message}`, TOAST_TYPES.ERROR);
    }
  },

  async stopAndRestore() {
    try {
      await API.stopIdle();
      UI.showToast("Idle screen stopped, terminal restored", TOAST_TYPES.SUCCESS);
    } catch (e) {
      UI.showToast(`Failed to stop: ${e.message}`, TOAST_TYPES.ERROR);
    }
  },

  initUploadZone() {
    const zone = document.getElementById("idle-upload-zone");
    const input = document.getElementById("idle-file-input");

    zone.addEventListener("click", (e) => {
      if (e.target !== input) input.click();
    });

    input.addEventListener("change", () => {
      if (input.files[0]) {
        IdleManager.uploadBackground(input.files[0]);
        input.value = "";
      }
    });
  },
};
