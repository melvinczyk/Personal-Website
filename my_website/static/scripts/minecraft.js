// A button through the portal sounds like Minecraft: one click, and nothing on
// hover. A sound on every pointer crossing is a codec-screen habit; on a page
// you scroll through sixty boss cards it is a rattle.
let audioCtx = null, clickBuffer = null, clickFrom = 0;

function getCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

// Where the sound actually starts.
//
// A clip exported from the game can carry half a second of silence in front
// of it, and playing that from zero puts the click half a second after the
// press, which reads as lag rather than as a quiet file. Measured rather than
// hard-coded, so swapping the mp3 needs no sums.
//
// Two starts are worked out and the honest one is chosen. The first is where
// the silence ends. The second walks BACK from the loudest moment, which is
// what this clip needs: it is silent for 530ms, blips once at four percent of
// peak, goes quiet again for seventy milliseconds, and only then clicks - so
// the end of its silence is the blip, not the click.
//
// The backward one is only trusted when it looks like that case: a first
// sound close in front of the real one with the level dropping back to
// silence in between. Without that guard it eats the beginning of anything
// whose peak arrives late, starting a sound that swells on its crest. Kept
// identical to portfolio.js's copy - the two pages load one script each, and
// a click should not mean two different things depending which page it is on.
const BLIP_MS = 120;               // how far in front of the sound a false start may sit

