// Pi Display Manager - Frontend JavaScript

// State
let selectedPlaylistId = null;
let selectedPlaylistType = null;
let currentStatus = {};
let downloadPollingInterval = null;

// DOM Elements
const playBtn = document.getElementById("play-btn");
const stopBtn = document.getElementById("stop-btn");
const newPlaylistBtn = document.getElementById("new-playlist-btn");
const uploadImageBtn = document.getElementById("upload-image-btn");
const downloadVideoTriggerBtn = document.getElementById(
  "download-video-trigger-btn",
);
const closeImagesBtn = document.getElementById("close-images-btn");
const fileInput = document.getElementById("file-input");
const playlistsContainer = document.getElementById("playlists-container");
const imagesContainer = document.getElementById("images-container");
const imagesSection = document.getElementById("images-section");
const playlistModal = document.getElementById("playlist-modal");
const videoModal = document.getElementById("video-modal");
const createPlaylistBtn = document.getElementById("create-playlist-btn");
const cancelPlaylistBtn = document.getElementById("cancel-playlist-btn");
const playlistNameInput = document.getElementById("playlist-name");
const playlistTypeSelect = document.getElementById("playlist-type");
const videoUrlInput = document.getElementById("video-url");
const downloadVideoBtn = document.getElementById("download-video-btn");
const cancelVideoBtn = document.getElementById("cancel-video-btn");
const downloadStatusDiv = document.getElementById("download-status");
const loadingOverlay = document.getElementById("loading-overlay");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  refreshStatus();
  loadPlaylists();

  // Auto-refresh status every 3 seconds
  setInterval(refreshStatus, 3000);
});

// Event Listeners
function initEventListeners() {
  playBtn.addEventListener("click", playSlideshow);
  stopBtn.addEventListener("click", stopSlideshow);
  newPlaylistBtn.addEventListener("click", showPlaylistModal);
  uploadImageBtn.addEventListener("click", () => fileInput.click());
  downloadVideoTriggerBtn.addEventListener("click", showVideoModal);
  closeImagesBtn.addEventListener("click", closeImagesView);
  createPlaylistBtn.addEventListener("click", createPlaylist);
  cancelPlaylistBtn.addEventListener("click", hidePlaylistModal);
  downloadVideoBtn.addEventListener("click", startVideoDownload);
  cancelVideoBtn.addEventListener("click", hideVideoModal);
  fileInput.addEventListener("change", handleFileUpload);

  // Modal close on background click
  playlistModal.addEventListener("click", (e) => {
    if (e.target === playlistModal) hidePlaylistModal();
  });

  videoModal.addEventListener("click", (e) => {
    if (e.target === videoModal) hideVideoModal();
  });

  // Modal close buttons
  document.querySelector(".close").addEventListener("click", hidePlaylistModal);
  document
    .querySelector(".close-video")
    .addEventListener("click", hideVideoModal);

  // Enter key in playlist name input
  playlistNameInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") createPlaylist();
  });

  // Enter key in video URL input
  videoUrlInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") startVideoDownload();
  });
}

// API Calls
async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(`/api${endpoint}`, options);
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("API call failed:", error);
    showToast(
      "Connection error. Please check if the service is running.",
      "error",
    );
    return null;
  }
}

// Status Management
async function refreshStatus() {
  const data = await apiCall("/status");
  if (!data) return;

  currentStatus = data;
  updateStatusDisplay(data);
}

function updateStatusDisplay(status) {
  const statusBadge = document.getElementById("status");
  const activePlaylistSpan = document.getElementById("active-playlist");
  const imageCountSpan = document.getElementById("image-count");

  // Update status badge
  if (status.running) {
    statusBadge.textContent = "Playing";
    statusBadge.classList.add("running");
    playBtn.disabled = true;
    stopBtn.disabled = false;
  } else {
    statusBadge.textContent = "Stopped";
    statusBadge.classList.remove("running");
    playBtn.disabled = selectedPlaylistId === null;
    stopBtn.disabled = true;
  }

  // Update active playlist
  if (status.current_playlist) {
    activePlaylistSpan.textContent = status.current_playlist;
  } else {
    activePlaylistSpan.textContent = "None";
  }

  // Update image count
  imageCountSpan.textContent = status.image_count || 0;
}

