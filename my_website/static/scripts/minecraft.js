// A button through the portal sounds like Minecraft: one click, and nothing on
// hover. A sound on every pointer crossing is a codec-screen habit; on a page
// you scroll through sixty boss cards it is a rattle.
let audioCtx = null, clickBuffer = null, clickFrom = 0;

function getCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

// Where the sound actually starts. A clip exported from the game can carry
// half a second of silence in front of it, and playing that from zero puts the
// click half a second after the press, which reads as lag rather than as a
// quiet file. Found rather than hard-coded, so swapping the mp3 needs no sums.
function soundStart(buffer) {
  const d = buffer.getChannelData(0);
  let peak = 0;
  for (let i = 0; i < d.length; i++) { const v = Math.abs(d[i]); if (v > peak) peak = v; }
  if (!peak) return 0;
  const floor = peak * 0.02;
  let i = 0;
  while (i < d.length && Math.abs(d[i]) < floor) i++;
  // back off a couple of milliseconds so the attack is not clipped off
  return Math.max(0, (i / buffer.sampleRate) - 0.004);
}

async function loadSound(url) {
  try {
    const res = await fetch(url);
    return await getCtx().decodeAudioData(await res.arrayBuffer());
  } catch (e) { return null; }
}

function playBuffer(buffer, volume = 0.3, from = 0) {
  if (!buffer) return;
  const ctx = getCtx();
  const fire = () => {
    const src  = ctx.createBufferSource();
    const gain = ctx.createGain();
    gain.gain.value = volume;
    src.buffer = buffer;
    src.connect(gain);
    gain.connect(ctx.destination);
    src.start(0, from);
  };
  // resume() returns a promise even when the context is already running, and
  // waiting on it costs a frame the first click can least afford
  if (ctx.state === 'running') fire(); else ctx.resume().then(fire);
}

// Fetched and decoded up front, so the first click plays rather than starting
// a download. It cannot sound until the page has been interacted with anyway,
// which is what the resume above is for.
const clickReady = loadSound(PORTAL_URLS.click).then(buf => {
  clickBuffer = buf;
  if (buf) clickFrom = soundStart(buf);
});

