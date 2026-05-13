// ── Clock ─────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const s = t => String(t).padStart(2, '0');
  const str = `${s(now.getHours())}:${s(now.getMinutes())}:${s(now.getSeconds())}`;
  const el1 = document.getElementById('clock');
  const el2 = document.getElementById('sclk');
  if (el1) el1.textContent = str;
  if (el2) el2.textContent = str;
}
setInterval(updateClock, 1000);
updateClock();

// ── Blob data (PCA positions for scatter plots) ───────────────────
let _blobData = null;
fetch(BLOB_DATA_URL)
  .then(r => r.json())
  .then(d => { _blobData = d; drawScatter(null); })
  .catch(() => {});

// ── Elements ──────────────────────────────────────────────────────
const input     = document.getElementById('sv-input');
const resultsEl = document.getElementById('sv-results');
const songInfo  = document.getElementById('sv-song-info');
const idleHint  = document.getElementById('sv-idle-hint');
const songTitle = document.getElementById('sv-song-title');
const songArtist= document.getElementById('sv-song-artist');
const genresEl  = document.getElementById('sv-genres');
const tagsEl    = document.getElementById('sv-tags');
const canvas    = document.getElementById('sv-canvas');
const overlay   = document.getElementById('sv-canvas-overlay');
const caption   = document.getElementById('sv-caption');

// ── Search ────────────────────────────────────────────────────────
let _timer = null;

input.addEventListener('input', () => {
  clearTimeout(_timer);
  const q = input.value.trim();
  if (q.length < 2) { hideResults(); return; }
  _timer = setTimeout(() => doSearch(q), 220);
});

input.addEventListener('keydown', e => {
  if (e.key === 'Escape') hideResults();
  if (e.key === 'ArrowDown') {
    const first = resultsEl.querySelector('.sv-result-item');
    if (first) first.focus();
  }
});

document.addEventListener('click', e => {
  if (!e.target.closest('#sv-input') && !e.target.closest('#sv-results'))
    hideResults();
});

function hideResults() {
  resultsEl.style.display = 'none';
  resultsEl.innerHTML = '';
}

function doSearch(q) {
  fetch(`/song2vec/search/?q=${encodeURIComponent(q)}`)
    .then(r => r.json())
    .then(d => renderResults(d.results || []))
    .catch(() => {});
}

function renderResults(songs) {
  if (!songs.length) {
    resultsEl.innerHTML = '<div class="sv-no-results">No songs found in dataset</div>';
    resultsEl.style.display = 'block';
    return;
  }
  resultsEl.innerHTML = songs.map(s =>
    `<div class="sv-result-item" tabindex="0" data-id="${s.id}" data-name="${esc(s.name)}" data-artist="${esc(s.artist)}">
      <span class="sv-result-name">${esc(s.name)}</span>
      <span class="sv-result-artist">${esc(s.artist)}</span>
    </div>`
  ).join('');
  resultsEl.style.display = 'block';

  resultsEl.querySelectorAll('.sv-result-item').forEach(el => {
    el.addEventListener('click',   () => selectSong(el.dataset.id, el.dataset.name, el.dataset.artist));
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter')     selectSong(el.dataset.id, el.dataset.name, el.dataset.artist);
      if (e.key === 'ArrowDown') (el.nextElementSibling || el).focus();
      if (e.key === 'ArrowUp')   (el.previousElementSibling || input).focus();
    });
  });
}

// ── Select + Render ───────────────────────────────────────────────
function selectSong(id, name, artist) {
  hideResults();
  input.value = `${name}  ·  ${artist}`;

  // Show loading state on canvas
  setOverlay('RENDERING...');
  if (caption) caption.textContent = '';
  songInfo.style.display = 'none';
  idleHint.style.display = 'none';

  fetch(`/song2vec/render/?id=${encodeURIComponent(id)}`)
    .then(r => r.json())
    .then(data => {
      if (data.error) { setOverlay('ERROR: ' + data.error); return; }
      drawBlob(data);
    })
    .catch(() => setOverlay('ERROR: could not connect'));
}

function drawBlob(data) {
  const img = new Image();
  img.onload = () => {
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    overlay.classList.add('hidden');

    // Song info panel
    songTitle.textContent  = data.name;
    songArtist.textContent = data.artist;

    genresEl.innerHTML = data.genres.map(g =>
      `<span class="sv-chip genre">${esc(g)}</span>`
    ).join('');

    tagsEl.innerHTML = data.tags.map(t =>
      `<span class="sv-chip tag">${esc(t)}</span>`
    ).join('');

    songInfo.style.display = 'flex';
    idleHint.style.display = 'none';
    if (caption) caption.textContent = `${data.name}  ·  ${data.artist}`;

    drawScatter(data.genres);
  };
  img.onerror = () => setOverlay('ERROR: could not load image');
  img.src = 'data:image/png;base64,' + data.image;
}

