// Brightened from the brand colours so they read on black.
const SOCIAL_LINKS = [
  { label:'GitHub',   url:'https://github.com/melvinczyk',                          color:'#b07cff' },
  { label:'LinkedIn', url:'https://www.linkedin.com/in/nicholas-burczyk/',          color:'#4da3e8' },
  { label:'Spotify',  url:'https://open.spotify.com/artist/0uOm4SIBucaY6CHRlQoPBy', color:'#2ee06a' },
  { label:'Bandcamp', url:'https://zerobarbecue.bandcamp.com',                      color:'#35b8dd' },
];

// Every pictogram on the page, drawn rather than typed: the codec font has no
// arrows of its own and falls back to whatever the system offers.
const ICONS = {
  mark:   '<path d="M12 3l9 9-9 9-9-9z"/><path d="M12 9l3 3-3 3-3-3z" fill="currentColor"/>',
  ext:    '<path d="M7 17 17 7M9 7h8v8"/>',
  left:   '<path d="M15 5l-7 7 7 7"/>',
  right:  '<path d="M9 5l7 7-7 7"/>',
  reset:  '<path d="M4 12a8 8 0 1 0 3-6.2M4 4v5h5"/>',
  lock:   '<rect x="5" y="11" width="14" height="10"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  work:   '<rect x="3" y="7" width="18" height="13"/><path d="M9 7V4h6v3M3 13h18"/>',
  lab:    '<path d="M9 3h6M10 3v6L5 20h14L14 9V3M8 15h8"/>',
  school: '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11.5V16c3 2.5 9 2.5 12 0v-4.5"/>',
  learn:  '<rect x="6" y="6" width="12" height="12"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.5"/><path d="M12 1v5M12 18v5M1 12h5M18 12h5"/>',
  cube:   '<path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M3 7l9 5 9-5M12 12v10"/>',
  nodes:  '<circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 12h3M14 11l3.5-3.5M14 13l3.5 3.5"/>',
  tool:   '<rect x="3" y="4" width="18" height="16"/><path d="M7 9l3 3-3 3M12 15h5"/>',
  server: '<rect x="4" y="3" width="16" height="7"/><rect x="4" y="14" width="16" height="7"/><path d="M8 6.5h2M8 17.5h2"/>',
  globe:  '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/>',
};
const icon = (name, size = 18) =>
  `<svg class="ic" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square" aria-hidden="true">${ICONS[name]}</svg>`;

// The profile at 140.85: where he works, then what he is into.
const BIO_POSTS = [
  ['work',   'Viper Imaging',        'Software developer, AI integration'],
  ['lab',    'Sandia National Labs', 'Part time'],
  ['school', 'UAB',                  'MS in AI, Spring 2027'],
];
const BIO_TRACKS = [
  ['learn',  'LEARNING',  ['Dockerized deployable software', 'Linux hosting', 'Agentic AI integration']],
  ['target', 'INTERESTS', ['Distributed systems', 'Networking', 'AI integration', 'Docker']],
];

// What kind of thing each project is. The kind gives a project its colour, so
// the grid reads by kind at a glance instead of as one wall of green.
const KINDS = {
  'HARDWARE':       { color:'#ff9f43', icon:'learn' },
  'AI / ML':        { color:'#b48cff', icon:'nodes' },
  'TOOLS':          { color:'#ff6f91', icon:'tool' },
  'INFRASTRUCTURE': { color:'#ffd84d', icon:'server' },
  'MINECRAFT':      { color:'#59c2ff', icon:'cube' },
  'WEB':            { color:'#63e690', icon:'globe' },
};
const GH = 'https://github.com/melvinczyk/';
const IMG = name => `${STATIC_URLS.projImg}/${name}`;

