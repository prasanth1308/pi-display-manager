/**
 * UI Utilities
 * Common UI functions and helpers
 */

const UI = {
  /**
   * Show loading overlay
   */
  showLoading() {
    DOM.loadingOverlay.style.display = "flex";
  },

  /**
   * Hide loading overlay
   */
  hideLoading() {
    DOM.loadingOverlay.style.display = "none";
  },

  /**
   * Show toast notification
   */
  showToast(message, type = TOAST_TYPES.INFO) {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;

    DOM.toastContainer.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
      toast.style.animation = "fadeOut 0.3s";
      setTimeout(() => toast.remove(), 300);
    }, CONFIG.TOAST_DURATION);
  },

  /**
   * Update status display
   */
  updateStatusDisplay(status) {
    // Update status badge
    if (status.running) {
      DOM.statusBadge.textContent = "Playing";
      DOM.statusBadge.classList.add("running");
      DOM.playBtn.disabled = true;
      DOM.stopBtn.disabled = false;
    } else {
      DOM.statusBadge.textContent = "Stopped";
      DOM.statusBadge.classList.remove("running");
      DOM.playBtn.disabled = AppState.selectedPlaylistId === null;
      DOM.stopBtn.disabled = true;
    }

    // Update active playlist
    DOM.activePlaylistSpan.textContent = status.current_playlist || "None";

    // Update image count
    DOM.imageCountSpan.textContent = status.image_count || 0;
  },

  /**
   * Update playlist card selection UI
   */
  updatePlaylistSelection(selectedId) {
    document.querySelectorAll(".playlist-card").forEach((card) => {
      card.style.outline =
        card.dataset.playlistId === selectedId ? "3px solid #2563eb" : "none";
    });
  },

  /**
   * Show/hide content buttons based on playlist type
   */
  updateContentButtons(playlistType) {
    if (playlistType === CONTENT_TYPES.VIDEO) {
      DOM.uploadImageBtn.style.display = "inline-flex";
      DOM.uploadImageBtn.textContent = "📤 Upload Video";
      DOM.downloadVideoTriggerBtn.style.display = "inline-flex";
      DOM.videoUploadNote.style.display = "block";
    } else {
      DOM.uploadImageBtn.style.display = "inline-flex";
      DOM.uploadImageBtn.textContent = "📤 Upload Images";
      DOM.downloadVideoTriggerBtn.style.display = "none";
      DOM.videoUploadNote.style.display = "none";
    }
  },

  /**
   * Show progress bar with status
   */
  showProgress(message, progress = 0, details = "") {
    DOM.playlistDownloadStatus.style.display = "block";
    DOM.playlistDownloadStatus.querySelector(".status-message").textContent =
      message;
    DOM.playlistProgressBar.style.width = `${progress}%`;
    DOM.playlistProgressBar.setAttribute(
      "data-progress",
      `${progress.toFixed(1)}%`,
    );
    if (DOM.playlistProgressDetails) {
      DOM.playlistProgressDetails.textContent = details;
    }
  },

  /**
   * Hide progress bar
   */
  hideProgress() {
    DOM.playlistDownloadStatus.style.display = "none";
    DOM.playlistProgressBar.style.width = "0%";
    DOM.playlistProgressBar.setAttribute("data-progress", "0%");
    if (DOM.playlistProgressDetails) {
      DOM.playlistProgressDetails.textContent = "";
    }
  },

  /**
   * Escape HTML to prevent XSS
   */
  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  },

  /**
   * Format duration in seconds to readable format
   */
  formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    }
    return `${minutes}:${String(secs).padStart(2, "0")}`;
  },
};
