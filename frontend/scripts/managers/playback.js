/**
 * Playback Control
 * Handles slideshow start and stop
 */

const PlaybackControl = {
  /**
   * Start playback
   */
  async start() {
    if (!AppState.selectedPlaylistId) {
      UI.showToast("Please select a playlist first", TOAST_TYPES.WARNING);
      return;
    }

    UI.showLoading();

    const data = await API.startPlayback(AppState.selectedPlaylistId);

    UI.hideLoading();

    if (data && data.status === "started") {
      UI.showToast("Slideshow started", TOAST_TYPES.SUCCESS);
      StatusManager.refresh();
      setTimeout(() => PlaylistManager.load(), 500); // Refresh playlists to show playing state
    } else {
      UI.showToast(
        data?.message || "Failed to start slideshow",
        TOAST_TYPES.ERROR,
      );
    }
  },

  /**
   * Stop playback
   */
  async stop() {
    UI.showLoading();

    const data = await API.stopPlayback();

    UI.hideLoading();

    if (data && data.status === "stopped") {
      UI.showToast("Slideshow stopped", TOAST_TYPES.SUCCESS);
      StatusManager.refresh();
      setTimeout(() => PlaylistManager.load(), 500);
    } else {
      UI.showToast(
        data?.message || "Failed to stop slideshow",
        TOAST_TYPES.ERROR,
      );
    }
  },
};