const HOT = 'button, a, .masonry-item, .video-tile, .disc-slot';
document.addEventListener('pointerdown', e => {
  if (!e.target.closest || !e.target.closest(HOT)) return;
  if (clickBuffer) playBuffer(clickBuffer, 0.35, clickFrom);
  else clickReady.then(() => playBuffer(clickBuffer, 0.35, clickFrom));
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
  document.getElementById('entry-roster-count').textContent = (s.roster || []).length;
  document.getElementById('entry-gallery-count').textContent =
    s.screenshots.length + s.videos.length;
  document.getElementById('entry-roster').classList.toggle('empty', !(s.roster || []).length);
  document.getElementById('entry-gallery').classList.toggle('empty',
    !(s.screenshots.length + s.videos.length));
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

  // deaths only mean something next to each other: the bar is scaled against
  // whoever on this server has died the most rather than a made-up ceiling
  const worst = Math.max(1, ...players.map(p => (p.live && p.live.deaths) || 0));

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
              <div class="rc-name">${p.name}<span class="rc-mode${p.live && p.live.dead ? ' down' : ''}">${p.gamemode}</span></div>
              <div class="rc-id">${['ID ' + p.uuid.slice(0, 8).toUpperCase(), p.dimension]
                .filter(Boolean).join(' · ')}</div>
              <div class="rc-meters">
                ${meter('HEALTH', p.health_pct, `${p.health} / ${p.max_health}`, 'hp')}
                ${p.saved ? meter('ARMOR', p.defence_pct, `${p.defence}${p.defence_whole ? '' : '+'}`, 'armor') : ''}
                ${p.saved ? meter('TOUGHNESS', p.tough_pct, `${p.toughness}${p.defence_whole ? '' : '+'}`, 'tough') : ''}
                ${meter('LEVEL ' + p.level, p.xp_pct, p.saved ? `${p.xp} XP` : '', 'xp')}
                ${p.saved || !p.live ? '' :
                  meter('DEATHS', Math.round(p.live.deaths / worst * 100), `${p.live.deaths}`, 'deaths')}
              </div>
              <div class="rc-gear">
                ${gearChip('HELD', p.held)}
                ${gearChip('OFF', p.offhand)}
                ${p.armor.map(a => gearChip(a.slot, a)).join('')}
              </div>
              <div class="rc-where">
                ${p.pos ? `<span>X ${p.pos.x}</span><span>Y ${p.pos.y}</span><span>Z ${p.pos.z}</span>` : ''}
                ${p.absorption ? `<span class="rc-abs">+${p.absorption} ABSORB</span>` : ''}
                ${p.effects ? `<span>${p.effects} EFFECT${p.effects > 1 ? 'S' : ''}</span>` : ''}
                ${p.live ? `<span class="rc-live">◉ ${p.live.playtime} PLAYED</span>` : ''}
              </div>
              <div class="rc-tabs">
                ${p.carried.length ? `<button class="rc-tab" onclick="showPanel(event, ${i}, 'bag')">
                  <span class="icon triangle"></span><span class="lbl">INVENTORY</span>
                  <b>${p.carried.filter(Boolean).length}/36</b>
                </button>` : ''}
                ${p.attributes.length ? `<button class="rc-tab" onclick="showPanel(event, ${i}, 'attr')">
                  <span class="icon square"></span><span class="lbl">ATTRIBUTES</span>
                  <b>${p.attributes.length}</b>
                </button>` : ''}
                ${p.live ? `<button class="rc-tab" onclick="showPanel(event, ${i}, 'live')">
                  <span class="icon x"></span><span class="lbl">SERVER</span>
                  <b>${p.live.playtime}</b>
                </button>` : ''}
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
  5: '◉ ON THE SERVER',
};
function rosterTitle() {
  return ROSTER_TITLES[SEASONS[discIdx].number] || '◈ PLAYER ROSTER';
}

function layoutRoster() {
  const track = document.getElementById('roster-track');
  if (!track) return;
  const slot = track.querySelector('.roster-slot');
  // a rail that is not on screen measures zero, and centring against that
  // would throw away the offset the last real measurement worked out
  if (!slot || !slot.offsetWidth) return;
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
  panel.querySelector('.rp-title').textContent = PANEL_TITLES[view] || '';
  panel.querySelector('.rp-body').innerHTML =
    view === 'bag' ? bagPanel(player)
    : view === 'attr' ? attrPanel(player)
    : livePanel(player);
  panel.classList.add('on');
  markTabs(i, view);
}

const PANEL_TITLES = { bag: 'INVENTORY', attr: 'ATTRIBUTES', live: 'SERVER RECORD' };

// a card only carries the tabs it has something to put behind, so which tab is
// which is read off the button rather than counted
function markTabs(i, view) {
  document.querySelectorAll(`#player-${i} .rc-tab`).forEach(tab => {
    const own = (tab.getAttribute('onclick') || '').match(/'(\w+)'\)$/);
    tab.classList.toggle('active', !!own && own[1] === view);
  });
}

function hidePanel(i) {
  const panel = document.getElementById(`rc-panel-${i}`);
  if (panel) panel.classList.remove('on');
  markTabs(i, null);
  hideItemTip();
}

function panelOpen() { return document.querySelector('.rc-panel.on'); }

// the shoulder buttons walk the roster without leaving the drawer
function panelStep(event, dir) {
  event.stopPropagation();
  const drawer = panelOpen();
  const view = drawer && drawer.dataset.view;
  playerStep(dir);
  const next = (SEASONS[discIdx].roster || [])[playerIdx];
  const has = { bag: next && next.carried.length,
                attr: next && next.attributes.length,
                live: next && next.live };
  if (view && has[view]) showPanel(null, playerIdx, view);
}

