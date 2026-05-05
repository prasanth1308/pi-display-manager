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
    card.className = "image-card";

    const sizeKB = Math.round(image.size / 1024);

    card.innerHTML = `
      <div class="image-preview">🖼️</div>
      <div class="image-name" title="${UI.escapeHtml(image.filename)}">${UI.escapeHtml(image.filename)}</div>
      <div class="image-info">${sizeKB} KB</div>
      <div class="image-actions">
        <button class="btn btn-danger btn-sm delete-image">Delete</button>
      </div>
    `;

    card.querySelector(".delete-image").addEventListener("click", () => {
      this.delete(playlistId, image.filename);
    });

    return card;
  },

  /**
   * Handle file upload
   */
  async upload(event) {
    const files = Array.from(event.target.files);

    if (files.length === 0) return;

    if (!AppState.selectedPlaylistId) {
      UI.showToast("Please select a playlist first", TOAST_TYPES.WARNING);
      return;
    }

    UI.showLoading();

    let successCount = 0;
    let failCount = 0;

    for (const file of files) {
      const formData = new FormData();
      formData.append("image", file);

      const data = await API.uploadImage(AppState.selectedPlaylistId, formData);

      if (data && data.status === "success") {
        successCount++;
      } else {
        failCount++;
      }
    }

    UI.hideLoading();

    if (successCount > 0) {
      UI.showToast(
        `${successCount} image${successCount !== 1 ? "s" : ""} uploaded successfully`,
        TOAST_TYPES.SUCCESS,
      );
      this.load(AppState.selectedPlaylistId);
      PlaylistManager.load(); // Refresh to update counts
    }

    if (failCount > 0) {
      UI.showToast(
        `${failCount} image${failCount !== 1 ? "s" : ""} failed to upload`,
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
};
