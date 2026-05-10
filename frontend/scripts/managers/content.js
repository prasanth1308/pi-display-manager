/**
 * Content Manager
 * Coordinates content display for images and videos
 */

const ContentManager = {
  /**
   * Show content section for a playlist
   */
  async show(playlistId, playlistName, playlistType) {
    DOM.selectedPlaylistName.textContent = playlistName;
    DOM.imagesSection.style.display = "block";

    UI.updateContentButtons(playlistType);

    if (playlistType === CONTENT_TYPES.VIDEO) {
      await VideoManager.load(playlistId);
    } else if (playlistType === CONTENT_TYPES.PDF) {
      await PDFManager.load(playlistId);
    } else {
      await ImageManager.load(playlistId);
    }
  },

  /**
   * Close content section
   */
  close() {
    DOM.imagesSection.style.display = "none";
    AppState.clearSelectedPlaylist();
    AppState.stopPolling();
    UI.hideProgress();
    UI.updatePlaylistSelection(null);
  },

  /**
   * Display empty state
   */
  displayEmpty(type) {
    const config = PLAYLIST_TYPE_CONFIG[type];
    DOM.imagesContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">${config.emptyIcon}</div>
        <div class="empty-state-text">${config.emptyText}</div>
        <div class="empty-state-subtext">${config.emptySubtext}</div>
      </div>
    `;
  },
};