// Playlist Management
async function loadPlaylists() {
  const data = await apiCall("/playlists");
  if (!data || !data.playlists) return;

  displayPlaylists(data.playlists);
}

function displayPlaylists(playlists) {
  if (playlists.length === 0) {
    playlistsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📁</div>
                <div class="empty-state-text">No playlists yet</div>
                <div class="empty-state-subtext">Create your first playlist to get started</div>
            </div>
        `;
    return;
  }

  playlistsContainer.innerHTML = "";

  playlists.forEach((playlist) => {
    const card = createPlaylistCard(playlist);
    playlistsContainer.appendChild(card);
  });
}

function createPlaylistCard(playlist) {
  const card = document.createElement("div");
  card.className = "playlist-card";
  card.dataset.playlistId = playlist.id;
  card.dataset.playlistType = playlist.type || "image";

  if (playlist.is_active) card.classList.add("active");
  if (playlist.is_playing) card.classList.add("playing");

  const badges = [];
  if (playlist.is_playing)
    badges.push('<span class="mini-badge playing">▶ Playing</span>');
  if (playlist.is_active)
    badges.push('<span class="mini-badge active">✓ Active</span>');

  // Determine type badge and content count
  const isVideo = playlist.type === "video";
  const typeIcon = isVideo ? "📹" : "🖼️";
  const contentCount = isVideo
    ? playlist.video_count || 0
    : playlist.image_count || 0;
  const contentLabel = isVideo
    ? `${contentCount} video${contentCount !== 1 ? "s" : ""}`
    : `${contentCount} image${contentCount !== 1 ? "s" : ""}`;

  const typeBadge = isVideo
    ? '<span class="type-badge video">📹 Video</span>'
    : '<span class="type-badge image">🖼️ Image</span>';

  card.innerHTML = `
        <div class="playlist-header">
            <div class="playlist-name">${typeIcon} ${escapeHtml(playlist.name)}</div>
            <div class="playlist-actions">
                ${playlist.id !== "default" ? '<button class="icon-btn delete-playlist" title="Delete">🗑️</button>' : ""}
            </div>
        </div>
        <div class="playlist-info">
            ${typeBadge}
            <span>${contentLabel}</span>
        </div>
        <div class="playlist-badges">
            ${badges.join("")}
        </div>
    `;

  // Click to select and view content
  card.addEventListener("click", (e) => {
    if (!e.target.classList.contains("delete-playlist")) {
      selectPlaylist(playlist.id, playlist.type || "image");
      showPlaylistContent(playlist.id, playlist.name, playlist.type || "image");
    }
  });

  // Delete button
  const deleteBtn = card.querySelector(".delete-playlist");
  if (deleteBtn) {
    deleteBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deletePlaylist(playlist.id);
    });
  }

  return card;
}

function selectPlaylist(playlistId, playlistType = "image") {
  selectedPlaylistId = playlistId;
  selectedPlaylistType = playlistType;

  // Update UI
  document.querySelectorAll(".playlist-card").forEach((card) => {
    card.style.outline =
      card.dataset.playlistId === playlistId ? "3px solid #2563eb" : "none";
  });

  // Enable play button if not running
  if (!currentStatus.running) {
    playBtn.disabled = false;
  }
}

function showPlaylistModal() {
  playlistNameInput.value = "";
  playlistModal.classList.add("show");
  playlistNameInput.focus();
}

function hidePlaylistModal() {
  playlistModal.classList.remove("show");
}

async function createPlaylist() {
  const name = playlistNameInput.value.trim();
  const type = playlistTypeSelect.value;

  if (!name) {
    showToast("Please enter a playlist name", "warning");
    return;
  }

  showLoading();

  const data = await apiCall("/playlists/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, type }),
  });

  hideLoading();

  if (data && data.status === "success") {
    showToast(
      `${type === "video" ? "Video" : "Image"} playlist created successfully`,
      "success",
    );
    hidePlaylistModal();
    loadPlaylists();
  } else {
    showToast(data?.message || "Failed to create playlist", "error");
  }
}

async function deletePlaylist(playlistId) {
  if (
    !confirm(
      "Are you sure you want to delete this playlist? All images will be removed.",
    )
  ) {
    return;
  }

  showLoading();

  const data = await apiCall(`/playlists/${playlistId}`, {
    method: "DELETE",
  });

  hideLoading();

  if (data && data.status === "success") {
    showToast("Playlist deleted successfully", "success");
    if (selectedPlaylistId === playlistId) {
      selectedPlaylistId = null;
      closeImagesView();
    }
    loadPlaylists();
  } else {
    showToast(data?.message || "Failed to delete playlist", "error");
  }
}

// Content Management (Images/Videos)
async function showPlaylistContent(playlistId, playlistName, playlistType) {
  document.getElementById("selected-playlist-name").textContent = playlistName;
  imagesSection.style.display = "block";

  // Show/hide appropriate buttons based on playlist type
  if (playlistType === "video") {
    uploadImageBtn.style.display = "none";
    downloadVideoTriggerBtn.style.display = "inline-block";
  } else {
    uploadImageBtn.style.display = "inline-block";
    downloadVideoTriggerBtn.style.display = "none";
  }

  // Scroll to content section
  imagesSection.scrollIntoView({ behavior: "smooth" });

  if (playlistType === "video") {
    await loadPlaylistVideos(playlistId);
  } else {
    await loadPlaylistImages(playlistId);
  }
}

function closeImagesView() {
  imagesSection.style.display = "none";
  selectedPlaylistId = null;
  selectedPlaylistType = null;

  // Stop any download polling
  if (downloadPollingInterval) {
    clearInterval(downloadPollingInterval);
    downloadPollingInterval = null;
  }

  // Remove outlines from playlist cards
  document.querySelectorAll(".playlist-card").forEach((card) => {
    card.style.outline = "none";
  });
}

async function loadPlaylistImages(playlistId) {
  const data = await apiCall(`/playlists/${playlistId}/images`);

  if (!data || data.status !== "success") {
    imagesContainer.innerHTML = "<p>Failed to load images</p>";
    return;
  }

  displayImages(data.images, playlistId);
}

function displayImages(images, playlistId) {
  if (images.length === 0) {
    imagesContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🖼️</div>
                <div class="empty-state-text">No images in this playlist</div>
                <div class="empty-state-subtext">Upload images to get started</div>
            </div>
        `;
    return;
  }

  imagesContainer.innerHTML = "";

  images.forEach((image) => {
    const card = createImageCard(image, playlistId);
    imagesContainer.appendChild(card);
  });
}