// the grid the game itself uses: three rows of storage over the hotbar
function bagPanel(p) {
  const tile = item => {
    if (!item) return '<span class="bag-cell"></span>';
    const art = item.icon
      ? `<img src="${item.icon}" alt="" loading="lazy">`
      : `<i>${item.label.slice(0, 2)}</i>`;
    return `<span class="bag-cell full${item.enchants ? ' ench' : ''}"
      data-name="${item.label}">
      ${art}${item.count > 1 ? `<b>${item.count}</b>` : ''}</span>`;
  };
  const cells = p.carried.map(tile);
  return `<div class="bag-wrap">
    <div class="bag-grid">${cells.slice(0, 27).join('')}</div>
    <div class="bag-grid hot">${cells.slice(27).join('')}</div>
  </div>`;
}

// A slot names what is in it while the pointer is over it. The tip hangs off
// the page rather than the panel, so a slot in the top row is not cut off by
// the drawer it sits in.
let itemTip = null;
let tipCell = null;

function showItemTip(cell) {
  if (!itemTip) {
    itemTip = document.createElement('div');
    itemTip.id = 'item-tip';
    document.body.appendChild(itemTip);
  }
  itemTip.textContent = cell.dataset.name;
  itemTip.style.borderColor =
    getComputedStyle(cell).getPropertyValue('--rc').trim() || 'rgba(255,255,255,0.45)';
  itemTip.classList.add('on');

  const slot = cell.getBoundingClientRect();
  const tip = itemTip.getBoundingClientRect();
  const left = Math.min(Math.max(6, slot.left + (slot.width - tip.width) / 2),
                        window.innerWidth - tip.width - 6);
  const above = slot.top - tip.height - 6;
  itemTip.style.left = `${Math.round(left)}px`;
  itemTip.style.top = `${Math.round(above < 6 ? slot.bottom + 6 : above)}px`;
}

function hideItemTip() {
  tipCell = null;
  if (itemTip) itemTip.classList.remove('on');
}

document.addEventListener('mouseover', e => {
  const cell = e.target.closest ? e.target.closest('.bag-cell.full') : null;
  if (cell === tipCell) return;
  if (cell) { tipCell = cell; showItemTip(cell); } else { hideItemTip(); }
});

function attrPanel(p) {
  if (!p.attributes.length) return '<p class="rp-none">nothing recorded</p>';
  return `<div class="attr-list">${p.attributes.map(a => `
    <span class="attr-row${a.core ? ' core' : ''}" title="${a.label}${a.mod ? ` · ${a.mod}` : ''}">
      <b>${a.label}</b>${a.mod ? `<i>${a.mod}</i>` : ''}
      <em>${a.value}</em>
    </span>`).join('')}</div>`;
}

