/**
 * DOM Element References
 * Centralized access to DOM elements
 */

const DOM = {
  // Buttons
  playBtn: document.getElementById("play-btn"),
  stopBtn: document.getElementById("stop-btn"),
  newPlaylistBtn: document.getElementById("new-playlist-btn"),
  uploadImageBtn: document.getElementById("upload-image-btn"),
  downloadVideoTriggerBtn: document.getElementById(
    "download-video-trigger-btn",
  ),
  closeImagesBtn: document.getElementById("close-images-btn"),
  createPlaylistBtn: document.getElementById("create-playlist-btn"),
  cancelPlaylistBtn: document.getElementById("cancel-playlist-btn"),
  downloadVideoBtn: document.getElementById("download-video-btn"),
  cancelVideoBtn: document.getElementById("cancel-video-btn"),

  // Inputs
  fileInput: document.getElementById("file-input"),
  playlistNameInput: document.getElementById("playlist-name"),
  playlistTypeSelect: document.getElementById("playlist-type"),
  videoUrlInput: document.getElementById("video-url"),

  // Containers
  playlistsContainer: document.getElementById("playlists-container"),
  imagesContainer: document.getElementById("images-container"),
  imagesSection: document.getElementById("images-section"),

  // Modals
  playlistModal: document.getElementById("playlist-modal"),
  videoModal: document.getElementById("video-modal"),

  // Status elements
  statusBadge: document.getElementById("status"),
  activePlaylistSpan: document.getElementById("active-playlist"),
  imageCountSpan: document.getElementById("image-count"),
  selectedPlaylistName: document.getElementById("selected-playlist-name"),

  // Progress & Loading
  downloadStatusDiv: document.getElementById("download-status"),
  loadingOverlay: document.getElementById("loading-overlay"),
  playlistDownloadStatus: document.getElementById("playlist-download-status"),
  playlistProgressBar: document.getElementById("playlist-progress-bar"),
  playlistProgressDetails: document.getElementById("playlist-progress-details"),

  // Toast container
  toastContainer: document.getElementById("toast-container"),

  // Idle screen
  idleSaveBtn: document.getElementById("idle-save-btn"),

  // Scheduler
  newScheduleBtn: document.getElementById("new-schedule-btn"),
  schedulesContainer: document.getElementById("schedules-container"),
  scheduleModal: document.getElementById("schedule-modal"),
  scheduleNameInput: document.getElementById("schedule-name"),
  schedulePlaylistSelect: document.getElementById("schedule-playlist"),
  scheduleCronInput: document.getElementById("schedule-cron"),
  createScheduleBtn: document.getElementById("create-schedule-btn"),
  cancelScheduleBtn: document.getElementById("cancel-schedule-btn"),
};
