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

// Each season is a "game" on the rail: moving left/right slides the track so
// the selected slot sits dead centre and the stage re-renders with its files.
const SLOT_GAP = 26;
let discIdx = 0;
let currentTab = 'screenshots';

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

  // scaled against the fullest disc, so the biggest one reads full
  const maxShots = Math.max(1, ...SEASONS.map(x => x.screenshots.length));
  const maxClips = Math.max(1, ...SEASONS.map(x => x.videos.length));
  document.getElementById('meter-shots').style.width = (s.screenshots.length / maxShots * 100) + '%';
  document.getElementById('meter-clips').style.width = (s.videos.length / maxClips * 100) + '%';
  document.getElementById('count-shots').textContent = s.screenshots.length;
  document.getElementById('count-clips').textContent = s.videos.length;
  document.getElementById('tab-count-shots').textContent = s.screenshots.length;
  document.getElementById('tab-count-clips').textContent = s.videos.length;

  const bg = document.getElementById('console-bg');
  if (s.hero) { bg.style.backgroundImage = `url("${s.hero}")`; bg.classList.add('on'); }
  else        { bg.classList.remove('on'); }

  renderMedia();
  renderRoster();
}

// The roster is a second rail: one card per player, centred like the discs.
// Each card carries a CSS-3D model of that player's own skin (mcskin.js).
const ROSTER_GAP = 18;
let playerIdx = 0;

function renderRoster() {
  const el = document.getElementById('roster');
  const players = SEASONS[discIdx].roster || [];
  playerIdx = 0;

  if (!players.length) { el.innerHTML = ''; el.classList.remove('on'); return; }
  el.classList.add('on');
  el.dataset.season = SEASONS[discIdx].number;

  el.innerHTML = `
    <div class="roster-head">
      <span class="rh-t">${rosterTitle()}</span>
      <span class="rh-r"><span id="roster-pos">1</span> OF ${players.length}</span>
    </div>
    <div class="roster-rail">
      <button class="rr-arrow prev" onclick="playerStep(-1)" aria-label="Previous player">◂</button>
      <button class="rr-arrow next" onclick="playerStep(1)" aria-label="Next player">▸</button>
      <div class="roster-track" id="roster-track">${players.map((p, i) => `
        <div class="roster-slot" id="player-${i}" onclick="playerClick(${i})">
          <div class="roster-card">
            <div class="rc-stage">
              <div class="rc-pad"></div>
              <div class="rc-model" id="rc-model-${i}"></div>
              <div class="rc-scan"></div>
            </div>
            <div class="rc-info">
              <div class="rc-name">${p.name}<span class="rc-mode">${p.gamemode}</span></div>
              <div class="rc-id">ID ${p.uuid.slice(0, 8).toUpperCase()} · ${p.dimension}</div>
              <div class="rc-meters">
                ${meter('HEALTH', p.health_pct, `${p.health} / ${p.max_health}`, 'hp')}
                ${meter('ARMOR', p.defence_pct, `${p.defence}${p.defence_whole ? '' : '+'}`, 'armor')}
                ${meter('TOUGHNESS', p.tough_pct, `${p.toughness}${p.defence_whole ? '' : '+'}`, 'tough')}
                ${meter('LEVEL ' + p.level, p.xp_pct, `${p.xp} XP`, 'xp')}
              </div>
              <div class="rc-gear">
                ${gearChip('HELD', p.held)}
                ${gearChip('OFF', p.offhand)}
                ${p.armor.map(a => gearChip(a.slot, a)).join('')}
              </div>
              <div class="rc-where">
                <span>X ${p.pos.x}</span><span>Y ${p.pos.y}</span><span>Z ${p.pos.z}</span>
                ${p.absorption ? `<span class="rc-abs">+${p.absorption} ABSORB</span>` : ''}
                ${p.effects ? `<span>${p.effects} EFFECT${p.effects > 1 ? 'S' : ''}</span>` : ''}
              </div>
              <div class="rc-tabs">
                <button class="rc-tab" onclick="showPanel(event, ${i}, 'bag')">
                  <span class="icon triangle"></span><span class="lbl">INVENTORY</span>
                  <b>${p.carried.filter(Boolean).length}/36</b>
                </button>
                <button class="rc-tab" onclick="showPanel(event, ${i}, 'attr')">
                  <span class="icon square"></span><span class="lbl">ATTRIBUTES</span>
                  <b>${p.attributes.length}</b>
                </button>
              </div>
            </div>
            <div class="rc-panel" id="rc-panel-${i}" onclick="event.stopPropagation()">
              <div class="rp-head">
                <span class="rp-title"></span>
                <button class="rp-close" onclick="hidePanel(${i})" aria-label="Close">
                  <span class="icon circle"></span><span class="lbl">CLOSE</span>
                </button>
              </div>
              <div class="rp-body"></div>
              <div class="rp-foot">
                <button class="rp-nav" onclick="panelStep(event, -1)">
                  <span class="icon l1"></span><span class="lbl">PREV</span>
                </button>
                <span class="rp-who">${p.name}</span>
                <button class="rp-nav" onclick="panelStep(event, 1)">
                  <span class="lbl">NEXT</span><span class="icon r1"></span>
                </button>
              </div>
            </div>
          </div>
        </div>`).join('')}
      </div>
    </div>`;

  selectPlayer(0);
}