function createImageCard(image, playlistId) {
  const card = document.createElement("div");
  card.className = "image-card";

  const sizeKB = Math.round(image.size / 1024);

  card.innerHTML = `
        <div class="image-preview">🖼️</div>
        <div class="image-name" title="${escapeHtml(image.filename)}">${escapeHtml(image.filename)}</div>
        <div class="image-info">${sizeKB} KB</div>
        <div class="image-actions">
            <button class="btn btn-danger btn-sm delete-image">Delete</button>
        </div>
    `;

  // Delete button
  card.querySelector(".delete-image").addEventListener("click", () => {
    deleteImage(playlistId, image.filename);
  });

  return card;
}

async function handleFileUpload(event) {
  const files = Array.from(event.target.files);

  if (files.length === 0) return;

  if (!selectedPlaylistId) {
    showToast("Please select a playlist first", "warning");
    return;
  }

  showLoading();

  let successCount = 0;
  let failCount = 0;

  for (const file of files) {
    const formData = new FormData();
    formData.append("image", file);

    const data = await apiCall(`/playlists/${selectedPlaylistId}/upload`, {
      method: "POST",
      body: formData,
    });

    if (data && data.status === "success") {
      successCount++;
    } else {
      failCount++;
    }
  }

  hideLoading();

  if (successCount > 0) {
    showToast(
      `${successCount} image${successCount !== 1 ? "s" : ""} uploaded successfully`,
      "success",
    );
    loadPlaylistImages(selectedPlaylistId);
    loadPlaylists(); // Refresh to update image counts
  }

  if (failCount > 0) {
    showToast(
      `${failCount} image${failCount !== 1 ? "s" : ""} failed to upload`,
      "error",
    );
  }

  // Reset file input
  fileInput.value = "";
}