function soundStart(buffer) {
  const d = buffer.getChannelData(0);
  const rate = buffer.sampleRate;
  // A millisecond at a time. A waveform crosses zero many times inside its
  // own attack, so anything reading raw samples would call the first of
  // those crossings the start of the sound; the envelope is what a listener
  // actually hears rising.
  const win = Math.max(1, Math.round(rate / 1000));
  const env = [];
  for (let i = 0; i < d.length; i += win) {
    let pk = 0;
    for (let j = i, end = Math.min(i + win, d.length); j < end; j++) {
      const v = Math.abs(d[j]);
      if (v > pk) pk = v;
    }
    env.push(pk);
  }
  let peak = 0, top = 0;
  for (let i = 0; i < env.length; i++) if (env[i] > peak) { peak = env[i]; top = i; }
  if (!peak) return 0;

  const hush = peak * 0.015;
  let first = 0;
  while (first < env.length && env[first] <= hush) first++;

  let back = top;
  while (back > 0 && env[back - 1] >= peak * 0.1) back--;

  let quiet = false;                 // does the level fall away again in between?
  for (let i = first; i < back; i++) if (env[i] < hush) { quiet = true; break; }

  const start = (quiet && back > first && back <= first + BLIP_MS) ? back : first;
  // back off a few milliseconds so the attack is not clipped off
  return Math.max(0, (start * win / rate) - 0.006);
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
  // The context starts suspended and only a gesture may wake it, so wake it
  // on the first press anywhere rather than on the first press that happens
  // to want a sound. Otherwise somebody who opens a boss card before they
  // touch a button pays the wake-up on the button, and that one click is
  // late for a reason that has nothing to do with the button.
  const ctx = getCtx();
  if (ctx.state !== 'running') ctx.resume();
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
                  meter('DEATHS', Math.round(p.live.deaths / worst * 100), `${compact(p.live.deaths)}`, 'deaths')}
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
    `<span class="live-cell"><i>${label}</i><b${exact(value)}>${compact(value)}</b>${note ? `<u>${note}</u>` : ''}</span>`;
  // Every section used to be the same grey bar over the same dark cells, so
  // five of them stacked read as one undifferentiated sheet of numbers. Each
  // gets a key of its own now - where it sits on the page is the same, but
  // what it is about is legible before a word of it is read.
  const section = (label, right, body, key) => `
    <div class="live-section" data-key="${key}">
      <div class="lb-head"><span>${label}</span>${right ? `<b>${right}</b>` : ''}</div>
      <div class="live-grid">${body}</div>
    </div>`;

  // health and hunger are the two numbers with a natural scale to bar against,
  // so they read as meters the way the season roster's own stats do rather
  // than as one more pair of bare numbers lost in the grid
  const hpPct   = Math.max(0, Math.min(100, (L.health / (L.max_health || 20)) * 100));
  const foodPct = Math.max(0, Math.min(100, (L.food / 20) * 100));
  const vitals = `<div class="live-vitals">
    ${meter('HEALTH', hpPct, `${L.health}/${L.max_health}`, 'hp')}
    ${meter('HUNGER', foodPct, `${L.food}/20`, 'food')}
  </div>`;

  const activity = [
    cell('PLAY TIME', L.playtime),
    cell('LEVEL', L.level),
    cell('BLOCKS MOVED', L.travelled, `${compact(L.sprinted)} SPRINTED`),
    cell('JUMPS', L.jumps),
  ].join('');

  const combat = [
    cell('DEATHS', L.deaths,
         L.dead ? 'ON THE RESPAWN SCREEN'
         : L.deaths ? `LAST ${L.since_death} AGO` : 'UNBEATEN'),
    cell('MOB KILLS', L.mob_kills, L.ratio === null ? '' : `${L.ratio} PER DEATH`),
    cell('PVP KILLS', L.player_kills),
    cell('DAMAGE DEALT', L.dealt),
    cell('DAMAGE TAKEN', L.taken),
  ].join('');

  // Somebody with a dozen bosses on their record had a dozen rows of it, in
  // no order a reader could use. The three that say the most come first and
  // the rest fold away behind them: hardest grade, then the biggest thing
  // they took on at that grade, then how much of it was theirs, and the
  // moment of that best fight to settle the last of it.
  const ranked = [...L.bosses].sort((a, b) =>
    (b.tier || 0) - (a.tier || 0) ||
    (b.health || 0) - (a.health || 0) ||
    (b.share || 0) - (a.share || 0) ||
    String(b.at || '').localeCompare(String(a.at || '')));
  const TOP = 3;

  const bosses = L.bosses.length ? `
    <div class="live-boss" data-key="boss">
      <div class="lb-head"><span>BOSSES</span><b>${L.boss_kills} KILL${
        L.boss_kills === 1 ? '' : 'S'}${(() => {
          const lent = L.bosses.reduce((n, b) => n + (b.assists || 0), 0);
          return lent ? ` \u00b7 ${lent} ASSIST${lent === 1 ? '' : 'S'}` : '';
        })()}${(() => {
          const led = L.bosses.filter(b => b.first).length;
          return led ? ` \u00b7 <em class="lb-head-first">${led} FIRST${
            led === 1 ? '' : 'S'}</em>` : '';
        })()}</b></div>
      ${ranked.map((b, place) => {
        const cls = b.category === 'miniboss' ? 'mini' : `t${b.tier}`;
        // a row with no kills on it is one they only ever helped with: the
        // count would read "x0", which is not what happened
        const helped = b.assists ? `<em class="lb-assist">+${b.assists}</em>` : '';
        // the row is filled to the share they took off it, in its own tier's
        // colour: what it is ranked on, drawn rather than spelled out, and
        // costing the row no extra height to say
        const grade = b.category === 'miniboss' ? 'MINIBOSS' : `TIER ${b.tier}`;
        const facts = [grade, b.health ? `${compact(b.health)} HP` : '',
                       b.kills ? '' : 'HELPED'].filter(Boolean).join(' \u00b7 ');
        return `<span class="lb-row ${cls}${b.kills ? '' : ' assisted'}${
          place >= TOP ? ' rest' : ''}" style="--fill:${b.share || 0}%">
          ${place < TOP ? `<i class="lb-rank r${place + 1}">${place + 1}</i>` : ''}
          <span class="lb-star ${cls}">${PIXEL_STAR_SVG}</span>
          <span class="lb-main">
            <span class="lb-top"><b>${b.name}</b>${
              b.first ? `<span class="lb-first"
                title="First blood: nobody on this server had beaten it before them"
                >${PIXEL_FLAG_SVG}</span>` : ''}${
              b.kills ? `<em>x${b.kills}</em>` : ''}${helped}</span>
            <span class="lb-sub"><i>${facts}</i><u>${
              b.share ? `<b class="lb-best">${b.share}%</b> \u00b7 ` : ''}${b.last}</u></span>
          </span>
        </span>`;
      }).join('')}
      ${ranked.length > TOP ? `<button type="button" class="lb-more"
          onclick="event.stopPropagation();this.parentElement.classList.toggle('more')">
          <span class="lb-more-in">show all ${ranked.length}</span>
          <span class="lb-more-out">show the top ${TOP}</span>
        </button>` : ''}
    </div>` : '<div class="live-boss empty" data-key="boss">no boss has gone down yet</div>';

  // The two counts the COMBAT grid above gives as bare totals, broken out by
  // what they were against: which mobs a player's kills came from, and which
  // mobs their deaths came from. Side by side because the pair is the point -
  // the Twilight Forest regular whose deaths all come from one mod's sky
  // bosses reads differently from the fisherman whose worst enemy has killed
  // him three times.
  //
  // The bars run against the top row of their own column rather than against
  // the column's total, so the podium is drawn against itself. Against the
  // total, a player spread across forty kinds of mob would draw three near
  // empty bars and the comparison worth making would be invisible.
  const mobColumn = (tally, key, title, note) => {
    if (!tally || !tally.top.length) {
      return `<div class="mob-col ${key}">
        <div class="mob-cap"><b>${title}</b></div>
        <div class="mob-none">${note}</div>
      </div>`;
    }
    return `<div class="mob-col ${key}">
      <div class="mob-cap"><b>${title}</b></div>
      ${tally.top.map((m, i) => `
        <span class="mob-row r${i + 1}" style="--fill:${m.share}%"
              title="${m.name} \u00b7 ${m.id}">
          <i class="mob-rank">${i + 1}</i>
          <span class="mob-main">
            <span class="mob-top"><b>${m.name}</b><em>${compact(m.count)}</em></span>
            <span class="mob-bar"><u></u></span>
          </span>
          <span class="mob-cut">${m.cut}%</span>
        </span>`).join('')}
      ${(() => {
        // the tail with its weight on it, rather than a bare count of kinds:
        // three rows out of forty means one thing when the other thirty-seven
        // are half the total and quite another when they are a handful of
        // one-offs, and that is the whole reason the podium is only three
        const kinds = tally.kinds - tally.top.length;
        if (!kinds) return '<div class="mob-tail">nothing else</div>';
        return `<div class="mob-tail">${kinds} more kind${kinds === 1 ? '' : 's'}${
          tally.rest ? ` \u00b7 ${compact(tally.rest)} between them` : ''}</div>`;
      })()}
    </div>`;
  };

  const H = L.hunted, N = L.nemeses;
  const hunting = (H || N) ? `
    <div class="live-mobs" data-key="mobs">
      <div class="lb-head"><span>KILLS &amp; DEATHS</span><b>${
        H ? `${compact(H.total)} KILL${H.total === 1 ? '' : 'S'}` : ''}${
        H && N ? ' \u00b7 ' : ''}${
        N ? `${compact(N.total)} DEATH${N.total === 1 ? '' : 'S'}` : ''}</b></div>
      <div class="mob-cols">
        ${mobColumn(H, 'prey', 'MOST KILLED', 'nothing has gone down yet')}
        ${mobColumn(N, 'bane', 'DIED TO', 'never been killed')}
      </div>
    </div>` : '';

  const F = L.fieldguide;
  const fieldguide = F && F.total ? `
    <div class="live-fieldguide" data-key="guide">
      <div class="lb-head"><span>FIELD GUIDE</span><b>${F.total} SCANNED</b></div>
      <div class="fg-grid">
        <span class="fg-cell"><i class="fg-icon monster"></i><b>${F.categories.monster}</b><u>MONSTER</u></span>
        <span class="fg-cell"><i class="fg-icon animal"></i><b>${F.categories.animal}</b><u>ANIMAL</u></span>
        <span class="fg-cell"><i class="fg-icon plant"></i><b>${F.categories.plant}</b><u>PLANT</u></span>
        <span class="fg-cell"><i class="fg-icon boss"></i><b>${F.categories.boss}</b><u>BOSS</u></span>
      </div>
    </div>` : '';

  // Three counts that are easy to run together, so they are kept apart: what
  // has been landed all told, how many kinds of it, and how many of those
  // kinds are legendary. The rows under them are the trophies - rarest
  // first - and each carries the best specimen of its kind rather than the
  // last one, which is what the mod itself keeps.
  const R = L.fishing;
  const fishing = R && (R.total || R.species || R.fish.length) ? `
    <div class="live-fish" data-key="fish">
      <div class="lb-head"><span>FISHING</span><b>${compact(R.total)} LANDED</b></div>
      <div class="fg-grid fish">
        <span class="fg-cell"><b>${compact(R.total)}</b><u>LANDED</u></span>
        <span class="fg-cell"><b>${compact(R.species)}</b><u>SPECIES</u></span>
        <span class="fg-cell${R.legendary ? ' lit' : ''}"><b>${compact(R.legendary)}</b><u>LEGENDARY</u></span>
      </div>
      ${R.fish.map(f => `
        <span class="lb-row fish-row">
          <i class="fish-pip ${f.rarity.toLowerCase()}"></i>
          <span class="lb-main">
            <span class="lb-top"><b>${f.name}</b><em>x${compact(f.count)}</em></span>
            <span class="lb-sub">
              <i>${[f.rarity, f.golden ? 'GOLDEN' : '', f.perfect ? 'PERFECT' : '']
                   .filter(Boolean).join(' \u00b7 ')}</i>
              <u>${f.size} cm \u00b7 ${f.weight}${f.top ? ` \u00b7 top ${f.top}%` : ''}</u>
            </span>
          </span>
        </span>`).join('')}
      ${R.more ? `<div class="fish-note">${R.more} more not shown</div>` : ''}
      ${R.covers && R.covers !== 'ALL'
        ? `<div class="fish-note">only ${R.covers} catches are recorded per fish</div>` : ''}
    </div>` : '';

  return `<div class="live-wrap">
    ${vitals}
    ${section('ACTIVITY', L.dimension
        ? `<span class="realm" data-realm="${L.realm || ''}">${L.dimension}</span>`
        : null, activity, 'activity')}
    ${section('COMBAT', null, combat, 'combat')}
    ${bosses}
    ${hunting}
    ${fieldguide}
    ${fishing}
    <div class="live-when">SERVER READ ${localMoment(L.recorded)}</div>
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
let bossOpen  = null;           // key of the boss card expanded, if any
let liveDue   = LIVE_EVERY;
let livePolling = false;

// Six figures in a tile the width of a word is a wall, and nobody reads the
// hundreds place of a number that size anyway. Past ten thousand a count gets
// one decimal and a suffix; below that it still fits, so it stays exact. The
// decimal is cut rather than rounded, so a number never reads as more than it
// is - 10293 is 10.2k, not 10.3k. The figure itself is never lost: whatever
// shows a compacted number hangs the full one off it as a title.
function compact(n) {
  if (typeof n !== 'number' || !isFinite(n)) return n;
  const size = Math.abs(n);
  if (size < 1e4) return `${n}`;
  const sign = n < 0 ? '-' : '';
  for (const [step, mark] of [[1e9, 'B'], [1e6, 'M'], [1e3, 'k']]) {
    if (size >= step) return `${sign}${Math.floor(size / step * 10) / 10}${mark}`;
  }
  return `${n}`;
}

// a fight's own damage-share colour: green for whoever carried it, yellow
// for a real but lesser part, red for barely tipping in - a scale of how
// much of the boss that share actually was, not a decoration.
// ── the fight history ──────────────────────────────────────────────────────
// A boss beaten four times was four full-width cards, each repeating the same
// three stat tiles and the same participant bar under the same name: four
// hundred pixels to say "mysteriousmex21 again, a little faster". The record
// is grouped under whoever landed the last blow now, one line per fight, and
// each player's run of them folds away on its own.

// Fights in the order they arrive - newest first - collected under whoever
// the kill belongs to, so a player's own run stays in one block and the
// blocks themselves stay in most-recent-first order. That is the player who
// took the most off the boss rather than the one who landed the last blow:
// the Ancient Guardian was finished with a loaf of bread by the one who had
// dealt the smaller half of its health, and the kill is not theirs.
function byLead(fights) {
  const groups = [], held = {};
  for (const fight of fights) {
    const who = fight.lead || fight.finisher || 'unknown';
    if (!held[who]) groups.push(held[who] = { name: who, fights: [] });
    held[who].fights.push(fight);
  }
  return groups;
}

// One bar per fight rather than one per participant: the shares are already
// fractions of the same boss's health, so they tile end to end and the split
// reads off a single strip. Whatever the players do not account for is health
// the boss lost to the world - see _fight_history - and it takes the rest of
// the strip in hazard stripes, so a bar is always a whole boss.
function shareBar(fight) {
  const seg = (name, pct, cls) =>
    `<span class="bcf-seg ${cls}" style="width:${pct}%" title="${name} ${pct}%"></span>`;
  const parts = fight.participants.map(p => seg(p.name, p.share, shareTier(p.share)));
  if (fight.untracked_share) {
    parts.push(seg('Untracked', fight.untracked_share, 'discard'));
  }
  return `<span class="bcf-bar">${parts.join('')}</span>`;
}

// A row is one fight at a glance. What it cannot hold - the moment in full,
// and what each player actually dealt rather than only their share of it -
// waits underneath until the row is asked for it.
function fightDetail(fight, faces) {
  const cell = (label, value) =>
    `<span class="bcf-cell"><i>${label}</i><b>${value}</b></span>`;
  // A name is who; a face is which of them. Every other list of players on
  // this page - the killer chips, the group headers, the record's own
  // heading - leads with the head off their skin, and this one read as the
  // odd list out for not doing the same.
  const part = (name, pct, dmg, cls, skin) => `
    <div class="bcf-part${cls === 'discard' ? ' untracked' : ''}">
      ${cls === 'discard' ? '<i class="bcf-noface" aria-hidden="true"></i>'
        : `<i class="bc-face"${skin ? ` style="--skin:url('${skin}')"` : ''}></i>`}
      <span class="bcf-pname">${name}</span>
      <span class="bcf-dmg">${dmg}</span>
      <span class="bcf-bar"><span class="bcf-seg ${cls}" style="width:${pct}%"></span></span>
      <span class="bcf-pct">${pct}%</span>
    </div>`;

  // The rows above are ordered by share, which is what decides whose kill a
  // fight was. Opened up, the question is a different one - who actually hit
  // it hardest - so the split is ordered by the damage itself. The two agree
  // most of the time and the times they do not are the interesting ones.
  const dealt = [...fight.participants].sort((a, b) => b.damage - a.damage);

  return `
    <div class="bcf-detail">
      <div class="bcf-meta">
        ${cell('WHEN', localMoment(fight.time))}
        ${cell('DURATION', fight.duration)}
        ${cell('BOSS HEALTH', compact(fight.max_health))}
        ${cell('FINISHING BLOW', fight.weapon || '\u2014')}
      </div>
      <div class="bcf-split">
        ${dealt.map(p => part(
            p.name, p.share, `${compact(Math.round(p.damage))} dmg`,
            shareTier(p.share), (faces || {})[p.name])).join('')}
        ${fight.untracked_share ? part(
            'Untracked', fight.untracked_share, 'the world', 'discard') : ''}
      </div>
    </div>`;
}

function fightRow(fight, owner, id, faces) {
  const mine = fight.participants.find(p => p.name === owner);
  const others = fight.participants.filter(p => p.name !== owner);
  return `
    <div class="bcf-fight" id="ff-${id}">
      <div class="bcf-row" role="button" tabindex="0"
           aria-label="Fight on ${localMoment(fight.time)}"
           onclick="event.stopPropagation();toggleFight('${id}')"
           onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();event.stopPropagation();toggleFight('${id}');}">
        <span class="bcf-when">${localMoment(fight.time)}</span>
        <span class="bcf-dur">${fight.duration}</span>
        <span class="bcf-hp">${compact(fight.max_health)} HP</span>
        <span class="bcf-wep" title="${fight.weapon}">${fight.weapon || '\u2014'}</span>
        ${shareBar(fight)}
        <span class="bcf-pct">${mine ? mine.share : 0}%</span>
        <span class="bcf-caret"></span>
      </div>
      ${others.length ? `<div class="bcf-with">${(() => {
        // a quarter of a boss is the line between the two - see ASSIST_SHARE.
        // Whoever cleared it was in on the kill; whoever did not lent a hand,
        // and the row should not call the first of those "helping"
        const said = [];
        const named = who => who.map(p => `<b>${p.name}</b> ${p.share}%`).join(' \u00b7 ');
        const with_ = others.filter(p => p.credited);
        const from = others.filter(p => !p.credited);
        if (with_.length) said.push(`with ${named(with_)}`);
        if (from.length) said.push(`helped by ${named(from)}`);
        return said.join(' \u00b7 ');
      })()}</div>` : ''}
      ${fightDetail(fight, faces)}
    </div>`;
}

// One fight open at a time, the same rule the boss cards and the player
// drawer already keep: a page with six of them stretched out at once is a
// page you scroll rather than read.
let fightOpen = null;

function toggleFight(id) {
  fightOpen = fightOpen === id ? null : id;
  for (const el of document.querySelectorAll('.bcf-fight')) {
    el.classList.toggle('open', el.id === `ff-${fightOpen}`);
  }
}

// The card itself opens and shuts on a click anywhere in it, so a control
// inside it has to keep its own click to itself or folding a player's run
// would shut the whole card on the way.
function toggleFightGroup(header) {
  const group = header.parentElement;
  if (group) group.classList.toggle('shut');
}

// What a player is drawn in when the page has to tell them apart. Their own
// skin's colour wherever we have the skin - see roster._tone, which reads the
// one colour it is most obviously wearing - so mysteriousmex21 is the brown
// he walks around in and blindhustler the teal of his armour, rather than
// whichever slot in a list they happened to land in. The fallbacks are only
// for a player with no skin on file, and are picked to sit apart from each
// other rather than to mean anything.

// ── the kills, plotted ─────────────────────────────────────────────────────
// A list says who and a list says when, but neither says whether a boss went
// down once a week for a month or five times in one evening - and the fights
// are grouped by player, so the order they actually happened in is the one
// thing the list below cannot show. One pip per fight along a real time axis,
// coloured by whoever it counted for, stacked where several land on the same
// day. Small enough to sit above the list rather than instead of it.
// How far back a chart may look. Max is the whole record, which is what a card
// opens on: the point of the line is the total it climbs to.
const CHART_RANGES = [
  ['12h',  432e5],       ['1 day',    864e5],
  ['1 week', 6048e5],    ['2 weeks', 12096e5],
  ['1 month', 2592e6],   ['3 months', 7776e6],
  ['1 year', 31536e6],   ['max', Infinity],
];

// Points per chart, kept so the probe can find the nearest kill without
// redoing the arithmetic on every mouse move.
// The one breakpoint the chart itself cares about: below it the chart is drawn
// in a narrower box so it comes out taller for the width it is given.
//
// Crossing it has to redraw, or a phone turned on its side keeps the tall
// aspect and a desktop window dragged narrow keeps the wide one. Both the
// media query and a plain resize are watched, because an emulated resize does
// not always raise the first, and the redraw is guarded on the flag actually
// flipping so an ordinary resize costs a comparison and nothing else.
const CHART_TIGHT = window.matchMedia('(max-width: 700px)');
let chartTight = CHART_TIGHT.matches;

function retuneCharts() {
  if (CHART_TIGHT.matches === chartTight) return;
  chartTight = CHART_TIGHT.matches;
  for (const host of [...document.querySelectorAll('.bkc[data-boss]')]) {
    const boss = (liveBoard.bosses || []).find(b => b.key === host.dataset.boss);
    if (boss) host.outerHTML = killChart(boss, null);
  }
}

CHART_TIGHT.addEventListener('change', retuneCharts);
window.addEventListener('resize', retuneCharts);

const CHART_POINTS = {};
const CHART_RANGE = {};
// when each chart was last drawn, and how much time a pixel of it is worth
const CHART_DRAWN = {};

function chartRange(key) { return CHART_RANGE[key] ?? Infinity; }

// Re-draw one card's chart when its range changes. Only that chart: the boss
// list is sixty cards of WebGL and rebuilding it to change a dropdown would be
// an absurd way to spend a frame.
function setChartRange(key, ms) {
  CHART_RANGE[key] = ms === 'Infinity' ? Infinity : Number(ms);
  const boss = (liveBoard.bosses || []).find(b => b.key === key);
  const host = document.querySelector(`.bkc[data-boss="${key}"]`);
  if (!boss || !host) return;
  host.outerHTML = killChart(boss, null);
}

// A pointer over the chart, from whichever kind of pointer it is.
//
// The chart used to probe on mousemove, which a touchscreen never sends: on a
// phone the readout simply did not exist. A finger says the same thing with a
// press and a drag, so a touch probes from the moment it goes down and keeps
// probing as it slides, while a mouse still probes on hover alone.
//
// The stopPropagation matters as much as the probing does: the card is itself
// a toggle, so without it a tap meant to read the line closed the card.
// Scrolling is left alone - the svg's touch-action allows the vertical pan, so
// a finger dragged down the page still scrolls it rather than scrubbing.
function chartPoint(event, key) {
  if (event.pointerType !== 'mouse') event.stopPropagation();
  // a mouse probes by hovering; a finger only while it is actually down
  if (event.pointerType === 'mouse' || event.type !== 'pointermove' || event.buttons ||
      event.pressure > 0) probeChart(event, key);
}

// The readout under the line. Finds the kill nearest the pointer along the
// time axis rather than by straight distance, because the line is flat between
// kills and a diagonal measure would keep snapping to whichever end was higher.
function probeChart(event, key) {
  const pts = CHART_POINTS[key];
  const svg = event.currentTarget;
  const box = document.querySelector(`.bkc[data-boss="${key}"] .bkc-probe`);
  if (!pts || !pts.length || !box) return;

  const rect = svg.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * svg.viewBox.baseVal.width;
  let near = pts[0];
  for (const pt of pts) if (Math.abs(pt.x - x) < Math.abs(near.x - x)) near = pt;

  box.innerHTML = `${near.skin ? `<i style="--skin:url('${near.skin}')"></i>`
                              : '<i class="none"></i>'}
    <b>${near.who}</b><span>${localMoment(near.time)}</span>
    <em>${near.total} total</em>`;
  box.classList.add('on');

  const line = svg.querySelector('.bkc-cursor');
  const dot  = svg.querySelector('.bkc-cursor-dot');
  if (line) { line.setAttribute('x1', near.x); line.setAttribute('x2', near.x); line.style.opacity = 1; }
  if (dot)  { dot.setAttribute('cx', near.x); dot.setAttribute('cy', near.y);
              dot.style.opacity = 1; }
}

function unprobeChart(key) {
  const box = document.querySelector(`.bkc[data-boss="${key}"] .bkc-probe`);
  const svg = document.querySelector(`.bkc[data-boss="${key}"] .bkc-svg`);
  if (box) box.classList.remove('on');
  if (svg) {
    const line = svg.querySelector('.bkc-cursor'), dot = svg.querySelector('.bkc-cursor-dot');
    if (line) line.style.opacity = 0;
    if (dot) dot.style.opacity = 0;
  }
}

// Keep the open charts' right edge on the present.
//
// Only the time axis moves, so a chart is redrawn whole rather than patched -
// there is at most one boss card open at a time and the SVG is a few hundred
// nodes. What stops that being wasteful is the gate: a chart is left alone
// until a pixel's worth of its own axis has gone by, and left alone entirely
// while someone is touching it - rebuilding the node under a pointer would
// drop the probe mid-hover, and under a keyboard would drop the range picker
// mid-choice.
function tickCharts() {
  if (!liveBoard || !liveBoard.bosses) return;
  for (const host of document.querySelectorAll('.bkc[data-boss]')) {
    const drawn = CHART_DRAWN[host.dataset.boss];
    if (!drawn || Date.now() - drawn.at < drawn.perPixel) continue;
    // :hover covers a pointer, the active element covers a keyboard, and the
    // showing probe covers a touch, where :hover is whatever the browser feels
    // like after a tap
    if (host.matches(':hover') || host.contains(document.activeElement)
        || host.querySelector('.bkc-probe.on')) continue;
    const boss = liveBoard.bosses.find(b => b.key === host.dataset.boss);
    if (boss) host.outerHTML = killChart(boss, null);
  }
}

function killChart(boss, faces) {
  const all = (boss.fights || []).filter(f => f.time && !isNaN(Date.parse(f.time)));
  if (!all.length) return '';

  const at = f => Date.parse(f.time);
  const inOrder = all.slice().sort((a, b) => at(a) - at(b));
  const whoOf = f => f.lead || f.finisher || 'unknown';

  // A player is their face here, the same one their card upstairs wears, so
  // the chart needs no palette at all. Colouring the lines was the wrong idea
  // twice over: skins cluster in the browns, so the colours were never far
  // apart, and a reader still had to hold a key in their head to use them.
  const skinOf = {};
  for (const p of [...(boss.killers || []), ...(boss.helpers || [])]) {
    if (p.name && p.skin) skinOf[p.name] = p.skin;
  }

  // Cumulative: every kill adds one and nothing takes it away, so the line
  // only climbs and finishes at the total in the top right corner.
  //
  // It starts at whatever the server logged but did not send. One fight is
  // one kill, and the card's kill count is the whole log's length, while the
  // history it is drawn from is capped - so a boss felled more times than the
  // cap allows would otherwise climb to the cap and contradict its own card.
  // Banking the difference up front makes the line finish on the real total.
  let running = Math.max(0, (boss.logged || all.length) - all.length);
  const steps = inOrder.map(f => ({
    t: at(f), who: whoOf(f), time: f.time, total: ++running,
  }));
  const total = running;

  // The axis ends at the present, never at the last kill. A boss nobody has
  // touched since Tuesday has been un-killed for days, and that gap is a real
  // reading - a chart that stopped at the last pip drew the flat stretch since
  // as nothing at all, and made a fortnight-old kill look like this morning's.
  // The line carries on level from the newest kill to the right edge instead.
  const span = CHART_RANGE[boss.key] ?? Infinity;
  const last = steps[steps.length - 1].t;
  // a kill stamped ahead of this browser's clock is clock skew, not the
  // future: let it set the edge rather than fall off the end of the chart
  const now  = Math.max(last, Date.now());
  // Max opens a little before the first kill rather than exactly on it, so
  // that first step up has somewhere to stand: a riser drawn along the axis
  // line reads as part of the frame rather than as a kill.
  const first = steps[0].t;
  const from = span === Infinity
    ? first - Math.max(6e5, (now - first) * 0.04)
    : now - span;
  const to   = now;
  const shown = steps.filter(st => st.t >= from && st.t <= to);
  const entering = steps.filter(st => st.t < from).length;

  // An svg scales to the width it is given and keeps its aspect, so a viewBox
  // this wide became 70 pixels tall inside a phone-width card: a chart with no
  // room to be read, and faces on it seven pixels across. A narrow screen gets
  // a narrower box for the same height, which is the same drawing at a taller
  // aspect rather than a scaled-down one, and everything measured in viewBox
  // units - the faces above all - comes out nearer its intended size.
  const tight = CHART_TIGHT.matches;
  const W = tight ? 430 : 892, H = 250,
        L = tight ? 34 : 46, R = 10, T = 26, B = 34;
  const plotW = W - L - R, plotH = H - T - B;
  const width = Math.max(1, to - from);
  const px = t => L + ((Math.min(Math.max(t, from), to) - from) / width) * plotW;
  const topV = Math.max(1, span === Infinity ? total
    : (shown.length ? shown[shown.length - 1].total : entering));
  const py = v => T + plotH - (v / topV) * plotH;

  // a staircase, because a kill is a step and not a slope
  const pts = [`${L},${py(entering)}`];
  let prev = entering;
  for (const st of shown) {
    pts.push(`${px(st.t)},${py(prev)}`, `${px(st.t)},${py(st.total)}`);
    prev = st.total;
  }
  pts.push(`${W - R},${py(prev)}`);
  const curve = pts.join(' ');

  // What one pixel of this axis is worth in time. tickCharts() redraws a chart
  // only once that much has passed, so a twelve-hour view moves about once a
  // minute and a year-wide one about once every two hours - live, without
  // rebuilding an SVG every second to move nothing.
  CHART_DRAWN[boss.key] = { at: Date.now(),
                            perPixel: Math.max(1000, width / plotW) };

  CHART_POINTS[boss.key] = shown.map(st => ({
    x: +px(st.t).toFixed(1), y: +py(st.total).toFixed(1),
    who: st.who, skin: skinOf[st.who] || '', time: st.time, total: st.total,
  }));

  const rungs = [];
  const every = Math.ceil(topV / 5) || 1;
  for (let n = every; n <= Math.round(topV); n += every) {
    rungs.push(`<line class="bkc-grid" x1="${L}" y1="${py(n).toFixed(1)}"
      x2="${W - R}" y2="${py(n).toFixed(1)}"/>
      <text class="bkc-gridlabel" x="${L - 8}" y="${(py(n) + 3.5).toFixed(1)}"
        text-anchor="end">${n}</text>`);
  }

  const dots = shown.map(st => `<circle class="bkc-dot" cx="${px(st.t).toFixed(1)}"
      cy="${py(st.total).toFixed(1)}" r="4"
      ><title>${st.who} \u2014 ${localMoment(st.time)} \u2014 ${st.total} total</title></circle>`).join('');

  // A face over the line for each unbroken run by one player, sat at the end of
  // that run and carrying the count when the run is longer than one. Runs
  // rather than kills, because an evening of the same person farming a boss is
  // eight kills and one fact; and any face that would land on top of the last
  // one drawn is dropped, the probe being there to name what it covered.
  const FACE = tight ? 34 : 26, GAP = tight ? 40 : 30;
  const runs = [];
  for (const st of shown) {
    const back = runs[runs.length - 1];
    if (back && back.who === st.who) { back.n += 1; back.end = st; }
    else runs.push({ who: st.who, n: 1, end: st });
  }
  let lastX = -Infinity;
  const heads = runs.map(run => {
    const x = px(run.end.t), y = py(run.end.total);
    if (x - lastX < GAP) return '';
    lastX = x;
    const skin = skinOf[run.who];
    const left = Math.min(Math.max(x - FACE / 2, L), W - R - FACE);
    const top = Math.max(y - FACE - 8, 2);
    return `<g class="bkc-head"><title>${run.who} \u2014 ${run.n} kill${
      run.n === 1 ? '' : 's'} in a row</title>
      ${skin ? `<svg class="bkc-headart" x="${left.toFixed(1)}" y="${top.toFixed(1)}"
           width="${FACE}" height="${FACE}" viewBox="8 8 8 8">
           <image href="${skin}" x="0" y="0" width="64" height="64"/></svg>`
        : `<rect class="bkc-headnone" x="${left.toFixed(1)}" y="${top.toFixed(1)}"
             width="${FACE}" height="${FACE}"/>`}
      <rect class="bkc-headedge" x="${left.toFixed(1)}" y="${top.toFixed(1)}"
            width="${FACE}" height="${FACE}"/>
      ${run.n > 1 ? `<text class="bkc-headn" x="${(left + FACE).toFixed(1)}"
        y="${(top + FACE).toFixed(1)}">${run.n}</text>` : ''}
    </g>`;
  }).join('');

  // The axis now always ends at the present, which makes the far end of a wide
  // one a date a year old sitting next to the word now - and 'Aug 29' beside
  // 'now' on the 29th of August reads as today. Past half a year, say which.
  const DAY = 86400000, HALF_YEAR = 15768e6;
  const label = ms => new Date(ms).toLocaleString(undefined,
    (to - from) > HALF_YEAR ? { year: 'numeric', month: 'short', day: 'numeric' }
    : (to - from) > DAY     ? { month: 'short', day: 'numeric' }
    :                         { hour: 'numeric', minute: '2-digit' });
  const fade = `bkc-fade-${boss.key}`;

  // Every one of these stops the event going up. The card itself is the
  // toggle - the whole tile is one big button - so on a phone, where opening
  // a native select is a tap rather than a hover-and-release, choosing a range
  // reached the card's own onclick and shut the card before the change ever
  // landed. On a mouse it never showed: the picker opens on mousedown and the
  // click that follows lands on the option list, not on the card.
  const picker = `<select class="bkc-range" aria-label="How far back to look"
      onpointerdown="event.stopPropagation()"
      onclick="event.stopPropagation()"
      onchange="event.stopPropagation();setChartRange('${boss.key}', this.value)">
      ${CHART_RANGES.map(([name, ms]) => `<option value="${ms}"${
        ms === span ? ' selected' : ''}>${name}</option>`).join('')}
    </select>`;

  // No key under the chart. The group headers immediately below it already
  // name every player with their count and their face, and did before this
  // chart existed; a second copy of that list is the thing that made one boss
  // card carry the same three names three times over.

  return `
    <div class="bkc" data-boss="${boss.key}">
      <div class="bkc-top">
        <span class="bkc-total"><b>${total}</b> kill${total === 1 ? '' : 's'} all told</span>
        ${picker}
      </div>
      <svg class="bkc-svg" viewBox="0 0 ${W} ${H}" role="img"
           onpointerdown="chartPoint(event, '${boss.key}')"
           onpointermove="chartPoint(event, '${boss.key}')"
           onpointerup="chartPoint(event, '${boss.key}')"
           onpointerleave="unprobeChart('${boss.key}')"
           onclick="event.stopPropagation()"
           aria-label="Running total of ${total} kill${total === 1 ? '' : 's'}, ${
             label(from)} to now">
        <defs>
          <linearGradient id="${fade}" x1="0" y1="0" x2="0" y2="1">
            <stop class="bkc-stop-top" offset="0%"/>
            <stop class="bkc-stop-bot" offset="100%"/>
          </linearGradient>
        </defs>
        <line class="bkc-axis" x1="${L}" y1="${T + plotH}" x2="${W - R}" y2="${T + plotH}"/>
        ${rungs.join('')}
        <polygon class="bkc-area" style="fill:url(#${fade})"
          points="${curve} ${W - R},${T + plotH} ${L},${T + plotH}"/>
        <polyline class="bkc-line" points="${curve}"/>
        <line class="bkc-cursor" y1="${T}" y2="${T + plotH}" style="opacity:0"/>
        ${dots}
        ${heads}
        <circle class="bkc-now" cx="${W - R}" cy="${py(prev).toFixed(1)}" r="3.5"/>
        <circle class="bkc-cursor-dot" r="6.5" style="opacity:0"/>
        <text class="bkc-tick" x="${L}" y="${H - 10}">${label(from)}</text>
        <text class="bkc-tick now" x="${W - R}" y="${H - 10}" text-anchor="end">now</text>
      </svg>
      <div class="bkc-probe"></div>
    </div>`;
}

// Was this player one of the ones the first fight counted as a kill for?
// Asked from the killer chips, so it has to survive a boss the log has never
// seen (no pioneer at all) as readily as one two players took down together.
function drewFirst(pioneer, name) {
  return !!pioneer && (pioneer.by || []).some(who => who.name === name);
}

function fightHistory(boss) {
  const fights = boss.fights || [];
  if (!fights.length) {
    return `<div class="bc-fights">
      <div class="bcf-title"><span>FIGHT HISTORY</span></div>
      <div class="bcf-empty">no fight on record</div>
    </div>`;
  }
  // The chips above already carry each player's face; the same skins serve
  // the group headers and the head beside every name in a fight's detail,
  // rather than being looked up a second way. Helpers are in it too - they
  // are named in the details as often as the killers are.
  const faces = {};
  for (const who of [...(boss.killers || []), ...(boss.helpers || [])]) {
    faces[who.name] = who.skin || '';
  }
  const groups = byLead(fights);
  // One entry in the fight log is one kill, so the count the heading gives is
  // the log's own length rather than the length of the capped list below it.
  const logged = Math.max(boss.logged || 0, fights.length);
  // an id a click can name, unique across the page: the grouping reorders the
  // fights, so a counter that runs over the groups as they are drawn is what
  // keeps one row's id from being another row's
  let seen = 0;

  // First blood, at the head of the details. It belongs above the log rather
  // than in it: every row below is one of many, and this is the one that was
  // not - the night this boss stopped being something nobody here had beaten.
  // Everyone the first fight counted as a kill for stands here, because two
  // players who both cleared the line beat it together and neither of them
  // came second. Whoever only assisted is named after the date instead: they
  // were there, which is worth saying, and they did not beat it, which is
  // the difference this line exists to keep.
  const blood = boss.pioneer;
  const firstBlood = blood ? `
    <div class="bcf-first">
      <span class="bcf-first-mark">${PIXEL_FLAG_SVG}</span>
      <span class="bcf-first-say">
        <b>FIRST BLOOD</b>
        <span class="bcf-first-who">${blood.by.map(who => `
          <span class="bcf-first-one"><i class="bc-face"${faces[who.name]
            ? ` style="--skin:url('${faces[who.name]}')"` : ''}></i>${who.name}</span>`)
          .join('')}</span>
        <em>${blood.at}${blood.party.length
          ? ` · with ${blood.party.join(', ')} assisting` : ''}</em>
      </span>
    </div>` : '';

  return `
    <div class="bc-fights">
      ${firstBlood}
      <div class="bcf-title">
        <span>FIGHT HISTORY</span>
        <em>${logged} fight${logged === 1 ? '' : 's'}${
          logged > fights.length ? ` \u00b7 last ${fights.length} shown` : ''}${
          groups.length > 1 ? ` \u00b7 ${groups.length} players` : ''}${
          boss.assists ? ` \u00b7 <b class="bcf-assists">${boss.assists} assist${
            boss.assists === 1 ? '' : 's'}</b>` : ''}</em>
      </div>
      ${killChart(boss, faces)}
      <div class="bcf-groups">${groups.map(group => `
        <div class="bcf-group shut">
          <button type="button" class="bcf-head"
                  onclick="event.stopPropagation();toggleFightGroup(this)">
            <i class="bc-face"${faces[group.name] ? ` style="--skin:url('${faces[group.name]}')"` : ''}></i>
            <b>${group.name}</b>
            <em>led ${group.fights.length}</em>
            <span class="bcf-caret"></span>
          </button>
          <div class="bcf-rows">${group.fights.map(f =>
            fightRow(f, group.name, `${boss.key}-${seen++}`, faces)).join('')}</div>
        </div>`).join('')}</div>
    </div>`;
}

function shareTier(pct) {
  if (pct >= 50) return 'hi';
  if (pct >= 20) return 'mid';
  return 'lo';
}

// what a compacted number wants hanging off it, and nothing at all otherwise
function exact(n) {
  return typeof n === 'number' && isFinite(n) && Math.abs(n) >= 1e4
    ? ` title="${n}"` : '';
}

// The server sends instants, not words: which clock a time should be read on
// is a question only the browser can answer. These put a UTC stamp onto
// whatever clock the reader is actually sitting at, so a fight logged at
// 03:03Z reads as 10:03pm in Chicago and 4:03am in Berlin, both correct.
//
// Deliberately not toLocaleString: that would hand back a different shape in
// every locale, and these sit in a fixed-width Minecraft face where the column
// has to stay put.
function localClock(d) {
  const h = d.getHours();
  return `${h % 12 || 12}:${String(d.getMinutes()).padStart(2, '0')}${h < 12 ? 'am' : 'pm'}`;
}

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

// 'Aug 27, 2026 10:03pm'. An unparseable stamp comes back as it arrived rather
// than as the word Invalid, so a bad reading is still a reading.
function localMoment(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return `${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()} ${localClock(d)}`;
}

function localTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : localClock(d);
}

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

// A model is a canvas rendered at a fixed pixel size, so a phone cannot be
// served the desktop one and told to shrink it: a WebGL canvas scaled down in
// CSS resamples pixel art into mush. It gets a smaller render instead, which
// is sharp at the size it is actually drawn. The width is read once per build
// rather than watched, since the only thing that changes it mid-visit is a
// device being turned on its side, and the next poll rebuilds anyway.
const NARROW = 560;
const narrow = () => window.innerWidth <= NARROW;
const pick = (wide, small) => () => (narrow() ? small : wide);

const LIVE_MODEL = pick({ width: 148, height: 168 }, { width: 104, height: 124 });
// the same trick the boss cards play when they open: a real render at the
// bigger size rather than a small canvas stretched over a bigger box
const LIVE_MODEL_OPEN = pick({ width: 232, height: 264 }, { width: 168, height: 192 });
const BOSS_MODEL = pick({ width: 124, height: 124 }, { width: 96, height: 96 });
// bigger canvas, not a bigger zoom: the auto-fit already shows the whole
// model at any canvas size (its own math is independent of it), so a real
// render at 240px is what actually makes the mob bigger. A zoom multiplier
// on top of that scales the model past its own camera frame instead and
// crops it top and bottom - the fight history's own layout, not a smaller
// model, is what got a felled player's name from being cut off.
const BOSS_MODEL_OPEN = pick({ width: 240, height: 240 }, { width: 176, height: 176 });

function renderLive(board) {
  const stage = document.getElementById('live-stage');
  if (!stage || !board) return;

  const shape = (board.players || []).map(p => p.uuid).join(',') + '|' +
                (board.bosses || []).map(b => `${b.key}${b.felled}${b.kills}`).join(',') + '|' +
                (board.fish || []).map(f => `${f.key}${f.count}`).join(',');
  if (shape !== liveShape) {
    liveShape = shape;
    buildLive(board);
    mountLive(board);
  }
  updateLive(board);
}

function buildLive(board) {
  fightOpen = null;                    // the rows this named are about to go
  for (const el of liveMounted) if (window.disposeModel) disposeModel(el);
  liveMounted = [];

  const players = board.players || [];
  document.getElementById('ls-list').innerHTML = players.length ? players.map(p => `
    <div class="pcard${p.online ? ' on' : ''}${p.dead ? ' down' : ''}" id="pc-${p.uuid}"
         data-realm="${p.realm || ''}"
         onclick="toggleLive('${p.uuid}')"
         onmouseenter="spin('pm-${p.uuid}', true)" onmouseleave="spin('pm-${p.uuid}', false)">
      <div class="pc-stage"><div class="pc-model" id="pm-${p.uuid}"></div></div>
      <div class="pc-foot">
        <div class="pc-name">${p.name}</div>
        <div class="pc-seen" id="pcs-${p.uuid}"></div>
        <div class="ps-prog pc-hp"><div class="ps-fill" id="pch-${p.uuid}"></div></div>
        <div class="pc-badges" id="pcb-${p.uuid}"></div>
        <div class="pc-nums">
          <span id="pct-${p.uuid}"></span><span id="pcd-${p.uuid}"></span>
        </div>
      </div>
      <div class="pc-panel" id="pp-${p.uuid}"
           onclick="event.stopPropagation()"></div>
    </div>`).join('') : '<p class="rp-none">the server has not reported anybody yet</p>';

  const bossCard = b => {
    // the same tier -> class mapping the star badges use (t1..t4, or mini),
    // so the card's own border can carry the tier's colour before anyone
    // has felled it, not just after. A boss with no tier at all - the index
    // and boss_rewards.js's own grading have gone out of sync - gets no
    // class rather than a guessed one: the plain slot border says "unknown"
    // honestly, where a fallback tier would just be a wrong colour.
    const tierCls = b.category === 'miniboss' ? 'mini' : (b.tier ? `t${b.tier}` : '');
    return `
    <div class="bcard${b.felled ? ' beaten' : ' locked'} ${b.category} ${tierCls}" id="bc-${b.key}"
         data-beaten="${b.felled ? 1 : 0}" onclick="toggleBoss('${b.key}')"
         onmouseenter="spin('bm-${b.key}', true)" onmouseleave="spin('bm-${b.key}', false)">
      <div class="bc-stage"><div class="bc-model" id="bm-${b.key}" data-boss="${b.key}"></div></div>
      <div class="bc-foot">
        <div class="bc-name">
          ${tierCls ? `<span class="bc-star ${tierCls}">${PIXEL_STAR_SVG}</span>` : ''}
          <span class="bc-name-text">${b.felled || REVEAL ? b.name : '???'}</span>
        </div>
        <div class="bc-mod">${b.mod.replace(/_/g, ' ')}</div>
        ${b.felled ? `
          <div class="bc-kills">${compact(b.kills)} kill${b.kills === 1 ? '' : 's'}${
            b.assists ? `<em class="bc-kills-assist">\u00b7 ${compact(b.assists)} assist${
              b.assists === 1 ? '' : 's'}</em>` : ''}</div>
          <div class="bc-killers">${b.killers.map(k => {
            // the flag goes to everyone the first fight counted as a kill
            // for, which is sometimes two of them and never a runner-up
            const drew = drewFirst(b.pioneer, k.name);
            return `
            <span class="bc-killer${drew ? ' first' : ''}"${
              k.skin ? ` style="--skin:url('${k.skin}')"` : ''}${
              drew ? ` title="${k.name} drew first blood on this one, ${
                b.pioneer.at}"` : ''}>
              <i class="bc-face"></i>${
              drew ? `<span class="bc-flag">${PIXEL_FLAG_SVG}</span>` : ''}<b>${
              k.name}</b><em>${k.kills}\u00d7</em>
            </span>`; }).join('')}${(b.helpers || []).map(h => `
            <span class="bc-killer helper"${h.skin ? ` style="--skin:url('${h.skin}')"` : ''}
                  title="${h.name} helped with ${h.fights} of these fights without leading one">
              <i class="bc-face"></i><b>${h.name}</b><em class="bc-assist">+${h.fights}</em>
            </span>`).join('')}</div>
        ` : ''}
      </div>
      ${b.felled ? fightHistory(b) : ''}
    </div>`;
  };

  // The legendary fish are a collection rather than a fight, so the board is
  // a shelf of them: every one Starcatcher can produce in this pack has a
  // slot from the start, drawn as the mod's own unknown_fish silhouette until
  // somebody lands it and it lights up gold. The name is left showing on a
  // slot nobody has filled - a boss keeps its name back because finding out
  // what it is IS the reward, where a fish you have not caught yet is
  // something to go looking for, and a shelf of thirteen identical ??? would
  // tell nobody where to cast.
  const unknown = board.fish_unknown || '';
  const fishCard = f => {
    const best = f.best;
    return `
    <div class="fcard${f.caught ? ' caught' : ' locked'}" id="fc-${f.key}"
         data-caught="${f.caught ? 1 : 0}">
      <div class="fc-stage">
        <img class="fc-icon" src="${f.caught ? f.icon : unknown}" alt=""
             loading="lazy" width="64" height="64">
      </div>
      <div class="fc-foot">
        <div class="fc-name">${f.name}</div>
        ${f.caught ? `
          <div class="fc-tally">${compact(f.count)} landed</div>
          <div class="fc-anglers">${f.anglers.map(a => `
            <span class="bc-killer"${a.skin ? ` style="--skin:url('${a.skin}')"` : ''}>
              <i class="bc-face"></i><b>${a.name}</b><em>${a.count}\u00d7</em>
            </span>`).join('')}</div>
          ${best ? `<div class="fc-best">${best.size} cm \u00b7 ${best.weight}</div>
            ${(() => {
              // a tile is a hundred and twenty pixels wide, so the placing and
              // the two flags share the one line rather than each running off
              // the end of its own
              const marks = [best.top ? `TOP ${best.top}%` : '',
                             best.golden ? 'GOLDEN' : '',
                             best.perfect ? 'PERFECT' : ''].filter(Boolean);
              return marks.length ? `<div class="fc-marks">${marks.join(' \u00b7 ')}</div>` : '';
            })()}` : ''}
        ` : ''}
      </div>
    </div>`;
  };

  const all = board.bosses || [];
  document.getElementById('ls-bosses').innerHTML =
    all.filter(b => b.category !== 'miniboss').map(bossCard).join('');
  document.getElementById('ls-minibosses').innerHTML =
    all.filter(b => b.category === 'miniboss').map(bossCard).join('');
  const shelf = document.getElementById('ls-fish');
  if (shelf) {
    shelf.innerHTML = (board.fish || []).map(fishCard).join('')
      || '<p class="rp-none">no legendary fish are catchable in this pack</p>';
  }
  filterBosses();
  filterFish();
}

// The list can be cut down to the ones already felled. A card that is filtered
// out is display: none, which means it never comes into view and never builds
// its model, so hiding sixty of them costs nothing. Bosses and minibosses are
// two separate grids with their own checkbox and their own count, so each is
// filtered and counted on its own rather than off the combined totals.
function filterSection(gridId, checkboxId, countId) {
  const grid = document.getElementById(gridId);
  if (!grid) return;
  const only = (document.getElementById(checkboxId) || {}).checked;
  let shown = 0, beaten = 0, total = 0;
  for (const card of grid.querySelectorAll('.bcard')) {
    total += 1;
    const isBeaten = card.dataset.beaten === '1';
    if (isBeaten) beaten += 1;
    const hide = only && !isBeaten;
    card.classList.toggle('hidden', hide);
    if (!hide) shown += 1;
  }
  const count = document.getElementById(countId);
  if (count) {
    count.textContent = only ? `${shown} shown of ${total}` : `${beaten} beaten of ${total}`;
  }
}

function filterBosses() {
  filterSection('ls-bosses', 'ls-beaten', 'ls-boss-count');
  filterSection('ls-minibosses', 'ls-mini-beaten', 'ls-mini-count');
}

// The same cut-down as the boss grids, over the tiles the fish shelf holds.
function filterFish() {
  const shelf = document.getElementById('ls-fish');
  if (!shelf) return;
  const only = (document.getElementById('ls-fish-caught') || {}).checked;
  let shown = 0, caught = 0, total = 0;
  for (const tile of shelf.querySelectorAll('.fcard')) {
    total += 1;
    const landed = tile.dataset.caught === '1';
    if (landed) caught += 1;
    const hide = only && !landed;
    tile.classList.toggle('hidden', hide);
    if (!hide) shown += 1;
  }
  const count = document.getElementById('ls-fish-count');
  if (count) {
    count.textContent = only ? `${shown} shown of ${total}`
                             : `${caught} caught of ${total}`;
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
      buildPlayerModel(box, { skin: p.skin, slim: p.slim, ...LIVE_MODEL() });
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
                         locked: !boss.felled && !REVEAL, ...BOSS_MODEL() });
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

// The exact star pixel art the user supplied, extracted from the source PNG
// (each in-game pixel measured 10x10 source pixels, sampled at cell centers)
// rather than redrawn or rasterised from a polygon. Reused for every tier:
// each class repaints the same four regions (outline, base, shadow, glint)
// through CSS custom properties.
const PIXEL_STAR_SVG = `<svg class="badge-star" viewBox="0 0 11 10" shape-rendering="crispEdges">
<rect x="5" y="0" width="1" height="1" class="px-o"/><rect x="4" y="1" width="1" height="1" class="px-o"/><rect x="5" y="1" width="1" height="1" class="px-s"/><rect x="6" y="1" width="1" height="1" class="px-o"/><rect x="4" y="2" width="1" height="1" class="px-o"/><rect x="5" y="2" width="1" height="1" class="px-b"/><rect x="6" y="2" width="1" height="1" class="px-o"/><rect x="1" y="3" width="1" height="1" class="px-o"/><rect x="2" y="3" width="1" height="1" class="px-o"/><rect x="3" y="3" width="1" height="1" class="px-o"/><rect x="4" y="3" width="1" height="1" class="px-b"/><rect x="5" y="3" width="1" height="1" class="px-h"/><rect x="6" y="3" width="1" height="1" class="px-s"/><rect x="7" y="3" width="1" height="1" class="px-o"/><rect x="8" y="3" width="1" height="1" class="px-o"/><rect x="9" y="3" width="1" height="1" class="px-o"/>
<rect x="0" y="4" width="1" height="1" class="px-o"/><rect x="1" y="4" width="1" height="1" class="px-b"/><rect x="2" y="4" width="1" height="1" class="px-h"/><rect x="3" y="4" width="1" height="1" class="px-h"/><rect x="4" y="4" width="1" height="1" class="px-h"/><rect x="5" y="4" width="1" height="1" class="px-h"/><rect x="6" y="4" width="1" height="1" class="px-b"/><rect x="7" y="4" width="1" height="1" class="px-b"/><rect x="8" y="4" width="1" height="1" class="px-h"/><rect x="9" y="4" width="1" height="1" class="px-s"/><rect x="10" y="4" width="1" height="1" class="px-o"/><rect x="1" y="5" width="1" height="1" class="px-o"/><rect x="2" y="5" width="1" height="1" class="px-b"/><rect x="3" y="5" width="1" height="1" class="px-h"/><rect x="4" y="5" width="1" height="1" class="px-h"/><rect x="5" y="5" width="1" height="1" class="px-b"/>
<rect x="6" y="5" width="1" height="1" class="px-b"/><rect x="7" y="5" width="1" height="1" class="px-h"/><rect x="8" y="5" width="1" height="1" class="px-s"/><rect x="9" y="5" width="1" height="1" class="px-o"/><rect x="2" y="6" width="1" height="1" class="px-o"/><rect x="3" y="6" width="1" height="1" class="px-s"/><rect x="4" y="6" width="1" height="1" class="px-b"/><rect x="5" y="6" width="1" height="1" class="px-b"/><rect x="6" y="6" width="1" height="1" class="px-h"/><rect x="7" y="6" width="1" height="1" class="px-b"/><rect x="8" y="6" width="1" height="1" class="px-o"/><rect x="2" y="7" width="1" height="1" class="px-o"/><rect x="3" y="7" width="1" height="1" class="px-b"/><rect x="4" y="7" width="1" height="1" class="px-s"/><rect x="5" y="7" width="1" height="1" class="px-o"/><rect x="6" y="7" width="1" height="1" class="px-s"/>
<rect x="7" y="7" width="1" height="1" class="px-b"/><rect x="8" y="7" width="1" height="1" class="px-o"/><rect x="1" y="8" width="1" height="1" class="px-o"/><rect x="2" y="8" width="1" height="1" class="px-b"/><rect x="3" y="8" width="1" height="1" class="px-s"/><rect x="4" y="8" width="1" height="1" class="px-o"/><rect x="6" y="8" width="1" height="1" class="px-o"/><rect x="7" y="8" width="1" height="1" class="px-s"/><rect x="8" y="8" width="1" height="1" class="px-b"/><rect x="9" y="8" width="1" height="1" class="px-o"/><rect x="1" y="9" width="1" height="1" class="px-o"/><rect x="2" y="9" width="1" height="1" class="px-o"/><rect x="3" y="9" width="1" height="1" class="px-o"/><rect x="7" y="9" width="1" height="1" class="px-o"/><rect x="8" y="9" width="1" height="1" class="px-o"/><rect x="9" y="9" width="1" height="1" class="px-o"/>
</svg>`;

// A hand, drawn the same way the star is: whole pixels on a grid the same
// shape, so it sits in the row of badges as one of them rather than as a
// glyph borrowed from somewhere else. It marks the kills a player turned up
// for without carrying, which is a thing a star cannot say - a star is for
// what you beat, and this is for what you helped beat.
const PIXEL_HAND_SVG = `<svg class="badge-hand" viewBox="0 0 11 10" shape-rendering="crispEdges">
<rect x="3" y="0" width="1" height="3" class="px-h"/><rect x="5" y="0" width="1" height="3" class="px-h"/><rect x="7" y="0" width="1" height="3" class="px-h"/>
<rect x="3" y="3" width="5" height="1" class="px-b"/>
<rect x="1" y="4" width="1" height="3" class="px-h"/>
<rect x="2" y="4" width="6" height="1" class="px-b"/>
<rect x="2" y="5" width="6" height="1" class="px-b"/>
<rect x="2" y="6" width="6" height="1" class="px-b"/>
<rect x="3" y="7" width="4" height="1" class="px-b"/>
<rect x="4" y="8" width="2" height="1" class="px-s"/>
</svg>`;

// A pennant on a pole, drawn on the same eleven by ten grid the star and the
// hand use so it sits in the row of badges as one of them. It marks the
// bosses this player put down before anybody else on the server did - not
// how well, not how often, only that they got there first, which is the one
// thing on this page nobody can take back or catch up to.
const PIXEL_FLAG_SVG = `<svg class="badge-flag" viewBox="0 0 11 10" shape-rendering="crispEdges">
<rect x="1" y="0" width="1" height="10" class="px-h"/><rect x="2" y="0" width="1" height="10" class="px-s"/>
<rect x="3" y="0" width="6" height="1" class="px-b"/><rect x="9" y="0" width="1" height="1" class="px-s"/>
<rect x="3" y="1" width="1" height="4" class="px-h"/>
<rect x="4" y="1" width="4" height="1" class="px-b"/><rect x="8" y="1" width="1" height="1" class="px-s"/>
<rect x="4" y="2" width="3" height="1" class="px-b"/><rect x="7" y="2" width="1" height="1" class="px-s"/>
<rect x="4" y="3" width="2" height="1" class="px-b"/><rect x="6" y="3" width="1" height="1" class="px-s"/>
<rect x="4" y="4" width="1" height="1" class="px-b"/><rect x="5" y="4" width="1" height="1" class="px-s"/>
<rect x="3" y="5" width="1" height="1" class="px-s"/>
<rect x="0" y="9" width="1" height="1" class="px-s"/><rect x="3" y="9" width="1" height="1" class="px-s"/>
</svg>`;

// One star per tier beaten, plus a grey star for minibosses. p.bosses already
// holds one entry per boss ID beaten, so counting entries (not summing kills)
// is what makes a boss killed three times still worth one star. Tier 4 has no
// bosses yet, but the counter and the CSS (.pc-badge.t4) are ready for it.
// What each badge is, in the pack's own words: boss_rewards.js grades every
// boss it knows as a Lesser, Greater or Apex Boss, and that is the name a
// player has already seen in chat when one went down. Tier 4 is the rung
// above, held open by the roster and unused so far.
const TIER_NAMES = {
  1: 'Lesser Boss', 2: 'Greater Boss', 3: 'Apex Boss', 4: 'Beyond Apex Boss',
};
// every grade ends in the word, so one rule pluralises all four
const plural = (name, n) => n === 1 ? name : `${name}es`;

function bossBadges(p) {
  const counts = { 4: 0, 3: 0, 2: 0, 1: 0, mini: 0 };
  for (const b of p.bosses || []) {
    // A star is for having beaten the thing, and helping to bring a boss
    // down is beating it - the Ancient Guardian took two of them the better
    // part of seven minutes and neither was a spectator. Which of them the
    // kill is counted against is a separate question, answered on the
    // boss's own card and in the row below this badge; the star is not the
    // place to relitigate it.
    if (b.category === 'miniboss') counts.mini++;
    else if (counts[b.tier] !== undefined) counts[b.tier]++;
  }
  // one note per badge, shown on hover and read out by anything that is not
  // looking - see [data-tip] in the stylesheet
  const chip = (cls, n, tip) => n
    ? `<span class="pc-badge ${cls}" role="img" data-tip="${tip(n)}"
             aria-label="${tip(n)}">${PIXEL_STAR_SVG}x${n}</span>` : '';
  const star = tier => n =>
    `${n} ${plural(TIER_NAMES[tier], n)} beaten (tier ${tier})`;
  // Hands lent to somebody else's kill. Last in the row and quietest in it:
  // a star says what they have beaten, and this says only what they turned
  // up for without carrying, which is the least of the two.
  const lent = (p.bosses || []).reduce((n, b) => n + (b.assists || 0), 0);
  const lentTip = `Was in ${lent} winning fight${
    lent === 1 ? '' : 's'} without dealing the biggest share`;
  const helped = lent
    ? `<span class="pc-badge assist" role="img" data-tip="${lentTip}"
             aria-label="${lentTip}">${PIXEL_HAND_SVG}x${lent}</span>`
    : '';
  // First blood. Not a tier and not a count of fights: the number of bosses
  // this server had never seen beaten until this player beat one. It sits
  // below the stars and above the hand, which is where it belongs in the
  // reading - the stars say what they have beaten, this says which of those
  // nobody had beaten before them, and the hand says what they only helped
  // with.
  const led = (p.bosses || []).filter(b => b.first).length;
  const ledTip = `First one to kill ${led} boss${led === 1 ? '' : 'es'}`;
  const firsts = led
    ? `<span class="pc-badge first" role="img" data-tip="${ledTip}"
             aria-label="${ledTip}">${PIXEL_FLAG_SVG}x${led}</span>`
    : '';
  return [chip('t4', counts[4], star(4)), chip('t3', counts[3], star(3)),
          chip('t2', counts[2], star(2)), chip('t1', counts[1], star(1)),
          chip('mini', counts.mini, n => `${n} ${plural('Miniboss', n)} beaten`),
          firsts, helped].join('');
}

// ── the world panel ────────────────────────────────────────────────────────
// The board's numbers are all about the people on the server. This is the
// server itself: the day it is on, the sky over it, the season the pack is
// running, and how well the tick is holding. It sits above the player totals
// because it is the ground all of them stand on.
//
// The sun, the moon and the calendar are the game's own textures rather than
// anything drawn here - see tools/extract_world_icons.py - so what the panel
// shows for a phase is the face a player sees in the sky for it.
const WORLD_ICONS = '/static/minecraft/icons';

// which sky the panel wears. Rain and thunder outrank the hour, because a
// storm is what you would notice first looking out of a window.
// The hour decides the sky and nothing else does. Weather used to replace it,
// which meant a rainy noon was drawn as night; it is its own layer now, and so
// is the season, so the three stack the way they do in the world.
function skyMood(w) {
  return w.daylight ? 'day' : 'night';
}

function skyWeather(w) {
  if (w.weather === 'Thunder') return 'storm';
  if (w.weather === 'Rain') return 'rain';
  return 'clear';
}

// one reading: a small label over a value, in a slot of its own
function worldFact(label, value, tone, hint) {
  if (value === '' || value === null || value === undefined) return '';
  return `<span class="lw-fact${tone ? ` ${tone}` : ''}"${
    hint ? ` title="${hint}"` : ''}><i>${label}</i><b>${value}</b></span>`;
}

function worldPanel(w, server) {
  const host = document.getElementById('ls-world');
  if (!host) return;
  // an export from before the world section existed, or one that could not be
  // read: say nothing rather than a panel full of zeroes
  if (!w || !Object.keys(w).length) {
    host.innerHTML = '';
    host.hidden = true;
    return;
  }
  host.hidden = false;

  const sky = w.daylight
    ? { src: `${WORLD_ICONS}/sun.png`, alt: 'Sun', name: w.phase || 'Day' }
    : { src: `${WORLD_ICONS}/moon_${w.moon || 0}.png`, alt: 'Moon',
        name: w.moon_name || w.phase || 'Night' };

  // the calendar face for this sub-season, when the pack names one this build
  // knows. An unknown season gets the words and no picture, which is honest.
  const leaf = w.sub_index >= 0
    ? `<img class="lw-orb leaf" src="${WORLD_ICONS}/season_${
        String(w.sub_index).padStart(2, '0')}.png" alt="${w.sub_season}">`
    : '';
  const soon = w.season_left
    ? `${w.season_left} day${w.season_left === 1 ? '' : 's'}${
        w.next_season ? ` to ${w.next_season}` : ' left'}`
    : '';
  const year = w.year_days
    ? `day ${w.season_day} of ${w.year_days}`
    : (w.season_day ? `day ${w.season_day}` : '');

  host.dataset.mood = skyMood(w);
  host.dataset.weather = skyWeather(w);
  host.dataset.season = (w.season || '').toLowerCase();

  // The weather gets real elements rather than one pseudo-element sheet. A
  // single sliding gradient is flat by construction: one angle, one speed, one
  // opacity, and rain read at every distance at once. These are three sheets
  // at three depths with a mist band and a splash line under them, which is
  // what gives it somewhere to fall from and somewhere to land.
  //
  // aria-hidden throughout: it is scenery, and the weather is already said in
  // words twice over in the panel behind it.
  const weather = `
    <div class="lw-weather" aria-hidden="true">
      <i class="lw-sheet far"></i>
      <i class="lw-sheet mid"></i>
      <i class="lw-sheet near"></i>
      <i class="lw-mist"></i>
      <i class="lw-splash"></i>
      <svg class="lw-bolt" viewBox="0 0 40 100" preserveAspectRatio="none">
        <path d="M24 0 L8 46 h12 L4 100 L34 40 H21 L32 0 Z"/>
      </svg>
    </div>`;

  host.innerHTML = weather + `
    <div class="lw-heroes">
      <div class="lw-hero sky">
        <img class="lw-orb" src="${sky.src}" alt="${sky.alt}">
        <div class="lw-say">
          <b>Day ${w.day}</b>
          <span>${w.clock}${w.clock && sky.name ? ' · ' : ''}${sky.name}</span>
          <em>${w.weather}</em>
        </div>
      </div>
      <div class="lw-hero season">
        ${leaf}
        <div class="lw-say">
          <b>${w.sub_season || w.season || '—'}</b>
          <span>${w.season}${w.season && year ? ' · ' : ''}${year}</span>
          <em>${soon}</em>
          ${w.year_pct ? `<span class="lw-year" title="${
            w.year_pct}% through the year"><i style="width:${w.year_pct}%"></i></span>` : ''}
        </div>
      </div>
    </div>
    <div class="lw-facts">
      ${(() => {
        // Up, the tile counts how long the server has been running. Down, it
        // counts how long it has been down instead - the same slot answering
        // the same question, "how long has it been like this", with the sign
        // flipped. Green for one and red for the other, so the state reads off
        // the colour before anybody parses the word.
        //
        // The downtime is measured from the last thing the server wrote, which
        // is the moment it stopped; see live.py's _server_up.
        const down = server && server.down;
        return down
          ? worldFact('downtime', fmtSpan(down), 'poor down',
                      'the server stopped writing this long ago')
          : worldFact('uptime', w.uptime, 'good');
      })()}
      ${worldFact('weather', w.weather)}
      ${worldFact('year', w.year_pct ? `${w.year_pct}%` : '', '',
                  w.year_days ? `day ${w.season_day} of ${w.year_days}` : '')}
    </div>`;
}

function updateLive(board) {
  const T = board.totals;
  if (!T) return;

  // up, down, or not yet known: an unsynced checkout has nothing to go on and
  // should say so rather than accuse a server that is very likely running
  const status = document.getElementById('ls-status');
  if (status) {
    const up = board.server ? board.server.online : null;
    status.textContent = up === null ? '' : up ? 'ONLINE' : 'OFFLINE';
    status.className = `ls-status${up === null ? '' : up ? ' on' : ' off'}`;
  }
  worldPanel(board.world, board.server);

  const tile = (label, value, hot) =>
    `<span class="ls-tile${hot ? ' hot' : ''}"><i>${label}</i><b>${value}</b></span>`;

  document.getElementById('ls-tiles').innerHTML =
    tile('online', `${T.online}/${T.tracked}`, T.online > 0) +
    tile('played', T.played) +
    tile('deaths', compact(T.deaths)) +
    tile('mob kills', compact(T.kills)) +
    tile('bosses', `${T.bosses}/${T.boss_all}`, T.bosses > 0) +
    tile('legendary fish', `${T.fish}/${T.fish_all}`, T.fish > 0);

  document.getElementById('ls-count').textContent =
    `${T.online} of ${T.tracked} online`;
  filterBosses();
  filterFish();

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
    set(`pcd-${p.uuid}`, `${compact(p.deaths)} deaths`);
    const badges = document.getElementById(`pcb-${p.uuid}`);
    if (badges) badges.innerHTML = bossBadges(p);
    // the health meter under every card: how much of them is left, and said
    // in words as well for anyone who does not read a red bar as hearts
    const left = p.max_health ? p.health / p.max_health : 0;
    const bar = document.getElementById(`pch-${p.uuid}`);
    if (bar) bar.style.width = `${Math.round(left * 100)}%`;
    const track = bar && bar.parentElement;
    if (track) {
      track.title = p.dead ? `${p.name} is on the respawn screen`
        : `Health ${Math.round(p.health * 10) / 10} of ${p.max_health}`;
    }
    const card = document.getElementById(`pc-${p.uuid}`);
    if (card) {
      card.classList.toggle('worst', p.deaths === worst && worst > 1);
      card.classList.toggle('hurt', !p.dead && left > 0 && left <= 0.5);
      card.classList.toggle('dying', !p.dead && left > 0 && left <= 0.25);
    }
  }

  if (liveOpen) drawDrawer(board);
  liveTick();
}

// The full record opens under the grid rather than inside a card: a card is
// mostly model, and there is nowhere in it to put twelve numbers.
// The record used to open in a drawer beneath the whole grid, which meant
// the card you clicked stayed its old size somewhere above while its numbers
// appeared somewhere else - and with nine cards in the way, often off screen.
// It goes in the card now, the same move a boss card makes: the card takes
// the row, goes to the head of the section, and the player stands full size
// beside their own numbers. No face crop in the heading any more either; the
// model is right there, and at that size it is a better likeness than a
// fourteen-pixel square of their scalp.
function drawDrawer(board) {
  for (const box of document.querySelectorAll('.pc-panel')) {
    if (box.id !== `pp-${liveOpen}`) box.innerHTML = '';
  }
  const player = (board.players || []).find(p => p.uuid === liveOpen);
  const panel = player && document.getElementById(`pp-${player.uuid}`);
  if (!panel) return;
  const state = player.dead ? 'respawning' : player.online ? 'online' : 'offline';
  panel.innerHTML = `
    <div class="pp-head">
      <span class="pp-title">SERVER RECORD</span>
      <i class="lsd-pill ${state}">${state}</i>
    </div>
    ${livePanel(player)}`;
}

// A locked card has no fight history to show, so clicking one is a no-op
// rather than opening an empty section. Only one boss card holds itself
// open at a time, the same as the player drawer, so the grid never carries
// more than one stretched-out row at once.
function toggleBoss(key) {
  const card = document.getElementById(`bc-${key}`);
  if (!card || card.dataset.beaten !== '1') return;
  const previous = bossOpen;
  bossOpen = bossOpen === key ? null : key;
  // a fight left stretched out inside a card nobody can see is a row that
  // opens on its own the next time that card does
  if (previous !== bossOpen && fightOpen) toggleFight(fightOpen);
  for (const c of document.querySelectorAll('.bcard')) {
    c.classList.toggle('open', c.id === `bc-${bossOpen}`);
  }
  // the model is rebuilt at each state's own canvas size rather than just
  // resized in CSS, so the open card's bigger stage gets a model actually
  // rendered for it instead of a small canvas stretched blurry over it
  const rebuild = (k, opts) => {
    const boss = (liveBoard.bosses || []).find(b => b.key === k);
    const el = document.getElementById(`bm-${k}`);
    if (boss && el) buildMobModel(el, { model: boss.model, locked: false, ...opts });
  };
  if (previous && previous !== bossOpen) rebuild(previous, BOSS_MODEL());
  if (bossOpen) rebuild(bossOpen, BOSS_MODEL_OPEN());
  // The card leaves its place in the grid for the head of the section, which
  // on a nine-row block is a long way above where it was clicked. Bringing it
  // into view is the other half of moving it there - after a frame, so the
  // grid has settled on where "there" is.
  if (bossOpen) {
    requestAnimationFrame(() =>
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' }));
  }
}

function toggleLive(uuid) {
  const previous = liveOpen;
  liveOpen = liveOpen === uuid ? null : uuid;
  for (const card of document.querySelectorAll('.pcard')) {
    card.classList.toggle('open', card.id === `pc-${liveOpen}`);
  }
  drawDrawer(liveBoard);

  // a model is rendered at a fixed canvas size, so each state gets its own
  // render rather than one bitmap stretched or shrunk over the other's box
  const redraw = (id, opts) => {
    const player = (liveBoard.players || []).find(p => p.uuid === id);
    const box = document.getElementById(`pm-${id}`);
    if (player && player.skin && box && typeof buildPlayerModel === 'function') {
      buildPlayerModel(box, { skin: player.skin, slim: player.slim, ...opts });
    }
  };
  if (previous && previous !== liveOpen) redraw(previous, LIVE_MODEL());
  if (liveOpen) {
    redraw(liveOpen, LIVE_MODEL_OPEN());
    // the card has left its place in the grid for the head of the section,
    // which on nine players is a long way from where it was clicked
    const card = document.getElementById(`pc-${liveOpen}`);
    if (card) requestAnimationFrame(() =>
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' }));
  }
}

// When the server was last asked, counted up second by second. Deliberately
// not the age of the numbers: the export only changes when something in the
// world does, so a board keyed to that would claim to be hours stale on a
// quiet night when in fact it had been checked minutes ago. This says the
// thing a reader actually wants to know, which is whether anyone is still
// listening.
function liveTick() {
  const el = document.getElementById('ls-age');
  if (!el || !liveBoard) return;
  const since = liveBoard.checked;
  if (since == null) { el.textContent = ''; return; }
  el.textContent = `last updated ${fmtSpan(since + (Date.now() - liveAt) / 1000)} ago`;
}

async function pollLive() {
  if (livePolling) return;
  livePolling = true;
  liveTick();
  liveDue = LIVE_EVERY;
  try {
    const res = await fetch(LIVE_URL, { headers: { 'X-Requested-With': 'fetch' } });
    if (!res.ok) throw new Error(res.status);
    const board = await res.json();
    if (board && board.players) {
      liveBoard = board;
      liveAt = Date.now();
      renderLive(board);
    }
  } catch (err) {
    /* a poll that does not land leaves the last good board on screen, and the
       counter keeps rising, which is itself the honest signal */
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

// ── the server's chat ───────────────────────────────────────────────────────
//
// A box in the corner rather than a section in the page, because it is the one
// reading here that is worth having in the corner of your eye while you read
// something else.
//
// It polls its own endpoint on its own clock, faster than the board does. That
// endpoint reads a file rather than the game host - see chat.py - so the tempo
// here costs the server nothing, and a hundred tabs cost it the same as one.
//
// Every row is built with textContent. Chat is written by whoever is on the
// server and nothing they type is ever handed to innerHTML.
const CHAT_EVERY = 10;          // seconds between polls
const CHAT_KEEP  = 200;         // rows kept in the box before the top is cut

let chatSeq     = null;         // last sequence number we have drawn
let chatDue     = 0;            // seconds until the next poll
let chatPolling = false;
let chatUnread  = 0;
let chatLive    = false;        // has a poll ever landed
// stuck to the bottom until the reader scrolls up, and stuck where they left
// it after that: a box that yanks itself back down mid-read is unreadable on
// a busy server, which is exactly when somebody would be reading it
let chatPinned  = true;

function chatOpen() {
  try { return localStorage.getItem('mc-chat') !== 'shut'; } catch (e) { return true; }
}

function toggleChat(force) {
  const box = document.getElementById('mc-chat');
  if (!box) return;
  const shut = force === undefined ? !box.classList.contains('shut') : !force;
  box.classList.toggle('shut', shut);
  const tab = document.getElementById('mcc-tab');
  if (tab) tab.setAttribute('aria-expanded', String(!shut));
  try { localStorage.setItem('mc-chat', shut ? 'shut' : 'open'); } catch (e) { /* private mode */ }
  if (!shut) {
    chatUnread = 0;
    chatBadge();
    chatToEnd();
  }
}

function chatBadge() {
  const el = document.getElementById('mcc-badge');
  if (!el) return;
  el.hidden = !chatUnread;
  el.textContent = chatUnread > 99 ? '99+' : String(chatUnread);
}

function chatToEnd() {
  const log = document.getElementById('mcc-log');
  if (!log) return;
  chatPinned = true;
  log.scrollTop = log.scrollHeight;
  const jump = document.getElementById('mcc-jump');
  if (jump) jump.hidden = true;
}

// A player's own colour, the one their face is reduced to everywhere else on
// the page, so a name in the chat matches the name on their card. Players who
// have never been on the board - or a message from before we knew them - fall
// through to the ordinary text colour rather than to a colour meaning nothing.
function chatTone(uuid) {
  if (!uuid || !liveBoard || !liveBoard.players) return '';
  const who = liveBoard.players.find(p => p.uuid === uuid);
  return (who && who.tone) || '';
}

function chatRow(message) {
  const row = document.createElement('div');
  row.className = 'mcc-row';

  const when = document.createElement('time');
  const stamp = new Date(message.at);
  if (!isNaN(stamp.getTime())) {
    when.dateTime = message.at;
    when.textContent = localClock(stamp);
  }
  row.appendChild(when);

  const who = document.createElement('b');
  who.textContent = message.name;
  const tone = chatTone(message.uuid);
  if (tone) who.style.color = tone;
  row.appendChild(who);

  const said = document.createElement('span');
  said.textContent = message.text;
  row.appendChild(said);
  return row;
}

// A break in the feed, drawn rather than glossed over. The server's buffer
// holds ten messages, so a tab left shut through a busy evening comes back to
// find the middle of it gone - see chat.py. Saying so is the only honest thing
// the box can do; quietly butting the two ends together would read as one
// conversation that never happened.
function chatGap(n) {
  const row = document.createElement('div');
  row.className = 'mcc-gap';
  row.textContent = `${n} message${n === 1 ? '' : 's'} not shown`;
  return row;
}

// Why the box is empty, in one line.
//
// `checked` is when the server was last asked, which is the reading that tells
// a quiet server from a stopped poller. A couple of minutes is the normal
// state of things - the worker looks every twenty-five seconds - so anything
// past a few minutes means nothing is filling the archive, and the box says so
// rather than implying the players have gone to bed.
const CHAT_COLD = 10 * 60;      // seconds before the feed itself is the story

function chatNote(feed) {
  const row = document.createElement('div');
  row.className = 'mcc-note';
  const since = feed.checked == null ? null : (Date.now() / 1000) - feed.checked;
  row.textContent = (since == null || since > CHAT_COLD)
    ? `feed not updating \u00b7 last checked ${
        since == null ? 'never' : fmtSpan(since) + ' ago'}`
    : 'nothing said in the last hour';
  if (since != null && since > CHAT_COLD) row.classList.add('cold');
  return row;
}

function chatDraw(feed) {
  const log = document.getElementById('mcc-log');
  const box = document.getElementById('mc-chat');
  if (!log || !box) return;

  const first = chatSeq === null;
  if (first) {
    box.hidden = false;
    toggleChat(chatOpen());
  }

  const dot = box.querySelector('.mcc-dot');
  if (dot) dot.classList.toggle('cold', (feed.source || {}).state === 'error');

  // Nothing said in the last hour empties the box, on the server's reckoning
  // rather than on a timer here - see chat.py's STALE. A tab left open all
  // afternoon clears itself on the poll that crosses the hour, so it shows
  // what a tab opened this second would show rather than this morning's
  // conversation under a heading that says the chat is live.
  if (feed.stale) {
    // Empty, but never blank. An empty box says nothing about *why* it is
    // empty, and the two reasons could not be further apart: nobody has
    // spoken in an hour, or the thing that fills the archive stopped running
    // and every message in it has simply aged out. Both look identical from
    // the outside, which is exactly how a feed that had not been pulled in
    // four hours passed for a quiet evening.
    log.replaceChildren(chatNote(feed));
    chatUnread = 0;
    chatBadge();
    chatToEnd();
    chatSeq = feed.seq;
    return;
  }

  if (feed.skipped) log.appendChild(chatGap(feed.skipped));
  for (const message of feed.messages) log.appendChild(chatRow(message));

  if (feed.messages.length) {
    while (log.childElementCount > CHAT_KEEP) log.removeChild(log.firstChild);
    if (!first && box.classList.contains('shut')) {
      chatUnread += feed.messages.length;
      chatBadge();
    }
  }
  chatSeq = feed.seq;

  if (chatPinned) {
    chatToEnd();
  } else if (feed.messages.length) {
    const jump = document.getElementById('mcc-jump');
    if (jump) jump.hidden = false;
  }

}

async function pollChat() {
  if (chatPolling) return;
  chatPolling = true;
  chatDue = CHAT_EVERY;
  try {
    const url = chatSeq === null ? CHAT_URL : `${CHAT_URL}?since=${chatSeq}`;
    const res = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } });
    if (!res.ok) throw new Error(res.status);
    const feed = await res.json();
    if (feed && Array.isArray(feed.messages)) {
      chatLive = true;
      chatDraw(feed);
    }
  } catch (err) {
    /* a poll that does not land leaves what is on screen there. The box is
       the least important thing on the page and it never takes anything else
       down with it. */
  } finally {
    chatPolling = false;
    if (chatDue <= 0) chatDue = CHAT_EVERY;
  }
}

function bootChat() {
  const log = document.getElementById('mcc-log');
  if (!log) return;
  log.addEventListener('scroll', () => {
    // a few pixels of slack: a box scrolled to within a line of the bottom is
    // a reader who is following along, not one who has gone back to look
    const end = log.scrollHeight - log.clientHeight - log.scrollTop < 24;
    chatPinned = end;
    const jump = document.getElementById('mcc-jump');
    if (jump && end) jump.hidden = true;
  });
  pollChat();
}


// ── the server's rhythm ─────────────────────────────────────────────────────
//
// Two readings off one log: which hours of which days the server is alive, and
// which days were the big ones. Both come from activity.py, which builds them
// by sampling a counter - nothing the game exports carries this history, so it
// starts the day the sampling started and grows forwards.
//
// The buckets arrive keyed by UTC hour and are rolled up here rather than on
// the server, because rolling them up means choosing a timezone: 8pm on the
// server's clock is a different evening for every reader, and the only useful
// answer is the one in the timezone of whoever is looking.
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

let rhythmBoard = null;
let rhythmBusy = false;

// '2026-08-30T14' -> a local Date. Built by hand rather than by handing the
// string to Date(), which reads a bare 'YYYY-MM-DDTHH' as local time on some
// engines and UTC on others; these keys are always UTC.
function rhythmHour(key) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2})$/.exec(key);
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4]));
}

// What the grid is showing. Three different questions off the same buckets,
// and the third is the one people actually ask: not when the server is busy
// but when everybody is on at once.
let rhythmMode = 'all';

// A bucket, reduced to one number under the current mode. `together` counts
// distinct players seen in the hour rather than summing their time: two people
// on for half an hour each is a pair, and the same half-hour played by one
// person twice as long is not.
function rhythmValue(bucket, mode) {
  if (!bucket || typeof bucket !== 'object') {
    // a bucket from the version that stored a bare total still reads under
    // 'all' and has nothing to say about who was in it
    return mode === 'all' && typeof bucket === 'number' ? bucket : 0;
  }
  const who = bucket.who || {};
  if (mode === 'all') return bucket.played || 0;
  if (mode === 'together') {
    return Object.values(who).filter(r => (r.n || 0) > 0 || (r.s || 0) > 0).length;
  }
  return (who[mode] || {}).s || 0;
}

// the grid, in the reader's own week: 7 rows of 24
function rhythmGrid(hours, mode) {
  const grid = DAYS.map(() => new Array(24).fill(0));
  const seen = DAYS.map(() => Array.from({ length: 24 }, () => new Set()));
  // downtime summed across every week that fed this cell, and how many hours
  // that was, so the band is drawn against the time the cell actually covers
  const down = DAYS.map(() => new Array(24).fill(0));
  const span = DAYS.map(() => new Array(24).fill(0));
  for (const [key, bucket] of Object.entries(hours || {})) {
    const when = rhythmHour(key);
    if (!when) continue;
    const day = when.getDay(), hour = when.getHours();
    down[day][hour] += (bucket && bucket.down) || 0;
    span[day][hour] += 3600;
    const value = rhythmValue(bucket, mode);
    // `together` is a headcount, and a headcount does not add up across four
    // Tuesdays: the cell takes the best that week ever managed, not the sum
    if (mode === 'together') {
      grid[day][hour] = Math.max(grid[day][hour], value);
    } else {
      grid[day][hour] += value;
    }
    for (const name of Object.keys((bucket && bucket.who) || {})) {
      seen[day][hour].add(name);
    }
  }
  return { grid, seen, down, span };
}

// A cell's weight against the busiest cell, eased. Play time is wildly
// lopsided - one evening raid can be twenty times a quiet Tuesday afternoon -
// and a linear ramp against the peak draws every ordinary hour as empty. The
// square root keeps the quiet hours visible while the busy ones still lead.
function rhythmHeat(value, peak) {
  if (!value || !peak) return 0;
  return Math.min(1, Math.sqrt(value / peak));
}

// How tall the red band on a cell should be, as a fraction of it.
//
// Nothing at all under the floor: a modded server restart is a couple of
// minutes and is not an outage worth colouring, and the number comes from the
// log rather than being kept here so the two cannot drift apart.
//
// Above it, eased the same way the green is. A one-hour outage inside a whole
// day is four percent of that day, which as a straight proportion is a band
// too thin to see; the square root plus a floor of an eighth means every
// outage past the threshold is visible and worse ones are visibly worse.
const DOWN_MIN_BAND = 0.125;

function rhythmDownBand(down, span) {
  const floor = (rhythmBoard && rhythmBoard.down_floor) || 300;
  if (!down || !span || down < floor) return 0;
  return Math.max(DOWN_MIN_BAND, Math.min(1, Math.sqrt(down / span)));
}

// the cell's own markup for that band, and the words for the readout
function rhythmDownAttr(down, span) {
  const band = rhythmDownBand(down, span);
  return band ? ` --down:${(band * 100).toFixed(1)}%` : '';
}

function rhythmDownSay(down) {
  const floor = (rhythmBoard && rhythmBoard.down_floor) || 300;
  return down && down >= floor ? ` · down ${rhythmSpan(down)}` : '';
}

function rhythmSpan(seconds) {
  if (!seconds) return '0m';
  // rounded to minutes first, then split. Splitting first and rounding the
  // remainder lets 3570 seconds round up to sixty minutes and print "1h 60m".
  const mins = Math.round(seconds / 60);
  const h = Math.floor(mins / 60), m = mins % 60;
  if (h >= 10) return `${h}h`;
  return h ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m`;
}

