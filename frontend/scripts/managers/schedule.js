/**
 * ScheduleManager
 * Handles cron-based playlist scheduling: list, create, edit, delete, toggle.
 */

const ScheduleManager = {
  _playlists: [],

  async load() {
    try {
      const [schedules, playlistsRes] = await Promise.all([
        API.getSchedules(),
        API.getPlaylists(),
      ]);
      // getPlaylists returns { status, playlists: [...] }
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

  _render(schedules) {
    const container = DOM.schedulesContainer;
    if (!schedules.length) {
      container.innerHTML = '<div class="empty-state">No schedules yet. Click "+ New Schedule" to add one.</div>';
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
          <span class="schedule-cron">${s.cron}</span>
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

  _populatePlaylistSelect() {
    DOM.schedulePlaylistSelect.innerHTML = this._playlists
      .map((p) => `<option value="${p.id}">${p.name}</option>`)
      .join("");
  },

  showCreateModal() {
    this._populatePlaylistSelect();
    document.getElementById("schedule-modal-title").textContent = "New Schedule";
    document.getElementById("schedule-id").value = "";
    DOM.scheduleNameInput.value = "";
    DOM.scheduleCronInput.value = "";
    if (this._playlists.length) DOM.schedulePlaylistSelect.value = this._playlists[0].id;
    document.getElementById("schedule-enabled").checked = true;
    DOM.scheduleModal.classList.add("show");
  },

  showEditModal(id) {
    API.getSchedule(id).then((s) => {
      this._populatePlaylistSelect();
      document.getElementById("schedule-modal-title").textContent = "Edit Schedule";
      document.getElementById("schedule-id").value = s.id;
      DOM.scheduleNameInput.value = s.name;
      DOM.scheduleCronInput.value = s.cron;
      DOM.schedulePlaylistSelect.value = s.playlist_id;
      document.getElementById("schedule-enabled").checked = s.enabled;
      DOM.scheduleModal.classList.add("show");
    });
  },

  hideModal() {
    DOM.scheduleModal.classList.remove("show");
  },

  async save() {
    const id = document.getElementById("schedule-id").value;
    const data = {
      name: DOM.scheduleNameInput.value.trim(),
      playlist_id: DOM.schedulePlaylistSelect.value,
      cron: DOM.scheduleCronInput.value.trim(),
      enabled: document.getElementById("schedule-enabled").checked,
    };

    if (!data.name || !data.playlist_id || !data.cron) {
      UI.showToast("Fill in all fields", TOAST_TYPES.ERROR);
      return;
    }

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
      UI.showToast(enabled ? "Schedule enabled" : "Schedule disabled", TOAST_TYPES.SUCCESS);
    } catch (e) {
      UI.showToast(`Failed to update: ${e.message}`, TOAST_TYPES.ERROR);
      this.load(); // re-render to restore checkbox state
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