async function deleteImage(playlistId, filename) {
  if (!confirm(`Delete ${filename}?`)) return;

  showLoading();

  const data = await apiCall(
    `/playlists/${playlistId}/images/${encodeURIComponent(filename)}`,
    {
      method: "DELETE",
    },
  );

  hideLoading();

  if (data && data.status === "success") {
    showToast("Image deleted successfully", "success");
    loadPlaylistImages(playlistId);
    loadPlaylists(); // Refresh to update image counts
  } else {
    showToast(data?.message || "Failed to delete image", "error");
  }
}

// Video Management
function showVideoModal() {
  videoUrlInput.value = "";
  downloadStatusDiv.style.display = "none";
  videoModal.classList.add("show");
  videoUrlInput.focus();
}

function hideVideoModal() {
  videoModal.classList.remove("show");
  if (downloadPollingInterval) {
    clearInterval(downloadPollingInterval);
    downloadPollingInterval = null;
  }

  // Reset progress bar and status
  videoUrlInput.value = "";
  downloadStatusDiv.style.display = "none";
  const progressBar = document.getElementById("download-progress-bar");
  const progressDetails = document.getElementById("progress-details");
  if (progressBar) {
    progressBar.style.width = "0%";
    progressBar.setAttribute("data-progress", "0%");
  }
  if (progressDetails) {
    progressDetails.textContent = "";
  }
  downloadVideoBtn.disabled = false;
}

async function startVideoDownload() {
  const url = videoUrlInput.value.trim();

  if (!url) {
    showToast("Please enter a YouTube URL", "warning");
    return;
  }

  if (!url.includes("youtube.com") && !url.includes("youtu.be")) {
    showToast("Only YouTube URLs are supported", "error");
    return;
  }

  if (!selectedPlaylistId) {
    showToast("Please select a playlist first", "warning");
    return;
  }

  // Show download status
  downloadStatusDiv.style.display = "block";
  downloadStatusDiv.querySelector(".status-message").textContent =
    "Starting download...";
  downloadVideoBtn.disabled = true;

  const data = await apiCall(`/playlists/${selectedPlaylistId}/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  if (data && data.status === "success") {
    const downloadId = data.download_id;
    showToast("Download started", "info");

    // Start polling for download status
    downloadPollingInterval = setInterval(
      () => pollDownloadStatus(downloadId),
      1000,
    );
  } else {
    showToast(data?.message || "Failed to start download", "error");
    downloadStatusDiv.style.display = "none";
    downloadVideoBtn.disabled = false;
  }
}

async function pollDownloadStatus(downloadId) {
  const data = await apiCall(`/download/${downloadId}`);

  if (!data) {
    clearInterval(downloadPollingInterval);
    downloadPollingInterval = null;
    return;
  }

  const statusMsg = downloadStatusDiv.querySelector(".status-message");
  const progressBar = document.getElementById("download-progress-bar");
  const progressDetails = document.getElementById("progress-details");

  if (data.status === "downloading") {
    const progress = data.progress || 0;
    const title = data.title || "Video";

    statusMsg.textContent = `Downloading: ${title}`;
    progressBar.style.width = `${progress}%`;
    progressBar.setAttribute("data-progress", `${progress.toFixed(1)}%`);

    // Show speed and ETA if available
    let details = [];
    if (data.speed) details.push(`Speed: ${data.speed}`);
    if (data.eta) details.push(`ETA: ${data.eta}`);
    progressDetails.textContent = details.join(" | ");
  } else if (data.status === "completed") {
    statusMsg.textContent = "Download complete!";
    progressBar.style.width = "100%";
    progressBar.setAttribute("data-progress", "100%");
    progressDetails.textContent = "";

    showToast("Video downloaded successfully", "success");
    downloadVideoBtn.disabled = false;

    clearInterval(downloadPollingInterval);
    downloadPollingInterval = null;

    // Refresh video list and playlists
    loadPlaylistVideos(selectedPlaylistId);
    loadPlaylists();

    // Close modal after a delay
    setTimeout(() => {
      hideVideoModal();
    }, 1500);
  } else if (data.status === "error") {
    statusMsg.textContent = `Error: ${data.message || "Download failed"}`;
    progressBar.style.width = "0%";
    progressDetails.textContent = "";

    showToast("Download failed", "error");
    downloadVideoBtn.disabled = false;

    clearInterval(downloadPollingInterval);
    downloadPollingInterval = null;
  }
}

async function loadPlaylistVideos(playlistId) {
  const data = await apiCall(`/playlists/${playlistId}/videos`);

  if (!data || data.status !== "success") {
    imagesContainer.innerHTML = "<p>Failed to load videos</p>";
    return;
  }

  displayVideos(data.videos, playlistId);
}

function displayVideos(videos, playlistId) {
  if (videos.length === 0) {
    imagesContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📹</div>
                <div class="empty-state-text">No videos in this playlist</div>
                <div class="empty-state-subtext">Download videos from YouTube to get started</div>
            </div>
        `;
    return;
  }

  imagesContainer.innerHTML = "";

  videos.forEach((video) => {
    const card = createVideoCard(video, playlistId);
    imagesContainer.appendChild(card);
  });
}

