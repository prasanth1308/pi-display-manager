/**
 * Status Manager
 * Handles status refresh and display
 */

const StatusManager = {
  /**
   * Refresh status from server
   */
  async refresh() {
    const data = await API.getStatus();
    if (!data) return;

    AppState.updateStatus(data);
    UI.updateStatusDisplay(data);
  },

  /**
   * Start auto-refresh
   */
  startAutoRefresh() {
    setInterval(() => this.refresh(), CONFIG.STATUS_REFRESH_INTERVAL);
  },
};
