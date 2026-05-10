/**
 * ScheduleManager
 * Handles playlist scheduling with a friendly time/repeat UI.
 * Converts to/from 5-field cron internally.
 */

const ScheduleManager = {
  _playlists: [],

  // ── Data loading ──────────────────────────────────────────────────────────

  async load() {
    try {
      const [schedules, playlistsRes] = await Promise.all([
        API.getSchedules(),
        API.getPlaylists(),
      ]);
      this._playlists = playlistsRes?.playlists || [];
      this._updateNewButton();
      this._render(Array.isArray(schedules) ? schedules : []);
    } catch (e) {
      console.error("Failed to load schedules:", e);
    }
  },

  _updateNewButton() {
    const hasPlaylists = this._playlists.length > 0;
    DOM.newScheduleBtn.disabled = !hasPlaylists;
    let hint = document.getElementById("schedules-no-playlist-hint");
    if (!hasPlaylists) {
      if (!hint) {
        hint = document.createElement("p");
        hint.id = "schedules-no-playlist-hint";
        hint.className = "help-text";
        hint.style.marginTop = "8px";
        hint.textContent = "Create a playlist first before adding schedules.";
        DOM.newScheduleBtn.insertAdjacentElement("afterend", hint);
      }
    } else if (hint) {
      hint.remove();
    }
  },

  // ── Rendering ─────────────────────────────────────────────────────────────

  _render(schedules) {
    const container = DOM.schedulesContainer;
    if (!schedules.length) {
      container.innerHTML =
        '<div class="empty-state">No schedules yet. Click "+ New Schedule" to add one.</div>';
      return;
    }
    container.innerHTML = schedules
      .map(
        (s) => `
      <div class="schedule-card" data-id="${s.id}">
        <div class="schedule-header">
          <span class="schedule-name">${s.name}</span>
          <label class="toggle-switch">
            <input type="checkbox" ${s.enabled ? "checked" : ""}
              onchange="ScheduleManager.toggleEnabled('${s.id}', this.checked)">
            <span class="toggle-track"></span>
          </label>
        </div>
        <div class="schedule-info">
          <span class="schedule-desc">${this._describeSchedule(s.cron)}</span>
          <span class="schedule-playlist">${this._playlistName(s.playlist_id)}</span>
        </div>
        <div class="schedule-footer">
          <button class="btn btn-secondary btn-sm" onclick="ScheduleManager.showEditModal('${s.id}')">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="ScheduleManager.delete('${s.id}')">Delete</button>
        </div>
      </div>`,
      )
      .join("");
  },

  _playlistName(id) {
    const p = this._playlists.find((p) => p.id === id);
    return p ? p.name : "Unknown playlist";
  },

  // ── Cron helpers ─────────────────────────────────────────────────────────

  _buildCron() {
    const type = document.getElementById("schedule-type").value;
    const time = DOM.scheduleTimeInput.value || "08:00";
    const [hourStr, minStr] = time.split(":");
    const hour = parseInt(hourStr, 10);
    const min = parseInt(minStr, 10);

    if (type === "daily") {
      return `${min} ${hour} * * *`;
    }

    if (type === "weekly") {
      const days = Array.from(
        document.querySelectorAll('input[name="sched-day"]:checked'),
      ).map((cb) => cb.value);
      if (!days.length) return null;
      return `${min} ${hour} * * ${days.join(",")}`;
    }

    if (type === "once") {
      const dateStr = document.getElementById("schedule-date").value;
      if (!dateStr) return null;
      // Parse date string manually to avoid timezone issues
      const [year, month, day] = dateStr.split("-").map(Number);
      return `${min} ${hour} ${day} ${month} *`;
    }

    return null;
  },

  _parseCronToUI(cron) {
    const parts = cron.trim().split(/\s+/);
    if (parts.length !== 5)
      return { type: "daily", time: "08:00", date: "", days: [] };

    const [min, hour, dom, month, dow] = parts;
    const time = `${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;

    if (dom !== "*" && month !== "*") {
      // once — reconstruct date using current or next year
      const year = new Date().getFullYear();
      let d = new Date(year, parseInt(month, 10) - 1, parseInt(dom, 10));
      if (d < new Date())
        d = new Date(year + 1, parseInt(month, 10) - 1, parseInt(dom, 10));
      const date = d.toISOString().split("T")[0];
      return { type: "once", time, date, days: [] };
    }

    if (dow !== "*") {
      return { type: "weekly", time, date: "", days: dow.split(",") };
    }

    return { type: "daily", time, date: "", days: [] };
  },

  _describeSchedule(cron) {
    try {
      const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const { type, time, date, days } = this._parseCronToUI(cron);
      const t = this._formatTime(time);

      if (type === "daily") return `Every day at ${t}`;
      if (type === "once") return `Once on ${date} at ${t}`;
      if (type === "weekly") {
        const sorted = [...days].sort((a, b) => Number(a) - Number(b));
        const names = sorted.map((d) => DAY_NAMES[parseInt(d, 10)]).join(", ");
        return `${names} at ${t}`;
      }
    } catch (_) {}
    return cron;
  },

  _formatTime(hhmm) {
    const [h, m] = hhmm.split(":");
    const hour = parseInt(h, 10);
    const ampm = hour >= 12 ? "PM" : "AM";
    const h12 = hour % 12 || 12;
    return `${h12}:${m} ${ampm}`;
  },

  // ── Modal ─────────────────────────────────────────────────────────────────

  _showTypeFields(type) {
    document.getElementById("schedule-days-wrap").style.display =
      type === "weekly" ? "block" : "none";
    document.getElementById("schedule-date-wrap").style.display =
      type === "once" ? "block" : "none";
  },

  _populatePlaylistSelect() {
    DOM.schedulePlaylistSelect.innerHTML = this._playlists
      .map((p) => `<option value="${p.id}">${p.name}</option>`)
      .join("");
  },

  showCreateModal() {
    this._populatePlaylistSelect();
    document.getElementById("schedule-modal-title").textContent =
      "New Schedule";
    document.getElementById("schedule-id").value = "";
    DOM.scheduleNameInput.value = "";
    DOM.scheduleTimeInput.value = "08:00";
    document.getElementById("schedule-type").value = "daily";
    document.getElementById("schedule-date").value = "";
    document
      .querySelectorAll('input[name="sched-day"]')
      .forEach((cb) => (cb.checked = false));
    document.getElementById("schedule-enabled").checked = true;
    this._showTypeFields("daily");
    DOM.scheduleModal.classList.add("show");
  },

  showEditModal(id) {
    API.getSchedule(id).then((s) => {
      this._populatePlaylistSelect();
      document.getElementById("schedule-modal-title").textContent =
        "Edit Schedule";
      document.getElementById("schedule-id").value = s.id;
      DOM.scheduleNameInput.value = s.name;
      DOM.schedulePlaylistSelect.value = s.playlist_id;
      document.getElementById("schedule-enabled").checked = s.enabled;

      const ui = this._parseCronToUI(s.cron);
      document.getElementById("schedule-type").value = ui.type;
      DOM.scheduleTimeInput.value = ui.time;
      document.getElementById("schedule-date").value = ui.date;
      document.querySelectorAll('input[name="sched-day"]').forEach((cb) => {
        cb.checked = ui.days.includes(cb.value);
      });
      this._showTypeFields(ui.type);
      DOM.scheduleModal.classList.add("show");
    });
  },

  hideModal() {
    DOM.scheduleModal.classList.remove("show");
  },

  // ── CRUD ──────────────────────────────────────────────────────────────────

  async save() {
    const id = document.getElementById("schedule-id").value;
    const type = document.getElementById("schedule-type").value;
    const cron = this._buildCron();

    if (!DOM.scheduleNameInput.value.trim()) {
      UI.showToast("Enter a name", TOAST_TYPES.ERROR);
      return;
    }
    if (!DOM.schedulePlaylistSelect.value) {
      UI.showToast("Select a playlist", TOAST_TYPES.ERROR);
      return;
    }
    if (!cron) {
      const msg =
        type === "weekly" ? "Select at least one day" : "Select a date";
      UI.showToast(msg, TOAST_TYPES.ERROR);
      return;
    }

    const data = {
      name: DOM.scheduleNameInput.value.trim(),
      playlist_id: DOM.schedulePlaylistSelect.value,
      cron,
      enabled: document.getElementById("schedule-enabled").checked,
    };

    try {
      if (id) {
        await API.updateSchedule(id, data);
        UI.showToast("Schedule updated", TOAST_TYPES.SUCCESS);
      } else {
        await API.createSchedule(data);
        UI.showToast("Schedule created", TOAST_TYPES.SUCCESS);
      }
      this.hideModal();
      this.load();
    } catch (e) {
      UI.showToast(`Save failed: ${e.message}`, TOAST_TYPES.ERROR);
    }
  },

  async toggleEnabled(id, enabled) {
    try {
      await API.updateSchedule(id, { enabled });
      UI.showToast(
        enabled ? "Schedule enabled" : "Schedule disabled",
        TOAST_TYPES.SUCCESS,
      );
    } catch (e) {
      UI.showToast(`Failed to update: ${e.message}`, TOAST_TYPES.ERROR);
      this.load();
    }
  },

  async delete(id) {
    if (!confirm("Delete this schedule?")) return;
    try {
      await API.deleteSchedule(id);
      UI.showToast("Schedule deleted", TOAST_TYPES.SUCCESS);
      this.load();
    } catch (e) {
      UI.showToast(`Delete failed: ${e.message}`, TOAST_TYPES.ERROR);
    }
  },
};