function setRhythmMode(mode) {
  rhythmMode = mode;
  if (rhythmBoard) rhythmPanel(rhythmBoard);
}

// How far out the grid is zoomed. A day is twenty-four hours in a row, a week
// is those hours stacked seven deep, and a month is one square per day laid
// out as a calendar. Week is the default because it is the only one of the
// three that shows a *habit*: a day is an anecdote and a month is a trend, but
// "Friday evening" only exists at this scale.
let rhythmScale = 'week';

function setRhythmScale(scale) {
  rhythmScale = scale;
  if (rhythmBoard) rhythmPanel(rhythmBoard);
}

// One day's row from the log, reduced under the current mode - the same three
// questions the hour buckets answer, asked of a whole day.
function rhythmDayValue(who, mode) {
  const rows = who || {};
  if (mode === 'together') {
    return Object.values(rows).filter(v => v > 0).length;
  }
  if (mode === 'all') {
    return Object.values(rows).reduce((n, v) => n + (v || 0), 0);
  }
  return rows[mode] || 0;
}

// ── the three grids ─────────────────────────────────────────────────────────
// Each returns the cells, the peak to scale the heat against, and what to put
// under them as a ruler.

// The last twenty-four hours, hour by hour. Not "today": at one in the
// morning today is an empty strip, and the zoomed-in view is the one somebody
// opens to see whether anything is happening *now*. An hour is the smallest
// bucket the log keeps, so this is as far in as the zoom can travel.
function rhythmDayGrid(board) {
  const row = new Array(24).fill(0);
  const seen = Array.from({ length: 24 }, () => new Set());
  const down = new Array(24).fill(0);

  // the 24 hours ending with the one we are in, as local Dates
  const top = new Date();
  top.setMinutes(0, 0, 0);
  const slots = [];
  for (let i = 23; i >= 0; i -= 1) {
    slots.push(new Date(top.getTime() - i * 3600000));
  }
  const at = {};
  slots.forEach((when, i) => { at[when.getTime()] = i; });

  for (const [key, bucket] of Object.entries(board.hours || {})) {
    const when = rhythmHour(key);
    if (!when) continue;
    const i = at[when.getTime()];
    if (i === undefined) continue;
    row[i] += rhythmValue(bucket, rhythmMode);
    down[i] += (bucket && bucket.down) || 0;
    for (const name of Object.keys((bucket && bucket.who) || {})) seen[i].add(name);
  }

  const peak = Math.max(...row, 0);
  const cells = `<div class="rh-row">${row.map((value, i) => `
    <span class="rh-cell" style="--heat:${rhythmHeat(value, peak).toFixed(3)};${
      rhythmDownAttr(down[i], 3600)}"
      data-t="${rhythmClock(slots[i].getHours())}${
        slots[i].getDate() === top.getDate() ? '' : ' yesterday'} · ${
        rhythmReading(value, seen[i])}${rhythmDownSay(down[i])}"
      onmouseenter="rhythmSay(this)" onmouseleave="rhythmSay(null)"></span>`).join('')}</div>`;

  // clock labels at the ends and the middle, since the columns are a rolling
  // window rather than a fixed midnight-to-midnight day
  const marks = [[0, 0], [8, 33.3], [16, 66.6]].map(([i, left]) =>
    `<i style="left:${left}%">${rhythmClock(slots[i].getHours())}</i>`).join('')
    + '<i style="right:0">now</i>';
  return { cells, peak, worst: Math.max(...down, 0), marks,
           empty: 'nothing played in the last day' };
}