// One record per project. `sum` says what it is in one sentence; `note` is the
// one thing worth knowing beyond that. `ask` is Snake's question and `tell`
// Otacon's answer, kept short; their clips are sk_<voice>.m4a and
// ot_<voice>_<n>.m4a (tools/generate_codec_voices.py), `voice` defaulting to
// the id. A project with no `link` is ours and stays unlinked.
const PROJECTS = [
  { id:'oculosaurus', name:'OCULOSAURUS', kind:'HARDWARE', status:'1ST PLACE',
    tech:'Python / OpenCV / Raspberry Pi / YOLO', link:GH+'StereoCamera-DepthObjectEstimator',
    img:IMG('oculosaurus_example.webp'), img2:IMG('oculosaurus_point_cloud.webp'), thumb:'img2',
    sum:'Stereo-camera goggles that warn visually impaired users about obstacles.',
    note:'First place at the senior capstone competition.',
    ask:"Oculosaurus. What am I looking at?",
    tell:["Goggles for the visually impaired. Two cameras judge depth the way your eyes do.",
          "When something gets close, a phone alert warns you. It took first place."] },
  { id:'gvoice', name:'GVOICE', kind:'AI / ML', also:['TOOLS'], status:'IN DEV',
    tech:'Python / FastAPI / Docker / Kokoro TTS / RVC', link:GH+'GVoice',
    sum:'A speech server that reads Minecraft chat aloud in AI voices.',
    note:'Each player picks from about 18,000 voices.',
    ask:"GVoice. What does it do?",
    tell:["It reads Minecraft chat out loud. Every player gets their own voice.",
          "There are eighteen thousand to choose from. It all runs in one Docker container."] },
  { id:'albumdl', name:'ALBUMDL', kind:'TOOLS', status:'LIVE',
    tech:'Python / FastAPI / yt-dlp / MusicBrainz / Docker', link:GH+'AlbumDL',
    img:GH+'AlbumDL/raw/master/docs/banner.gif',
    sum:'A self-hosted app that downloads whole albums as tagged MP3s.',
    note:'Covers, tags and lyrics are filled in automatically.',
    ask:"AlbumDL. What's this one for?",
    tell:["It downloads whole albums. Covers, tags and lyrics are filled in for you.",
          "It runs on his home server. That's where his music library lives."] },
  { id:'echo-scout', name:'ECHO SCOUT', kind:'HARDWARE',
    tech:'C++ / ESP32-S3 / mmWave radar / ToF', link:GH+'Echo-Scout',
    img:IMG('echo_scout_logo.gif'), pixel:true,
    sum:'A handheld scanner that finds people with radar and maps rooms in 3D.',
    ask:"Echo Scout. What does it pick up?",
    tell:["People. Its radar can find someone in the dark.",
          "A depth sensor maps the room in 3D at the same time."] },
  { id:'memprobe', name:'MEMPROBE', kind:'TOOLS', status:'IN DEV',
    tech:'Python / pyelftools / ELF + DWARF', link:GH+'memprobe/tree/master',
    sum:'Shows exactly where a firmware build spends its flash and RAM.',
    note:'Fails CI when firmware outgrows its size budget.',
    ask:"Memprobe. Break it down for me.",
    tell:["It reads compiled firmware and shows where every byte of memory goes.",
          "If a build grows too big, it stops it before it ships."] },
  { id:'homelab', name:'HOMELAB', kind:'INFRASTRUCTURE', status:'LIVE', noRepo:true,
    tech:'Ubuntu Server / Docker / Pi-hole / Jellyfin / Tailscale',
    sum:'A Dell OptiPlex 7080 rebuilt as my Ubuntu home server and router.',
    note:'Runs Pi-hole, Jellyfin, Tailscale, the music library and AlbumDL.',
    ask:"A homelab. What's he running?",
    tell:["An old office PC, rebuilt as a Linux server. It routes the whole house.",
          "It blocks ads, streams his media, and keeps the music library."] },
  { id:'song2vec', name:'SONG2VEC', kind:'AI / ML',
    tech:'Python / PyTorch / VAE / PCA', link:GH+'Song2Vec',
    img:GH+'Song2Vec/raw/main/outputs/multi_blobs.png',
    img2:GH+'Song2Vec/raw/main/outputs/comparisons/latent_path_Bossa_Antigua_to_Player_One.png',
    sum:'Maps songs by how they sound, then paints each one as a colour blob.',
    ask:"Song2Vec. What's the science here?",
    tell:["It places every song on a map. Songs that feel alike land close together.",
          "Then it paints each one as a blob of colour."] },
  { id:'modpack-updater', name:'GROIDPACK UPDATER', kind:'MINECRAFT', also:['TOOLS'], status:'LIVE',
    tech:'Java 17 / Swing / Backblaze B2', link:GH+'ModpackUpdater',
    img:IMG('groidpack_updater_logo.gif'), pixel:true,
    sum:"A desktop app that keeps every player's modpack matched to the server.",
    note:'Worlds, screenshots and settings are never touched.',
    ask:"GroidPack Updater. What's it do?",
    tell:["It keeps everyone's mods matched to the server. One click and you're current.",
          "Your worlds and settings are never touched."] },
  { id:'groidberbium', name:'GROIDBERBIUM', kind:'MINECRAFT', status:'IN DEV',
    tech:'Java / Minecraft Forge 1.20.1 / OpenGL', link:GH+'Groidberbium',
    img:IMG('groidberbium_logo.gif'), pixel:true,
    sum:'My fork of the Emberbium renderer that makes heavy modpacks run faster.',
    note:'About 30% more FPS on average.',
    ask:"Groidberbium. Sounds unstable.",
    tell:["It's actually very stable. It makes Minecraft draw faster.",
          "With two hundred forty mods, a MacBook Air still runs at two hundred fifty frames per second."] },
  { id:'personal-website', name:'NICHOLASBURCZYK.COM', kind:'WEB', status:'LIVE',
    tech:'Django / Qwen3-TTS / Modal / Web Audio', link:GH+'Personal-Website',
    img:IMG('site_icon.png'), pixel:true,
    sum:'This site: a codec screen with AI-cloned character voices.',
    ask:"His personal site. Anything to it?",
    tell:["You're inside it right now. My voice was cloned with AI.",
          "Even my mouth moves with the audio."] },
  { id:'bird-classifier', name:'BACKYARD BIRD CLASSIFIER', kind:'AI / ML', status:'LIVE',
    tech:'Python / CNN / Django', link:GH+'Bird-Classifier',
    img:'https://statesymbolsusa.org/sites/default/files/primary-images/NorthernFlickerMaleALbirdsymbol.jpg',
    img2:GH+'Bird-classifier/blob/main/final_matrix.png?raw=true',
    sum:'Names 30 Alabama bird species from a recording of their call.',
    ask:"Backyard Bird Classifier. Explain.",
    tell:["Play it a bird call and it names the species.",
          "It knows thirty Alabama birds. You can try it below."] },
  { id:'waste-drone', name:'WASTE DETECTION DRONE', kind:'HARDWARE', also:['AI / ML'],
    tech:'Python / YOLOv5 / Tello SDK', link:GH+'Waste-detection-drone',
    img:GH+'Waste-detection-drone/raw/main/images/Medium%20model%20frame.png',
    img2:GH+'Waste-detection-drone/raw/main/images/model_.gif',
    sum:'A drone that flies itself and spots litter from the air.',
    ask:"Waste Detection Drone. Give me the specs.",
    tell:["A small drone that flies itself and looks for trash.",
          "A vision model marks every piece it finds."] },
  { id:'minecraft-server', name:'MINECRAFT SERVER', kind:'MINECRAFT', status:'LIVE',
    tech:'Java / Python / Linux', link:GH+'Datapacks',
    img:IMG('minecraft_server_logo.webp'), pixel:true,
    sum:'My private server and custom modpack, now in its fifth season.',
    ask:"The Minecraft server. That's infrastructure.",
    tell:["A private world with its own modpack. Five seasons so far.",
          "The portal shows who's online right now."] },
];
const NUM_WORDS = ['Zero','One','Two','Three','Four','Five','Six','Seven','Eight','Nine','Ten','Eleven','Twelve',
                   'Thirteen','Fourteen','Fifteen','Sixteen','Seventeen','Eighteen','Nineteen','Twenty'];

let audioCtx = null;
let hoverBuffer = null, clickBuffer = null, bgMusic = null, bgMusicSource = null;

function getAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

// Mute: one master gain feeds every Web Audio source; the codec voice is a
// separate <audio> element muted directly. State persists.
let cxMuted = localStorage.getItem('cxMuted') === '1';
let cxMasterGain = null;
function getMasterGain() {
  const ctx = getAudioCtx();
  if (!cxMasterGain) {
    cxMasterGain = ctx.createGain();
    cxMasterGain.gain.value = cxMuted ? 0 : 1;
    cxMasterGain.connect(ctx.destination);
  }
  return cxMasterGain;
}
function cxSetMuted(m) {
  cxMuted = m;
  try { localStorage.setItem('cxMuted', m ? '1' : '0'); } catch (e) {}
  if (cxMasterGain) cxMasterGain.gain.value = m ? 0 : 1;
  if (typeof cxVoiceEl !== 'undefined' && cxVoiceEl) cxVoiceEl.muted = m;
  updateMuteBtn();
}
function cxToggleMute() { cxSetMuted(!cxMuted); }
const CX_ICON_SOUND = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a4 4 0 0 1 0 7"/><path d="M19.5 6a8 8 0 0 1 0 12"/></svg>';
const CX_ICON_MUTED = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9v6h4l5 4V5L8 9H4z"/><line x1="16" y1="9.5" x2="22" y2="15.5"/><line x1="22" y1="9.5" x2="16" y2="15.5"/></svg>';
function updateMuteBtn() {
  const b = document.getElementById('cx-mute');
  if (!b) return;
  b.classList.toggle('muted', cxMuted);
  b.setAttribute('aria-label', cxMuted ? 'Unmute' : 'Mute');
  b.title = cxMuted ? 'Unmute' : 'Mute';
  b.innerHTML = cxMuted ? CX_ICON_MUTED : CX_ICON_SOUND;
}
function initMuteButton() {
  let b = document.getElementById('cx-mute');
  if (!b) {
    b = document.createElement('button');
    b.id = 'cx-mute';
    b.className = 'cx-mute';
    (document.body || document.documentElement).appendChild(b);
  }
  b.onclick = (e) => { e.stopPropagation(); cxToggleMute(); };
  updateMuteBtn();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initMuteButton);
else initMuteButton();

// Where a clip's sound actually begins.
//
// These files carry digital silence in front of them - click.mp3 is dead for
// its first eighty milliseconds - and playing one from zero puts the sound
// that long after the press. It reads as lag, and it is not: it is a quiet
// file being played faithfully. The offset is measured rather than typed in,
// so replacing an mp3 needs no sums doing again.
//
// Two starts are worked out and the honest one is chosen. The first is where
// the silence ends. The second walks BACK from the loudest moment, which is
// what a clip needs when it opens with a stray blip, goes quiet, and only
// then makes its noise - the Minecraft click does exactly that, ticking once
// at 539ms and clicking at 609ms, and the end of its silence is the tick.
//
// The backward one is only trusted when it looks like that case: a first
// sound close in front of the real one, with the level dropping back to
// silence in between. Without that guard it eats the beginning of anything
// whose peak arrives late - the ring swells for half a second before its
// loudest point, and a rule that always walked back would throw the swell
// away and start on the crest.
const SOUND_START = new WeakMap();
const BLIP_MS = 120;               // how far in front of the sound a false start may sit