// A player in a modded set can run to a thousand boxes, so a model is only
// built once its card is the one in the middle or sits next to it.
function mountPlayer(i) {
  const players = SEASONS[discIdx].roster || [];
  if (i < 0 || i >= players.length) return;
  const box = document.getElementById(`rc-model-${i}`);
  // the renderer is a module, so it lands after this script has run
  if (!box || box.dataset.built || typeof buildPlayerModel !== 'function') return;

  box.dataset.built = '1';
  const p = players[i];
  if (p.skin) buildPlayerModel(box, { skin: p.skin, slim: p.slim, worn: p.worn });
  else box.classList.add('rc-noskin');
}

// Each season theming its own roster: the heading is the first thing that
// tells you which server you are looking at.
const ROSTER_TITLES = {
  1: '▣ SURVIVORS',
  2: '✦ ADVENTURING PARTY',
  3: '◈ PERSONNEL FILE',
  4: '⚓ THE CREW',
};
function rosterTitle() {
  return ROSTER_TITLES[SEASONS[discIdx].number] || '◈ PLAYER ROSTER';
}

function layoutRoster() {
  const track = document.getElementById('roster-track');
  if (!track) return;
  const slot = track.querySelector('.roster-slot');
  if (!slot) return;
  const w = slot.offsetWidth;
  track.style.transform = `translateX(${-(w / 2) - playerIdx * (w + ROSTER_GAP)}px)`;
}
window.addEventListener('resize', layoutRoster);

function selectPlayer(i) {
  const players = SEASONS[discIdx].roster || [];
  if (!players.length) return;
  playerIdx = (i + players.length) % players.length;
  document.querySelectorAll('.rc-panel.on').forEach(el =>
    hidePanel(Number(el.id.replace('rc-panel-', ''))));
  document.querySelectorAll('.roster-slot').forEach((el, n) =>
    el.classList.toggle('active', n === playerIdx));
  document.getElementById('roster-pos').textContent = playerIdx + 1;
  [-1, 0, 1].forEach(d => mountPlayer(playerIdx + d));
  if (typeof dressModel === 'function') dressRail();
  layoutRoster();
}

// The model in the middle is the only one wearing its armor, and cards that
// drift far enough along the rail give theirs back.
function dressRail() {
  document.querySelectorAll('#roster .rc-model[data-built]').forEach(el => {
    if (el.id === `rc-model-${playerIdx}`) return;
    undressModel(el);
    // a card this far along the rail will not be looked at again soon
    if (Math.abs(Number(el.id.replace('rc-model-', '')) - playerIdx) > 2) {
      disposeModel(el);
      el.innerHTML = '';
      el.className = 'rc-model';
      delete el.dataset.built;
    }
  });
  dressModel(document.getElementById(`rc-model-${playerIdx}`));
}
function playerStep(dir) { selectPlayer(playerIdx + dir); }
function playerClick(i) { if (i !== playerIdx) selectPlayer(i); }

// The two drawers: the card is only so big, so each opens over the whole of
// it rather than pushing the rest of the card around.
function showPanel(event, i, view) {
  if (event) event.stopPropagation();
  const panel = document.getElementById(`rc-panel-${i}`);
  if (!panel) return;
  if (panel.classList.contains('on') && panel.dataset.view === view) {
    return hidePanel(i);
  }
  const player = (SEASONS[discIdx].roster || [])[i];
  panel.dataset.view = view;
  panel.querySelector('.rp-title').textContent =
    view === 'bag' ? 'INVENTORY' : 'ATTRIBUTES';
  panel.querySelector('.rp-body').innerHTML =
    view === 'bag' ? bagPanel(player) : attrPanel(player);
  panel.classList.add('on');
  markTabs(i, view);
}

