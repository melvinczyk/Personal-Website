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
const HOT = 'button, a, .masonry-item, .video-tile, .disc-slot';
document.addEventListener('mouseenter', e => {
  if (e.target.closest && e.target.closest(HOT)) ensureSounds().then(() => playBuffer(hoverBuffer, 0.25));
}, true);
document.addEventListener('click', e => {
  if (e.target.closest && e.target.closest(HOT)) ensureSounds().then(() => playBuffer(clickBuffer, 0.35));
}, true);

// ══════════════════════════════════════════════════════════════════════
// DISC RAIL
// Each season is a "game". The rail holds every disc; moving left/right
// slides the track so the selected slot sits dead centre, and the media
// stage below re-renders with that disc's contents.
// ══════════════════════════════════════════════════════════════════════
const SLOT_GAP = 26;
let discIdx = 0;
let currentTab = 'screenshots';

// Slide the track so the selected slot lands on the rail's centre line.
// offsetWidth is the layout width, unaffected by the scale on inactive slots.
function layoutRail() {
  const track = document.getElementById('disc-track');
  const slot  = track.querySelector('.disc-slot');
  if (!slot) return;
  const w = slot.offsetWidth;
  track.style.transform = `translateX(${-(w / 2) - discIdx * (w + SLOT_GAP)}px)`;
}
window.addEventListener('resize', layoutRail);

function selectDisc(i) {
  if (!SEASONS.length) return;
  discIdx = (i + SEASONS.length) % SEASONS.length;
  const s = SEASONS[discIdx];

  layoutRail();
  document.querySelectorAll('.disc-slot').forEach((el, n) => el.classList.toggle('active', n === discIdx));

  document.getElementById('disc-pos').textContent   = discIdx + 1;
  document.getElementById('disc-title').textContent = s.name;
  document.getElementById('disc-desc').textContent  = s.description;

  // meters are scaled against the fullest disc, so the biggest reads full
  const maxShots = Math.max(1, ...SEASONS.map(x => x.screenshots.length));
  const maxClips = Math.max(1, ...SEASONS.map(x => x.videos.length));
  document.getElementById('meter-shots').style.width = (s.screenshots.length / maxShots * 100) + '%';
  document.getElementById('meter-clips').style.width = (s.videos.length / maxClips * 100) + '%';
  document.getElementById('count-shots').textContent = s.screenshots.length;
  document.getElementById('count-clips').textContent = s.videos.length;
  document.getElementById('tab-count-shots').textContent = s.screenshots.length;
  document.getElementById('tab-count-clips').textContent = s.videos.length;

  // the disc's own world behind the menu
  const bg = document.getElementById('console-bg');
  if (s.hero) { bg.style.backgroundImage = `url("${s.hero}")`; bg.classList.add('on'); }
  else        { bg.classList.remove('on'); }

  renderMedia();
}