function soundStart(buffer) {
  const d = buffer.getChannelData(0);
  const rate = buffer.sampleRate;
  // A millisecond at a time: a waveform crosses zero many times inside its own
  // attack, so sample-by-sample reading would call the first crossing the
  // start. The envelope is what a listener actually hears rising.
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
  // back off a few milliseconds so the attack itself is not clipped
  return Math.max(0, (start * win / rate) - 0.006);
}

async function loadSound(url) {
  try {
    const ctx = getAudioCtx();
    const res = await fetch(url);
    const arr = await res.arrayBuffer();
    const buf = await ctx.decodeAudioData(arr);
    // measured once, here, rather than on every press
    if (buf) SOUND_START.set(buf, soundStart(buf));
    return buf;
  } catch(e) { console.warn('Sound load failed:', url, e); return null; }
}

function playBuffer(buffer, volume=0.3) {
  if (!buffer) return;
  const ctx = getAudioCtx();
  const fire = () => {
    const src = ctx.createBufferSource();
    const gain = ctx.createGain();
    gain.gain.value = volume;
    src.buffer = buffer;
    src.connect(gain);
    gain.connect(getMasterGain());
    src.start(0, SOUND_START.get(buffer) || 0);
  };
  // resume() hands back a promise even when the context is already running,
  // and waiting on it costs the one press that can least afford it
  if (ctx.state === 'running') fire(); else ctx.resume().then(fire);
}

function playBackgroundMusic() {
  if (!bgMusic || bgMusicSource) return;
  const ctx = getAudioCtx();
  ctx.resume().then(() => {
    bgMusicSource = ctx.createBufferSource();
    const gain = ctx.createGain();
    bgMusicSource.buffer = bgMusic;
    bgMusicSource.loop = true;
    gain.gain.value = 0.15;
    bgMusicSource.connect(gain);
    gain.connect(getMasterGain());
    bgMusicSource.start(0);
  });
}

function playHoverBeep()  { playBuffer(hoverBuffer, 0.3); }
function playClickSound() { playBuffer(clickBuffer, 0.4); }

// mouseenter also fires on the document itself, which has no closest()
document.addEventListener('mouseenter', e => {
  if (e.target.closest && e.target.closest('button, a')) playHoverBeep();
}, true);
document.addEventListener('click', e => {
  const target = e.target.closest('button, a');
  if (target && target.id !== 'codec-btn') {
    playClickSound();
    const btn = e.target.closest('button');
    if (btn) {
      btn.classList.add('btn-flash');
      setTimeout(() => btn.classList.remove('btn-flash'), 350);
    }
  }
}, true);

async function enterSite() {
  const btn    = document.getElementById('codec-btn');
  const codec  = document.getElementById('codec-screen');
  const screen = document.getElementById('screen');

  btn.disabled = true;
  try { sessionStorage.setItem('cxEntered', '1'); } catch (e) {}
  cxUnlockVoice();   // prime the voice element while we're in a user gesture
  codec.classList.add('codec-entering');

  // everything is fetched at once; only the ring has to land before it plays.
  // The music is the one large file, so the codec opens without waiting on it
  // and the track starts whenever it arrives.
  loadSound(STATIC_URLS.menu).then(buf => {
    bgMusic = buf;
    if (screen.classList.contains('visible')) playBackgroundMusic();
  });
  const rest = Promise.all(['hover', 'click', 'open'].map(k => loadSound(STATIC_URLS[k])));
  playBuffer(await loadSound(STATIC_URLS.ring), 0.8);
  let openBuffer;
  [hoverBuffer, clickBuffer, openBuffer] = await rest;

  setTimeout(() => {
    codec.classList.add('fade-out');
    playBuffer(openBuffer, 0.7);
    // on a clock rather than on animationend: a browser that throttles or
    // skips the fade must not leave the visitor parked on the call screen
    setTimeout(() => {
      codec.style.display = 'none';
      screen.classList.add('visible', 'crt-open');
      setTimeout(playBackgroundMusic, 300);
      initCodec();
    }, 800);
  }, 1800);
}

// ── the content panel under the codec ──────────────────────────────────────
const out = document.getElementById('output');
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
// LIVE and IN DEV say whether it runs today; an award outranks both.
const statusHtml = st => st
  ? `<span class="pj-status ${st === 'LIVE' ? 'live' : st === 'IN DEV' ? 'dev' : 'award'}">${esc(st)}</span>` : '';
// `kind` sets the colour and icon; `also` lists any other kinds it counts as.
const kindsOf = p => [p.kind, ...(p.also || [])];
const kindStyle = p => `--accent:${KINDS[p.kind].color}`;
const chipsHtml = items => `<div class="chips">${items.map(c => `<span>${esc(c)}</span>`).join('')}</div>`;
const REDUCED_MOTION = matchMedia('(prefers-reduced-motion: reduce)').matches;

// Swap what the panel shows. Where the browser can, the old view morphs into
// the new one: the element named pj-hero on each side is the same object.
function cxShow(html, after, morph){
  const swap = () => { out.innerHTML = html; cxDecodeAll(); if (after) after(); };
  if (morph !== 'slide') delete document.documentElement.dataset.dir;
  if (morph && document.startViewTransition && !REDUCED_MOTION) {
    // a transition cut short by the next one (fast tuning) is expected, not an error
    const vt = document.startViewTransition(swap);
    [vt.ready, vt.finished, vt.updateCallbackDone].forEach(p => p.catch(() => {}));
  } else swap();
}

// Text that resolves out of noise, left to right, the way the codec tunes in.
function cxDecodeAll(){
  if (REDUCED_MOTION) return;
  const glyphs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%/';
  out.querySelectorAll('[data-decode]').forEach(el => {
    const final = el.textContent;
    let n = 0;
    const t = setInterval(() => {
      if (!el.isConnected || ++n >= final.length) { clearInterval(t); el.textContent = final; return; }
      el.textContent = final.replace(/\S/g, (c, i) => i < n ? c : glyphs[Math.random() * glyphs.length | 0]);
    }, 30);
  });
}

function aboutHtml(){
  return `<section class="ps-panel dossier">
    <div class="ps-bar"><span class="ps-t">${icon('mark')}PROFILE</span><span class="ps-r">140.85</span></div>
    <div class="dos-id">
      <div class="dos-badge" aria-hidden="true"><img src="${IMG('site_icon.png')}" alt=""></div>
      <div>
        <div class="dos-name" data-decode>NICK BURCZYK</div>
        <div class="dos-role">SOFTWARE DEVELOPER / AI INTEGRATION ENGINEER</div>
      </div>
    </div>
    <div class="dos-posts">${BIO_POSTS.map(([ic, head, where], i) => `<div class="dos-post" style="--i:${i}">
      ${icon(ic, 26)}<div><b>${esc(head)}</b><span>${esc(where)}</span></div>
    </div>`).join('')}</div>
    <div class="dos-tracks">${BIO_TRACKS.map(([ic, label, items], i) => `<div class="dos-track" style="--i:${i + BIO_POSTS.length}">
      <h4>${icon(ic, 16)}${label}</h4>${chipsHtml(items)}
    </div>`).join('')}</div>
    <div class="dos-links" style="--i:${BIO_POSTS.length + BIO_TRACKS.length}">${SOCIAL_LINKS.map(l =>
      `<a href="${l.url}" target="_blank" rel="noopener" style="--lc:${l.color}">${l.label}${icon('ext', 15)}</a>`).join('')}</div>
  </section>`;
}

