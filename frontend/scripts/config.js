/**
 * Configuration and Constants
 * Centralized configuration for the application
 */

const CONFIG = {
  POLLING_INTERVAL: 1000, // Download status polling (ms)
  STATUS_REFRESH_INTERVAL: 3000, // Status auto-refresh (ms)
  TOAST_DURATION: 3000, // Toast notification duration (ms)
  PROGRESS_HIDE_DELAY: 3000, // Progress bar hide delay after completion (ms)
};

const CONTENT_TYPES = {
  IMAGE: "image",
  VIDEO: "video",
  PDF: "pdf",
  PPT: "ppt",
};

const PLAYLIST_TYPE_CONFIG = {
  [CONTENT_TYPES.IMAGE]: {
    icon: "🖼️",
    badge: "🖼️ Image",
    emptyIcon: "🖼️",
    emptyText: "No images in this playlist",
    emptySubtext: "Upload images to get started",
  },
  [CONTENT_TYPES.VIDEO]: {
    icon: "📹",
    badge: "📹 Video",
    emptyIcon: "📹",
    emptyText: "No videos in this playlist",
    emptySubtext: "Download videos from YouTube to get started",
  },
  [CONTENT_TYPES.PDF]: {
    icon: "📄",
    badge: "📄 PDF",
    emptyIcon: "📄",
    emptyText: "No PDF files in this playlist",
    emptySubtext: "Upload PDF files to get started",
  },
  [CONTENT_TYPES.PPT]: {
    icon: "📊",
    badge: "📊 PowerPoint",
    emptyIcon: "📊",
    emptyText: "No PowerPoint files in this playlist",
    emptySubtext: "Upload PowerPoint files to get started",
  },
};

const TOAST_TYPES = {
  INFO: "info",
  SUCCESS: "success",
  WARNING: "warning",
  ERROR: "error",
};