// The week as a habit: every Tuesday 8pm that has ever been recorded, in one
// square. This is the view the whole feature was built for.
function rhythmWeekGrid(board) {
  const { grid, seen, down, span } = rhythmGrid(board.hours, rhythmMode);
  const peak = Math.max(...grid.flat(), 0);
  const cells = grid.map((row, day) => `
    <div class="rh-row">
      <i class="rh-day">${DAYS[day][0]}</i>
      ${row.map((value, hour) => `<span class="rh-cell"
          style="--heat:${rhythmHeat(value, peak).toFixed(3)};${
            rhythmDownAttr(down[day][hour], span[day][hour])}"
          data-t="${DAYS[day]} ${rhythmClock(hour)} · ${
            rhythmReading(value, seen[day][hour])}${
            rhythmDownSay(down[day][hour])}"
          onmouseenter="rhythmSay(this)" onmouseleave="rhythmSay(null)"
          ></span>`).join('')}
    </div>`).join('');
  // a grid where the only thing that happened was an outage still has
  // something to draw, so the peak alone must not decide it is empty
  const worst = Math.max(...down.flat(), 0);
  return { cells, peak, worst, ruler: true, indent: true };
}

// A square per day, laid out as a calendar: weekday columns, weeks running
// down. Padded to whole weeks so the columns actually line up with a weekday
// rather than drifting by one every row.
function rhythmMonthGrid(board) {
  // six whole weeks. Sliced after padding rather than before, so the grid is
  // always six rows tall whichever weekday the window happens to start on -
  // a seventh row would make the panel taller than the week view beside it.
  const rows = (board.days || []).slice(-45);
  if (!rows.length) return { cells: '', peak: 0, empty: 'no days on record yet' };

  const cell = day => {
    const when = new Date(`${day.day}T00:00:00`);
    return { when, value: rhythmDayValue(day.who, rhythmMode),
             down: day.down || 0,
             names: new Set(Object.keys(day.who || {})), day };
  };
  const filled = rows.map(cell);
  const peak = Math.max(...filled.map(c => c.value), 0);

  // lead the first week with blanks so Sunday is always the first column
  const pad = filled[0].when.getDay();
  const slots = new Array(pad).fill(null).concat(filled);
  while (slots.length % 7) slots.push(null);

  const weeks = [];
  for (let i = 0; i < slots.length; i += 7) weeks.push(slots.slice(i, i + 7));
  while (weeks.length > 6) weeks.shift();

  const cells = weeks.map(week => `
    <div class="rh-row month">
      ${week.map(slot => slot === null
        ? '<span class="rh-cell blank"></span>'
        : `<span class="rh-cell"
             style="--heat:${rhythmHeat(slot.value, peak).toFixed(3)};${
               rhythmDownAttr(slot.down, 86400)}"
             data-t="${rhythmDate(slot.day.day)} · ${
               rhythmReading(slot.value, slot.names)}${rhythmDownSay(slot.down)}"
             onmouseenter="rhythmSay(this)" onmouseleave="rhythmSay(null)"
             ></span>`).join('')}
    </div>`).join('');

  const ruler = `<div class="rh-ruler month">${
    DAYS.map(d => `<i>${d[0]}</i>`).join('')}</div>`;
  return { cells, peak, worst: Math.max(...filled.map(c => c.down), 0),
           days: ruler };
}

