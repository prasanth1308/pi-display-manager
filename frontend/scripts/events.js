/**
 * Event Listeners
 * Binds all UI events to their handlers
 */

const EventListeners = {
  /**
   * Initialize all event listeners
   */
  init() {
    // Playback controls
    DOM.playBtn.addEventListener("click", () => PlaybackControl.start());
    DOM.stopBtn.addEventListener("click", () => PlaybackControl.stop());

    // Playlist controls
    DOM.newPlaylistBtn.addEventListener("click", () =>
      PlaylistManager.showCreateModal(),
    );
    DOM.createPlaylistBtn.addEventListener("click", () =>
      PlaylistManager.create(),
    );
    DOM.cancelPlaylistBtn.addEventListener("click", () =>
      PlaylistManager.hideCreateModal(),
    );

    // Content controls
    DOM.uploadImageBtn.addEventListener("click", () => DOM.fileInput.click());
    DOM.downloadVideoTriggerBtn.addEventListener("click", () =>
      VideoManager.showDownloadModal(),
    );
    DOM.closeImagesBtn.addEventListener("click", () => ContentManager.close());

    // Video download
    DOM.downloadVideoBtn.addEventListener("click", () =>
      VideoManager.startDownload(),
    );
    DOM.cancelVideoBtn.addEventListener("click", () =>
      VideoManager.hideDownloadModal(),
    );

    // File upload
    DOM.fileInput.addEventListener("change", (e) => ImageManager.upload(e));

    // Modal interactions
    DOM.playlistModal.addEventListener("click", (e) => {
      if (e.target === DOM.playlistModal) PlaylistManager.hideCreateModal();
    });

    DOM.videoModal.addEventListener("click", (e) => {
      if (e.target === DOM.videoModal) VideoManager.hideDownloadModal();
    });

    document
      .querySelector(".close")
      .addEventListener("click", () => PlaylistManager.hideCreateModal());
    document
      .querySelector(".close-video")
      .addEventListener("click", () => VideoManager.hideDownloadModal());

    // Keyboard shortcuts
    DOM.playlistNameInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") PlaylistManager.create();
    });

    DOM.videoUrlInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") VideoManager.startDownload();
    });

    // Idle screen
    DOM.idleSaveBtn.addEventListener("click", () => IdleManager.save());
    IdleManager.initUploadZone();
  },
};