// What the server itself has on a player: hours, deaths, damage traded, ground
// covered. None of it is in a save, so this is the only place it can come from.
function livePanel(p) {
  // a roster card carries its server record under .live; a board row is one
  const L = p.live || p;
  if (!L || L.deaths === undefined)
    return '<p class="rp-none">the server has not reported this player</p>';

  const cell = (label, value, note) => value === null || value === undefined ? '' :
    `<span class="live-cell"><i>${label}</i><b>${value}</b>${note ? `<u>${note}</u>` : ''}</span>`;

  const stats = [
    cell('PLAY TIME', L.playtime),
    cell('DEATHS', L.deaths,
         L.dead ? 'ON THE RESPAWN SCREEN'
         : L.deaths ? `LAST ${L.since_death} AGO` : 'UNBEATEN'),
    cell('MOB KILLS', L.mob_kills, L.ratio === null ? '' : `${L.ratio} PER DEATH`),
    cell('PVP KILLS', L.player_kills),
    cell('DAMAGE DEALT', L.dealt),
    cell('DAMAGE TAKEN', L.taken),
    cell('BLOCKS MOVED', L.travelled, `${L.sprinted} SPRINTED`),
    cell('JUMPS', L.jumps),
  ].join('');

  const bosses = L.bosses.length ? `
    <div class="live-boss">
      <div class="lb-head"><span>BOSSES</span><b>${L.boss_kills} KILL${L.boss_kills === 1 ? '' : 'S'}</b></div>
      ${L.bosses.map(b => `<span class="lb-row">
        <b>${b.name}</b><i>TIER ${b.tier}</i>
        <em>x${b.kills}</em><u>${b.damage} DMG · ${b.last}</u>
      </span>`).join('')}
    </div>` : '<div class="live-boss empty">no boss has gone down yet</div>';

  return `<div class="live-wrap">
    <div class="live-grid">${stats}</div>
    ${bosses}
    <div class="live-when">SERVER READ ${L.recorded}</div>
  </div>`;
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
  toggleMedia(false);
  toggleRoster(false);
}
// The disc has two screens on it and neither opens on its own: picking a
// disc leaves you on its menu, the way a console does.
function openSection(id, entry, force) {
  const el = document.getElementById(id);
  const open = typeof force === 'boolean' ? force : !el.classList.contains('open');
  el.classList.toggle('open', open);
  document.getElementById(entry).classList.toggle('open', open);
  if (open) closeOthers(id);
  syncScreen();
  layoutRail();     // the slots resized, so re-centre
  layoutRoster();   // the roster rail could not be measured while it was shut
  if (open) requestAnimationFrame(() => {
    layoutRoster();
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}

function closeOthers(keep) {
  for (const [id, entry] of [['roster', 'entry-roster'], ['disc-media', 'entry-gallery']]) {
    if (id === keep) continue;
    document.getElementById(id).classList.remove('open');
    document.getElementById(entry).classList.remove('open');
  }
}

// the disc rail gives up room whenever either screen is showing
function syncScreen() {
  const open = document.querySelector('#roster.open, #disc-media.open');
  document.querySelector('.console-screen').classList.toggle('loaded', !!open);
}

function toggleMedia(force)  { openSection('disc-media', 'entry-gallery', force); }
function toggleRoster(force) { openSection('roster', 'entry-roster', force); }
function sectionOpen() { return document.querySelector('#roster.open, #disc-media.open'); }
function discStep(dir) {
  selectDisc(discIdx + dir);
  toggleMedia(false);
  toggleRoster(false);
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
  const screen = sectionOpen();
  if (screen) {
    return screen.id === 'roster' ? toggleRoster(false) : toggleMedia(false);
  }
  if (liveOpen) { toggleLive(liveOpen); return; }
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


// ── the live season ─────────────────────────────────────────────────────────
// The season being played does not get a disc. It gets the top of the screen
// and a board that asks the server for new numbers while you are looking at
// it, so what you are reading is minutes old at worst rather than whenever
// somebody last remembered to copy a folder.

// How often the page asks its own server for the board. That read is a local
// file, not the game host: it costs nothing and keeps the age counter honest.
// It is no use running faster than the pull behind it, though, which is a
// quarter of an hour, so this is a minute rather than the twenty seconds it
// was when every poll could bring something new.
const LIVE_EVERY = 60;          // seconds between polls
let liveBoard = typeof LIVE_BOARD !== 'undefined' ? LIVE_BOARD : null;
let liveAt    = Date.now();     // when the board we are showing was read
let liveOpen  = null;           // uuid of the row expanded, if any
let liveDue   = LIVE_EVERY;
let livePolling = false;
let liveChase   = null;         // timer chasing a pull that has not finished
let liveChases  = 0;            // how many times this one has been chased

// matches _span() on the server, so the age counter reads the same whether it
// came down with the page or was counted up here since
function fmtSpan(seconds) {
  seconds = Math.max(0, Math.round(seconds));
  const d = Math.floor(seconds / 86400),
        h = Math.floor(seconds % 86400 / 3600),
        m = Math.floor(seconds % 3600 / 60);
  if (d) return `${d}d ${String(h).padStart(2, '0')}h`;
  if (h) return `${h}h ${String(m).padStart(2, '0')}m`;
  if (m) return `${m}m`;
  return `${seconds}s`;
}

// The board is rebuilt only when the cast changes. A model is a WebGL scene
// and there are ten of them on this screen: tearing them all down every twenty
// seconds to write the same numbers back would be absurd, so a poll that finds
// the same players and the same bosses only touches the text.
let liveShape = '';
let liveMounted = [];

// ?reveal=1 draws every boss with its texture on, beaten or not, and names it.
// It is for checking the models are the mobs they claim to be. Otherwise a
// boss keeps its name until somebody has beaten it, and the search matches
// only what a card is actually showing - so it cannot be used to confirm a
// name the roster is still holding back.
const REVEAL = new URLSearchParams(location.search).has('reveal');

const LIVE_MODEL = { width: 148, height: 168 };
const BOSS_MODEL = { width: 124, height: 124 };

function renderLive(board) {
  const stage = document.getElementById('live-stage');
  if (!stage || !board) return;

  const shape = (board.players || []).map(p => p.uuid).join(',') + '|' +
                (board.bosses || []).map(b => `${b.key}${b.felled}${b.kills}`).join(',');
  if (shape !== liveShape) {
    liveShape = shape;
    buildLive(board);
    mountLive(board);
  }
  updateLive(board);
}

function buildLive(board) {
  for (const el of liveMounted) if (window.disposeModel) disposeModel(el);
  liveMounted = [];

  const players = board.players || [];
  document.getElementById('ls-list').innerHTML = players.length ? players.map(p => `
    <div class="pcard${p.online ? ' on' : ''}${p.dead ? ' down' : ''}" id="pc-${p.uuid}"
         onclick="toggleLive('${p.uuid}')"
         onmouseenter="spin('pm-${p.uuid}', true)" onmouseleave="spin('pm-${p.uuid}', false)">
      <div class="pc-stage"><div class="pc-model" id="pm-${p.uuid}"></div></div>
      <div class="pc-foot">
        <div class="pc-name">${p.name}</div>
        <div class="pc-seen" id="pcs-${p.uuid}"></div>
        <div class="ps-prog pc-hp"><div class="ps-fill" id="pch-${p.uuid}"></div></div>
        <div class="pc-nums">
          <span id="pct-${p.uuid}"></span><span id="pcd-${p.uuid}"></span>
        </div>
      </div>
    </div>`).join('') : '<p class="rp-none">the server has not reported anybody yet</p>';

  const bosses = board.bosses || [];
  document.getElementById('ls-bosses').innerHTML = bosses.map(b => `
    <div class="bcard${b.felled ? ' beaten' : ' locked'}" id="bc-${b.key}"
         data-beaten="${b.felled ? 1 : 0}"
         onmouseenter="spin('bm-${b.key}', true)" onmouseleave="spin('bm-${b.key}', false)">
      <div class="bc-stage"><div class="bc-model" id="bm-${b.key}" data-boss="${b.key}"></div></div>
      <div class="bc-foot">
        <div class="bc-name">${b.felled || REVEAL ? b.name : '???'}</div>
        <div class="bc-mod">${b.mod.replace(/_/g, ' ')}${b.tier ? ` \u00b7 tier ${b.tier}` : ''}</div>
        ${b.felled ? `
          <div class="bc-kills">${b.kills} kill${b.kills === 1 ? '' : 's'}</div>
          <div class="bc-killers">${b.killers.map(k => `
            <span class="bc-killer"${k.skin ? ` style="--skin:url('${k.skin}')"` : ''}>
              <i class="bc-face"></i><b>${k.name}</b><em>${k.kills}\u00d7</em>
            </span>`).join('')}</div>
        ` : ''}
      </div>
    </div>`).join('');
  filterBosses();
}

// The list can be cut down to the ones already felled. A card that is filtered
// out is display: none, which means it never comes into view and never builds
// its model, so hiding sixty of them costs nothing.
function filterBosses() {
  const only = (document.getElementById('ls-beaten') || {}).checked;
  let shown = 0;
  for (const card of document.querySelectorAll('.bcard')) {
    const hide = only && card.dataset.beaten !== '1';
    card.classList.toggle('hidden', hide);
    if (!hide) shown += 1;
  }
  const count = document.getElementById('ls-boss-count');
  if (count && liveBoard && liveBoard.totals) {
    const T = liveBoard.totals;
    count.textContent = only
      ? `${shown} shown of ${T.boss_all}`
      : `${T.bosses} beaten of ${T.boss_all}`;
  }
}

// a model turns while the pointer is on it and stands still otherwise: ten
// scenes all spinning at once is a lot of painting for no one's benefit
function spin(id, on) {
  if (typeof turnModel === 'function') turnModel(document.getElementById(id), on);
}

function mountLive(board) {
  if (typeof buildPlayerModel !== 'function') return;   // the module is late
  for (const p of board.players || []) {
    const box = document.getElementById(`pm-${p.uuid}`);
    if (!box) continue;
    if (p.skin) {
      buildPlayerModel(box, { skin: p.skin, slim: p.slim, ...LIVE_MODEL });
      liveMounted.push(box);
    } else {
      box.classList.add('rc-noskin');
    }
  }
  // Sixty mobs is sixty scenes, and a page that builds them all before it will
  // draw anything is no use to anybody. A card is built when it comes into
  // view, which for most of this list is never.
  watchBosses(board);
}

let bossWatcher = null;

function watchBosses(board) {
  if (bossWatcher) bossWatcher.disconnect();
  const byKey = Object.fromEntries((board.bosses || []).map(b => [b.key, b]));

  const raise = box => {
    const boss = byKey[box.dataset.boss];
    if (!boss || box.dataset.built) return;
    box.dataset.built = '1';
    buildMobModel(box, { model: boss.model,
                         locked: !boss.felled && !REVEAL, ...BOSS_MODEL });
    liveMounted.push(box);
  };

  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.bc-model').forEach(raise);
    return;
  }
  bossWatcher = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      raise(entry.target);
      bossWatcher.unobserve(entry.target);
    }
  }, { root: document.getElementById('stage'), rootMargin: '300px' });

  document.querySelectorAll('.bc-model').forEach(box => bossWatcher.observe(box));
}

