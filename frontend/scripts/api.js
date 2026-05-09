/**
 * API Module
 * Handles all API communication with the backend
 */

const API = {
  /**
   * Generic API call handler
   */
  async call(endpoint, options = {}) {
    try {
      const response = await fetch(`/api${endpoint}`, options);
      const data = await response.json();
      return data;
    } catch (error) {
      console.error("API call failed:", error);
      UI.showToast(
        "Connection error. Please check if the service is running.",
        TOAST_TYPES.ERROR,
      );
      return null;
    }
  },

  // Status endpoints
  getStatus: () => API.call("/status"),

  // Playlist endpoints
  getPlaylists: () => API.call("/playlists"),
  createPlaylist: (name, type, delay = 5) =>
    API.call("/playlists/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, type, delay }),
    }),
  updatePlaylist: (playlistId, data) =>
    API.call(`/playlists/${playlistId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deletePlaylist: (playlistId) =>
    API.call(`/playlists/${playlistId}`, { method: "DELETE" }),

  // Image endpoints
  getPlaylistImages: (playlistId) =>
    API.call(`/playlists/${playlistId}/images`),
  uploadImage: (playlistId, formData) =>
    API.call(`/playlists/${playlistId}/upload`, {
      method: "POST",
      body: formData,
    }),
  uploadImageWithProgress: (playlistId, formData, onProgress) => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable && onProgress) {
          const percentComplete = (e.loaded / e.total) * 100;
          onProgress(percentComplete, e.loaded, e.total);
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve(data);
          } catch (error) {
            reject(new Error("Invalid JSON response"));
          }
        } else {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      });

      xhr.addEventListener("error", () => {
        reject(new Error("Upload failed"));
      });

      xhr.addEventListener("abort", () => {
        reject(new Error("Upload cancelled"));
      });

      xhr.open("POST", `/api/playlists/${playlistId}/upload`);
      xhr.send(formData);
    });
  },
  deleteImage: (playlistId, filename) =>
    API.call(
      `/playlists/${playlistId}/images/${encodeURIComponent(filename)}`,
      {
        method: "DELETE",
      },
    ),
  skipImage: (playlistId, filename) =>
    API.call(
      `/playlists/${playlistId}/images/${encodeURIComponent(filename)}/skip`,
      {
        method: "POST",
      },
    ),
  unskipImage: (playlistId, filename) =>
    API.call(
      `/playlists/${playlistId}/images/${encodeURIComponent(filename)}/skip`,
      {
        method: "DELETE",
      },
    ),

  // Video endpoints
  getPlaylistVideos: (playlistId) =>
    API.call(`/playlists/${playlistId}/videos`),
  downloadVideo: (playlistId, url) =>
    API.call(`/playlists/${playlistId}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }),
  getDownloadStatus: (downloadId) => API.call(`/download/${downloadId}`),
  getUploadStatus: (uploadId) => API.call(`/upload/${uploadId}`),
  getDownscaleStatus: (downscaleId) => API.call(`/downscale/${downscaleId}`),
  deleteVideo: (playlistId, filename) =>
    API.call(
      `/playlists/${playlistId}/videos/${encodeURIComponent(filename)}`,
      {
        method: "DELETE",
      },
    ),

  // Control endpoints
  startPlayback: (playlistId) => API.call(`/start?playlist=${playlistId}`),
  stopPlayback: () => API.call("/stop"),

  // Idle screen endpoints
  getIdleConfig: () => API.call("/idle-config"),
  saveIdleConfig: (data) =>
    API.call("/idle-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  // Scheduler endpoints
  getSchedules: () => API.call("/schedules"),
  getSchedule: (id) => API.call(`/schedules/${id}`),
  createSchedule: (data) =>
    API.call("/schedules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateSchedule: (id, data) =>
    API.call(`/schedules/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteSchedule: (id) => API.call(`/schedules/${id}`, { method: "DELETE" }),
};
