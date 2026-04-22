// ── API helpers ──────────────────────────────────────────────────────────────

const api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async put(path, body) {
    const r = await fetch(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async delete(path) {
    const r = await fetch(path, { method: 'DELETE' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
};

// ── Toast ─────────────────────────────────────────────────────────────────────

let toastTimer;
function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.className = '', 3000);
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

document.querySelectorAll('nav.tabs button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('nav.tabs button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
  });
});

// ── Status polling ────────────────────────────────────────────────────────────

async function pollStatus() {
  try {
    const s = await api.get('/api/control/status');
    const badge = document.getElementById('status-badge');
    const name = document.getElementById('now-playing-name');

    if (s.is_playing) {
      badge.textContent = s.is_paused ? 'Paused' : 'Playing';
      badge.className = `${s.is_paused ? 'paused' : 'playing'}`;
      const filename = s.current_file ? s.current_file.split('/').pop() : '—';
      name.textContent = filename;
    } else {
      badge.textContent = 'Stopped';
      badge.className = 'stopped';
      name.textContent = '—';
    }
  } catch (_) {}
}
setInterval(pollStatus, 3000);
pollStatus();

// ── Transport controls ────────────────────────────────────────────────────────

async function controlAction(action) {
  try {
    await api.post(`/api/control/${action}`, {});
    setTimeout(pollStatus, 300);
  } catch (e) {
    toast(e.message, 'error');
  }
}

document.getElementById('btn-pause').addEventListener('click', async () => {
  const status = await api.get('/api/control/status');
  controlAction(status.is_paused ? 'resume' : 'pause');
});
document.getElementById('btn-stop').addEventListener('click', () => controlAction('stop'));
document.getElementById('btn-next').addEventListener('click', () => controlAction('next'));

// ── Files tab ─────────────────────────────────────────────────────────────────

let allFiles = [];

async function loadFiles() {
  allFiles = await api.get('/api/files/');
  renderFiles();
}

function fileTypeIcon(type) {
  if (type === 'video') return '🎬';
  if (type === 'presentation') return '📊';
  return '🖼️';
}