function updateLive(board) {
  const T = board.totals;
  if (!T) return;
  const tile = (label, value, hot) =>
    `<span class="ls-tile${hot ? ' hot' : ''}"><i>${label}</i><b>${value}</b></span>`;

  document.getElementById('ls-tiles').innerHTML =
    tile('online', `${T.online}/${T.tracked}`, T.online > 0) +
    tile('played', T.played) +
    tile('deaths', T.deaths) +
    tile('mob kills', T.kills) +
    tile('bosses', `${T.bosses}/${T.boss_all}`, T.bosses > 0);

  document.getElementById('ls-count').textContent =
    `${T.online} of ${T.tracked} online`;
  filterBosses();

  const worst = Math.max(1, ...(board.players || []).map(p => p.deaths));
  for (const p of board.players || []) {
    const set = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    };
    set(`pcs-${p.uuid}`, p.dead ? 'respawning'
        : p.online ? 'online' : `last seen ${p.seen} ago`);
    const seen = document.getElementById(`pcs-${p.uuid}`);
    if (seen) seen.className = `pc-seen${p.dead ? ' dead' : p.online ? ' on' : ''}`;
    set(`pct-${p.uuid}`, p.playtime);
    set(`pcd-${p.uuid}`, `${p.deaths} deaths`);
    const bar = document.getElementById(`pch-${p.uuid}`);
    if (bar) bar.style.width =
      `${p.max_health ? Math.round(p.health / p.max_health * 100) : 0}%`;
    const card = document.getElementById(`pc-${p.uuid}`);
    if (card) card.classList.toggle('worst', p.deaths === worst && worst > 1);
  }

  if (liveOpen) drawDrawer(board);
  liveTick();
}

