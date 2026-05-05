/**
 * Video Manager
 * Handles video download, display, and deletion
 */

const VideoManager = {
  /**
   * Load videos for a playlist
   */
  async load(playlistId) {
    const data = await API.getPlaylistVideos(playlistId);

    if (!data || data.status !== "success") {
      DOM.imagesContainer.innerHTML = "<p>Failed to load videos</p>";
      return;
    }

    this.display(data.videos, playlistId);
  },

  /**
   * Display videos
   */
  display(videos, playlistId) {
    if (videos.length === 0) {
      ContentManager.displayEmpty(CONTENT_TYPES.VIDEO);
      return;
    }

    DOM.imagesContainer.innerHTML = "";

    videos.forEach((video) => {
      const card = this.createCard(video, playlistId);
      DOM.imagesContainer.appendChild(card);
    });
  },

  /**
   * Create video card
   */
  createCard(video, playlistId) {
    const card = document.createElement("div");
    card.className = "image-card"; // Reuse image card styling

    const sizeMB = (video.size / (1024 * 1024)).toFixed(2);
    const duration = video.duration
      ? UI.formatDuration(video.duration)
      : "Unknown";

    card.innerHTML = `
      <div class="image-preview">📹</div>
      <div class="image-name" title="${UI.escapeHtml(video.filename)}">${UI.escapeHtml(video.filename)}</div>
      <div class="image-info">${sizeMB} MB • ${duration}</div>
      <div class="image-actions">
        <button class="btn btn-danger btn-sm delete-video">Delete</button>
      </div>
    `;

    card.querySelector(".delete-video").addEventListener("click", () => {
      this.delete(playlistId, video.filename);
    });

    return card;
  },

  /**
   * Show download modal
   */
  showDownloadModal() {
    DOM.videoUrlInput.value = "";
    DOM.downloadStatusDiv.style.display = "none";
    DOM.videoModal.classList.add("show");
    DOM.videoUrlInput.focus();
  },

  /**
   * Hide download modal
   */
  hideDownloadModal() {
    DOM.videoModal.classList.remove("show");
    DOM.videoUrlInput.value = "";
    DOM.downloadStatusDiv.style.display = "none";

    const progressBar = document.getElementById("download-progress-bar");
    const progressDetails = document.getElementById("progress-details");
    if (progressBar) {
      progressBar.style.width = "0%";
      progressBar.setAttribute("data-progress", "0%");
    }
    if (progressDetails) {
      progressDetails.textContent = "";
    }
  },

  /**
   * Start video download
   */
  async startDownload() {
    const url = DOM.videoUrlInput.value.trim();

    if (!url) {
      UI.showToast("Please enter a YouTube URL", TOAST_TYPES.WARNING);
      return;
    }

    if (!url.includes("youtube.com") && !url.includes("youtu.be")) {
      UI.showToast("Only YouTube URLs are supported", TOAST_TYPES.ERROR);
      return;
    }

    if (!AppState.selectedPlaylistId) {
      UI.showToast("Please select a playlist first", TOAST_TYPES.WARNING);
      return;
    }

    const data = await API.downloadVideo(AppState.selectedPlaylistId, url);

    if (data && data.status === "started") {
      const downloadId = data.download_id;
      UI.showToast("Download started", TOAST_TYPES.INFO);

      this.hideDownloadModal();

      UI.showProgress("Starting download...", 0);

      // Start polling for download status
      AppState.startPolling(() => this.pollStatus(downloadId));
    } else {
      UI.showToast(
        data?.message || "Failed to start download",
        TOAST_TYPES.ERROR,
      );
    }
  },

  /**
   * Poll download status
   */
  async pollStatus(downloadId) {
    const data = await API.getDownloadStatus(downloadId);

    if (!data) {
      AppState.stopPolling();
      return;
    }

    if (data.status === "downloading") {
      const progress = data.progress || 0;
      const title = data.title || "Video";

      let details = [];
      if (data.speed) details.push(`Speed: ${data.speed}`);
      if (data.eta) details.push(`ETA: ${data.eta}`);

      UI.showProgress(`Downloading: ${title}`, progress, details.join(" | "));
    } else if (data.status === "completed") {
      UI.showProgress("Download complete!", 100);
      UI.showToast("Video downloaded successfully", TOAST_TYPES.SUCCESS);

      AppState.stopPolling();

      // Refresh video list and playlists
      this.load(AppState.selectedPlaylistId);
      PlaylistManager.load();

      // Hide progress after delay
      setTimeout(() => UI.hideProgress(), CONFIG.PROGRESS_HIDE_DELAY);
    } else if (data.status === "error") {
      UI.showProgress(`Error: ${data.message || "Download failed"}`, 0);
      UI.showToast("Download failed", TOAST_TYPES.ERROR);

      AppState.stopPolling();

      // Hide progress after delay
      setTimeout(() => UI.hideProgress(), CONFIG.PROGRESS_HIDE_DELAY);
    }
  },

  /**
   * Delete a video
   */
  async delete(playlistId, filename) {
    if (!confirm(`Delete ${filename}?`)) return;

    UI.showLoading();

    const data = await API.deleteVideo(playlistId, filename);

    UI.hideLoading();

    if (data && data.status === "success") {
      UI.showToast("Video deleted successfully", TOAST_TYPES.SUCCESS);
      this.load(playlistId);
      PlaylistManager.load(); // Refresh to update counts
    } else {
      UI.showToast(
        data?.message || "Failed to delete video",
        TOAST_TYPES.ERROR,
      );
    }
  },
};