function rhythmDate(day) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day || '');
  if (!m) return day || '';
  const when = new Date(+m[1], +m[2] - 1, +m[3]);
  return `${DAYS[when.getDay()]} ${MONTHS[when.getMonth()]} ${when.getDate()}`;
}

function rhythmPanel(board) {
  const host = document.getElementById('ls-rhythm');
  if (!host) return;

  // a player picked and then never seen again in the window would leave the
  // grid stuck on an empty mode with no way back
  if (rhythmMode !== 'all' && rhythmMode !== 'together'
      && !(board.players || []).includes(rhythmMode)) {
    rhythmMode = 'all';
  }

  const drawn = rhythmScale === 'day' ? rhythmDayGrid(board)
    : rhythmScale === 'month' ? rhythmMonthGrid(board)
    : rhythmWeekGrid(board);

  const scales = `<span class="rh-zoom">${
    ['day', 'week', 'month'].map(key => `<button type="button"
      class="rh-z${rhythmScale === key ? ' on' : ''}"
      onclick="setRhythmScale('${key}')">${key}</button>`).join('')}</span>`;

  const names = board.players || [];
  const picker = `
    <div class="rh-pick">
      <button type="button" class="rh-tab${rhythmMode === 'all' ? ' on' : ''}"
              onclick="setRhythmMode('all')">everyone</button>
      <button type="button" class="rh-tab${rhythmMode === 'together' ? ' on' : ''}"
              onclick="setRhythmMode('together')">together</button>
      ${names.length ? `<select class="rh-who" onchange="setRhythmMode(this.value)">
        <option value="all">one player…</option>
        ${names.map(n => `<option value="${n}"${
          rhythmMode === n ? ' selected' : ''}>${n}</option>`).join('')}
      </select>` : ''}
    </div>`;

  const head = `
    <div class="rh-head">
      <b title="times shown in ${rhythmZone()}">ACTIVE HOURS</b>
      ${scales}
    </div>`;

  if (!drawn.peak && !drawn.worst) {
    host.innerHTML = `${head}${picker}
      <div class="rh-empty"><span>${drawn.empty
        || 'nothing recorded yet &mdash; the game keeps no history of when it was'
           + ' played, so this fills in from here'}</span></div>
      ${rhythmTotals(board.periods)}`;
    return;
  }

  // hours across the bottom for the two hourly scales, weekday letters for the
  // calendar; the week grid indents its ruler past the column of day letters
  const ruler = drawn.days ? drawn.days : `
    <div class="rh-ruler">${drawn.indent ? '<i class="rh-day"></i>' : ''}
      <span class="rh-ticks">${drawn.marks || [0, 6, 12, 18].map(h =>
        `<i style="left:${(h / 24) * 100}%">${rhythmClock(h)}</i>`).join('')}</span>
    </div>`;

  host.innerHTML = `${head}${picker}
    <div class="rh-grid ${rhythmScale}">
      ${drawn.cells}
      ${ruler}
    </div>
    <div class="rh-read" id="rh-read">${rhythmPeakOf(drawn)}</div>
    ${rhythmTotals(board.periods)}`;
}