function createVideoCard(video, playlistId) {
  const card = document.createElement("div");
  card.className = "image-card"; // Reuse image card styling

  const sizeMB = (video.size / (1024 * 1024)).toFixed(2);
  const duration = video.duration ? formatDuration(video.duration) : "Unknown";

  card.innerHTML = `
        <div class="image-preview">📹</div>
        <div class="image-name" title="${escapeHtml(video.filename)}">${escapeHtml(video.filename)}</div>
        <div class="image-info">${sizeMB} MB • ${duration}</div>
        <div class="image-actions">
            <button class="btn btn-danger btn-sm delete-video">Delete</button>
        </div>
    `;

  // Delete button
  card.querySelector(".delete-video").addEventListener("click", () => {
    deleteVideo(playlistId, video.filename);
  });

  return card;
}

function formatDuration(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

async function deleteVideo(playlistId, filename) {
  if (!confirm(`Delete ${filename}?`)) return;

  showLoading();

  const data = await apiCall(
    `/playlists/${playlistId}/videos/${encodeURIComponent(filename)}`,
    {
      method: "DELETE",
    },
  );

  hideLoading();

  if (data && data.status === "success") {
    showToast("Video deleted successfully", "success");
    loadPlaylistVideos(playlistId);
    loadPlaylists(); // Refresh to update video counts
  } else {
    showToast(data?.message || "Failed to delete video", "error");
  }
}

// Slideshow Controls
async function playSlideshow() {
  if (!selectedPlaylistId) {
    showToast("Please select a playlist first", "warning");
    return;
  }

  showLoading();

  const data = await apiCall(`/start?playlist=${selectedPlaylistId}`);

  hideLoading();

  if (data && data.status === "started") {
    showToast("Slideshow started", "success");
    refreshStatus();
    setTimeout(loadPlaylists, 500); // Refresh playlists to show playing state
  } else {
    showToast(data?.message || "Failed to start slideshow", "error");
  }
}

async function stopSlideshow() {
  showLoading();

  const data = await apiCall("/stop");

  hideLoading();

  if (data && data.status === "stopped") {
    showToast("Slideshow stopped", "success");
    refreshStatus();
    setTimeout(loadPlaylists, 500);
  } else {
    showToast(data?.message || "Failed to stop slideshow", "error");
  }
}

// UI Utilities
function showLoading() {
  loadingOverlay.style.display = "flex";
}

function hideLoading() {
  loadingOverlay.style.display = "none";
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;

  const container = document.getElementById("toast-container");
  container.appendChild(toast);

  // Auto-remove after 3 seconds
  setTimeout(() => {
    toast.style.animation = "fadeOut 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Add fadeOut animation
const style = document.createElement("style");
style.textContent = `
    @keyframes fadeOut {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(100%); }
    }
`;
document.head.appendChild(style);