function musicHtml(){
  return `<section class="ps-panel">
    <div class="ps-bar"><span class="ps-t">${icon('mark')}ZERO BARBECUE</span><span class="ps-r">141.52</span></div>
    <div class="ps-body">
      <div class="ps-frame"><iframe src="https://open.spotify.com/embed/album/0i6OlE6MZoOlEIAwWcI5aL?utm_source=generator&theme=0" height="200" allowfullscreen allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy" title="Zero Barbecue on Spotify"></iframe></div>
      <div class="ps-btnrow">
        <a class="ps-btn ps-sm ps-alt" href="https://open.spotify.com/artist/0uOm4SIBucaY6CHRlQoPBy" target="_blank" rel="noopener"><span class="ps-lbl">SPOTIFY</span></a>
        <a class="ps-btn ps-sm ps-alt" href="https://zerobarbecue.bandcamp.com" target="_blank" rel="noopener"><span class="ps-lbl">BANDCAMP</span></a>
      </div>
    </div>
  </section>`;
}

// ── projects: a grid of records, each opening into its own file ────────────
const projectById = id => PROJECTS.find(p => p.id === id);

function projectsHtml(heroId){
  const filters = ['ALL', ...Object.keys(KINDS).filter(k => PROJECTS.some(p => kindsOf(p).includes(k)))];
  return `<section class="ps-panel">
    <div class="ps-bar"><span class="ps-t">${icon('mark')}PROJECTS</span><span class="ps-r" id="pj-count">${PROJECTS.length} SHOWN</span></div>
    <div class="ps-body">
      <div class="pj-filter">${filters.map((f, i) =>
        `<button class="tag${i ? '' : ' on'}" aria-pressed="${i ? 'false' : 'true'}" style="${i ? `--accent:${KINDS[f].color}` : ''}" onclick="cxFilterProjects(this)">${esc(f)}</button>`).join('')}</div>
      <div class="pj-grid">${PROJECTS.map((p, i) => {
        const shot = p[p.thumb || 'img'];
        return `<button class="pj-tile${p.pixel ? ' pixel' : ''}" data-kind="${esc(kindsOf(p).join('|'))}" onclick="cxOpenProject('${p.id}', this)"
            style="--i:${i};${kindStyle(p)}${p.id === heroId ? ';view-transition-name:pj-hero' : ''}">
          <span class="pj-art${shot ? '' : ' pj-sig'}">${shot ? `<img class="pj-shot" src="${shot}" alt="" loading="lazy" onerror="this.parentElement.classList.add('pj-sig');this.remove()">` : ''}${icon(KINDS[p.kind].icon, 44)}<span class="pj-file">${String(i + 1).padStart(2, '0')}</span><i class="pj-sweep"></i></span>
          <span class="pj-kind">${esc(kindsOf(p).join(' · '))}</span>
          <span class="pj-name">${esc(p.name)}</span>
          <span class="pj-sum">${esc(p.sum)}</span>
          ${statusHtml(p.status)}
        </button>`;
      }).join('')}</div>
    </div>
  </section>`;
}

out.addEventListener('pointermove', e => {
  const t = e.target.closest('.pj-tile, .dos-post');
  if (!t) return;
  const r = t.getBoundingClientRect();
  t.style.setProperty('--mx', (e.clientX - r.left) + 'px');
  t.style.setProperty('--my', (e.clientY - r.top) + 'px');
  if (t.classList.contains('pj-tile') && !REDUCED_MOTION) {
    t.style.setProperty('--ry', (((e.clientX - r.left) / r.width) - 0.5) * 7 + 'deg');
    t.style.setProperty('--rx', (0.5 - ((e.clientY - r.top) / r.height)) * 7 + 'deg');
  }
});
out.addEventListener('pointerout', e => {
  const t = e.target.closest('.pj-tile');
  if (t && !t.contains(e.relatedTarget)) { t.style.removeProperty('--rx'); t.style.removeProperty('--ry'); }
});

// Every few seconds one record catches interference, so the grid never sits
// dead even when nobody is touching it.
setInterval(() => {
  if (REDUCED_MOTION || document.hidden) return;
  const tiles = [...out.querySelectorAll('.pj-tile:not([hidden]):not(:hover)')];
  if (!tiles.length) return;
  const t = tiles[Math.floor(Math.random() * tiles.length)];
  t.classList.remove('glitch'); void t.offsetWidth; t.classList.add('glitch');
  setTimeout(() => t.classList.remove('glitch'), 600);
}, 2600);

function cxFilterProjects(btn){
  const tag = btn.textContent;
  btn.parentElement.querySelectorAll('.on').forEach(b => { b.classList.remove('on'); b.setAttribute('aria-pressed', 'false'); });
  btn.classList.add('on');
  btn.setAttribute('aria-pressed', 'true');
  let shown = 0;
  out.querySelectorAll('.pj-tile').forEach(t => {
    t.hidden = tag !== 'ALL' && !t.dataset.kind.split('|').includes(tag);
    if (t.hidden) return;
    // replay the entrance so the survivors close ranks instead of jumping
    t.style.setProperty('--i', shown++);
    t.style.animation = 'none'; void t.offsetWidth; t.style.animation = '';
  });
  const count = document.getElementById('pj-count');
  if (count) count.textContent = `${shown} SHOWN`;
}

// What a project card carries besides its description.
const PROJECT_DEMOS = {
  'bird-classifier':  { html: () => `<div class="proj-demo">${psBirdPanel()}</div>` },
  'minecraft-server': { html: () => `<div class="proj-demo">${psPortalPanel()}</div>`, after: () => psFillFaces() },
};

function projectHtml(p){
  const i = PROJECTS.indexOf(p), n = PROJECTS.length;
  const prev = PROJECTS[(i + n - 1) % n], next = PROJECTS[(i + 1) % n];
  const shots = [p.img, p.img2].filter(Boolean);
  const demo = PROJECT_DEMOS[p.id];
  return `<article class="ps-panel proj-card" style="${kindStyle(p)}">
    <div class="ps-bar">
      <button class="pj-back" onclick="cxBackToProjects('${p.id}')">${icon('left', 14)}RECORDS</button>
      <span class="ps-t" data-decode>${esc(p.name)}</span>
      <span class="ps-r">${String(i + 1).padStart(2, '0')} / ${n}</span>
    </div>
    <div class="proj-body">
      ${shots.length ? `<div class="proj-media${p.pixel ? ' pixel' : ''}">
        <img class="proj-main" src="${shots[0]}" alt="${esc(p.name)}" onerror="this.closest('.proj-media').remove()">
        ${shots.length > 1 ? `<div class="proj-strip">${shots.map((s, k) =>
          `<button class="${k ? '' : 'on'}" onclick="cxSwapShot(this)" aria-label="Image ${k + 1}"><img src="${s}" alt="" loading="lazy" onerror="this.parentElement.remove()"></button>`).join('')}</div>` : ''}
      </div>` : ''}
      <div class="proj-info">
        <div class="proj-kind">${icon(KINDS[p.kind].icon, 16)}${esc(kindsOf(p).join(' · '))}${statusHtml(p.status)}</div>
        <p class="proj-sum">${esc(p.sum)}</p>
        ${p.note ? `<p class="proj-note">${esc(p.note)}</p>` : ''}
        ${chipsHtml(p.tech.split(' / '))}
        ${p.link
          ? `<a class="ps-btn ps-sm" href="${p.link}" target="_blank" rel="noopener"><span class="ps-lbl">VIEW ON GITHUB${icon('ext', 17)}</span></a>`
          : p.noRepo ? '' : `<div class="proj-private">${icon('lock', 15)}PRIVATE REPOSITORY</div>`}
      </div>
    </div>
    ${demo ? demo.html() : ''}
    <div class="pj-nav">
      <button onclick="cxOpenProject('${prev.id}')">${icon('left', 14)}<span>${esc(prev.name)}</span></button>
      <button onclick="cxOpenProject('${next.id}')"><span>${esc(next.name)}</span>${icon('right', 14)}</button>
    </div>
  </article>`;
}