// what the panel says with nothing hovered: the high-water mark of whatever
// is currently drawn, in that scale's own units
function rhythmPeakOf(drawn) {
  if (!drawn.peak) {
    return drawn.worst ? `server down ${rhythmSpan(drawn.worst)}` : '';
  }
  const what = rhythmMode === 'together'
    ? `${drawn.peak} player${drawn.peak === 1 ? '' : 's'} at once`
    : `${rhythmSpan(drawn.peak)} played`;
  // the day grid is a rolling twenty-four hours, not a calendar day, so it
  // does not get to say "today"
  const when = rhythmScale === 'day' ? 'busiest hour since yesterday'
    : rhythmScale === 'month' ? 'biggest day' : 'busiest hour';
  return `${when}: ${what}`;
}

function rhythmZone() {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    return zone ? zone.split('/').pop().replace(/_/g, ' ') : 'your time';
  } catch (e) { return 'your time'; }
}

function rhythmClock(hour) {
  return `${hour % 12 || 12}${hour < 12 ? 'am' : 'pm'}`;
}

// a cell's value in the units of whatever mode drew it
function rhythmReading(value, names) {
  if (rhythmMode === 'together') {
    const who = [...names].sort().join(', ');
    return `${value} player${value === 1 ? '' : 's'}${who ? ` · ${who}` : ''}`;
  }
  if (rhythmMode !== 'all') return rhythmSpan(value);
  const who = [...names].sort().join(', ');
  return `${rhythmSpan(value)}${who ? ` · ${who}` : ''}`;
}