// Clicking the highlighted disc loads it (its files open underneath);
// clicking any other disc just moves the rail to it first.
function discClick(i) {
  if (i === discIdx) { toggleMedia(); return; }
  selectDisc(i);
}
function toggleMedia(force) {
  const el = document.getElementById('disc-media');
  const open = typeof force === 'boolean' ? force : !el.classList.contains('open');
  el.classList.toggle('open', open);
  document.querySelector('.console-screen').classList.toggle('loaded', open);
  layoutRail();                       // the slots resized, so re-centre
  if (open) requestAnimationFrame(() =>
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' }));
}
function discStep(dir) {
  const wasOpen = document.getElementById('disc-media').classList.contains('open');
  selectDisc(discIdx + dir);
  toggleMedia(wasOpen);
}
// L1/R1 page the viewer while it is open, otherwise they change disc
function shoulder(dir) {
  if (lbOpen()) { lbStep(dir); return; }
  discStep(dir);
}

function renderMedia() {
  const s = SEASONS[discIdx];
  const shots = document.getElementById('panel-screenshots');
  const clips = document.getElementById('panel-videos');

  shots.innerHTML = s.screenshots.length ? `<div class="masonry-grid">${s.screenshots.map((it, i) => `
    <div class="masonry-item" onclick="openLightbox('screenshots', ${i})">
      <span class="icon x tile-x"></span>
      <img src="${it.url}" alt="${it.label}" loading="lazy">
      <div class="masonry-overlay"><div class="masonry-label">${it.label}</div></div>
    </div>`).join('')}</div>`
    : '<div class="empty-msg">// no screenshots on this disc</div>';

  clips.innerHTML = s.videos.length ? `<div class="video-grid">${s.videos.map((it, i) => `
    <div class="video-tile" onclick="openLightbox('videos', ${i})">
      <span class="icon x tile-x"></span>
      <video muted preload="metadata"><source src="${it.url}" type="video/mp4"></video>
      <div class="video-tile-overlay"><div class="play-circle">▶</div></div>
      <div class="tile-type-badge">VID</div>
      <div class="video-tile-label">${it.label}</div>
    </div>`).join('')}</div>`
    : '<div class="empty-msg">// no clips on this disc</div>';
}

// ── TABS ─────────────────────────────────────────────────────
function switchTab(tabName) {
  currentTab = tabName;
  toggleMedia(true);
  document.querySelectorAll('.media-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.dataset.panel === tabName));
}
function cycleTab() { switchTab(currentTab === 'screenshots' ? 'videos' : 'screenshots'); }

// ── CONTROLLER ACTIONS ───────────────────────────────────────
function jumpTop()   { document.getElementById('stage').scrollTo({ top: 0, behavior: 'smooth' }); }
function jumpMedia() { toggleMedia(true); }
function loadDisc()  { toggleMedia(); }
// ○ backs out one level: viewer, then the open disc, then home
function psxBack() {
  if (lbOpen()) { closeLightbox(); return; }
  if (document.getElementById('disc-media').classList.contains('open')) { toggleMedia(false); return; }
  window.location.href = HOME_URL;
}

// ── VIEWER ───────────────────────────────────────────────────
let lbMediaType = 'screenshots';
let lbIdx = 0;
function lbOpen() { return document.getElementById('lightbox').classList.contains('open'); }

function openLightbox(mediaType, idx) {
  lbMediaType = mediaType;
  lbIdx = idx;
  renderLightbox();
  document.getElementById('lightbox').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function renderLightbox() {
  const items = SEASONS[discIdx][lbMediaType];
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
  const typeStr = lbMediaType === 'screenshots' ? 'IMG' : 'VID';
  document.getElementById('lightbox-caption').textContent =
    `DISC ${SEASONS[discIdx].number} · ${typeStr} · ${item.label}`;
  document.getElementById('lb-counter-text').textContent =
    `${String(lbIdx + 1).padStart(3, '0')} / ${String(total).padStart(3, '0')}`;
}

function lbStep(dir) {
  const items = SEASONS[discIdx][lbMediaType];
  if (!items || !items.length) return;
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

// keyboard mirrors the on-screen pad
document.addEventListener('keydown', e => {
  if (e.target.matches('input, textarea')) return;
  if (lbOpen()) {
    if (e.key === 'Escape')     closeLightbox();
    if (e.key === 'ArrowRight') lbStep(1);
    if (e.key === 'ArrowLeft')  lbStep(-1);
    return;
  }
  if (e.key === 'ArrowRight') { e.preventDefault(); discStep(1); }
  if (e.key === 'ArrowLeft')  { e.preventDefault(); discStep(-1); }
  if (e.key === 'ArrowDown')  { e.preventDefault(); jumpMedia(); }
  if (e.key === 'ArrowUp')    { e.preventDefault(); jumpTop(); }
  if (e.key === 'Enter')      { e.preventDefault(); loadDisc(); }
  if (e.key === 'Backspace')  { e.preventDefault(); psxBack(); }
  if (e.key === 'Tab')        { e.preventDefault(); cycleTab(); }
});

selectDisc(0);