function cxSwapShot(btn){
  btn.parentElement.querySelectorAll('.on').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  const main = btn.closest('.proj-media').querySelector('.proj-main');
  main.classList.remove('swap'); void main.offsetWidth; main.classList.add('swap');
  main.src = btn.firstElementChild.src;
}

// Snake asks, Otacon explains, and the card opens out of the tile that was
// clicked.
function cxOpenProject(id, tile){
  const p = projectById(id);
  if (!p) return;
  // the tile the visitor came back to still carries the name; only one may
  if (tile) {
    out.querySelectorAll('.pj-tile').forEach(t => t.style.viewTransitionName = '');
    tile.style.viewTransitionName = 'pj-hero';
  }
  const demo = PROJECT_DEMOS[id];
  cxShow(projectHtml(p), demo && demo.after, true);
  document.getElementById('cx-content').scrollIntoView({ behavior: 'smooth', block: 'start' });
  // Otacon holds the left portrait even if a project was clicked before the
  // intro handed off to him
  cxProjectsIntroDone = true;
  cxSetPortrait('otacon');
  const voice = p.voice || p.id;
  cxSay([{ text: p.ask, speaker: 'snake', key: `sk_${p.askVoice || voice}` },
         ...p.tell.map((text, n) => ({ text, speaker: 'otacon', key: `ot_${voice}_${n}` }))]);
}
function cxBackToProjects(heroId){
  cxHardStop();
  cxShow(projectsHtml(heroId), null, true);
}

// ── the Minecraft portal and bird classifier panels ────────────────────────
function psPortalPanel(){
  const mc = STATIC_URLS.mc, url = STATIC_URLS.minecraft;
  const stats = [[mc.seasons, 'SEASONS'], [mc.shots, 'SCREENSHOTS'], [mc.clips, 'CLIPS'], [mc.span, 'UPTIME']];
  return `<section class="ps-panel ps-portal">
    <div class="ps-bar"><span class="ps-t">${icon('mark')}MINECRAFT SERVER</span><span class="ps-r"><span class="ps-live"></span>SEASON ${mc.seasons}</span></div>
    <div class="ps-body">
      <div class="ps-stats">${stats.map(([v, k], i) => `<div style="--i:${i}"><b>${v}</b><i>${k}</i></div>`).join('')}</div>
      <div class="ps-thumbs">${mc.thumbs.map((t, i) =>
        `<a href="${url}" data-s="SEASON ${t.s}" style="--i:${i}"><img src="${t.url}" alt="Season ${t.s} screenshot" loading="lazy" onerror="this.parentElement.remove()"></a>`).join('')}
        <a href="${url}" class="ps-more" style="--i:${mc.thumbs.length}"><span>+${Math.max(0, mc.shots - mc.thumbs.length)}<br>MORE</span></a>
      </div>
      <div class="ps-faces" id="ps-faces"><span class="ps-face-none">reading the server...</span></div>
      <div class="ps-frame ps-map" id="ps-map" hidden></div>
      <a class="ps-btn" href="${url}"><span class="ps-lbl">OPEN THE PORTAL</span></a>
      <div class="ps-hint">the live map, the full roster and every boss still standing are inside</div>
    </div>
  </section>`;
}

// The panel is drawn the moment the channel opens; who is on the server has to
// be asked for. Everyone tracked gets a face, the ones online lit and the rest
// dimmed, so an empty server still shows a crew - and a failed fetch says so
// rather than leaving "reading the server" up for good.
//
// The same answer says whether the live map is there to be framed. It is only
// drawn when it is: a map that is down, or one served over plain http to an
// https page (which the browser refuses to frame), is an empty black box.
async function psFillFaces(){
  const row = document.getElementById('ps-faces');
  if (!row) return;
  try {
    const board = await (await fetch(STATIC_URLS.live)).json();
    const map = document.getElementById('ps-map'), src = STATIC_URLS.mc.map;
    if (map && src && (board.map_probe || {}).ok && !(location.protocol === 'https:' && src.startsWith('http:'))) {
      map.innerHTML = `<iframe src="${src}" loading="lazy" title="Live world map"></iframe>`;
      map.hidden = false;
    }
    const players = (board.players || []).slice().sort((a, b) => !!b.online - !!a.online);
    if (!players.length) throw new Error('nobody on file');
    const on = players.filter(p => p.online).length;
    row.innerHTML = `<span class="ps-faces-t">${on} OF ${players.length} ONLINE</span>` +
      players.map(p => `<span class="ps-face${p.online ? ' on' : ''}" title="${esc(p.name)}">
        <i${p.skin ? ` style="background-image:url('${esc(p.skin)}')"` : ''}></i>
        <b>${esc(p.name)}</b>
      </span>`).join('');
  } catch (err) {
    row.innerHTML = '<span class="ps-face-none">roster unavailable</span>';
  }
}

function psBirdPanel(){
  const u = STATIC_URLS.uploadFile;
  const rows = [['NORTHERN FLICKER', 94], ['RED-BELLIED WOODPKR', 31], ['PILEATED WOODPECKER', 18],
                ['BLUE JAY', 9], ['CAROLINA WREN', 4]]
    .map(([name, pc], i) => `<div class="ps-row${i ? ' ps-dim' : ''}">
        <span class="ps-nm">${name}</span>
        <div class="ps-prog"><div class="ps-fill" style="width:${pc}%;--i:${i}"></div></div>
        <span class="ps-pc">${pc}%</span>
      </div>`).join('');
  return `<section class="ps-panel">
    <div class="ps-bar"><span class="ps-t">${icon('mark')}BIRD CLASSIFIER</span><span class="ps-r">30 SPECIES</span></div>
    <div class="ps-body">
      ${chipsHtml(['CNN', 'MEL-SPECTROGRAM', 'PYTORCH', 'DJANGO'])}
      <p class="ps-p">Feed it a bird call and it returns a species, the top five candidates with confidence, and the spectrogram it actually classified.</p>
      <div class="ps-sub"><span>SAMPLE OUTPUT</span><span>northern_flicker.wav</span></div>
      ${rows}
      <a class="ps-btn" href="${u}#drop-zone"><span class="ps-lbl">UPLOAD A RECORDING</span></a>
      <div class="ps-btnrow">
        <a class="ps-btn ps-sm ps-alt" href="${u}#start-recording"><span class="ps-lbl">RECORD FROM MIC</span></a>
        <a class="ps-btn ps-sm ps-alt" href="${u}#bird-search"><span class="ps-lbl">TRY A SAMPLE CALL</span></a>
      </div>
      <div class="ps-hint">WAV, MP3, OGG or M4A, or pull one by Macaulay ML number</div>
    </div>
  </section>`;
}

// Sprites and voice lines are built here rather than by {% static %}, so they
// carry the server's stamp: the newest mtime among them. A replaced frame or
// line changes it; until then every visit is served from the browser cache.
const CX_BUST = STATIC_URLS.codecVer || Date.now();
const CX_F = n => `${STATIC_URLS.codecBase}/campbell_f${n}.png?v=${CX_BUST}`;
const SN_F = n => `${STATIC_URLS.codecBase}/snake_f${n}.png?v=${CX_BUST}`;
const OT_F = n => `${STATIC_URLS.codecBase}/otacon_f${n}.png?v=${CX_BUST}`;
const CX_VOICE_URL = key => `${STATIC_URLS.voiceBase}/${key}.m4a?v=${CX_BUST}`;
// The Colonel and Otacon share the left portrait slot ('campbell'); Snake is
// the right one. Each speaker carries a neutral face plus four visemes.
const CX_SPEAKERS = {
  colonel: { imgId: 'campbell', neutral: CX_F('00'),
             pose: [CX_F('10'), CX_F('09'), CX_F('08'), CX_F('08')] },
  snake:   { imgId: 'snake',    neutral: SN_F('03'),
             pose: [SN_F('03'), SN_F('03'), SN_F('08'), SN_F('08')] },
  otacon:  { imgId: 'campbell', neutral: OT_F('00'),
             pose: [OT_F('00'), OT_F('01'), OT_F('02'), OT_F('02')] },
};
let cxSpeaker = CX_SPEAKERS.colonel;
// Every frame is fetched and decoded up front and held here. A frame swapped in
// for the first time mid-line otherwise blanks the portrait while it loads,
// which is what made Otacon's face drop out as he started talking.
const cxFrames = [...new Set(Object.values(CX_SPEAKERS).flatMap(s => [s.neutral, ...s.pose]))]
  .map(src => { const im = new Image(); im.src = src; if (im.decode) im.decode().catch(() => {}); return im; });
