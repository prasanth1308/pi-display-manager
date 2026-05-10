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
    DOM.playlistTypeSelect.addEventListener("change", () =>
      PlaylistManager.toggleDelayVisibility(),
    );

    // Edit playlist controls
    document
      .getElementById("save-edit-playlist-btn")
      .addEventListener("click", () => PlaylistManager.saveEdit());
    document
      .getElementById("cancel-edit-playlist-btn")
      .addEventListener("click", () => PlaylistManager.hideEditModal());

    // Content controls
    DOM.uploadImageBtn.addEventListener("click", () => {
      // Set file accept type based on playlist type
      const playlistType = AppState.selectedPlaylistType;
      if (playlistType === CONTENT_TYPES.PDF) {
        DOM.fileInput.accept = ".pdf";
      } else if (playlistType === CONTENT_TYPES.PPT) {
        DOM.fileInput.accept = ".ppt,.pptx";
      } else if (playlistType === CONTENT_TYPES.VIDEO) {
        DOM.fileInput.accept = ".mp4,.avi,.mkv,.mov,.wmv,.flv,.webm";
      } else {
        DOM.fileInput.accept = "image/*";
      }
      DOM.fileInput.click();
    });
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
    DOM.fileInput.addEventListener("change", (e) => {
      const playlistType = AppState.selectedPlaylistType;
      if (playlistType === CONTENT_TYPES.PDF) {
        PDFManager.upload(e);
      } else if (playlistType === CONTENT_TYPES.PPT) {
        PPTManager.upload(e);
      } else if (playlistType === CONTENT_TYPES.VIDEO) {
        ImageManager.upload(e); // Video upload uses ImageManager
      } else {
        ImageManager.upload(e);
      }
    });

    // Modal interactions
    DOM.playlistModal.addEventListener("click", (e) => {
      if (e.target === DOM.playlistModal) PlaylistManager.hideCreateModal();
    });

    DOM.editPlaylistModal.addEventListener("click", (e) => {
      if (e.target === DOM.editPlaylistModal) PlaylistManager.hideEditModal();
    });

    DOM.videoModal.addEventListener("click", (e) => {
      if (e.target === DOM.videoModal) VideoManager.hideDownloadModal();
    });

    document
      .querySelector(".close")
      .addEventListener("click", () => PlaylistManager.hideCreateModal());
    DOM.editPlaylistModal
      .querySelector(".close")
      .addEventListener("click", () => PlaylistManager.hideEditModal());
    document
      .querySelector(".close-video")
      .addEventListener("click", () => VideoManager.hideDownloadModal());

    // Keyboard shortcuts
    DOM.playlistNameInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") PlaylistManager.create();
    });

    DOM.editPlaylistNameInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") PlaylistManager.saveEdit();
    });

    DOM.editPlaylistDelayInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") PlaylistManager.saveEdit();
    });

    DOM.videoUrlInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") VideoManager.startDownload();
    });

    // Idle screen
    DOM.idleSaveBtn.addEventListener("click", () => IdleManager.save());
    IdleManager.initUploadZone();

    // Scheduler
    DOM.newScheduleBtn.addEventListener("click", () =>
      ScheduleManager.showCreateModal(),
    );
    DOM.createScheduleBtn.addEventListener("click", () =>
      ScheduleManager.save(),
    );
    DOM.cancelScheduleBtn.addEventListener("click", () =>
      ScheduleManager.hideModal(),
    );
    DOM.scheduleModal.addEventListener("click", (e) => {
      if (e.target === DOM.scheduleModal) ScheduleManager.hideModal();
    });
    document
      .querySelector(".close-schedule")
      .addEventListener("click", () => ScheduleManager.hideModal());
  },
};
