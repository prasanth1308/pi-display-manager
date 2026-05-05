/**
 * Application State Management
 * Centralized state for the application
 */

const AppState = {
  selectedPlaylistId: null,
  selectedPlaylistType: null,
  currentStatus: {},
  downloadPollingInterval: null,

  /**
   * Set the currently selected playlist
   */
  setSelectedPlaylist(id, type) {
    this.selectedPlaylistId = id;
    this.selectedPlaylistType = type;
  },

  /**
   * Clear the selected playlist
   */
  clearSelectedPlaylist() {
    this.selectedPlaylistId = null;
    this.selectedPlaylistType = null;
  },

  /**
   * Update current status
   */
  updateStatus(status) {
    this.currentStatus = status;
  },

  /**
   * Start polling with a callback
   */
  startPolling(callback, interval = CONFIG.POLLING_INTERVAL) {
    this.stopPolling();
    this.downloadPollingInterval = setInterval(callback, interval);
  },

  /**
   * Stop polling
   */
  stopPolling() {
    if (this.downloadPollingInterval) {
      clearInterval(this.downloadPollingInterval);
      this.downloadPollingInterval = null;
    }
  },
};