// What each slot shows at rest, so it keeps the last character who used it.
const cxSlotNeutral = {
  [CX_SPEAKERS.colonel.imgId]: CX_SPEAKERS.colonel.neutral,
  [CX_SPEAKERS.snake.imgId]:   CX_SPEAKERS.snake.neutral,
};
function cxSetPortrait(speakerKey){
  const sp = CX_SPEAKERS[speakerKey];
  if (!sp) return;
  cxSlotNeutral[sp.imgId] = sp.neutral;
  const img = document.getElementById(sp.imgId);
  if (img) img.src = sp.neutral;
}


// One channel per frequency. `view` is what the panel shows and `script` what
// gets said on arrival, or nothing when the line has already been delivered.
// Lines carry their own voice key (static/audio/codec/<key>.m4a); a key with no
// file plays as text, which is the right failure for a line not yet recorded.
let cxProjectsIntroDone = false;
const CX_CONTACTS = [
  { freq:'140.85', name:'COLONEL', view: () => [aboutHtml()],
    // the Colonel briefs once; after that the channel idles on "..."
    script(){
      if (this.done) return null;
      this.done = true;
      return [
        { key:'c0_l0', text:"Snake, this is Nick Burczyk. He's a software developer and AI integration engineer at Viper Imaging." },
        { key:'c0_l1', text:"Everything we've gathered on him is laid out below. We've also attached his direct links. For anything specific, tune through the other channels, or open MEMORY for the list." },
      ];
    } },
  { freq:'141.12', name:'PROJECTS', view: () => [projectsHtml()],
    // a one-time three-way handoff, then only Otacon greets you
    script(){
      if (cxProjectsIntroDone) return [{ text:"Want to learn more about any projects?", speaker:'otacon', key:'ot_repeat' }];
      cxProjectsIntroDone = true;
      const n = PROJECTS.length;
      return [
        // the recorded take says "twelve"; any other count is text until re-recorded
        { text:`His operation records. ${NUM_WORDS[n] || n} declassified projects on file.`, key: n === 12 ? 'c1_l0' : `c1_l0_${n}` },
        { text:"For the details, get Otacon on the line. Hal's been cataloguing all of it.", key:'c1_l1' },
        { text:"Hal Emmerich. Been a while since Shadow Moses. Patch him in.", speaker:'snake', key:'snake_hal' },
        { text:"He's already listening.", key:'c1_l2' },
        { text:"Hey, Snake. It's been a while.", speaker:'otacon', key:'ot_hello' },
        { text:"Click on any project to see the full briefing. I can fill you in on the details, too.", speaker:'otacon', key:'ot_brief' },
        { text:"Alright. Let's take a look, then.", speaker:'snake', key:'snake_look' },
      ];
    } },
  { freq:'141.52', name:'MUSIC', view: () => [musicHtml()],
    script: () => [
      { key:'c2_l0', text:"He also records as Zero Barbecue. A one-man operation." },
      { key:'c2_l1', text:"First single's out now. Listen below." },
    ] },
  { freq:'140.07', name:'MC PORTAL', view: () => [psPortalPanel(), psFillFaces],
    script: () => [
      { key:'c3_p0', text:`A private Minecraft world: custom modpack, custom server. ${NUM_WORDS[STATIC_URLS.mc.seasons] || STATIC_URLS.mc.seasons} seasons on record.` },
      { key:'c3_p1', text:"We've opened a portal into it. The live map, who's online, and every boss still standing. Go through it, Snake." },
    ] },
];
let cxIdx = 0;
let cxBooted = false;

// Typing drives the mouth; if the voice outruns the typing the mouth keeps
// flapping until the audio ends, and the next line waits for both.
let cxTypeTimer = null;
// One steady timer eases the mouth a step at a time toward a target openness
// (0 closed .. 3 wide) so it never snaps open<->shut, which read as jitter.
// While a clip plays, the target comes from its precomputed viseme track
// instead of the typed text; cxAudioMouth flags that mode.
let cxMouth = 0, cxMouthTarget = 0, cxMouthTimer = null, cxFlap = false, cxFlapPhase = 0;
let cxAudioMouth = false, cxMouthF = 0, cxLastMouthIdx = -1;
const CX_FLAP_CYCLE = [1, 2, 3, 2, 1, 0];
function cxSetMouthFrame(idx){
  idx = Math.max(0, Math.min(cxSpeaker.pose.length - 1, idx));
  if (idx === cxLastMouthIdx) return;
  cxLastMouthIdx = idx;
  const img = document.getElementById(cxSpeaker.imgId);
  if (img) img.src = cxSpeaker.pose[idx];
}
function cxMouthStep(){
  if (cxFlap){
    cxFlapPhase = (cxFlapPhase + 1) % CX_FLAP_CYCLE.length;
    cxMouthTarget = CX_FLAP_CYCLE[cxFlapPhase];
  }
  if (cxMouth < cxMouthTarget) cxMouth++;
  else if (cxMouth > cxMouthTarget) cxMouth--;
  cxSetMouthFrame(cxMouth);
}
function cxStartMouth(){ if (!cxMouthTimer) cxMouthTimer = setInterval(cxMouthStep, 70); }
function cxClearMouthTimer(){ if (cxMouthTimer){ clearInterval(cxMouthTimer); cxMouthTimer = null; } }
function cxAudioMouthTick(env){
  if (!env || !env.mouth) return;
  const idx = Math.min(env.mouth.length - 1, Math.floor(cxVoice.currentTime / env.step));
  const target = env.mouth[idx] || 0;
  cxMouthF += (target - cxMouthF) * 0.4;   // low-pass so it eases, not snaps
  cxSetMouthFrame(Math.round(cxMouthF));
}
function cxStopMouth(){
  cxClearMouthTimer();
  cxFlap = false; cxFlapPhase = 0; cxMouth = 0; cxMouthTarget = 0;
  cxAudioMouth = false; cxMouthF = 0; cxLastMouthIdx = -1;
}
let cxQueue = [], cxCurrentLine = '', cxVoice = null;
// extra per-line typing lead (ms before audio end that typing finishes)
const CX_TYPE_LEAD = { 'c0_l1': 1500 };
// One reusable element for all voice lines. It gets 'unlocked' during the
// SELECT click (Safari only allows play() from a user gesture until an
// element has played once), then plays freely for the rest of the session.
const cxVoiceEl = new Audio();
cxVoiceEl.muted = cxMuted;
function cxUnlockVoice(){
  cxVoiceEl.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQIAAACAgA==';
  cxVoiceEl.play().catch(() => {});
}
let cxTypeDone = true, cxVoiceDone = true, cxAdvanceTimer = null;

