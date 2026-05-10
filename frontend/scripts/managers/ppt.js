/**
 * PowerPoint Manager
 * Handles PowerPoint upload, conversion to images, and display
 */

const PPTManager = {
  /**
   * Load PowerPoint images for a playlist
   */
  async load(playlistId) {
    // PowerPoint files are converted to images, so use the same endpoint as images
    const data = await API.getPlaylistImages(playlistId);

    if (!data || data.status !== "success") {
      DOM.imagesContainer.innerHTML =
        "<p>Failed to load PowerPoint content</p>";
      return;
    }

    this.display(data.images, playlistId);
  },

  /**
   * Display PowerPoint-converted images
   */
  display(images, playlistId) {
    if (images.length === 0) {
      ContentManager.displayEmpty(CONTENT_TYPES.PPT);
      return;
    }

    DOM.imagesContainer.innerHTML = "";

    images.forEach((image) => {
      const card = this.createCard(image, playlistId);
      DOM.imagesContainer.appendChild(card);
    });
  },

  /**
   * Create image card for PowerPoint slide
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
   * Handle PowerPoint file upload
   */
  async upload(event) {
    const files = Array.from(event.target.files);

    if (files.length === 0) return;

    if (!AppState.selectedPlaylistId) {
      UI.showToast("Please select a playlist first", TOAST_TYPES.WARNING);
      return;
    }

    // Validate PowerPoint files
    const pptFiles = files.filter((file) => {
      const ext = file.name.split(".").pop().toLowerCase();
      return ext === "ppt" || ext === "pptx";
    });

    if (pptFiles.length === 0) {
      UI.showToast(
        "Please select PowerPoint files only (.ppt or .pptx)",
        TOAST_TYPES.WARNING,
      );
      return;
    }

    if (pptFiles.length !== files.length) {
      UI.showToast(
        "Only PowerPoint files are allowed for PowerPoint playlists",
        TOAST_TYPES.WARNING,
      );
      return;
    }

    let successCount = 0;

    UI.showLoading();

    for (const file of pptFiles) {
      const formData = new FormData();
      formData.append("ppt", file);

      try {
        const result = await API.uploadPPT(
          AppState.selectedPlaylistId,
          formData,
        );

        if (result && result.status === "success") {
          successCount++;
          UI.showToast(
            `PowerPoint "${file.name}" uploaded and converted to ${result.slide_count} slide(s)`,
            TOAST_TYPES.SUCCESS,
          );
        }
      } catch (error) {
        console.error("Upload error:", error);
        UI.showToast(
          `Failed to upload ${file.name}: ${error.message || "Unknown error"}`,
          TOAST_TYPES.ERROR,
        );
      }
    }

    UI.hideLoading();

    if (successCount > 0) {
      await this.load(AppState.selectedPlaylistId);
      await StatusManager.refreshStatus();
    }

    // Clear file input
    event.target.value = "";
  },

  /**
   * Toggle skip status for a PowerPoint slide image
   */
  async toggleSkip(playlistId, filename, currentSkipStatus) {
    try {
      const result = await API.skipImage(
        playlistId,
        filename,
        !currentSkipStatus,
      );

      if (result && result.status === "success") {
        await this.load(playlistId);
        UI.showToast(
          `${currentSkipStatus ? "Unskipped" : "Skipped"} successfully`,
          TOAST_TYPES.SUCCESS,
        );
      }
    } catch (error) {
      UI.showToast("Failed to update skip status", TOAST_TYPES.ERROR);
    }
  },

  /**
   * Delete a PowerPoint slide image
   */
  async delete(playlistId, filename) {
    if (!confirm(`Delete ${filename}?`)) return;

    try {
      const result = await API.deleteImage(playlistId, filename);

      if (result && result.status === "success") {
        await this.load(playlistId);
        await StatusManager.refreshStatus();
        UI.showToast("Deleted successfully", TOAST_TYPES.SUCCESS);
      }
    } catch (error) {
      UI.showToast("Failed to delete image", TOAST_TYPES.ERROR);
    }
  },

  /**
   * Show PowerPoint upload modal
   */
  showUploadModal() {
    DOM.fileInput.accept = ".ppt,.pptx";
    DOM.fileInput.click();
  },
};