// The full record opens under the grid rather than inside a card: a card is
// mostly model, and there is nowhere in it to put twelve numbers.
function drawDrawer(board) {
  const drawer = document.getElementById('ls-drawer');
  if (!drawer) return;
  const player = (board.players || []).find(p => p.uuid === liveOpen);
  if (!player) { drawer.className = 'ls-drawer'; drawer.innerHTML = ''; return; }
  drawer.className = 'ls-drawer open';
  drawer.innerHTML = `
    <div class="lsd-head">
      <span class="lsd-who">${player.name}</span>
      <span class="lsd-sub">SERVER RECORD</span>
      <button class="rp-close" onclick="toggleLive('${player.uuid}')" aria-label="Close">
        <span class="icon circle"></span><span class="lbl">CLOSE</span>
      </button>
    </div>
    ${livePanel(player)}`;
}

function toggleLive(uuid) {
  liveOpen = liveOpen === uuid ? null : uuid;
  for (const card of document.querySelectorAll('.pcard')) {
    card.classList.toggle('open', card.id === `pc-${liveOpen}`);
  }
  drawDrawer(liveBoard);
  if (liveOpen) {
    const drawer = document.getElementById('ls-drawer');
    if (drawer) requestAnimationFrame(() =>
      drawer.scrollIntoView({ behavior: 'smooth', block: 'nearest' }));
  }
}