// Signal-meter VU: the wedge follows a precomputed amplitude envelope synced
// by playback time, so the audio element never has to be rerouted.
let cxBarEls = [], cxMeterRAF = null, cxEnvCache = {};
function cxLoadEnvelope(key){
  if (cxEnvCache[key] !== undefined) return Promise.resolve(cxEnvCache[key]);
  return fetch(CX_VOICE_URL(key))
    .then(r => r.arrayBuffer())
    .then(b => getAudioCtx().decodeAudioData(b))
    .then(audio => {
      const data = audio.getChannelData(0);
      const hop = Math.max(1, Math.floor(audio.sampleRate * 0.03));  // 30ms frames
      const env = [], zcr = [];
      for (let i = 0; i < data.length; i += hop){
        let s = 0, n = 0, zc = 0, prev = 0;
        for (let j = i; j < i + hop && j < data.length; j++){
          const v = data[j];
          s += v * v; n++;
          if (j > i && (v >= 0) !== (prev >= 0)) zc++;
          prev = v;
        }
        env.push(Math.sqrt(s / (n || 1)));
        zcr.push(zc / (n || 1));         // zero-crossing rate: spectral proxy
      }
      let peak = 0.0001;
      for (const v of env) if (v > peak) peak = v;
// Mouth openness per frame from the real speech: silence stays shut, high-ZCR
// fricatives stay narrow, voiced vowels open in proportion to their energy.
      const mouth = env.map((v, i) => {
        const e = v / peak;
        if (e < 0.08) return 0;
        if (zcr[i] > 0.16) return 1;
        return e > 0.62 ? 3 : e > 0.32 ? 2 : 1;
      });
      const e = { frames: env.map(v => v / peak), mouth, step: 0.03 };
      cxEnvCache[key] = e;
      return e;
    })
    .catch(() => { cxEnvCache[key] = null; return null; });
}
function cxMeterStart(key){
  if (!cxBarEls.length) return;
  cxLoadEnvelope(key).then(env => {
    if (cxMeterRAF) cancelAnimationFrame(cxMeterRAF);
    if (env && env.mouth){ cxAudioMouth = true; cxClearMouthTimer(); cxMouthF = 0; }
    const loop = () => {
      if (!cxVoice || cxVoice.paused || cxVoice.ended){ cxMeterStop(); return; }
      if (cxAudioMouth) cxAudioMouthTick(env);
      let level = 0.45;
      if (env){ const idx = Math.min(env.frames.length - 1, Math.floor(cxVoice.currentTime / env.step)); level = env.frames[idx] || 0; }
// fill from the bottom up: loud speech lights higher bars
      const lit = Math.round(level * cxBarEls.length);
      const n = cxBarEls.length;
      cxBarEls.forEach((el, i) => {
        const fromBottomIdx = n - 1 - i;               // 0 = bottom bar
        el.style.opacity = fromBottomIdx < lit ? '1' : String(el._base);
      });
      cxMeterRAF = requestAnimationFrame(loop);
    };
    loop();
  });
}
function cxMeterStop(){
  if (cxMeterRAF){ cancelAnimationFrame(cxMeterRAF); cxMeterRAF = null; }
  cxBarEls.forEach(el => { el.style.opacity = el._base; });
}

function cxViseme(ch){
  ch = (ch || '').toLowerCase();
  if ('ao'.includes(ch))      return 3;
  if ('eiuy'.includes(ch))    return 2;
  if ('mbpfvw'.includes(ch))  return 0;
  if (ch >= 'a' && ch <= 'z') return 1;
  return 0;
}
function cxSpeakChar(ch){
  if (cxAudioMouth) return;
  cxFlap = false;
  cxMouthTarget = cxViseme(ch);
  cxStartMouth();
}
function cxRest(){
// each slot back to its occupant's neutral, so a speaker swap never leaves a
// stuck mouth (the Colonel and Otacon share the left slot)
  cxStopMouth();
  for (const imgId in cxSlotNeutral){
    const img = document.getElementById(imgId);
    if (img) img.src = cxSlotNeutral[imgId];
  }
}
function cxStopVoice(){
  if (cxVoice) { cxVoice.pause(); cxVoice = null; }
  cxStopMouth();
  cxMeterStop();
  cxVoiceDone = true;
}
function cxSpotlight(imgId){
  document.querySelectorAll('.cx-portrait').forEach(p =>
    p.classList.toggle('talking', !!imgId && !!p.querySelector('#' + imgId)));
}
function cxHardStop(){
  cxSpotlight(null);
  if (cxTypeTimer) { clearInterval(cxTypeTimer); cxTypeTimer = null; }
  if (cxAdvanceTimer) { clearTimeout(cxAdvanceTimer); cxAdvanceTimer = null; }
  cxStopVoice();
  cxQueue = [];
  cxTypeDone = true;
  cxRest();
}
function cxStartFlap(){
  if (cxAudioMouth) return;
// voice still speaking after the text finished: keep the mouth on a steady
// open/close cycle rather than random jitter
  cxFlap = true;
  cxStartMouth();
}
function cxMaybeAdvance(){
  if (!cxTypeDone || !cxVoiceDone) return;
  cxRest();
  if (cxQueue.length) {
    cxAdvanceTimer = setTimeout(() => {
      cxAdvanceTimer = null;
      if (cxTypeDone && cxVoiceDone) cxTypeNext();
    }, 800);
  }
}
function cxTypeNext(){
  const dlg = document.getElementById('cx-dialogue');
  if (!dlg || cxQueue.length === 0) { cxRest(); return; }
  const item = cxQueue.shift();
  cxCurrentLine = item.text;
  cxSpeaker = item.speaker || CX_SPEAKERS.colonel;
// this speaker now owns its slot, so Otacon can take the left one from the
// Colonel mid-conversation and stay there at rest
  cxSlotNeutral[cxSpeaker.imgId] = cxSpeaker.neutral;
  cxTypeDone = false;
  cxStopVoice();
  cxRest();
  dlg.textContent = '';
  dlg.dataset.who = item.who.toUpperCase();
  cxSpotlight(cxSpeaker.imgId);
  let i = 0;
  const startedAt = performance.now();
  const tick = () => {
    dlg.textContent = cxCurrentLine.slice(0, ++i);
    cxSpeakChar(cxCurrentLine[i - 1]);
    if (i >= cxCurrentLine.length) {
      clearInterval(cxTypeTimer); cxTypeTimer = null;
      cxTypeDone = true;
      if (!cxVoiceDone) cxStartFlap(); else cxRest();
      cxMaybeAdvance();
    }
  };
  const startTicking = ms => {
    if (cxTypeTimer) clearInterval(cxTypeTimer);
    cxTypeTimer = setInterval(tick, ms);
  };
  startTicking(30);
  if (item.key) {
    const a = cxVoiceEl;
    a.volume = 0.9;
    cxVoice = a; cxVoiceDone = false;
    cxLoadEnvelope(item.key);   // warm the viseme track so it's ready at play
    a.onloadedmetadata = (() => {
      if (!cxTypeTimer || cxTypeDone || !isFinite(a.duration)) return;
// finish typing ~0.5s before the audio ends so the text leads the voice like
// subtitles; per-line leads live in CX_TYPE_LEAD
      const lead = CX_TYPE_LEAD[item.key] || 1000;
      const remainMs = a.duration * 1000 - (performance.now() - startedAt) - lead;
      const remainChars = cxCurrentLine.length - i;
      if (remainChars > 0 && remainMs > 200) {
        startTicking(Math.min(38, Math.max(10, remainMs / remainChars)));
      }
    });
    a.onended = () => {
      cxStopMouth();
      cxMeterStop();
      cxVoiceDone = true; cxMaybeAdvance();
    };
    a.onerror = () => { cxVoiceDone = true; cxMaybeAdvance(); };
    a.src = CX_VOICE_URL(item.key);
    const vkey = item.key;
    a.play().then(() => cxMeterStart(vkey)).catch(() => { cxVoiceDone = true; });   // file missing: text-only
  }
}
// Which lines have a recording, by key: the names of the clips on disk.
const CX_VOICES = new Set(STATIC_URLS.voices);
function cxSay(lines){
  cxHardStop();
  // a line whose clip has not been recorded is typed in silence, not asked for
  cxQueue = lines.map(l => ({ text: l.text, key: CX_VOICES.has(l.key) ? l.key : null, who: l.speaker || 'colonel',
                               speaker: CX_SPEAKERS[l.speaker] || CX_SPEAKERS.colonel }));
  cxTypeNext();
}
function skipTyping(){
  const dlg = document.getElementById('cx-dialogue');
  if (!dlg) return;
  if (cxTypeTimer) {
    clearInterval(cxTypeTimer); cxTypeTimer = null;
    dlg.textContent = cxCurrentLine;
    cxTypeDone = true;
    cxStopVoice();
    cxRest();
    cxMaybeAdvance();
  } else if (cxQueue.length) {
    if (cxAdvanceTimer) { clearTimeout(cxAdvanceTimer); cxAdvanceTimer = null; }
    cxStopVoice();
    cxTypeNext();
  } else if (!cxVoiceDone) {
    cxStopVoice();
    cxRest();
  }
}

