/**
 * Playlist Manager
 * Handles playlist CRUD operations
 */

const PlaylistManager = {
  currentEditPlaylistId: null,

  /**
   * Load and display all playlists
   */
  async load() {
    const data = await API.getPlaylists();
    if (!data || !data.playlists) return;

    this.display(data.playlists);
  },

  /**
   * Display playlists in the UI
   */
  display(playlists) {
    if (playlists.length === 0) {
      DOM.playlistsContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📁</div>
          <div class="empty-state-text">No playlists yet</div>
          <div class="empty-state-subtext">Create your first playlist to get started</div>
        </div>
      `;
      return;
    }

    DOM.playlistsContainer.innerHTML = "";

    playlists.forEach((playlist) => {
      const card = this.createCard(playlist);
      DOM.playlistsContainer.appendChild(card);
    });
  },

  /**
   * Create a playlist card element
   */
  createCard(playlist) {
    const card = document.createElement("div");
    card.className = "playlist-card";
    card.dataset.playlistId = playlist.id;
    card.dataset.playlistType = playlist.type || CONTENT_TYPES.IMAGE;

    if (playlist.is_active) card.classList.add("active");
    if (playlist.is_playing) card.classList.add("playing");

    const badges = [];
    if (playlist.is_playing)
      badges.push('<span class="mini-badge playing">▶ Playing</span>');
    if (playlist.is_active)
      badges.push('<span class="mini-badge active">✓ Active</span>');

    const isVideo = playlist.type === CONTENT_TYPES.VIDEO;
    const config = PLAYLIST_TYPE_CONFIG[playlist.type || CONTENT_TYPES.IMAGE];
    const contentCount = isVideo
      ? playlist.video_count || 0
      : playlist.image_count || 0;
    const contentLabel = isVideo
      ? `${contentCount} video${contentCount !== 1 ? "s" : ""}`
      : `${contentCount} image${contentCount !== 1 ? "s" : ""}`;

    const typeBadge = `<span class="type-badge ${playlist.type || "image"}">${config.badge}</span>`;

    card.innerHTML = `
      <div class="playlist-header">
        <div class="playlist-name">${config.icon} ${UI.escapeHtml(playlist.name)}</div>
        <div class="playlist-actions">
          ${playlist.id !== "default" ? '<button class="icon-btn edit-playlist" title="Edit Settings">⚙️</button>' : ""}
          ${playlist.id !== "default" ? '<button class="icon-btn delete-playlist" title="Delete">🗑️</button>' : ""}
        </div>
      </div>
      <div class="playlist-info">
        ${typeBadge}
        <span>${contentLabel}</span>
        ${!isVideo ? `<span>⏱️ ${playlist.delay || 5}s</span>` : ""}
      </div>
      <div class="playlist-badges">
        ${badges.join("")}
      </div>
    `;

    // Click to select and view content
    card.addEventListener("click", (e) => {
      if (
        !e.target.classList.contains("delete-playlist") &&
        !e.target.classList.contains("edit-playlist")
      ) {
        this.select(playlist.id, playlist.type || CONTENT_TYPES.IMAGE);
        ContentManager.show(
          playlist.id,
          playlist.name,
          playlist.type || CONTENT_TYPES.IMAGE,
        );
      }
    });

    // Edit button
    const editBtn = card.querySelector(".edit-playlist");
    if (editBtn) {
      editBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.edit(playlist);
      });
    }

    // Delete button
    const deleteBtn = card.querySelector(".delete-playlist");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.delete(playlist.id);
      });
    }

    return card;
  },

  /**
   * Select a playlist
   */
  select(playlistId, playlistType = CONTENT_TYPES.IMAGE) {
    AppState.setSelectedPlaylist(playlistId, playlistType);
    UI.updatePlaylistSelection(playlistId);

    // Enable play button if not running
    if (!AppState.currentStatus.running) {
      DOM.playBtn.disabled = false;
    }
  },

  /**
   * Show create playlist modal
   */
  showCreateModal() {
    DOM.playlistNameInput.value = "";
    DOM.playlistModal.classList.add("show");
    DOM.playlistNameInput.focus();
  },

  /**
   * Hide create playlist modal
   */
  hideCreateModal() {
    DOM.playlistModal.classList.remove("show");
  },

  /**
   * Show edit playlist modal
   */
  showEditModal(playlist) {
    this.currentEditPlaylistId = playlist.id;
    DOM.editPlaylistNameInput.value = playlist.name;
    DOM.editPlaylistDelayInput.value = playlist.delay || 5;
    DOM.editPlaylistModal.classList.add("show");
    DOM.editPlaylistNameInput.focus();
  },

  /**
   * Hide edit playlist modal
   */
  hideEditModal() {
    DOM.editPlaylistModal.classList.remove("show");
    this.currentEditPlaylistId = null;
  },

  /**
   * Create a new playlist
   */
  async create() {
    const name = DOM.playlistNameInput.value.trim();
    const type = DOM.playlistTypeSelect.value;
    const delay = parseInt(DOM.playlistDelayInput.value) || 5;

    if (!name) {
      UI.showToast("Please enter a playlist name", TOAST_TYPES.WARNING);
      return;
    }

    UI.showLoading();

    const data = await API.createPlaylist(name, type, delay);

    UI.hideLoading();

    if (data && data.status === "success") {
      UI.showToast(
        `${type === CONTENT_TYPES.VIDEO ? "Video" : "Image"} playlist created successfully`,
        TOAST_TYPES.SUCCESS,
      );
      this.hideCreateModal();
      this.load();
    } else {
      UI.showToast(
        data?.message || "Failed to create playlist",
        TOAST_TYPES.ERROR,
      );
    }
  },

  /**
   * Edit playlist settings
   */
  async edit(playlist) {
    this.showEditModal(playlist);
  },

  /**
   * Save edited playlist settings
   */
  async saveEdit() {
    const newName = DOM.editPlaylistNameInput.value.trim();
    const delayValue = DOM.editPlaylistDelayInput.value.trim();

    // Validate name
    if (!newName) {
      UI.showToast("Playlist name cannot be empty", TOAST_TYPES.WARNING);
      DOM.editPlaylistNameInput.focus();
      return;
    }

    // Validate delay
    const delay = parseInt(delayValue);
    if (isNaN(delay) || delay < 1 || delay > 60) {
      UI.showToast(
        "Delay must be between 1 and 60 seconds",
        TOAST_TYPES.WARNING,
      );
      DOM.editPlaylistDelayInput.focus();
      return;
    }

    UI.showLoading();

    const data = await API.updatePlaylist(this.currentEditPlaylistId, {
      name: newName,
      delay: delay,
    });

    UI.hideLoading();

    if (data && data.status === "success") {
      UI.showToast("Playlist updated successfully", TOAST_TYPES.SUCCESS);
      this.hideEditModal();
      this.load();
    } else {
      UI.showToast(
        data?.message || "Failed to update playlist",
        TOAST_TYPES.ERROR,
      );
    }
  },

  /**
   * Delete a playlist
   */
  async delete(playlistId) {
    if (
      !confirm(
        "Are you sure you want to delete this playlist? All content will be removed.",
      )
    ) {
      return;
    }

    UI.showLoading();

    const data = await API.deletePlaylist(playlistId);

    UI.hideLoading();

    if (data && data.status === "success") {
      UI.showToast("Playlist deleted successfully", TOAST_TYPES.SUCCESS);
      if (AppState.selectedPlaylistId === playlistId) {
        AppState.clearSelectedPlaylist();
        ContentManager.close();
      }
      this.load();
    } else {
      UI.showToast(
        data?.message || "Failed to delete playlist",
        TOAST_TYPES.ERROR,
      );
    }
  },
};