// How old the numbers are: a timestamp the game server writes into the export
// itself, counted up second by second. Refresh does not reset it, because
// refreshing fetches the same file until the game writes a new one; the state
// beside it is what says whether the fetch went through. An export that has
// stopped being written therefore says so, instead of either looking current
// or looking like a failed download.
function liveTick() {
  const age = document.getElementById('ls-age');
  if (!age || !liveBoard) return;
  const old = (liveBoard.age || 0) + (Date.now() - liveAt) / 1000;
  age.textContent = `last updated ${fmtSpan(old)} ago`;
  age.style.color = old > 600 ? 'var(--mc-gold)' : '';
}

function liveState(source) {
  const el = document.getElementById('ls-state');
  if (!el || !source) return;
  const say = {
    // nothing fetched is the usual outcome, not a failure: the server rewrites
    // its export once a minute and most reads land on the same copy
    ok:           ['', source.fetched
                       ? `pulled ${source.fetched} file${source.fetched === 1 ? '' : 's'} from the server`
                       : 'up to date with the server'],
    idle:         ['', 'standing by'],
    // this host fetches on a schedule instead: Refresh re-reads what the last
    // scheduled run left on disk, which is all there is to read
    scheduled:    ['', source.message || 'read on a schedule'],
    busy:         ['', 'a pull is already running'],
    // the server says which part is still missing; showing that beats a fixed
    // line that goes on naming a file which by then exists
    unconfigured: ['warn', `not pulling: ${source.message || 'no mc_sync.json'}`
                           + ', showing the last synced copy'],
    // and say when it will try again, so a refusal does not read as a page
    // that has simply given up
    error:        ['bad', (source.message || 'the server could not be reached')
                          + (source.wait > 60 ? `, retrying in ${Math.round(source.wait / 60)}m` : '')],
  }[source.state] || ['', source.state];
  el.className = `ls-state ${say[0]}`;
  el.textContent = source.running ? 'reading the server…' : say[1];
}

function pullBtn(busy) {
  const btn = document.getElementById('ls-pull');
  if (btn) btn.disabled = !!busy;
}

