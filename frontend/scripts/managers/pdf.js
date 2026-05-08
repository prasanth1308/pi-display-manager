/**
 * PDF Manager
 * Handles PDF upload and page display for PDF playlists.
 * PDFs are converted to PNG images server-side (via pdftoppm).
 */

const PdfManager = {
  async load(playlistId, pageDuration = 10) {
    const data = await API.getPlaylistImages(playlistId);

    if (!data || data.status !== "success") {
      DOM.imagesContainer.innerHTML = "<p>Failed to load PDF pages</p>";
      return;
    }

    this.display(data.images, playlistId, pageDuration);
  },

  display(pages, playlistId, pageDuration = 10) {
    DOM.imagesContainer.innerHTML = "";

    // Timing control — always visible so user can adjust before uploading too
    const timing = document.createElement("div");
    timing.className = "pdf-timing-bar";
    timing.innerHTML = `
      <label>Seconds per page:</label>
      <input type="number" id="pdf-timing-input" class="input-field"
             value="${pageDuration}" min="1" max="3600"
             style="width:80px;display:inline-block;margin:0 8px">
      <button class="btn btn-primary btn-sm" id="pdf-timing-save">Save</button>
    `;
    DOM.imagesContainer.appendChild(timing);

    document.getElementById("pdf-timing-save").addEventListener("click", async () => {
      const val = parseInt(document.getElementById("pdf-timing-input").value) || 10;
      const result = await API.updatePlaylist(playlistId, { page_duration: val });
      if (result && result.status === "success") {
        UI.showToast(`Timing updated: ${val}s per page`, TOAST_TYPES.SUCCESS);
      } else {
        UI.showToast(result?.message || "Failed to update timing", TOAST_TYPES.ERROR);
      }
    });

    if (pages.length === 0) {
      ContentManager.displayEmpty(CONTENT_TYPES.PDF);
      return;
    }

    const info = document.createElement("div");
    info.className = "pdf-info-bar";
    info.innerHTML = `<span>📄</span><span>${pages.length} page${pages.length !== 1 ? "s" : ""} — click "📄 Upload PDF" to replace</span>`;
    DOM.imagesContainer.appendChild(info);

    pages.forEach((page, i) => {
      const card = document.createElement("div");
      card.className = "image-card";
      const sizeKB = Math.round(page.size / 1024);
      card.innerHTML = `
        <div class="image-preview">📄</div>
        <div class="image-name">Page ${i + 1}</div>
        <div class="image-info">${sizeKB} KB</div>
      `;
      DOM.imagesContainer.appendChild(card);
    });
  },

  async upload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!AppState.selectedPlaylistId) {
      UI.showToast("Please select a playlist first", TOAST_TYPES.WARNING);
      return;
    }

    UI.showLoading();

    const formData = new FormData();
    formData.append("pdf", file);

    const data = await API.uploadPdf(AppState.selectedPlaylistId, formData);

    UI.hideLoading();

    if (data && data.status === "success") {
      UI.showToast(
        `PDF uploaded: ${data.page_count} page${data.page_count !== 1 ? "s" : ""} extracted`,
        TOAST_TYPES.SUCCESS,
      );
      await PdfManager.load(AppState.selectedPlaylistId);
      PlaylistManager.load();
    } else {
      UI.showToast(data?.message || "PDF upload failed", TOAST_TYPES.ERROR);
    }

    DOM.pdfFileInput.value = "";
  },
};
