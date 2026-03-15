setInterval(() => {
  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString('en-US', { hour12: false });
}, 1000);

// ── SOUNDS ───────────────────────────────────────────────────
let audioCtx = null, hoverBuffer = null, clickBuffer = null;

function getCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}
async function loadSound(url) {
  try {
    const ctx = getCtx();
    const res = await fetch(url);
    const arr = await res.arrayBuffer();
    return ctx.decodeAudioData(arr);
  } catch(e) { return null; }
}
function playBuffer(buffer, volume = 0.3) {
  if (!buffer) return;
  const ctx = getCtx();
  ctx.resume().then(() => {
    const src  = ctx.createBufferSource();
    const gain = ctx.createGain();
    gain.gain.value = volume;
    src.buffer = buffer;
    src.connect(gain);
    gain.connect(ctx.destination);
    src.start(0);
  });
}

let soundsLoaded = false;
async function ensureSounds() {
  if (soundsLoaded) return;
  soundsLoaded = true;
  [hoverBuffer, clickBuffer] = await Promise.all([
    loadSound(GALLERY_URLS.hover),
    loadSound(GALLERY_URLS.click),
  ]);
}
document.addEventListener('mouseenter', e => {
  if (e.target.matches('button, a, .sb-btn, .sb-season-btn, .masonry-item, .video-tile, .lb-nav-btn, .back-btn, .season-header'))
    ensureSounds().then(() => playBuffer(hoverBuffer, 0.25));
}, true);
document.addEventListener('click', e => {
  if (e.target.matches('button, a, .sb-btn, .sb-season-btn, .masonry-item, .video-tile, .lb-nav-btn, .back-btn, .season-header'))
    ensureSounds().then(() => playBuffer(clickBuffer, 0.35));
}, true);

function toggleSeason(seasonNum) {
  const block  = document.getElementById(`season-${seasonNum}`);
  const sbBtn  = document.getElementById(`sb-season-${seasonNum}`);
  const isOpen = block.classList.contains('open');

  block.classList.toggle('open', !isOpen);
  if (sbBtn) sbBtn.classList.toggle('open', !isOpen);

  if (!isOpen) {
    setTimeout(() => {
      block.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  }
}

function scrollToSeason(seasonNum) {
  const block = document.getElementById(`season-${seasonNum}`);
  if (!block) return;
  if (!block.classList.contains('open')) toggleSeason(seasonNum);
  else block.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── TABS ──────────────────────────────────────────────────────
function switchTab(seasonNum, tabName) {
  const body = document.getElementById(`body-${seasonNum}`);
  body.querySelectorAll('.media-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
  body.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.dataset.panel === tabName));
}

// ── LIGHTBOX ─────────────────────────────────────────────────
// GALLERY_DATA injected by template:
// { "season1": { "screenshots": [...], "videos": [...] }, ... }

let lbSeasonKey = null;
let lbMediaType = null;
let lbIdx       = 0;

function openLightbox(seasonKey, mediaType, idx) {
  lbSeasonKey = seasonKey;
  lbMediaType = mediaType;
  lbIdx       = idx;
  renderLightbox();
  document.getElementById('lightbox').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function renderLightbox() {
  const items = GALLERY_DATA[lbSeasonKey]?.[lbMediaType];
  if (!items || !items[lbIdx]) return;

  const item = items[lbIdx];
  const wrap = document.getElementById('lightbox-media-wrap');
  wrap.innerHTML = '';

  if (item.type === 'img') {
    const img = document.createElement('img');
    img.src = item.url;
    img.alt = item.label;
    wrap.appendChild(img);
  } else {
    const vid = document.createElement('video');
    vid.controls = true;
    vid.autoplay = true;
    const src = document.createElement('source');
    src.src  = item.url;
    src.type = 'video/mp4';
    vid.appendChild(src);
    wrap.appendChild(vid);
  }

  const total   = items.length;
  const season  = lbSeasonKey.replace('season', 'S');
  const typeStr = lbMediaType === 'screenshots' ? 'IMG' : 'VID';

  document.getElementById('lightbox-caption').textContent =
    `${season} · ${typeStr} · ${item.label}`;
  document.getElementById('lightbox-counter').textContent =
    `${lbIdx + 1} / ${total}`;
}

function lbStep(dir) {
  const items = GALLERY_DATA[lbSeasonKey]?.[lbMediaType];
  if (!items) return;
  const vid = document.querySelector('#lightbox-media-wrap video');
  if (vid) vid.pause();
  lbIdx = (lbIdx + dir + items.length) % items.length;
  renderLightbox();
}

function closeLightbox() {
  const vid = document.querySelector('#lightbox-media-wrap video');
  if (vid) vid.pause();
  document.getElementById('lightbox').classList.remove('open');
  document.body.style.overflow = '';
}

document.getElementById('lightbox').addEventListener('click', e => {
  if (e.target === document.getElementById('lightbox')) closeLightbox();
});

document.addEventListener('keydown', e => {
  if (!document.getElementById('lightbox').classList.contains('open')) return;
  if (e.key === 'Escape')     closeLightbox();
  if (e.key === 'ArrowRight') lbStep(1);
  if (e.key === 'ArrowLeft')  lbStep(-1);
});