function markTabs(i, view) {
  const tabs = document.querySelectorAll(`#player-${i} .rc-tab`);
  tabs.forEach((tab, n) => tab.classList.toggle('active',
    view === (n === 0 ? 'bag' : 'attr')));
}

function hidePanel(i) {
  const panel = document.getElementById(`rc-panel-${i}`);
  if (panel) panel.classList.remove('on');
  markTabs(i, null);
}

function panelOpen() { return document.querySelector('.rc-panel.on'); }

// the shoulder buttons walk the roster without leaving the drawer
function panelStep(event, dir) {
  event.stopPropagation();
  const drawer = panelOpen();
  const view = drawer && drawer.dataset.view;
  playerStep(dir);
  if (view) showPanel(null, playerIdx, view);
}

// the grid the game itself uses: three rows of storage over the hotbar
function bagPanel(p) {
  const tile = item => {
    if (!item) return '<span class="bag-cell"></span>';
    const art = item.icon
      ? `<img src="${item.icon}" alt="" loading="lazy">`
      : `<i>${item.label.slice(0, 2)}</i>`;
    return `<span class="bag-cell full${item.enchants ? ' ench' : ''}"
      title="${item.label}${item.count > 1 ? ` x${item.count}` : ''} · ${item.mod}">
      ${art}${item.count > 1 ? `<b>${item.count}</b>` : ''}</span>`;
  };
  const cells = p.carried.map(tile);
  return `<div class="bag-wrap">
    <div class="bag-grid">${cells.slice(0, 27).join('')}</div>
    <div class="bag-grid hot">${cells.slice(27).join('')}</div>
  </div>`;
}

function attrPanel(p) {
  if (!p.attributes.length) return '<p class="rp-none">nothing recorded</p>';
  return `<div class="attr-list">${p.attributes.map(a => `
    <span class="attr-row${a.core ? ' core' : ''}" title="${a.label}${a.mod ? ` · ${a.mod}` : ''}">
      <b>${a.label}</b>${a.mod ? `<i>${a.mod}</i>` : ''}
      <em>${a.value}</em>
    </span>`).join('')}</div>`;
}

function meter(name, pct, value, cls) {
  return `<div class="ps-row rc-row ${cls}">
    <span class="ps-nm">${name}</span>
    <div class="ps-prog"><div class="ps-fill" style="width:${pct}%"></div></div>
    <span class="ps-pc">${value}</span>
  </div>`;
}

// Enchanted gear gets the PS1 highlight, the way a menu marks a special item.
// Armor the model cannot wear is marked so the card still accounts for it.
function gearChip(slot, item) {
  if (!item) return '';
  const count = item.count > 1 ? ` x${item.count}` : '';
  const off = item.shown === false;
  const note = off ? `${item.mod} · drawn by the mod, not shown on the model` : item.mod;
  return `<span class="rc-chip${item.enchants ? ' ench' : ''}${off ? ' unworn' : ''}" title="${note}">
    <b>${slot}</b>${item.label}${count}${item.enchants ? `<i>+${item.enchants}</i>` : ''}
  </span>`;
}

// Clicking the highlighted disc loads it; any other disc moves the rail first.
function discClick(i) {
  if (i === discIdx) { toggleMedia(); return; }
  selectDisc(i);
}
function toggleMedia(force) {
  const el = document.getElementById('disc-media');
  const open = typeof force === 'boolean' ? force : !el.classList.contains('open');
  el.classList.toggle('open', open);
  document.querySelector('.console-screen').classList.toggle('loaded', open);
  layoutRail();   // the slots resized, so re-centre
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

function switchTab(tabName) {
  currentTab = tabName;
  toggleMedia(true);
  document.querySelectorAll('.media-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.dataset.panel === tabName));
}
function cycleTab() { switchTab(currentTab === 'screenshots' ? 'videos' : 'screenshots'); }

function jumpTop()   { document.getElementById('stage').scrollTo({ top: 0, behavior: 'smooth' }); }
function jumpMedia() { toggleMedia(true); }
function loadDisc()  { toggleMedia(); }
// ○ backs out one level: viewer, then the open disc, then home
function psxBack() {
  if (lbOpen()) { closeLightbox(); return; }
  const drawer = panelOpen();
  if (drawer) { hidePanel(Number(drawer.id.replace('rc-panel-', ''))); return; }
  if (document.getElementById('disc-media').classList.contains('open')) { toggleMedia(false); return; }
  window.location.href = HOME_URL;
}

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

// the model renderer is a module and so arrives after this file: once it is
// here, put the roster on
window.addEventListener('mcmodel-ready', () => { if (SEASONS.length) selectPlayer(playerIdx); });