// Day, week and month totals on one line. Deliberately three numbers rather
// than another chart: the bars that used to sit under this grid were the thing
// that made the panel clunky, and what anybody actually wants from them is
// whether this week is a big one. The record for each scale is behind its
// title, and the whole history is behind the endpoint.
function rhythmTotals(periods) {
  if (!periods) return '';
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const wanted = [
    ['today', 'day', `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`],
    ['week', 'week', rhythmIsoWeek(now)],
    ['month', 'month', `${now.getFullYear()}-${pad(now.getMonth() + 1)}`],
  ];

  const parts = wanted.map(([label, scale, key]) => {
    const rows = periods[scale] || [];
    const row = rows.find(r => r.key === key);
    const best = rows.reduce((a, b) => (!a || b.total > a.total ? b : a), null);
    // the record for this scale, so a quiet week reads as quiet against
    // something rather than as a number on its own
    const hint = best
      ? `best ${scale}: ${rhythmSpan(best.total)} (${best.key}) · ${
          rows.length} on record`
      : 'nothing on record yet';
    return `<span class="rh-tot" title="${hint}"><i>${label}</i><b>${
      rhythmSpan(row ? row.total : 0)}</b></span>`;
  }).join('');

  return `<div class="rh-totals">${parts}</div>`;
}

