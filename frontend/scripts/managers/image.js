/**
 * Image Manager
 * Handles image upload, display, and deletion
 */

const ImageManager = {
  /**
   * Load images for a playlist
   */
  async load(playlistId) {
    const data = await API.getPlaylistImages(playlistId);

    if (!data || data.status !== "success") {
      DOM.imagesContainer.innerHTML = "<p>Failed to load images</p>";
      return;
    }

    this.display(data.images, playlistId);
  },

  /**
   * Display images
   */
  display(images, playlistId) {
    if (images.length === 0) {
      ContentManager.displayEmpty(CONTENT_TYPES.IMAGE);
      return;
    }

    DOM.imagesContainer.innerHTML = "";

    images.forEach((image) => {
      const card = this.createCard(image, playlistId);
      DOM.imagesContainer.appendChild(card);
    });
  },

  /**
   * Create image card
   */
  createCard(image, playlistId) {
    const card = document.createElement("div");
    card.className = "image-card" + (image.skipped ? " skipped" : "");

    const sizeKB = Math.round(image.size / 1024);

    card.innerHTML = `
      <div class="image-preview">
        <img src="/data/playlists/${playlistId}/${encodeURIComponent(image.filename)}" alt="${UI.escapeHtml(image.filename)}" loading="lazy">
        ${image.skipped ? '<div class="skip-overlay">Skipped</div>' : ""}
      </div>
      <div class="image-name" title="${UI.escapeHtml(image.filename)}">${UI.escapeHtml(image.filename)}</div>
      <div class="image-info">${sizeKB} KB</div>
      <div class="image-actions">
        <button class="btn btn-warning btn-sm skip-image">${image.skipped ? "Unskip" : "Skip"}</button>
        <button class="btn btn-danger btn-sm delete-image">Delete</button>
      </div>
    `;

    card.querySelector(".skip-image").addEventListener("click", () => {
      this.toggleSkip(playlistId, image.filename, image.skipped);
    });

    card.querySelector(".delete-image").addEventListener("click", () => {
      this.delete(playlistId, image.filename);
    });

    return card;
  },

  /**
   * Handle file upload (images or videos)
   */
  async upload(event) {
    const files = Array.from(event.target.files);

    if (files.length === 0) return;

    if (!AppState.selectedPlaylistId) {
      UI.showToast("Please select a playlist first", TOAST_TYPES.WARNING);
      return;
    }

    // Check if any file is a video
    const videoExtensions = ["mp4", "avi", "mkv", "mov", "wmv", "flv", "webm"];
    const hasVideo = files.some((file) => {
      const ext = file.name.split(".").pop().toLowerCase();
      return videoExtensions.includes(ext);
    });

    // If video, only allow 1 file
    if (hasVideo && files.length > 1) {
      UI.showToast(
        "Only one video can be uploaded at a time",
        TOAST_TYPES.WARNING,
      );
      return;
    }

    let successCount = 0;
    let failCount = 0;

    for (const file of files) {
      const formData = new FormData();
      const ext = file.name.split(".").pop().toLowerCase();
      const isVideo = videoExtensions.includes(ext);

      // Check if it's a large video file (>10MB)
      const isLargeVideo = isVideo && file.size > 10 * 1024 * 1024;

      // Use appropriate form field name
      formData.append(isVideo ? "video" : "image", file);

      if (isLargeVideo) {
        // Show progress for large video uploads using XHR progress events
        UI.showProgress(`Uploading ${file.name}...`, 0);

        try {
          const data = await API.uploadImageWithProgress(
            AppState.selectedPlaylistId,
            formData,
            (percentComplete, loaded, total) => {
              const sizeMB = (loaded / (1024 * 1024)).toFixed(1);
              const totalMB = (total / (1024 * 1024)).toFixed(1);
              UI.showProgress(
                `Uploading ${file.name}...`,
                Math.floor(percentComplete),
                `${sizeMB} MB / ${totalMB} MB`,
              );
            },
          );

          if (data && data.status === "success") {
            UI.showProgress("Upload complete!", 100, "Processing...");
            setTimeout(() => {
              UI.hideProgress();
            }, 1000);
            successCount++;
          } else {
            UI.hideProgress();
            failCount++;
            if (data && data.message) {
              UI.showToast(data.message, TOAST_TYPES.ERROR);
            }
          }
        } catch (error) {
          UI.hideProgress();
          failCount++;
          UI.showToast(`Upload failed: ${error.message}`, TOAST_TYPES.ERROR);
        }
      } else {
        // Small files - use regular upload
        UI.showLoading();
        const data = await API.uploadImage(
          AppState.selectedPlaylistId,
          formData,
        );

        UI.hideLoading();

        if (data && data.status === "success") {
          successCount++;
        } else {
          failCount++;
          if (data && data.message) {
            UI.showToast(data.message, TOAST_TYPES.ERROR);
          }
        }
      }
    }

    if (successCount > 0) {
      const fileType = hasVideo ? "video" : "image";
      const plural = successCount !== 1 && !hasVideo ? "s" : "";
      UI.showToast(
        `${successCount} ${fileType}${plural} uploaded successfully`,
        TOAST_TYPES.SUCCESS,
      );

      // Reload appropriate content type
      if (hasVideo) {
        await VideoManager.load(AppState.selectedPlaylistId);
      } else {
        await this.load(AppState.selectedPlaylistId);
      }
      PlaylistManager.load(); // Refresh to update counts
    }

    if (failCount > 0) {
      const fileType = hasVideo ? "video" : "image";
      const plural = failCount !== 1 && !hasVideo ? "s" : "";
      UI.showToast(
        `${failCount} ${fileType}${plural} failed to upload`,
        TOAST_TYPES.ERROR,
      );
    }

    // Reset file input
    DOM.fileInput.value = "";
  },

  /**
   * Delete an image
   */
  async delete(playlistId, filename) {
    if (!confirm(`Delete ${filename}?`)) return;

    UI.showLoading();

    const data = await API.deleteImage(playlistId, filename);

    UI.hideLoading();

    if (data && data.status === "success") {
      UI.showToast("Image deleted successfully", TOAST_TYPES.SUCCESS);
      this.load(playlistId);
      PlaylistManager.load(); // Refresh to update counts
    } else {
      UI.showToast(
        data?.message || "Failed to delete image",
        TOAST_TYPES.ERROR,
      );
    }
  },

  /**
   * Toggle skip status of an image
   */
  async toggleSkip(playlistId, filename, isCurrentlySkipped) {
    UI.showLoading();

    const data = isCurrentlySkipped
      ? await API.unskipImage(playlistId, filename)
      : await API.skipImage(playlistId, filename);

    UI.hideLoading();

    if (data && data.status === "success") {
      const action = isCurrentlySkipped ? "unskipped" : "skipped";
      UI.showToast(`Image ${action} successfully`, TOAST_TYPES.SUCCESS);
      this.load(playlistId);
    } else {
      UI.showToast(
        data?.message || "Failed to update image",
        TOAST_TYPES.ERROR,
      );
    }
  },
};