function renderFiles() {
  const grid = document.getElementById('file-grid');
  if (!allFiles.length) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <div class="icon">📂</div><p>No files uploaded yet</p></div>`;
    return;
  }
  grid.innerHTML = allFiles.map(f => `
    <div class="file-card" data-id="${f.id}" data-type="${f.file_type}" data-path="${f.file_path}">
      <div class="file-card-thumb">${fileTypeIcon(f.file_type)}</div>
      <div class="file-card-info">
        <div class="file-card-name" title="${f.original_name}">${f.original_name}</div>
        <div class="file-card-type">${f.file_type}</div>
      </div>
      <div class="file-card-actions">
        <button class="icon-btn play" title="Play now" onclick="playFile(${f.id}, event)">▶</button>
        <button class="icon-btn" title="Delete" onclick="deleteFile(${f.id}, event)">🗑</button>
      </div>
    </div>`).join('');
}

async function playFile(id, e) {
  e.stopPropagation();
  try {
    await api.post('/api/control/play', { file_id: id });
    toast('Playing file');
    setTimeout(pollStatus, 500);
  } catch (err) {
    toast(err.message, 'error');
  }
}

async function deleteFile(id, e) {
  e.stopPropagation();
  if (!confirm('Delete this file?')) return;
  try {
    await api.delete(`/api/files/${id}`);
    toast('File deleted');
    loadFiles();
  } catch (err) {
    toast(err.message, 'error');
  }
}

// Upload
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');

uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', () => uploadFiles(fileInput.files));

async function uploadFiles(fileList) {
  const progress = document.getElementById('upload-progress');
  const fill = document.getElementById('upload-progress-fill');
  const label = document.getElementById('upload-progress-label');

  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i];
    label.textContent = `Uploading ${file.name}…`;
    progress.style.display = 'block';
    fill.style.width = '0%';

    const fd = new FormData();
    fd.append('file', file);

    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/files/upload');
      xhr.upload.onprogress = e => {
        if (e.lengthComputable) fill.style.width = (e.loaded / e.total * 100) + '%';
      };
      xhr.onload = () => {
        if (xhr.status === 200) { fill.style.width = '100%'; resolve(); }
        else reject(new Error(xhr.responseText));
      };
      xhr.onerror = () => reject(new Error('Upload failed'));
      xhr.send(fd);
    }).catch(err => toast(err.message, 'error'));
  }

  progress.style.display = 'none';
  fileInput.value = '';
  toast(`${fileList.length} file(s) uploaded`);
  loadFiles();
  loadPlaylists(); // refresh selectors
}

// ── Playlists tab ─────────────────────────────────────────────────────────────

let allPlaylists = [];
let editingPlaylistId = null;
let editorItems = []; // [{media_file_id, name, type, order, duration}]

async function loadPlaylists() {
  allPlaylists = await api.get('/api/playlists/');
  renderPlaylists();
  refreshPlaylistSelects();
}

function renderPlaylists() {
  const list = document.getElementById('playlist-list');
  if (!allPlaylists.length) {
    list.innerHTML = `<div class="empty-state"><div class="icon">📋</div><p>No playlists yet</p></div>`;
    return;
  }
  list.innerHTML = allPlaylists.map(p => `
    <div class="list-row">
      <div class="row-main">
        <div class="row-title">${p.name}</div>
      </div>
      <div class="row-actions">
        <button class="btn btn-sm btn-secondary" onclick="playPlaylist(${p.id})">▶ Play</button>
        <button class="btn btn-sm btn-secondary" onclick="openPlaylistEditor(${p.id})">✏ Edit</button>
        <button class="btn btn-sm btn-danger" onclick="deletePlaylist(${p.id})">Delete</button>
      </div>
    </div>`).join('');
}

async function playPlaylist(id) {
  try {
    await api.post('/api/control/play', { playlist_id: id });
    toast('Playing playlist');
    setTimeout(pollStatus, 500);
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deletePlaylist(id) {
  if (!confirm('Delete this playlist?')) return;
  try {
    await api.delete(`/api/playlists/${id}`);
    toast('Playlist deleted');
    loadPlaylists();
  } catch (e) {
    toast(e.message, 'error');
  }
}

// Open editor for new or existing playlist
async function openPlaylistEditor(playlistId = null) {
  editingPlaylistId = playlistId;
  editorItems = [];

  const editor = document.getElementById('playlist-editor');
  editor.classList.add('open');

  if (playlistId) {
    const p = await api.get(`/api/playlists/${playlistId}`);
    document.getElementById('playlist-name-input').value = p.name;
    editorItems = p.items.map(i => ({
      media_file_id: i.media_file_id,
      name: i.media_file.original_name,
      type: i.media_file.file_type,
      order: i.order,
      duration: i.duration,
    }));
  } else {
    document.getElementById('playlist-name-input').value = '';
  }
  renderEditorItems();
}

function closePlaylistEditor() {
  document.getElementById('playlist-editor').classList.remove('open');
  editingPlaylistId = null;
  editorItems = [];
}

function renderEditorItems() {
  const list = document.getElementById('playlist-items-list');
  if (!editorItems.length) {
    list.innerHTML = `<div style="color:var(--muted);text-align:center;padding:20px;font-size:13px;">
      Add files from the Files tab or select below</div>`;
    return;
  }
  list.innerHTML = editorItems.map((item, idx) => `
    <div class="playlist-row" draggable="true" data-idx="${idx}">
      <span class="drag-handle">⠿</span>
      <span class="row-name" title="${item.name}">${item.name}</span>
      <span class="row-type">${item.type}</span>
      <span class="row-duration">
        ${item.type !== 'video' ? `<input type="number" min="1" max="300" value="${item.duration}"
          onchange="updateItemDuration(${idx}, this.value)" title="Display seconds"> s` : '<span style="color:var(--muted);font-size:12px">auto</span>'}
      </span>
      <button class="icon-btn" onclick="removeEditorItem(${idx})" title="Remove">✕</button>
    </div>`).join('');
  initDragSort();
}

function updateItemDuration(idx, val) {
  editorItems[idx].duration = parseFloat(val) || 10;
}

function removeEditorItem(idx) {
  editorItems.splice(idx, 1);
  renderEditorItems();
}

// Add files to editor from file grid selection
function addFilesToEditor(fileIds) {
  fileIds.forEach(id => {
    const f = allFiles.find(f => f.id === id);
    if (!f) return;
    if (editorItems.find(i => i.media_file_id === id)) return; // no duplicates
    editorItems.push({ media_file_id: id, name: f.original_name, type: f.file_type, order: editorItems.length, duration: 10 });
  });
  renderEditorItems();
}

// File picker within editor
document.getElementById('add-to-playlist-btn').addEventListener('click', () => {
  const modal = document.getElementById('file-picker-modal');
  modal.style.display = 'flex';
  renderFilePicker();
});
document.getElementById('file-picker-close').addEventListener('click', () => {
  document.getElementById('file-picker-modal').style.display = 'none';
});
document.getElementById('file-picker-confirm').addEventListener('click', () => {
  const checked = [...document.querySelectorAll('#file-picker-list input:checked')];
  addFilesToEditor(checked.map(c => parseInt(c.value)));
  document.getElementById('file-picker-modal').style.display = 'none';
});

function renderFilePicker() {
  const list = document.getElementById('file-picker-list');
  if (!allFiles.length) {
    list.innerHTML = '<p style="color:var(--muted);padding:20px;text-align:center">No files uploaded</p>';
    return;
  }
  list.innerHTML = allFiles.map(f => `
    <label style="display:flex;align-items:center;gap:10px;padding:10px;cursor:pointer;border-radius:6px;border:1px solid var(--border);margin-bottom:6px;">
      <input type="checkbox" value="${f.id}">
      <span style="font-size:18px">${fileTypeIcon(f.file_type)}</span>
      <span style="font-size:13px">${f.original_name}</span>
    </label>`).join('');
}

async function savePlaylist() {
  const name = document.getElementById('playlist-name-input').value.trim();
  if (!name) { toast('Enter a playlist name', 'error'); return; }
  if (!editorItems.length) { toast('Add at least one file', 'error'); return; }

  const payload = {
    name,
    items: editorItems.map((item, idx) => ({
      media_file_id: item.media_file_id,
      order: idx,
      duration: item.duration,
    })),
  };

  try {
    if (editingPlaylistId) {
      await api.put(`/api/playlists/${editingPlaylistId}`, payload);
      toast('Playlist updated');
    } else {
      await api.post('/api/playlists/', payload);
      toast('Playlist created');
    }
    closePlaylistEditor();
    loadPlaylists();
  } catch (e) {
    toast(e.message, 'error');
  }
}

// Drag-to-reorder
function initDragSort() {
  const rows = document.querySelectorAll('.playlist-row');
  let dragIdx = null;

  rows.forEach(row => {
    row.addEventListener('dragstart', () => { dragIdx = parseInt(row.dataset.idx); row.style.opacity = '0.4'; });
    row.addEventListener('dragend', () => { row.style.opacity = '1'; });
    row.addEventListener('dragover', e => e.preventDefault());
    row.addEventListener('drop', () => {
      const targetIdx = parseInt(row.dataset.idx);
      if (dragIdx === null || dragIdx === targetIdx) return;
      const [moved] = editorItems.splice(dragIdx, 1);
      editorItems.splice(targetIdx, 0, moved);
      dragIdx = null;
      renderEditorItems();
    });
  });
}

// ── Schedules tab ─────────────────────────────────────────────────────────────

async function loadSchedules() {
  const schedules = await api.get('/api/schedules/');
  renderSchedules(schedules);
}

function renderSchedules(schedules) {
  const list = document.getElementById('schedule-list');
  if (!schedules.length) {
    list.innerHTML = `<div class="empty-state"><div class="icon">🕐</div><p>No schedules yet</p></div>`;
    return;
  }
  list.innerHTML = schedules.map(s => {
    const playlist = allPlaylists.find(p => p.id === s.playlist_id);
    return `
    <div class="list-row">
      <div class="row-main">
        <div class="row-title">${s.name}</div>
        <div class="row-sub">${s.cron_expression} — ${playlist ? playlist.name : 'Unknown playlist'}</div>
      </div>
      <label class="toggle" title="${s.is_active ? 'Active' : 'Paused'}">
        <input type="checkbox" ${s.is_active ? 'checked' : ''} onchange="toggleSchedule(${s.id}, this.checked)">
        <span class="toggle-slider"></span>
      </label>
      <div class="row-actions">
        <button class="btn btn-sm btn-danger" onclick="deleteSchedule(${s.id})">Delete</button>
      </div>
    </div>`;
  }).join('');
}

async function toggleSchedule(id, active) {
  try {
    const s = await api.get('/api/schedules/');
    const schedule = s.find(x => x.id === id);
    if (!schedule) return;
    await api.put(`/api/schedules/${id}`, { ...schedule, is_active: active });
    toast(active ? 'Schedule activated' : 'Schedule paused');
    loadSchedules();
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deleteSchedule(id) {
  if (!confirm('Delete this schedule?')) return;
  try {
    await api.delete(`/api/schedules/${id}`);
    toast('Schedule deleted');
    loadSchedules();
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function createSchedule() {
  const name = document.getElementById('schedule-name').value.trim();
  const cron = document.getElementById('schedule-cron').value.trim();
  const playlist_id = parseInt(document.getElementById('schedule-playlist').value);

  if (!name || !cron || !playlist_id) { toast('Fill all fields', 'error'); return; }

  try {
    await api.post('/api/schedules/', { name, cron_expression: cron, playlist_id, is_active: true });
    toast('Schedule created');
    document.getElementById('schedule-name').value = '';
    document.getElementById('schedule-cron').value = '';
    loadSchedules();
  } catch (e) {
    toast(e.message, 'error');
  }
}

function refreshPlaylistSelects() {
  const sel = document.getElementById('schedule-playlist');
  sel.innerHTML = '<option value="">— Select playlist —</option>' +
    allPlaylists.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
}

// ── Cron helper ───────────────────────────────────────────────────────────────

document.querySelectorAll('.cron-preset').forEach(btn => {
  btn.addEventListener('click', () => {
    document.getElementById('schedule-cron').value = btn.dataset.cron;
  });
});

// ── Init ──────────────────────────────────────────────────────────────────────

(async () => {
  await loadFiles();
  await loadPlaylists();
  await loadSchedules();
})();