// A pull runs on a thread of its own, so the answer that starts one comes back
// before it has finished. The board is read again a few seconds later to pick
// up whatever landed. That chase keeps a timer of its own rather than borrowing
// the countdown below: the countdown holds still while the tab is in the
// background, and a refresh somebody asked for should finish saying what
// happened either way. It gives up after a minute, so a pull left hanging on an
// unreachable host cannot strand the footer on "reading the server".
function chaseLive() {
  clearTimeout(liveChase);
  if (++liveChases > 20) { pullBtn(false); return; }
  liveChase = setTimeout(() => { liveChase = null; pollLive(); }, 3000);
}

async function pollLive(force) {
  // a click landing on top of a read in flight waits for it rather than being
  // swallowed, so the button always does something
  if (livePolling) {
    if (force) { clearTimeout(liveChase); liveChase = setTimeout(() => pollLive(true), 400); }
    return;
  }
  clearTimeout(liveChase);
  liveChase = null;
  livePolling = true;
  if (force) { liveChases = 0; pullBtn(true); }
  liveTick();
  liveDue = LIVE_EVERY;
  try {
    const res = await fetch(LIVE_URL + (force ? '?force=1' : ''), {
      headers: { 'X-Requested-With': 'fetch' },
    });
    if (!res.ok) throw new Error(res.status);
    const board = await res.json();
    if (board && board.players) {
      liveBoard = board;
      liveAt = Date.now();
      renderLive(board);
    }
    liveState(board && board.source);
    // the button stays down for as long as the pull it asked for is running,
    // so it reads as work in progress instead of a click that did nothing
    if (board && board.source && board.source.running) chaseLive();
    else { liveChases = 0; pullBtn(false); }
  } catch (err) {
    liveState({ state: 'error', message: 'could not reach the site' });
    pullBtn(false);
  } finally {
    livePolling = false;
    if (liveDue > LIVE_EVERY || liveDue <= 0) liveDue = LIVE_EVERY;
    liveTick();
  }
}

// Every stretch of the board folds away. Players and bosses start open, since
// they are what the page is for; the map starts shut, because it is a BlueMap:
// a WebGL renderer of its own, streaming chunk meshes off the game host, on a
// page that already runs a scene per card. A folded section is display:none,
// which also means the models inside it go unbuilt until it is opened, the
// observer that builds them only firing on something that can actually be
// seen. The map's frame is made on first open and then left alone, because
// tearing it down would mean downloading the world again on the next look.
function toggleSection(key) {
  const box = document.getElementById(key);
  if (!box) return;
  const shut = box.classList.toggle('shut');
  const btn = document.querySelector(`[data-sec="${key}"]`);
  if (btn) btn.textContent = shut ? 'Show' : 'Hide';
  if (shut) return;

  if (box.dataset.src && !box.firstChild) {
    const frame = document.createElement('iframe');
    frame.title = 'Live world map';
    frame.src = box.dataset.src;
    box.appendChild(frame);
  }
  requestAnimationFrame(() => box.scrollIntoView({ behavior: 'smooth', block: 'nearest' }));
}

function pullNow() {
  pullBtn(true);
  pollLive(true);
}

function bootLive() {
  if (!document.getElementById('live-stage')) return;
  renderLive(liveBoard);
  liveState(liveBoard && liveBoard.source);
  liveTick();

  setInterval(() => {
    // a hidden tab is nobody watching, and polling one only burns the server's
    // ssh budget: the countdown holds until the tab comes back
    if (document.hidden) return;
    if (--liveDue <= 0) pollLive();
    liveTick();
  }, 1000);

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) pollLive();
  });
}

bootLive();

selectDisc(0);

// the model renderer is a module and so arrives after this file: once it is
// here, put the roster on
window.addEventListener('mcmodel-ready', () => {
  if (SEASONS.length) selectPlayer(playerIdx);
  if (liveBoard) mountLive(liveBoard);
});