// The ISO week the log counts in, worked out the way Python's isocalendar
// does: the week that owns this week's Thursday.
function rhythmIsoWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const jan1 = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d - jan1) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

function rhythmSay(cell) {
  const read = document.getElementById('rh-read');
  if (!read) return;
  if (!cell) { read.textContent = read.dataset.rest || ''; return; }
  if (!read.dataset.rest) read.dataset.rest = read.textContent;
  read.textContent = cell.dataset.t;
}

async function loadRhythm() {
  if (rhythmBusy || rhythmBoard) return;
  rhythmBusy = true;
  try {
    const res = await fetch(ACTIVITY_URL, { headers: { 'X-Requested-With': 'fetch' } });
    if (!res.ok) throw new Error(res.status);
    rhythmBoard = await res.json();
    rhythmPanel(rhythmBoard);
  } catch (err) {
    const host = document.getElementById('ls-rhythm');
    if (host) host.innerHTML = '<div class="rh-empty"><b>ACTIVE HOURS</b>'
      + '<span>could not read the log</span></div>';
  } finally {
    rhythmBusy = false;
  }
}


function bootLive() {
  if (!document.getElementById('live-stage')) return;
  renderLive(liveBoard);
  liveTick();

  setInterval(() => {
    // a hidden tab is nobody watching, and polling one only burns the server's
    // ssh budget: the countdown holds until the tab comes back
    if (document.hidden) return;
    if (--liveDue <= 0) pollLive();
    // chat runs on the same second hand but its own countdown: it is polling a
    // local file rather than the game host, so it can afford to be six times
    // as eager as the board without costing the server anything
    if (--chatDue <= 0) pollChat();
    liveTick();
    tickCharts();
  }, 1000);

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) { pollLive(); pollChat(); }
  });
}

bootLive();
bootChat();
loadRhythm();

selectDisc(0);

// the model renderer is a module and so arrives after this file: once it is
// here, put the roster on
window.addEventListener('mcmodel-ready', () => {
  if (SEASONS.length) selectPlayer(playerIdx);
  if (liveBoard) mountLive(liveBoard);
});