// The readout spins through the band before it settles, like a dial being turned.
let cxFreqTimer = null;
function cxRollFreq(to){
  const el = document.getElementById('freq-num');
  const pin = document.getElementById('pin-freq');
  if (pin) pin.textContent = to;
  clearInterval(cxFreqTimer);
  if (REDUCED_MOTION) { el.textContent = to; return; }
  let n = 0;
  cxFreqTimer = setInterval(() => {
    if (++n > 7) { clearInterval(cxFreqTimer); el.textContent = to; return; }
    el.textContent = (140 + Math.random() * 2).toFixed(2);
  }, 38);
}
function cxOpenContact(i, dir){
  const last = cxIdx;
  cxIdx = (i + CX_CONTACTS.length) % CX_CONTACTS.length;
  const c = CX_CONTACTS[cxIdx], idx = cxIdx;
  cxHardStop();
  cxRollFreq(c.freq);
  document.getElementById('cx-contact-name').textContent = c.name;
  const dlg = document.getElementById('cx-dialogue');
  dlg.textContent = '';
  delete dlg.dataset.who;
  document.querySelectorAll('.cx-portrait').forEach(p => {
    p.classList.add('static');
    setTimeout(() => p.classList.remove('static'), 280);
  });
  // the panel leaves the way the dial was turned and the next one follows it in
  document.documentElement.dataset.dir = (dir || (cxIdx >= last ? 1 : -1)) > 0 ? 'fwd' : 'back';
  document.getElementById('cx-content').classList.add('visible');
  const [html, after] = c.view();
  cxShow(html, after, cxBooted ? 'slide' : false);
  // Otacon holds the left portrait once he has taken over PROJECTS
  cxSetPortrait(c.name === 'PROJECTS' && cxProjectsIntroDone ? 'otacon' : 'colonel');
  const delay = cxBooted ? 420 : 2000;
  cxBooted = true;
  setTimeout(() => {
    if (idx !== cxIdx) return;  // user already retuned
    const lines = c.script();
    if (lines) return cxSay(lines);
    dlg.textContent = '...';
    cxRest();
  }, delay);
  cxUpdateMemoryHighlight();
}
function tuneStep(dir){ cxOpenContact(cxIdx + dir, dir); }

function cxBuildMemory(){
  const list = document.getElementById('cx-mem-list');
  if (!list) return;
  list.innerHTML = '';
  CX_CONTACTS.forEach((c, i) => {
    const b = document.createElement('button');
    b.className = 'cx-mem-row';
    b.innerHTML = `<span class="cx-mem-freq">${c.freq}</span><span class="cx-mem-name">${c.name}</span>`;
    b.onclick = () => { cxOpenContact(i); toggleMemory(false); };
    list.appendChild(b);
  });
}
function cxUpdateMemoryHighlight(){
  document.querySelectorAll('.cx-mem-row').forEach((r, i) =>
    r.classList.toggle('active', i === cxIdx));
}
function toggleMemory(force){
  const p = document.getElementById('cx-memory-panel');
  if (!p) return;
  const open = typeof force === 'boolean' ? force : !p.classList.contains('open');
  p.classList.toggle('open', open);
  document.querySelectorAll('.cx-memory').forEach(b => b.setAttribute('aria-expanded', String(open)));
  if (open) { const row = p.querySelector('.cx-mem-row.active') || p.querySelector('.cx-mem-row'); if (row) row.focus({ preventScroll: true }); }
}
document.addEventListener('pointerdown', e => {
  const p = document.getElementById('cx-memory-panel');
  if (p && p.classList.contains('open') && !p.contains(e.target) && !e.target.closest('.cx-memory')) toggleMemory(false);
});

// The subtitle strip: once the codec has scrolled out of sight, what is being
// said keeps showing along the top of the screen.
function cxInitPin(){
  const pin = document.getElementById('cx-pin'), dlg = document.getElementById('cx-dialogue');
  if (!pin || !dlg) return;
  const who = document.getElementById('pin-who'), line = document.getElementById('pin-line');
  const mirror = () => {
    who.textContent = dlg.dataset.who ? dlg.dataset.who + ':' : '';
    line.textContent = dlg.textContent;
  };
  new MutationObserver(mirror).observe(dlg, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['data-who'] });
  new IntersectionObserver(([en]) => {
    pin.classList.toggle('on', !en.isIntersecting && en.boundingClientRect.top < 0);
  }, { root: document.getElementById('screen') }).observe(dlg);
  document.getElementById('pin-text').onclick = () => document.getElementById('screen').scrollTo({ top: 0 });
}

function initCodec(){
  Object.values(CX_SPEAKERS).forEach(sp =>
    [sp.neutral, ...sp.pose].forEach(src => { new Image().src = src; }));
  // Signal meter: a dense stack of left-aligned bars on a concave curve, top
  // bar longest, matching the real codec display.
  const bars = document.getElementById('cx-bars');
  cxBarEls = [98, 59, 46, 39, 34, 30.5, 28, 26, 24.5].map(w => {
    const s = document.createElement('span');
    s.style.width = w + '%';
    s._base = 0.28;
    return bars.appendChild(s);
  });
  cxBuildMemory();
  cxInitPin();
  document.addEventListener('keydown', e => {
    if (e.target.closest && e.target.closest('input, textarea, select, [contenteditable]')) return;
    // the arrows on screen click for themselves; the keys have to be given one
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { playClickSound(); tuneStep(e.key === 'ArrowLeft' ? -1 : 1); }
    if (e.key === 'm' || e.key === 'M') toggleMemory();
    if (e.key === 'Escape') toggleMemory(false);
  });
  cxOpenContact(0);
}

// Returning in the same tab: skip the call screen. Browsers keep audio locked
// until the visitor touches the page, so the codec opens silent and the music
// starts on their first click or key.
function resumeSite(){
  const screen = document.getElementById('screen');
  screen.classList.add('visible', 'crt-open');
  initCodec();
  loadSound(STATIC_URLS.menu).then(buf => { bgMusic = buf; if (getAudioCtx().state === 'running') playBackgroundMusic(); });
  Promise.all(['hover', 'click'].map(k => loadSound(STATIC_URLS[k])))
    .then(([h, c]) => { hoverBuffer = h; clickBuffer = c; });
  const wake = () => {
    ['pointerdown', 'keydown'].forEach(t => document.removeEventListener(t, wake, true));
    getAudioCtx().resume().then(playBackgroundMusic);
  };
  ['pointerdown', 'keydown'].forEach(t => document.addEventListener(t, wake, true));
}
if (document.documentElement.classList.contains('cx-returning')) resumeSite();