// ── Scatter plots ─────────────────────────────────────────────────
const GENRE_LABELS = new Set([
  'metal','rock','pop','jazz','blues','folk','rap','edm','emo','punk',
  'classical','country','reggae','soul','funk','r&b','house','techno',
  'ambient','indie','grime','anime','kpop','bossa nova','flamenco',
  'gospel','disco','grunge','trance','ska','dnb','ebm','dub','lo-fi'
]);
const TAG_LABELS = new Set([
  'Energetic','Chill','Happy','Sad','Dark','Romantic','Aggressive',
  'Dreamy','Uplifting','Melancholic','Relaxing','Intense','Party',
  'Focus','Workout','Sleep','Angry','Nostalgic','Groovy','Epic'
]);

function drawScatter(activeGenres) {
  if (!_blobData) return;
  _drawScatterCanvas(
    document.getElementById('sv-scatter-genre'),
    _blobData.genres,
    activeGenres ? new Set(activeGenres.map(g => g.toLowerCase())) : null,
    GENRE_LABELS
  );
}

function _drawScatterCanvas(cvs, entries, activeSet, labelSet) {
  if (!cvs) return;
  const W = cvs.width, H = cvs.height;
  const ctx = cvs.getContext('2d');
  const pad = 24;

  ctx.fillStyle = '#050e0b';
  ctx.fillRect(0, 0, W, H);

  // Normalize coordinates to fill the canvas
  const vals = Object.values(entries);
  const minX = Math.min(...vals.map(v => v.x));
  const maxX = Math.max(...vals.map(v => v.x));
  const minY = Math.min(...vals.map(v => v.y));
  const maxY = Math.max(...vals.map(v => v.y));
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;

  const toX = x => pad + ((x - minX) / rangeX) * (W - pad * 2);
  const toY = y => pad + ((y - minY) / rangeY) * (H - pad * 2);

  const pairs = Object.entries(entries);

  // Pass 1: all background dots colored by their embedding color
  for (const [, v] of pairs) {
    ctx.beginPath();
    ctx.arc(toX(v.x), toY(v.y), 2.5, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${v.r},${v.g},${v.b},0.65)`;
    ctx.fill();
  }

  // Pass 2: labels for prominent entries (dim, no song selected yet)
  ctx.font = '12px "Share Tech Mono", monospace';
  ctx.textBaseline = 'middle';
  if (!activeSet) {
    for (const [name, v] of pairs) {
      if (!labelSet.has(name) && !labelSet.has(name.toLowerCase())) continue;
      const gx = toX(v.x), gy = toY(v.y);
      ctx.fillStyle = 'rgba(180,230,210,0.55)';
      ctx.fillText(name, gx + 6, gy);
    }
  }

  // Pass 3: active points — glow + bright dot + label
  if (activeSet) {
    // dim non-active
    ctx.fillStyle = 'rgba(5,14,11,0.5)';
    ctx.fillRect(0, 0, W, H);
    // redraw all dots dimmed
    for (const [, v] of pairs) {
      ctx.beginPath();
      ctx.arc(toX(v.x), toY(v.y), 2.5, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${v.r},${v.g},${v.b},0.25)`;
      ctx.fill();
    }

    for (const [name, v] of pairs) {
      if (!activeSet.has(name.toLowerCase())) continue;
      const gx = toX(v.x), gy = toY(v.y);
      // outer glow
      const grad = ctx.createRadialGradient(gx, gy, 0, gx, gy, 28);
      grad.addColorStop(0, `rgba(${v.r},${v.g},${v.b},0.6)`);
      grad.addColorStop(1, 'transparent');
      ctx.beginPath();
      ctx.arc(gx, gy, 28, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
      // bright dot
      ctx.beginPath();
      ctx.arc(gx, gy, 6, 0, Math.PI * 2);
      ctx.fillStyle = `rgb(${v.r},${v.g},${v.b})`;
      ctx.fill();
      // white ring
      ctx.beginPath();
      ctx.arc(gx, gy, 6, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255,255,255,0.7)';
      ctx.lineWidth = 1;
      ctx.stroke();
      // label
      ctx.fillStyle = `rgb(${v.r},${v.g},${v.b})`;
      ctx.font = '13px "Share Tech Mono", monospace';
      ctx.fillText(name, gx + 9, gy);
    }
  }
}

function setOverlay(msg) {
  overlay.classList.remove('hidden');
  document.getElementById('sv-canvas-msg').textContent = msg;
}

// ── Escape helper ─────────────────────────────────────────────────
function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
