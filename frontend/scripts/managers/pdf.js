/**
 * PDF Manager
 * Handles PDF upload, conversion to images, and display
 */

const PDFManager = {
  /**
   * Load PDF images for a playlist
   */
  async load(playlistId) {
    // PDFs are converted to images, so use the same endpoint as images
    const data = await API.getPlaylistImages(playlistId);

    if (!data || data.status !== "success") {
      DOM.imagesContainer.innerHTML = "<p>Failed to load PDF content</p>";
      return;
    }

    this.display(data.images, playlistId);
  },

  /**
   * Display PDF-converted images
   */
  display(images, playlistId) {
    if (images.length === 0) {
      ContentManager.displayEmpty(CONTENT_TYPES.PDF);
      return;
    }

    DOM.imagesContainer.innerHTML = "";

    images.forEach((image) => {
      const card = this.createCard(image, playlistId);
      DOM.imagesContainer.appendChild(card);
    });
  },

  /**
   * Create image card for PDF page
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
   * Handle PDF file upload
   */
  async upload(event) {
    const files = Array.from(event.target.files);

    if (files.length === 0) return;

    if (!AppState.selectedPlaylistId) {
      UI.showToast("Please select a playlist first", TOAST_TYPES.WARNING);
      return;
    }

    // Validate PDF files
    const pdfFiles = files.filter((file) => {
      const ext = file.name.split(".").pop().toLowerCase();
      return ext === "pdf";
    });

    if (pdfFiles.length === 0) {
      UI.showToast("Please select PDF files only", TOAST_TYPES.WARNING);
      return;
    }

    if (pdfFiles.length !== files.length) {
      UI.showToast(
        "Only PDF files are allowed for PDF playlists",
        TOAST_TYPES.WARNING,
      );
      return;
    }

    let successCount = 0;

    UI.showLoading();

    for (const file of pdfFiles) {
      const formData = new FormData();
      formData.append("pdf", file);

      try {
        const result = await API.uploadPDF(
          AppState.selectedPlaylistId,
          formData,
        );

        if (result && result.status === "success") {
          successCount++;
          UI.showToast(
            `PDF "${file.name}" uploaded and converted to ${result.page_count} page(s)`,
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
   * Toggle skip status for a PDF page image
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
   * Delete a PDF page image
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
   * Show PDF upload modal
   */
  showUploadModal() {
    DOM.fileInput.accept = ".pdf";
    DOM.fileInput.click();
  },
};
