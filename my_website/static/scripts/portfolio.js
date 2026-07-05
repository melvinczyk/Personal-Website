const TAG_CLASS = {
  'LIVE':'live', 'IN DEV':'dev', 'ONGOING':'ongoing', '1ST PLACE':'award',
  'ML/DL':'ai', 'EMBEDDED':'embedded', 'HARDWARE':'hardware', 'NETWORKING':'networking',
};

const PROJECTS = [
  { id:"oculosaurus",      name:"OCULOSAURUS",                tags:["1ST PLACE","HARDWARE","NETWORKING"], tech:"Python / OpenCV / Raspberry Pi / YOLO",              img:"https://github.com/melvinczyk/StereoCamera-DepthObjectEstimator/raw/main/assets/presentation/example.gif",  img2:"https://github.com/melvinczyk/StereoCamera-DepthObjectEstimator/raw/main/assets/presentation/point_cloud.png", desc:"Stereo vision system to assist visually impaired individuals with real-time depth perception. Distributed architecture: Raspberry Pi goggles, cloud compute, mobile notifications. Features live 3D point cloud visualization, proximity warnings, and optional YOLO object recognition.", link:"https://github.com/melvinczyk/StereoCamera-DepthObjectEstimator"},
  { id:"memprobe",         name:"MEMPROBE",                   tags:["EMBEDDED","WEB","LIVE"],         tech:"Django / Modal / PostgreSQL / pyelftools / Click CLI", img:"https://memprobe.dev/static/og-image.png", img2:null, desc:"Online ELF analyzer for embedded firmware. Upload a compiled binary and instantly see where flash and RAM go: per-section and per-symbol breakdown, treemap, address map, and memory warnings, with build-over-build size tracking. A Django web app with serverless ELF/DWARF parsing on Modal, a Postgres-backed build history, and a pip-installable CLI that gates firmware size in CI.", link:"https://memprobe.dev"},
  { id:"echo-scout",       name:"ECHO SCOUT",                 tags:["EMBEDDED","HARDWARE", "NETWORKING","IN DEV"],            tech:"C++ / ESP32-S3 / PlatformIO / LVGL / mmWave / ToF / IMU", img:"https://store.freenove.com/cdn/shop/files/FNK0104B.PT02.jpg?v=1758974333&width=1946",                img2:null,                                                                                                         desc:"Compact 2.8\" handheld device that detects people and maps out rooms in real time. The mmWave radar covers an 80 degree area in front of the user, while the 8x8 ToF sensor builds a 3D point cloud of the surrounding space. Orientation and heading tracked via IMU with a live compass on the touchscreen display.", link:"https://github.com/melvinczyk/Heartbeat-Sensor"},
  { id:"song2vec",         name:"SONG2VEC",                   tags:["ML/DL","LIVE"],                  tech:"Python / PyTorch / VAE / PCA / scikit-learn",        img:"https://github.com/melvinczyk/Song2Vec/raw/main/outputs/multi_blobs.png",                                  img2:"https://github.com/melvinczyk/Song2Vec/raw/main/outputs/comparisons/latent_path_Bossa_Antigua_to_Player_One.png", desc:"Skip-gram based embedding model that learns vector representations of genres, tags, and songs in a shared latent space. Includes a VAE that maps songs into a 16-dimensional latent space and synthesizes unique colour blob images driven by genre and mood embeddings. PCA projects 1,305 genre and 985 tag vectors into colour+layout space.", link:"https://github.com/melvinczyk/Song2Vec"},
  { id:"bird-classifier",  name:"BACKYARD BIRD CLASSIFIER",   tags:["ML/DL", "LIVE"],                 tech:"Python / CNN / Django / mel-spectrogram",             img:"https://statesymbolsusa.org/sites/default/files/primary-images/NorthernFlickerMaleALbirdsymbol.jpg",             img2:"https://github.com/melvinczyk/Bird-classifier/blob/main/final_matrix.png?raw=true",    desc:"Audio classification CNN identifying 30 Alabama bird species from calls. Applied to mel-spectrograms. Full-stack Django web app: upload a bird call, see the species prediction, top-5 guesses, and a spectrogram visualization.", link:"https://github.com/melvinczyk/Bird-Classifier"},
  { id:"personal-website", name:"NICHOLASBURCZYK.COM",        tags:["LIVE"],                         tech:"Django / Python",                                    img:"https://www.svgrepo.com/show/353657/django-icon.svg",                                                         img2:null,                                                                                                         desc:"This website. Built on Django for a secure backend, Tailwind CSS + DaisyUI for the frontend, and deployed ML model inference for the bird classifier.", link:"https://github.com/melvinczyk/Personal-Website"},
  { id:"waste-drone",      name:"WASTE DETECTION DRONE",      tags:["ML/DL","HARDWARE","NETWORKING"],             tech:"Python / YOLOv5 / Tello SDK",                        img:"https://github.com/melvinczyk/Waste-detection-drone/raw/main/images/Medium%20model%20frame.png",          img2:"https://github.com/melvinczyk/Waste-detection-drone/raw/main/images/model_.gif",        desc:"Autonomous drone for environmental waste monitoring. Custom YOLOv5 model trained on annotated waste datasets. Programmatic flight via Tello SDK with precision navigation, telemetry logging, and automated spatial classification.", link:"https://github.com/melvinczyk/Waste-detection-drone"},
  { id:"modpack-updater",  name:"MINECRAFT MODPACK UPDATER",  tags:["NETWORKING"],                               tech:"Java / JavaFX / Amazon S3 / Gradle",                 img:"https://github.com/user-attachments/assets/db32657d-8d6b-49d9-afe8-498cf750cc41",                          img2:"https://github.com/user-attachments/assets/a06daa21-547a-404c-8c95-eadcb740e267",                            desc:"Desktop app using Amazon S3 to host and sync Minecraft modpacks across a friend group. Git-style change tracking with a manifest. Admin panel: push updates, view changelogs, track folders, add new packs. One-click update for clients. Cross-platform.", link:"https://github.com/melvinczyk/ModpackUpdater"},
  { id:"visaudio",         name:"VISAUDIO",                   tags:[],                               tech:"Python / librosa / PyQt",                            img:"https://github.com/melvinczyk/VisAudio/blob/main/images/menu.png?raw=true",                                img2:null,                                                                                                         desc:"Desktop app for audio file manipulation: format conversion, bitrate resampling, noise reduction, YouTube audio downloader, mel-spectrogram and waveform visualization. Supports mp3, wav, flac, ogg, m4a, aac.", link:"https://github.com/melvinczyk/VisAudio"},
  { id:"born-in-spellbooks",name:"BORN IN SPELLBOOKS MOD",    tags:[],                               tech:"Java / Minecraft Forge 1.20.1",                      img:"https://i.ibb.co/BPCKZhr/2024-10-07-09-39-39.png",                                                          img2:null,                                                                                                         desc:"Open source Minecraft Forge compatibility mod combining Iron's Spells & Spellbooks with Born In Chaos. 17+ spells coded with custom rendering, animation layering, entity sharing. Three alpha releases.", link:"https://github.com/melvinczyk/Born_in_spellbooks"},
  { id:"fretwatch",        name:"FRETWATCH",                  tags:["IN DEV"],               tech:"Python / OpenCV / PyTorch / librosa",                 img:"https://i.ibb.co/Wn3Jxd2/Screenshot-2024-10-02-at-5-08-12-PM.png",                                        img2:null,                                                                                                         desc:"Live guitar note detection from video and audio. Signal processing extracts audio features to detect notes and chords being played. Combines librosa for audio analysis and OpenCV for live video frame manipulation.", link:"https://github.com/melvinczyk/FretWatch"},
  { id:"minecraft-server", name:"MINECRAFT SERVER & MODPACK", tags:["NETWORKING","ONGOING"],                     tech:"Java / JSON / mcscript / Linux server admin",        img:"https://i.ibb.co/7KCwNZr/minecraft.png",                                                                     img2:null,                                                                                                         desc:"Custom modpack with curated mods, resource & data packs. Server admin: config management, real-time troubleshooting, networking. Custom data packs with JSON/mcscript for custom mobs, biomes, loot tables, and structure generation.", link:"https://github.com/melvinczyk/Datapacks"},
];

// ══════════════════════════════════════════
// SIDEBAR PROJECT LIST
// ══════════════════════════════════════════
function buildSidebarProjects() {
  const container = document.getElementById('sb-projects');
  if (!container) return;
  container.innerHTML = '';
  PROJECTS.forEach(p => {
    const btn = document.createElement('button');
    btn.className = 'sb-proj-btn';
    btn.onclick = () => runCmd(`project ${p.id}`);
    const cls = p.tags.includes('1ST PLACE') ? 'sb-glow-award'
              : p.tags.includes('ML/DL')     ? 'sb-glow-ai'
              : p.tags.includes('EMBEDDED')  ? 'sb-glow-embedded'
              : '';
    btn.innerHTML = `<span class="${cls}">${p.id.toUpperCase()}</span>`;
    container.appendChild(btn);
  });
}

document.addEventListener('DOMContentLoaded', buildSidebarProjects);

// ══════════════════════════════════════════
// AUDIO
// ══════════════════════════════════════════
let audioCtx = null;
let hoverBuffer = null, clickBuffer = null, errorBuffer = null, bgMusic = null, bgMusicSource = null;

function getAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

async function loadSound(url) {
  try {
    const ctx = getAudioCtx();
    const res = await fetch(url);
    const arr = await res.arrayBuffer();
    return await ctx.decodeAudioData(arr);
  } catch(e) { console.warn('Sound load failed:', url, e); return null; }
}

function playBuffer(buffer, volume=0.3) {
  if (!buffer) return;
  const ctx = getAudioCtx();
  ctx.resume().then(() => {
    const src = ctx.createBufferSource();
    const gain = ctx.createGain();
    gain.gain.value = volume;
    src.buffer = buffer;
    src.connect(gain);
    gain.connect(ctx.destination);
    src.start(0);
  });
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
    gain.connect(ctx.destination);
    bgMusicSource.start(0);
  });
}

function playHoverBeep()  { playBuffer(hoverBuffer, 0.3); }
function playClickSound() { playBuffer(clickBuffer, 0.4); }
function playErrorSound() { playBuffer(errorBuffer, 0.5); }

document.addEventListener('mouseenter', e => {
  if (e.target.closest('button, a, .qbtn, .sb-btn, .sb-proj-btn')) playHoverBeep();
}, true);
document.addEventListener('click', e => {
  const target = e.target.closest('button, a, .qbtn, .sb-btn, .sb-proj-btn');
  if (target && target.id !== 'codec-btn') {
    playClickSound();
    const btn = e.target.closest('button');
    if (btn) {
      btn.classList.add('btn-flash');
      setTimeout(() => btn.classList.remove('btn-flash'), 350);
    }
  }
}, true);

// ══════════════════════════════════════════
// CODEC INTRO ENTRY
// ══════════════════════════════════════════
async function enterSite() {
  const btn    = document.getElementById('codec-btn');
  const codec  = document.getElementById('codec-screen');
  const screen = document.getElementById('screen');

  btn.disabled = true;
  btn.textContent = '[ CONNECTING... ]';
  cxUnlockVoice();   // prime the voice element while we're in a user gesture
  codec.classList.add('codec-entering');

  const ringBuffer = await loadSound(STATIC_URLS.ring);
  playBuffer(ringBuffer, 0.8);

  [hoverBuffer, clickBuffer, errorBuffer, bgMusic] = await Promise.all([
    loadSound(STATIC_URLS.hover),
    loadSound(STATIC_URLS.click),
    loadSound(STATIC_URLS.error),
    loadSound(STATIC_URLS.menu),
  ]);

  const openBuffer = await loadSound(STATIC_URLS.open);

  setTimeout(() => {
    codec.classList.add('fade-out');
    playBuffer(openBuffer, 0.7);
    codec.addEventListener('animationend', () => {
      codec.style.display = 'none';
      // reveal happens entirely through the CRT line-open animation
      screen.classList.add('visible', 'crt-open');
      setTimeout(playBackgroundMusic, 300);
      initCodec();
    }, { once: true });
  }, 1800);
}


// ══════════════════════════════════════════
// TERMINAL HELPERS
// ══════════════════════════════════════════
const out = document.getElementById('output');
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function ln(html='',cls='line'){const d=document.createElement('div');d.className=`line ${cls} fade-in`;d.innerHTML=html;out.appendChild(d);out.scrollTop=out.scrollHeight;}
function bl(){const d=document.createElement('div');d.className='blank fade-in';out.appendChild(d);out.scrollTop=out.scrollHeight;}
function addHtml(h){const d=document.createElement('div');d.className='fade-in';d.innerHTML=h;out.appendChild(d);out.scrollTop=out.scrollHeight;}
function echo(cmd){ln(`<span style="color:var(--mgs-border)">>></span> <span style="color:var(--mgs-cyan)">${esc(cmd)}</span>`);}

// ══════════════════════════════════════════
// COMMANDS
// ══════════════════════════════════════════
const CMDS = {
about(){
  bl();
  addHtml(`<div class="who-card fade-in">
    <div class="who-info">
      <div class="who-name">NICK BURCZYK</div>
      <div class="who-row"><span class="who-key">school</span><span class="who-val">MSAI @ UAB - Spring 2027</span></div>
      <div class="who-row"><span class="who-key">work</span><span class="who-val">TITANS-SW R&amp;D Intern @ Sandia National Labs</span></div>
      <div class="who-row"><span class="who-key">teaching</span><span class="who-val">TA - Software Development @ UAB</span></div>
      <div class="who-row"><span class="who-key">interests</span><span class="who-val">complex software, hardware integration</span></div>
      <div class="who-row"><span class="who-key">learning</span><span class="who-val">C/C++ - embedded, performance computing, low-level work</span></div>
      <div class="who-row"><span class="who-key">music</span><span class="who-val">Zero Barbecue - producer / artist</span></div>
      <div class="who-row"><span class="who-key">gaming</span><span class="who-val">Minecraft - modding, custom server, Forge mods</span></div>
    </div>
  </div>`);
  bl();
},

projects(){
  bl();
  PROJECTS.forEach((p,i)=>{
    const n=String(i+1).padStart(2,'0');
    ln(`  <span style="color:#225544">${n}</span>  <span style="color:var(--mgs-cyan);cursor:pointer;text-decoration:underline" onclick="runCmd('project ${p.id}')">${p.id.padEnd(22)}</span><span style="color:#559988">${esc(p.name)}</span>`);
  });
  bl();
},

project(id){
  id=(id||'').trim().toLowerCase();
  if(!id){ln(`  Usage: project [id]. Run <span style="color:var(--mgs-cyan)">projects</span> for a list`,'red');return;}
  const p=PROJECTS.find(x=>x.id===id||x.name.toLowerCase().includes(id));
  if(!p){ln(`  Not found: ${esc(id)}. Run <span style="color:var(--mgs-cyan)">projects</span> for a list`,'red');return;}
  bl();
  const img2html=p.img2?`<img src="${p.img2}" alt="secondary" style="width:100%;margin-top:8px;max-height:120px;object-fit:cover;border:2px solid var(--mgs-border);filter:grayscale(0.3) contrast(1.1);">` :'';
  const tagsHtml = (p.tags||[]).map(t=>`<span class="tag ${TAG_CLASS[t]||''}">${esc(t)}</span>`).join('');
  const esId   = p.id==='echo-scout'    ? `esdemo${Date.now()}` : null;
  const demoSection = esId ? `
    <div class="proj-demo-outer" id="${esId}-wrap">
      <div class="proj-demo-hdr">
        <span>◈ EMULATED LIVE DEMO</span>
        <span class="proj-demo-sim">SIMULATED SENSOR DATA</span>
      </div>
      <div class="proj-demo-body">
        <div class="echo-device-outer">
          <div class="echo-device-bezel">
            <div class="echo-device-notch"></div>
            <canvas id="${esId}" width="240" height="320" class="echo-device-canvas"></canvas>
          </div>
          <div class="echo-device-controls">
            <button class="echo-reset-btn" id="${esId}-reset">⟳ RESET</button>
            <div class="echo-device-footer">ECHO SCOUT v1.0 &nbsp;◈&nbsp; ESP32-S3</div>
          </div>
        </div>
        <div class="echo-demo-hint">
          <div class="echo-hint-title">◈ INTERACTIVE EMULATOR</div>
          <div class="echo-hint-body">
            <div class="echo-hint-row">● Boots automatically to menu</div>
            <div class="echo-hint-row">● Tap menu buttons to navigate</div>
            <div class="echo-hint-row">● Tap <b>&lt; MENU</b> to go back</div>
            <div class="echo-hint-row">● Tab bars switch sensor views</div>
            <div class="echo-hint-row">● RESET restarts from boot screen</div>
          </div>
        </div>
      </div>
    </div>` : (p.id==='song2vec' ? `
    <div class="proj-demo-outer" style="padding:16px 20px;">
      <div class="proj-demo-hdr" style="margin-bottom:10px;">
        <span>◈ LIVE INTERACTIVE DEMO</span>
        <span class="proj-demo-sim">203K SONGS · 1305 GENRES · 985 TAGS</span>
      </div>
      <a href="/song2vec/" class="proj-link" style="display:inline-block;margin-top:4px;">→ OPEN SONG2VEC DEMO /song2vec/</a>
    </div>` : (p.id==='memprobe' ? `
    <div class="proj-demo-outer" style="padding:16px 20px;">
      <div class="proj-demo-hdr" style="margin-bottom:10px;">
        <span>◈ LIVE SAAS</span>
        <span class="proj-demo-sim">ELF · DWARF · FLASH / RAM</span>
      </div>
      <a href="https://memprobe.dev" target="_blank" class="proj-link" style="display:inline-block;margin-top:4px;">→ OPEN MEMPROBE memprobe.dev</a>
    </div>` : ''));
  addHtml(`<div class="proj-card">
    <div class="proj-card-header"><span class="proj-name">${esc(p.name)}</span>${tagsHtml}</div>
    <div class="proj-card-body">
      <div class="proj-img-wrap"><div style="width:100%"><img src="${p.img}" alt="${esc(p.name)}" onerror="this.parentElement.style.display='none'">${img2html}</div></div>
      <div class="proj-info">
        <div class="proj-tech">tech: <span style="color:#99ddcc">${esc(p.tech)}</span></div>
        <div class="proj-desc">${esc(p.desc)}</div>
        <a class="proj-link" href="${p.link}" target="_blank">→ ${p.link.includes('github.com') ? `GITHUB: ${p.link.replace('https://github.com/','')}` : `LIVE: ${p.link.replace(/^https?:\/\//,'')}`}</a>
      </div>
    </div>
    ${demoSection}
  </div>`);
  if (esId)   requestAnimationFrame(()=>startEchoScoutDemo(esId));
  bl();
},

music(){
  bl();
  ln('  Artist: <span style="color:var(--mgs-cyan)">Zero Barbecue</span>','line');
  ln('  First single out now.','white');
  bl();
  ln('  <span style="color:#1DB954">●</span> Spotify  → <a class="tl" href="https://open.spotify.com/artist/0uOm4SIBucaY6CHRlQoPBy" target="_blank">open.spotify.com/artist/Zero-Barbecue</a>');
  ln('  <span style="color:#1da0c3">●</span> Bandcamp → <a class="tl" href="https://zerobarbecue.bandcamp.com" target="_blank">zerobarbecue.bandcamp.com</a>');
  bl();
  addHtml(`<div style="padding:4px 20px 8px;max-width:620px"><div style="border:2px solid var(--mgs-border);border-left:4px solid var(--mgs-cyan);padding:12px;background:rgba(0,25,25,0.5)"><iframe style="border-radius:4px;border:none;display:block" src="https://open.spotify.com/embed/album/0i6OlE6MZoOlEIAwWcI5aL?utm_source=generator&theme=0" width="100%" height="200" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe></div></div>`);
  bl();
},

contact(){
  bl();
  [['LinkedIn','https://www.linkedin.com/in/nicholas-burczyk/','#0077B5'],['GitHub','https://github.com/melvinczyk','var(--mgs-cyan)'],['Bandcamp','https://zerobarbecue.bandcamp.com','#1da0c3'],['Spotify','https://open.spotify.com/artist/0uOm4SIBucaY6CHRlQoPBy','#1DB954']].forEach(([label,url,col])=>{
    addHtml(`<div class="contact-row fade-in" style="margin:6px 20px;max-width:600px"><span class="contact-label">${label}</span><a class="contact-link" style="color:${col}" href="${url}" target="_blank">${url}</a></div>`);
  });
  bl();
},

map(){
  bl();
  ln('  Live Bluemap render: real-time world data','white');
  ln('  Full view → <a class="tl" href="http://216.219.93.66:8100/" target="_blank">216.219.93.66:8100/</a>');
  bl();
  addHtml(`<div style="padding:4px 20px 10px;max-width:700px"><div style="border:2px solid var(--mgs-border);border-left:4px solid var(--mgs-cyan);padding:12px;background:rgba(0,25,25,0.5)"><iframe src="http://servermap.minecraft.bz:8100/#server_v3:189:0:87:1500:0:0:0:0:perspective" width="100%" height="360" frameborder="0" style="border:1px solid var(--mgs-border);display:block;"></iframe></div></div>`);
  bl();
},

gallery(){
  bl();
  ln('  <span style="color:var(--mgs-cyan)">Minecraft Server Gallery</span>','line');
  ln('  Screenshots &amp; clips from all seasons','white');
  bl();
  ln('  Redirecting in <span style="color:var(--mgs-cyan)" id="countdown">3</span>...','line');
  bl();
  addHtml(`<div style="padding:0 20px 8px;max-width:480px"><div style="border:2px solid var(--mgs-border);border-left:4px solid var(--mgs-cyan);padding:12px 16px;background:rgba(0,25,25,0.5);display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;"><div><div style="color:var(--mgs-cyan);font-family:'Orbitron',monospace;font-size:16px;letter-spacing:2px;font-weight:700">MC GALLERY</div><div style="color:var(--mgs-border);font-size:11px;margin-top:4px">All seasons · screenshots &amp; video clips</div></div><a href="${STATIC_URLS.gallery}" style="display:inline-flex;align-items:center;gap:6px;background:transparent;border:2px solid var(--mgs-cyan);color:var(--mgs-cyan);font-family:'Orbitron',monospace;font-size:11px;font-weight:700;padding:8px 16px;text-decoration:none;transition:all .2s;" onmouseover="this.style.background='rgba(0,255,204,.15)'" onmouseout="this.style.background='transparent'">▸ OPEN</a></div></div>`);
  bl();
  let n=3;
  const cd=document.getElementById('countdown');
  const t=setInterval(()=>{ n--; if(cd) cd.textContent=n; if(n<=0){clearInterval(t);window.location.href=STATIC_URLS.gallery;} },1000);
},

clear(){ out.innerHTML=''; },

'bird-classifier'(){
  bl();
  ln('  <span style="color:var(--mgs-cyan)">Backyard Alabama Bird Detector</span>','line');
  ln('  CNN · mel-spectrogram · 30 Alabama species','white');
  bl();
  ln('  Redirecting in <span style="color:var(--mgs-cyan)" id="countdown">3</span>...','line');
  bl();
  addHtml(`<div style="padding:0 20px 8px;max-width:480px"><div style="border:2px solid var(--mgs-border);border-left:4px solid var(--mgs-cyan);padding:12px 16px;background:rgba(0,25,25,0.5);display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;"><div><div style="color:var(--mgs-cyan);font-family:'Orbitron',monospace;font-size:16px;letter-spacing:2px;font-weight:700">BIRD CLASSIFIER</div><div style="color:var(--mgs-border);font-size:11px;margin-top:4px">Upload or record a bird call to classify it</div></div><a href="${STATIC_URLS.uploadFile}" style="display:inline-flex;align-items:center;gap:6px;background:transparent;border:2px solid var(--mgs-cyan);color:var(--mgs-cyan);font-family:'Orbitron',monospace;font-size:11px;font-weight:700;padding:8px 16px;text-decoration:none;transition:all .2s;" onmouseover="this.style.background='rgba(0,255,204,.15)'" onmouseout="this.style.background='transparent'">▸ LAUNCH</a></div></div>`);
  bl();
  let n=3;
  const cd=document.getElementById('countdown');
  const t=setInterval(()=>{ n--; if(cd) cd.textContent=n; if(n<=0){clearInterval(t);window.location.href=STATIC_URLS.uploadFile;} },1000);
},
};

CMDS['classifier']=CMDS['bird-classifier'];
CMDS['classify']=CMDS['bird-classifier'];

CMDS['song2vec'] = function() {
  bl();
  ln('  <span style="color:var(--mgs-cyan)">Song2Vec · Musical Blob Visualizer</span>','line');
  ln('  VAE · PCA · 203K songs · 1305 genres · 985 tags','white');
  bl();
  ln('  Redirecting in <span style="color:var(--mgs-cyan)" id="countdown2">3</span>...','line');
  bl();
  addHtml(`<div style="padding:0 20px 8px;max-width:480px"><div style="border:2px solid var(--mgs-border);border-left:4px solid var(--mgs-cyan);padding:12px 16px;background:rgba(0,25,25,0.5);display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;"><div><div style="color:var(--mgs-cyan);font-family:'Orbitron',monospace;font-size:16px;letter-spacing:2px;font-weight:700">SONG2VEC</div><div style="color:var(--mgs-border);font-size:11px;margin-top:4px">Search a song and generate its musical blob</div></div><a href="/song2vec/" style="display:inline-flex;align-items:center;gap:6px;background:transparent;border:2px solid var(--mgs-cyan);color:var(--mgs-cyan);font-family:'Orbitron',monospace;font-size:11px;font-weight:700;padding:8px 16px;text-decoration:none;transition:all .2s;" onmouseover="this.style.background='rgba(0,255,204,.15)'" onmouseout="this.style.background='transparent'">▸ LAUNCH</a></div></div>`);
  bl();
  let n=3;
  const cd=document.getElementById('countdown2');
  const t=setInterval(()=>{ n--; if(cd) cd.textContent=n; if(n<=0){clearInterval(t);window.location.href='/song2vec/';} },1000);
};
CMDS['gallery']=CMDS['gallery'];
CMDS['mc-gallery']=CMDS['gallery'];

// ══════════════════════════════════════════
// COMMAND RUNNER
// ══════════════════════════════════════════
function runCmd(raw){
  const trimmed=(raw||'').trim();
  echo(trimmed);
  if(!trimmed){bl();return;}
  const lo=trimmed.toLowerCase();
  if(lo==='project'||lo.startsWith('project ')){ CMDS['project'](trimmed.slice('project'.length).trim()); return; }
  const fn=CMDS[lo]||CMDS[lo.split(' ')[0]];
  if(fn){ fn(trimmed.split(' ').slice(1).join(' ')); }
  else { playErrorSound(); ln(`  command not found: <span style="color:#ff5555">${esc(trimmed)}</span>. Type <span style="color:var(--mgs-cyan)">help</span>`); bl(); }
}


// ══════════════════════════════════════════
// ECHO SCOUT LIVE DEMO: full device emulator
// ══════════════════════════════════════════
let _esDemoRAF = null;

function startEchoScoutDemo(canvasId) { // eslint-disable-line no-unused-vars
  if (_esDemoRAF) { cancelAnimationFrame(_esDemoRAF); _esDemoRAF = null; }

  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  // ── State machine ──
  let screen    = 'loading';
  let subTab    = 0;
  let t         = 0;
  let loadPct   = 0;
  let lastScreen = '';
  let lastSubTab = -1;
  // ANGL state: 0=idle,1=aLocked,2=done
  let anglState = 0;
  // Scope buffers
  const SCOPE_SAMPLES = 240;
  const _scopeBuf = [new Float32Array(SCOPE_SAMPLES), new Float32Array(SCOPE_SAMPLES), new Float32Array(SCOPE_SAMPLES)];
  let _scopeHead = 0;

  // Reset button
  const resetBtn = document.getElementById(`${canvasId}-reset`);
  if (resetBtn) resetBtn.addEventListener('click', () => {
    screen='loading'; subTab=0; t=0; loadPct=0; lastScreen=''; lastSubTab=-1; anglState=0; _scopeHead=0;
  });

  // ── Colour palette ──
  const K = { BG:'#000000', G:'#00FC00', DIM:'#006000', FAINT:'#003000',
              SEP:'#005800', RED:'#FF0000', AMB:'#F85C00', WHT:'#FFFFFF' };

  // ── Primitives ──
  function fr(x,y,w,h,c)        { ctx.fillStyle=c; ctx.fillRect(x,y,w,h); }
  function dr(x,y,w,h,c)        { ctx.strokeStyle=c; ctx.lineWidth=1; ctx.strokeRect(x+.5,y+.5,w-1,h-1); }
  function hl(x,y,l,c)          { ctx.fillStyle=c; ctx.fillRect(x,y,l,1); }
  function vl(x,y,l,c)          { ctx.fillStyle=c; ctx.fillRect(x,y,1,l); }
  function fc(cx,cy,r,c)        { ctx.fillStyle=c; ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.fill(); }
  function lnC(x1,y1,x2,y2,c)  { ctx.strokeStyle=c; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke(); }
  function txt(s,x,y,sz,c,al='left') {
    ctx.save(); ctx.fillStyle=c;
    ctx.font=`${sz===1?8:sz===2?13:sz===4?24:8}px "Courier New",monospace`;
    ctx.textBaseline='top'; ctx.textAlign=al; ctx.fillText(s,x,y); ctx.restore();
  }
  function ctxt(s,cx,y,sz,c) { txt(s,cx,y,sz,c,'center'); }

  // ── ASCII art renderer ──
  function drawArt(lines, sx, sy, cw, lh, col) {
    ctx.save(); ctx.fillStyle=col;
    ctx.font=`${lh}px "Courier New",monospace`;
    ctx.textBaseline='top';
    for (let row=0; row<lines.length; row++) {
      const line=lines[row];
      for (let c=0; c<line.length; c++) {
        if (line[c]===' ') continue;
        ctx.fillText(line[c], sx+c*cw, sy+row*lh);
      }
    }
    ctx.restore();
  }

  const ECHO_ART = [
    '___________      .__          ',
    '\\_   _____/ ____ |  |__   ____',
    ' |    __)__/ ___\\|  |  \\ /  _ \\',
    ' |        \\  \\___|   Y  (  <_> )',
    '/_______  /\\___  >___|  /\\____/',
    '        \\/     \\/     \\/       ',
  ];
  const SCOUT_ART = [
    '  _________                    __  ',
    ' /   _____/ ____  ____  __ ___/  |_',
    ' \\_____  \\_/ ___\\/  _ \\|  |  \\   __\\',
    ' /        \\  \\__(  <_> )  |  /|  | ',
    '/_______  /\\___  >____/|____/ |__| ',
    '        \\/     \\/                  ',
  ];

  // ── Shared header ──
  function drawHeader(title, showCal=false) {
    fr(0,0,240,28,K.BG); hl(0,27,240,K.SEP);
    ctx.save(); ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    ctx.beginPath(); ctx.roundRect(3,3,64,22,[3]); ctx.stroke();
    if (showCal) { ctx.beginPath(); ctx.roundRect(173,3,64,22,[3]); ctx.stroke(); }
    ctx.restore();
    ctxt('< MENU',35,7,2,K.DIM); ctxt(title,120,9,2,K.G);
    if (showCal) ctxt('CAL',205,7,2,K.DIM);
  }

  // ── Tab bar ──
  function drawTabBar(labels, active) {
    const tw=Math.floor(240/labels.length);
    fr(0,280,240,40,K.BG); hl(0,280,240,K.SEP);
    labels.forEach((lbl,i) => {
      const x=i*tw;
      if(i===active) { fr(x,281,tw-1,39,K.FAINT); hl(x,280,tw,K.G); ctxt(lbl,x+tw/2,293,1,K.G); }
      else ctxt(lbl,x+tw/2,293,1,K.DIM);
    });
  }

  // ── Loading screen ──
  function drawLoading() {
    fr(0,0,240,320,K.BG);
    dr(2,2,236,316,K.FAINT);
    drawArt(ECHO_ART,  42, 16, 5, 9, K.G);
    drawArt(SCOUT_ART, 30, 80, 5, 9, K.G);
    ctxt('FLASHING SENSOR FIRMWARE',120,162,1,K.DIM);
    const BX=20,BY=185,BW=200,BH=14;
    dr(BX-1,BY-1,BW+2,BH+2,K.DIM);
    const fill=Math.round((BW-4)*loadPct/100);
    if(fill>0) fr(BX+2,BY+2,fill,BH-4,K.G);
    ctxt(`${Math.round(loadPct)}%`,120,BY+BH+6,1,K.DIM);
  }

  // ── Menu screen ──
  function drawMenu() {
    fr(0,0,240,320,K.BG);
    dr(2,2,236,316,K.FAINT);
    // Title frame
    dr(8,8,224,138,K.DIM); dr(12,12,216,130,K.G);
    hl(16,16,16,K.G); vl(16,16,16,K.G);
    hl(207,16,16,K.G); vl(223,16,16,K.G);
    hl(16,138,16,K.G); vl(16,123,16,K.G);
    hl(207,138,16,K.G); vl(223,123,16,K.G);
    fr(70,137,100,6,K.BG);
    ctxt('VERSION: 1.0',120,137,1,K.DIM);
    drawArt(ECHO_ART,  42, 16, 5, 9, K.G);
    drawArt(SCOUT_ART, 30, 80, 5, 9, K.G);
    // Status bar
    const sy=147, sh=13;
    fr(0,sy,240,sh,K.BG);
    hl(8,sy,224,K.SEP); hl(8,sy+sh-1,224,K.SEP);
    vl(88,sy+2,sh-4,K.SEP); vl(160,sy+2,sh-4,K.SEP);
    function sUnit(cx,label) {
      const w=label.length*6+13, sx2=cx-w/2;
      fc(sx2+3,sy+sh/2,3,K.G);
      ctx.save(); ctx.fillStyle=K.G; ctx.font='8px "Courier New",monospace';
      ctx.textBaseline='middle'; ctx.textAlign='left';
      ctx.fillText(label,sx2+10,sy+sh/2); ctx.restore();
    }
    sUnit(44,'RADAR'); sUnit(124,'IMU'); sUnit(200,'TOF');
    hl(8,158,224,K.SEP);
    // RADAR launch button
    const bx=12,by=160,bw=216,bh=44, arm=10;
    dr(bx,by,bw,bh,K.DIM); dr(bx+2,by+2,bw-4,bh-4,K.G);
    hl(bx+6,by+6,arm,K.G); vl(bx+6,by+6,arm,K.G);
    hl(bx+bw-arm-6,by+6,arm,K.G); vl(bx+bw-7,by+6,arm,K.G);
    hl(bx+6,by+bh-7,arm,K.G); vl(bx+6,by+bh-arm-6,arm,K.G);
    hl(bx+bw-arm-6,by+bh-7,arm,K.G); vl(bx+bw-7,by+bh-arm-6,arm,K.G);
    // Compass icon left of RADAR text
    const ix=bx+22, iy=by+bh/2;
    vl(ix,iy-7,14,K.G);
    lnC(ix,iy,ix-5,iy-6,K.G); lnC(ix,iy,ix+5,iy-6,K.G);
    hl(ix-6,iy,13,K.G);
    for(let a=-50;a<=50;a+=10){
      const r=a*Math.PI/180;
      ctx.fillStyle=K.G;
      ctx.fillRect(ix+Math.round(8*Math.sin(r))-0.5, iy-Math.round(8*Math.cos(r))-0.5,1,1);
      ctx.fillRect(ix+Math.round(12*Math.sin(r))-0.5,iy-Math.round(12*Math.cos(r))-0.5,1,1);
    }
    ctxt('[ RADAR ]',128,by+13,4,K.G);
    hl(8,204,224,K.SEP);
    function mBtn(bx2,by2,bw2,bh2,label) {
      dr(bx2,by2,bw2,bh2,K.DIM); dr(bx2+2,by2+2,bw2-4,bh2-4,K.G);
      ctxt(label,bx2+bw2/2,by2+bh2/2-4,1,K.G);
    }
    mBtn(8,206,108,30,'3D MAP'); mBtn(120,206,108,30,'SURVEYOR');
    hl(8,236,224,K.SEP);
    mBtn(8,238,108,26,'SCANNER'); mBtn(120,238,108,26,'ATTITUDE');
    hl(8,264,224,K.SEP);
    mBtn(8,266,108,24,'SETTINGS'); mBtn(120,266,108,24,'BATTERY');
    hl(8,290,224,K.SEP);
    dr(40,294,160,16,K.RED); ctxt('[ POWER OFF ]',120,297,1,K.RED);
  }

  // ── Pre-bake radar cone grid ──
  const _coneCanvas=document.createElement('canvas');
  _coneCanvas.width=240; _coneCanvas.height=320;
  (function buildCone(){
    const gc=_coneCanvas.getContext('2d');
    gc.fillStyle=K.BG; gc.fillRect(0,0,240,320);
    const AX=120,AY=316,CLEN=227,HD=55,AR=4000;
    const sd=d=>Math.pow(Math.min(d/AR,1),0.75)*0.88;
    [-55,-27.5,0,27.5,55].forEach((a,i)=>{
      const r=a*Math.PI/180;
      gc.strokeStyle=(i===0||i===4)?K.DIM:K.FAINT; gc.lineWidth=1;
      gc.beginPath(); gc.moveTo(AX,AY); gc.lineTo(AX+CLEN*Math.sin(r),AY-CLEN*Math.cos(r)); gc.stroke();
    });
    [1000,2000,3000,4000].forEach((rMM,ri)=>{
      const rpx=sd(rMM)*CLEN; gc.strokeStyle=ri===3?K.DIM:K.FAINT; gc.lineWidth=1;
      gc.beginPath(); let first=true;
      for(let a=-HD;a<=HD;a+=1.5){
        const r=a*Math.PI/180,gx=AX+rpx*Math.sin(r),gy=AY-rpx*Math.cos(r);
        if(gy<28) continue;
        first?(gc.moveTo(gx,gy),first=false):gc.lineTo(gx,gy);
      }
      gc.stroke();
      const ly=Math.max(32,AY-rpx);
      gc.fillStyle=K.DIM; gc.font='8px "Courier New",monospace';
      gc.textBaseline='top'; gc.textAlign='left';
      gc.fillText(rMM>=1000?`${rMM/1000}m`:`${rMM}mm`,AX+2,ly-8);
    });
    [-55,-27.5,0,27.5,55].forEach(a=>{
      const r=a*Math.PI/180;
      const lx=Math.max(8,Math.min(232,AX+CLEN*Math.sin(r)));
      const ly=Math.max(32,Math.min(AY-10,AY-CLEN*Math.cos(r)));
      gc.fillStyle=K.DIM; gc.font='8px "Courier New",monospace';
      gc.textBaseline='top'; gc.textAlign='center';
      gc.fillText(`${a>0?'+':''}${a}`,lx,ly);
    });
    gc.fillStyle=K.G; gc.beginPath(); gc.arc(AX,AY,4,0,Math.PI*2); gc.fill();
  })();

  const _tgts=[
    {ph:0,   ps:0.009,db:1400,da:500,ab:12, aa:28},
    {ph:2.1, ps:0.015,db:850, da:320,ab:-20,aa:18},
  ];

  // ── Radar screen ──
  function drawRadar(t) {
    const AX=120,AY=316,CLEN=227,AR=4000,CTOP=28;
    const sd=d=>Math.pow(Math.min(d/AR,1),0.75)*0.88;
    const DY=30,DH=54,CW=76,DP=4;
    fr(0,0,240,320,K.BG);
    drawHeader('ECHO SCOUT');
    hl(0,DY+DH,240,K.SEP);
    for(let i=0;i<3;i++) dr(DP+i*(CW+DP),DY+2,CW,DH-4,K.DIM);
    ctxt('DIST', DP+CW/2,           DY+5,1,K.DIM);
    ctxt('ANGLE',DP+(CW+DP)+CW/2,   DY+5,1,K.DIM);
    ctxt('SPEED',DP+2*(CW+DP)+CW/2, DY+5,1,K.DIM);
    ctx.drawImage(_coneCanvas,0,CTOP,240,320-CTOP,0,CTOP,240,320-CTOP);
    const blips=_tgts.map(tg=>{
      const phase=tg.ph+t*tg.ps, dist=tg.db+tg.da*Math.sin(phase), angle=tg.ab+tg.aa*Math.sin(phase*0.7);
      const rpx=sd(dist)*CLEN, rad=angle*Math.PI/180;
      const sx=AX+rpx*Math.sin(rad), sy=AY-rpx*Math.cos(rad);
      return {dist,angle,sx,sy,ok:sy>=CTOP&&sy<316};
    });
    blips.forEach(b=>{
      if(!b.ok) return;
      const g=ctx.createRadialGradient(b.sx,b.sy,0,b.sx,b.sy,9);
      g.addColorStop(0,'rgba(255,0,0,0.55)'); g.addColorStop(1,'rgba(255,0,0,0)');
      ctx.fillStyle=g; ctx.beginPath(); ctx.arc(b.sx,b.sy,9,0,Math.PI*2); ctx.fill();
      fc(b.sx,b.sy,5,K.RED);
    });
    const vis=blips.filter(b=>b.ok);
    if(vis.length){
      const cl=vis.reduce((a,b)=>a.dist<b.dist?a:b);
      const dStr=cl.dist<1000?`${Math.round(cl.dist)}mm`:`${(cl.dist/1000).toFixed(2)}m`;
      const spd=(0.25+0.15*Math.sin(t*0.025)).toFixed(2);
      ctxt(dStr,                        DP+CW/2,           DY+18,2,K.G);
      ctxt(`${cl.angle>=0?'+':''}${cl.angle.toFixed(0)}°`,DP+(CW+DP)+CW/2,DY+18,2,K.AMB);
      ctxt(`${spd}m/s`,                 DP+2*(CW+DP)+CW/2,DY+18,2,K.RED);
    } else {
      [DP+CW/2,DP+(CW+DP)+CW/2,DP+2*(CW+DP)+CW/2].forEach(x=>ctxt('--',x,DY+20,2,K.DIM));
    }
  }

  // ── TOF helpers ──
  function tofCol(d) {
    if(d<=0)   return '#202020';
    if(d<300)  return '#FF0000';
    if(d<600)  {const f=(d-300)/300; return `rgb(248,${Math.round(f*80)},0)`;}
    if(d<1200) {const f=(d-600)/600; return `rgb(${Math.round(248*(1-f))},${Math.round(80+f*172)},0)`;}
    if(d<2500) return K.G;
    return K.DIM;
  }

  // GRID tab
  function drawTofGrid(t) {
    const CELL=30, GY=28;
    const cd=280+700*(0.5+0.5*Math.sin(t/110));
    for(let i=0;i<64;i++){
      const row=Math.floor(i/8),col=i%8;
      const dr_=row-3.5,dc_=col-3.5;
      const d=Math.max(50,Math.min(3000,cd+Math.sqrt(dr_*dr_+dc_*dc_)*230+Math.sin(i*17+t*0.08)*25));
      ctx.fillStyle=tofCol(d); ctx.fillRect(col*CELL+1,GY+row*CELL+1,CELL-2,CELL-2);
    }
  }

  // ANGL tab – 3D angle measurement tool
  function drawTofAngl(t) {
    const VIZ_CX=120, VIZ_CY=189;
    const ANGL_NUM_H=76, BTN_Y=236, BTN_H=44;
    // Simulated angle cycling 0→90
    const angleVal=(45+40*Math.sin(t*0.008)).toFixed(1);
    if(anglState===0){
      ctxt('POINT AT TARGET A',120,30,1,K.DIM);
      ctxt('--',120,44,4,K.DIM);
    } else if(anglState===1){
      ctxt('POINT AT TARGET B',120,30,1,K.AMB);
      ctxt(`${angleVal}`,120,44,4,K.AMB);
    } else {
      ctxt('ANGLE LOCKED',120,30,1,K.G);
      ctxt(`${angleVal}`,120,44,4,K.G);
    }
    // 3D axes
    function proj3(x,y,z){
      const rx=0.3,ry=t*0.01;
      const cx=Math.cos(rx),sx=Math.sin(rx),cy=Math.cos(ry),sy2=Math.sin(ry);
      const x2=x*cy+z*sy2, z2=-x*sy2+z*cy;
      const y2=y*cx-z2*sx, z3=y*sx+z2*cx;
      const sc=180/(z3+5);
      return [VIZ_CX+x2*sc, VIZ_CY+y2*sc];
    }
    const axLen=55;
    [[axLen,0,0,K.RED],[0,axLen,0,K.G],[0,0,axLen,K.DIM]].forEach(([x,y,z,c])=>{
      const p0=proj3(0,0,0), p1=proj3(x,y,z);
      lnC(p0[0],p0[1],p1[0],p1[1],c);
    });
    ctx.save(); ctx.font='8px "Courier New",monospace'; ctx.textBaseline='top'; ctx.fillStyle=K.RED; ctx.fillText('X',...proj3(axLen+4,0,0));
    ctx.fillStyle=K.G; ctx.fillText('Y',...proj3(0,axLen+4,0));
    ctx.fillStyle=K.DIM; ctx.fillText('Z',...proj3(0,0,axLen+4)); ctx.restore();
    // Vector A (green)
    const aAngle=0.8, p0=proj3(0,0,0), pA=proj3(Math.cos(aAngle)*50,Math.sin(aAngle)*50,0);
    lnC(p0[0],p0[1],pA[0],pA[1],K.G);
    fc(pA[0],pA[1],4,K.G);
    if(anglState>0){
      // Vector B (amber)
      const bAngle=aAngle+parseFloat(angleVal)*Math.PI/180;
      const pB=proj3(Math.cos(bAngle)*50,Math.sin(bAngle)*50,0);
      lnC(p0[0],p0[1],pB[0],pB[1],K.AMB);
      fc(pB[0],pB[1],4,K.AMB);
      // arc between
      ctx.strokeStyle=anglState===2?K.G:K.AMB; ctx.lineWidth=1;
      ctx.beginPath();
      for(let s=0;s<=20;s++){
        const f=s/20, ang=aAngle+parseFloat(angleVal)*f*Math.PI/180;
        const pa=proj3(Math.cos(ang)*28,Math.sin(ang)*28,0);
        s===0?ctx.moveTo(pa[0],pa[1]):ctx.lineTo(pa[0],pa[1]);
      }
      ctx.stroke();
    }
    // Button
    const bLabel=anglState===0?'LOCK A':anglState===1?'LOCK B':'RESET';
    const bCol=anglState===0?K.G:anglState===1?K.AMB:K.DIM;
    dr(20,BTN_Y,200,BTN_H,bCol); dr(22,BTN_Y+2,196,BTN_H-4,bCol);
    ctxt(`[ ${bLabel} ]`,120,BTN_Y+16,2,bCol);
  }

  // DIST tab – side-view cone distance measurement
  function drawTofDist(t) {
    const DIST_VIZ_CX=120, DIST_VIZ_Y=64, DIST_VIZ_BOT=232;
    const DIST_BTN_Y=236, DIST_BTN_H=44, DIST_BTN_W=200, DIST_BTN_X=20;
    const dist=Math.round(500+1500*(0.5+0.5*Math.sin(t*0.008)));
    const distStr=dist<1000?`${dist}mm`:`${(dist/1000).toFixed(2)}m`;
    ctxt(distStr,120,4,4,K.G);
    // cone viz area
    const VH=DIST_VIZ_BOT-DIST_VIZ_Y, AX=DIST_VIZ_CX, AY=DIST_VIZ_BOT;
    const CLEN=VH;
    // center vline
    vl(AX,DIST_VIZ_Y,VH,K.DIM);
    // FOV lines spread=52deg
    const spread=52;
    lnC(AX,AY, AX+CLEN*Math.sin(spread*Math.PI/180), DIST_VIZ_Y, K.DIM);
    lnC(AX,AY, AX-CLEN*Math.sin(spread*Math.PI/180), DIST_VIZ_Y, K.DIM);
    // range rings at 500,1000,1500,2000,3000,4000mm
    const MAX_D=4000;
    [500,1000,1500,2000,3000,4000].forEach(ring=>{
      const yp=Math.round(AY-CLEN*ring/MAX_D);
      if(yp<DIST_VIZ_Y) return;
      const hw=Math.round(CLEN*Math.sin(spread*Math.PI/180)*ring/MAX_D);
      hl(AX-hw,yp,hw*2,K.FAINT);
      ctx.save(); ctx.fillStyle=K.DIM; ctx.font='7px "Courier New",monospace'; ctx.textBaseline='middle';
      ctx.fillText(ring>=1000?`${ring/1000}m`:`${ring}`,AX+hw+2,yp); ctx.restore();
    });
    // distance marker
    const markerY=Math.round(AY-CLEN*Math.min(dist,MAX_D)/MAX_D);
    if(markerY>=DIST_VIZ_Y){
      const hw2=Math.round(CLEN*Math.sin(spread*Math.PI/180)*Math.min(dist,MAX_D)/MAX_D);
      ctx.strokeStyle=K.G; ctx.lineWidth=1; ctx.setLineDash([3,3]);
      ctx.beginPath(); ctx.moveTo(AX-hw2,markerY); ctx.lineTo(AX+hw2,markerY); ctx.stroke();
      ctx.setLineDash([]);
      fc(AX,markerY,4,K.G);
    }
    // device rect at bottom
    fr(AX-8,AY-6,16,6,K.DIM);
    // Button
    dr(DIST_BTN_X,DIST_BTN_Y,DIST_BTN_W,DIST_BTN_H,K.G);
    dr(DIST_BTN_X+2,DIST_BTN_Y+2,DIST_BTN_W-4,DIST_BTN_H-4,K.G);
    ctxt('[ MEASURE ]',120,DIST_BTN_Y+16,2,K.G);
  }

  // NRML tab – surface normal + fitted plane
  function drawTofNrml(t) {
    const NUM_H=52, VIZ_Y=80, VIZ_CX=120, VIZ_CY=180, SCALE=55;
    const tiltX=(12*Math.sin(t*0.007)).toFixed(1);
    const azimuth=(30+25*Math.sin(t*0.005)).toFixed(1);
    txt(`TILT ${tiltX} deg`,10,28,2,K.G);
    txt(`AZ ${azimuth} deg`,10,46,2,K.AMB);
    // oblique projection
    function proj(x,y,z){ return [VIZ_CX+(x+z*0.35)*SCALE/500, VIZ_CY+(y-z*0.18)*SCALE/500]; }
    // axes
    [[500,0,0,K.RED],[0,500,0,K.G],[0,0,500,K.DIM]].forEach(([x,y,z,c])=>{
      const p0=proj(0,0,0), p1=proj(x,y,z);
      lnC(p0[0],p0[1],p1[0],p1[1],c);
    });
    // point cloud dots (8x8 on a tilted plane)
    for(let ri=0;ri<8;ri++) for(let ci=0;ci<8;ci++){
      const px_=(ci-3.5)*80, pz=(ri-3.5)*80;
      const py_=-px_*Math.sin(parseFloat(tiltX)*Math.PI/180)*0.3+Math.sin(t*0.05+ri*ci)*8;
      const [sx,sy]=proj(px_,py_,pz);
      ctx.fillStyle=K.DIM; ctx.fillRect(sx-1,sy-1,2,2);
    }
    // fitted plane AMBER quad
    const plCorners=[[-400,-20,-400],[-400,-20,400],[400,-20,400],[400,-20,-400]].map(([x,y,z])=>proj(x,y,z));
    ctx.strokeStyle=K.AMB; ctx.lineWidth=1; ctx.beginPath();
    ctx.moveTo(plCorners[0][0],plCorners[0][1]);
    plCorners.forEach(p=>ctx.lineTo(p[0],p[1]));
    ctx.closePath(); ctx.stroke();
    // normal arrow GREEN with circle tip
    const tipP=proj(0,-350,0);
    lnC(VIZ_CX,VIZ_CY,tipP[0],tipP[1],K.G);
    fc(tipP[0],tipP[1],5,K.G);
  }

  function drawTof(t, tab) {
    fr(0,0,240,320,K.BG);
    drawHeader('TOF IMAGER');
    if(tab===0) drawTofGrid(t);
    else if(tab===1) drawTofAngl(t);
    else if(tab===2) drawTofDist(t);
    else drawTofNrml(t);
    drawTabBar(['GRID','ANGL','DIST','NRML'],tab);
  }

  // ── IMU/Attitude screen ──
  function drawImuCube(t) {
    const CX=120,CY=154,SZ=62;
    const rx=t*0.012, ry=t*0.018, rz=t*0.007;
    const cos=Math.cos,sin=Math.sin;
    function rot([x,y,z]) {
      let nx=x,ny=y*cos(rx)-z*sin(rx),nz=y*sin(rx)+z*cos(rx);
      [nx,nz]=[nx*cos(ry)+nz*sin(ry),-nx*sin(ry)+nz*cos(ry)];
      [nx,ny]=[nx*cos(rz)-ny*sin(rz),nx*sin(rz)+ny*cos(rz)];
      return [nx,ny,nz];
    }
    const verts=[[-1,-1,-1],[-1,-1,1],[-1,1,-1],[-1,1,1],[1,-1,-1],[1,-1,1],[1,1,-1],[1,1,1]].map(v=>rot(v));
    const prj=v=>[CX+v[0]*SZ/(v[2]+4),CY+v[1]*SZ/(v[2]+4)];
    const edges=[[0,1],[0,2],[0,4],[1,3],[1,5],[2,3],[2,6],[3,7],[4,5],[4,6],[5,7],[6,7]];
    ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    edges.forEach(([a,b])=>{const pa=prj(verts[a]),pb=prj(verts[b]);ctx.beginPath();ctx.moveTo(pa[0],pa[1]);ctx.lineTo(pb[0],pb[1]);ctx.stroke();});
    ctx.strokeStyle=K.G;
    edges.slice(9).forEach(([a,b])=>{const pa=prj(verts[a]),pb=prj(verts[b]);ctx.beginPath();ctx.moveTo(pa[0],pa[1]);ctx.lineTo(pb[0],pb[1]);ctx.stroke();});
    hl(0,248,240,K.SEP);
    const roll=(Math.sin(t*0.012)*45).toFixed(1),pitch=(Math.sin(t*0.018)*30).toFixed(1),yaw=((t*0.007*180/Math.PI)%360).toFixed(1);
    ctxt(`R:${roll>=0?'+':''}${roll}`,60,253,1,K.G);
    ctxt(`P:${pitch>=0?'+':''}${pitch}`,120,253,1,K.AMB);
    ctxt(`Y:${parseFloat(yaw).toFixed(1)}`,180,253,1,K.DIM);
    ctxt('ROLL / PITCH / YAW',120,265,1,K.FAINT);
  }

  function drawImuPlmb(t) {
    const CX=120,CY=154,R=80,MD=66,BR=9;
    ctx.save(); ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    ctx.beginPath(); ctx.arc(CX,CY,R,0,Math.PI*2); ctx.stroke();
    ctx.beginPath(); ctx.arc(CX,CY,R-8,0,Math.PI*2); ctx.stroke();
    ctx.restore();
    // tick marks
    for(let a=0;a<360;a+=30){
      const r=a*Math.PI/180;
      const ox=Math.cos(r),oy=Math.sin(r);
      lnC(CX+ox*(R-8),CY+oy*(R-8),CX+ox*R,CY+oy*R,K.DIM);
    }
    hl(CX-R+6,CY,2*(R-6)+1,K.DIM); vl(CX,CY-R+6,2*(R-6)+1,K.DIM);
    const bx=MD*0.35*Math.sin(t/95),by=MD*0.35*Math.cos(t/75);
    const level=Math.sqrt(bx*bx+by*by)<10;
    fc(Math.round(CX+bx),Math.round(CY+by),BR,level?K.G:K.RED);
    fc(Math.round(CX+bx)-3,Math.round(CY+by)-3,3,K.WHT);
    hl(0,248,240,K.SEP);
    const rollV=(bx/MD*40).toFixed(1),pitchV=(by/MD*40).toFixed(1);
    ctxt(`X: ${rollV>=0?'+':''}${rollV}°   Y: ${pitchV>=0?'+':''}${pitchV}°`,120,255,1,K.G);
    ctxt(level?'LEVEL':'TILTED',120,268,1,level?K.G:K.RED);
  }

  // Push new sample to scope buffer each tick
  function tickScope(t) {
    _scopeBuf[0][_scopeHead]=Math.sin(t*0.012)*45;            // Roll
    _scopeBuf[1][_scopeHead]=Math.sin(t*0.018+1.0)*30;        // Pitch
    _scopeBuf[2][_scopeHead]=(t*0.007*180/Math.PI)%360-180;  // Yaw (centred)
    _scopeHead=(_scopeHead+1)%SCOPE_SAMPLES;
  }

  function drawScopeFrame() {
    // SCOPE_Y0=46, SCOPE_LANE_H=78, 3 lanes
    const SCOPE_Y0=46, LH=78;
    const LANES=[{lbl:'R',col:K.G},{lbl:'P',col:K.AMB},{lbl:'Y',col:K.DIM}];
    const RANGES=[90,60,180];
    // lane separators
    hl(0,SCOPE_Y0+LH,240,K.FAINT);
    hl(0,SCOPE_Y0+LH*2,240,K.FAINT);
    // mid-lane guides
    [SCOPE_Y0+LH/2, SCOPE_Y0+LH+LH/2, SCOPE_Y0+LH*2+LH/2].forEach(my=>{
      hl(0,Math.round(my),240,K.FAINT);
    });
    // Legend squares at x=178
    LANES.forEach(({lbl,col},i)=>{
      fr(178,32+i*10,6,6,col);
      ctx.save(); ctx.fillStyle=col; ctx.font='8px "Courier New",monospace';
      ctx.textBaseline='top'; ctx.fillText(lbl,186,32+i*10-1); ctx.restore();
    });
    LANES.forEach(({col},li)=>{
      const RANGE=RANGES[li];
      const midY=SCOPE_Y0+li*LH+LH/2;
      ctx.strokeStyle=col; ctx.lineWidth=1; ctx.beginPath();
      for(let x=0;x<240;x++){
        const idx=(_scopeHead-240+x+SCOPE_SAMPLES)%SCOPE_SAMPLES;
        const v=_scopeBuf[li][idx];
        const y=midY - (v/RANGE)*(LH/2-3);
        x===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
      }
      ctx.stroke();
    });
  }

  function drawIMU(t, tab) {
    fr(0,0,240,320,K.BG);
    drawHeader('ATTITUDE',true);
    if(tab===0) drawImuCube(t);
    else if(tab===1) drawImuPlmb(t);
    else drawScopeFrame();
    drawTabBar(['CUBE','PLMB','SCPE'],tab);
  }

  // ── Battery screen ──
  function drawBattery(t) {
    fr(0,0,240,320,K.BG);
    drawHeader('BATTERY');
    const pct=Math.round(72+8*Math.sin(t/200));
    const col=pct>30?K.G:K.RED;
    // "CHARGE LEVEL" label
    ctxt('CHARGE LEVEL',120,58,1,K.DIM);
    // Rounded rect shell
    const BX=10,BY=72,BW=196,BH=46,BR=5;
    ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    ctx.beginPath(); ctx.roundRect(BX,BY,BW,BH,BR); ctx.stroke();
    // tip nub
    fr(206,86,8,18,K.DIM);
    // fill bar
    const fillW=Math.round((BW-8)*pct/100);
    if(fillW>0){ ctx.save(); ctx.beginPath(); ctx.roundRect(BX+4,BY+4,BW-8,BH-8,BR-2); ctx.clip(); fr(BX+4,BY+4,fillW,BH-8,col); ctx.restore(); }
    // VOLTAGE
    ctxt('VOLTAGE',120,128,2,K.DIM);
    ctxt('3.84 V',120,146,4,K.G);
    // REMAINING
    ctxt('REMAINING',120,180,2,K.DIM);
    ctxt(`${Math.round(pct*18)}/1800 mAh`,120,198,2,K.G);
    // separator
    hl(8,220,224,K.SEP);
    // CHARGE
    ctxt('CHARGE',120,228,2,K.DIM);
    ctxt(`${pct}%`,120,246,4,col);
  }

  // ── Settings screen ──
  function drawSettings() {
    fr(0,0,240,320,K.BG);
    drawHeader('SETTINGS');
    // Layout constants matching firmware
    const ARROW_W=52, ROW_H=46, HDR_H=22;
    const sections=[
      {hdr:'DETECTION',  items:[['MAX RANGE','4000 MM','max detect dist'],['SENSITIVITY','MED','target filter level']]},
      {hdr:'GEOMETRY',   items:[['FOV ANGLE','55 DEG','radar sweep angle']]},
      {hdr:'DISPLAY',    items:[['BRIGHTNESS','100%','screen brightness'],['THEME','GREEN','color theme']]},
      {hdr:'POWER',      items:[['SLEEP TIME','60 SEC','idle sleep delay']]},
    ];
    let y=28;
    sections.forEach(sec=>{
      if(y+HDR_H>270) return;
      // header row: AMBER underline + AMBER centred label
      fr(0,y,240,HDR_H,K.BG);
      hl(0,y+HDR_H-1,240,K.AMB);
      ctxt(sec.hdr,120,y+6,1,K.AMB);
      y+=HDR_H;
      sec.items.forEach(([lbl,val,desc])=>{
        if(y+ROW_H>270) return;
        fr(0,y,240,ROW_H,K.BG);
        hl(0,y+ROW_H-1,240,K.SEP);
        // vertical dividers
        vl(ARROW_W,y+2,ROW_H-4,K.SEP);
        vl(240-ARROW_W,y+2,ROW_H-4,K.SEP);
        // arrow buttons
        ctxt('<',26,y+ROW_H/2-6,2,K.DIM);
        ctxt('>',240-26,y+ROW_H/2-6,2,K.DIM);
        // label + desc
        txt(lbl,ARROW_W+8,y+6,1,K.DIM);
        txt(desc,ARROW_W+8,y+18,1,K.FAINT);
        // value centred
        ctxt(val,120,y+ROW_H/2-6,2,K.G);
        y+=ROW_H;
      });
    });
    // RESET DEFAULTS button at bottom
    const ry=270;
    dr(16,ry+7,208,26,K.RED);
    ctxt('RESET DEFAULTS',120,ry+14,2,K.RED);
  }

  // ── 3D Map pre-generated room point cloud ──
  const _mapPts=(function(){
    const pts=[]; const N=400; const ROOM=300;
    // 6 faces of a box: ceiling,floor,left,right,front,back
    for(let i=0;i<N;i++){
      const u=(Math.random()-0.5)*2*ROOM, v=(Math.random()-0.5)*2*ROOM;
      const face=Math.floor(Math.random()*6);
      let p;
      if(face===0) p=[u,  ROOM,v];   // ceiling
      else if(face===1) p=[u,-ROOM,v]; // floor
      else if(face===2) p=[-ROOM,u,v]; // left
      else if(face===3) p=[ ROOM,u,v]; // right
      else if(face===4) p=[u,v,  ROOM]; // front
      else              p=[u,v,-ROOM];  // back
      pts.push(p);
    }
    return pts;
  })();

  // Iron colormap by depth
  function ironColor(v) {
    v=Math.max(0,Math.min(1,v));
    if(v<0.33)  { const f=v/0.33; return `rgb(${Math.round(f*200)},0,${Math.round(f*80)})`; }
    if(v<0.66)  { const f=(v-0.33)/0.33; return `rgb(${Math.round(200+f*55)},${Math.round(f*160)},${Math.round(80*(1-f))})`; }
    const f=(v-0.66)/0.34; return `rgb(255,${Math.round(160+f*95)},${Math.round(f*255)})`;
  }

  function drawMap3d(t) {
    fr(0,0,240,320,K.BG);
    drawHeader('3D MAP');
    const VIEW_Y=28, VIEW_H=244, VIEW_CX=120, VIEW_CY=150, FOCAL=200;
    // Rotate Y axis slowly
    const ry=t*0.006;
    const cosY=Math.cos(ry), sinY=Math.sin(ry);
    // Collect projected points with depth
    const projected=[];
    _mapPts.forEach(([px,py,pz])=>{
      const rx=px*cosY+pz*sinY, rz=-px*sinY+pz*cosY;
      const depth=rz+600;
      if(depth<10) return;
      const sx=VIEW_CX+rx*FOCAL/depth;
      const sy=VIEW_CY+py*FOCAL/depth;
      if(sy<VIEW_Y||sy>VIEW_Y+VIEW_H||sx<0||sx>240) return;
      projected.push({sx,sy,depth});
    });
    // Sort back to front
    projected.sort((a,b)=>b.depth-a.depth);
    projected.forEach(({sx,sy,depth})=>{
      const v=1-Math.min(1,(depth-10)/900);
      ctx.fillStyle=ironColor(v);
      ctx.fillRect(Math.round(sx)-1,Math.round(sy)-1,2,2);
    });
    // CLEAR button
    hl(8,272,224,K.SEP);
    fr(8,279,224,32,K.BG);
    dr(8,279,224,32,K.DIM);
    ctxt('CLEAR',120,289,2,K.DIM);
  }

  // ── Surveyor screen ──
  // Surface colors matching firmware RGB565→CSS
  const SURF_COLS=['#00FFFF','#848484','#FF8000','#0000FF','#00FF00','#FF0000'];
  const SURF_NAMES=['CEILING','FLOOR','LEFT','RIGHT','FRONT','BACK'];
  // Captured flags (simulated)
  const _survCap=[true,true,false,false,false,false];

  function drawSurveyor(t) {
    fr(0,0,240,320,K.BG);
    drawHeader('SURVEYOR');
    // INFO bar
    const INFO_Y=28, INFO_H=16;
    fr(0,INFO_Y,240,INFO_H,K.BG);
    ctxt('ROOM DIMENSIONS',120,INFO_Y+3,1,K.DIM);
    hl(0,INFO_Y+INFO_H-1,240,K.SEP);
    // 6 surface buttons in 3×2 grid (BTN_Y=44, BTN_ROW_H=36, 3 rows)
    const BTN_Y=44, BTN_ROW_H=36;
    for(let i=0;i<6;i++){
      const col=i%2, row=Math.floor(i/2);
      const bx=col===0?0:120, bw=120, by=BTN_Y+row*BTN_ROW_H, bh=BTN_ROW_H;
      const sc=SURF_COLS[i], cap=_survCap[i];
      fr(bx,by,bw,bh,cap?'#0a0a0a':K.BG);
      dr(bx,by,bw,bh,cap?sc:K.DIM);
      ctx.save(); ctx.fillStyle=cap?sc:K.DIM; ctx.font='8px "Courier New",monospace';
      ctx.textBaseline='middle'; ctx.textAlign='center';
      ctx.fillText(SURF_NAMES[i],bx+bw/2,by+bh/2); ctx.restore();
    }
    // CAPTURE + CLEAR ALL at CLR_Y=152
    const CLR_Y=152, CLR_H=24;
    dr(4,CLR_Y,140,CLR_H,K.G); ctxt('CAPTURE',74,CLR_Y+7,1,K.G);
    dr(152,CLR_Y,84,CLR_H,K.DIM); ctxt('CLEAR ALL',194,CLR_Y+7,1,K.DIM);
    hl(0,CLR_Y+CLR_H,240,K.SEP);
    // 3D wireframe box  VIZ_Y=176, VIZ_CX=120, VIZ_CY=248
    const VIZ_Y=177, VIZ_CX=120, VIZ_CY=248, VIZ_H=143;
    fr(0,VIZ_Y,240,VIZ_H,K.BG);
    // 8 corners of room box
    const W2=80,H2=50,D2=60;
    const corners=[
      [-W2,-H2,-D2],[ W2,-H2,-D2],[ W2, H2,-D2],[-W2, H2,-D2],
      [-W2,-H2, D2],[ W2,-H2, D2],[ W2, H2, D2],[-W2, H2, D2],
    ];
    // view rotation: yaw=0.55+slow spin, pitch=-0.4
    const yaw=0.55+t*0.004, pitch=-0.4;
    const cy=Math.cos(yaw),sy2=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
    function projRoom(x,y,z){
      const x2=x*cy-z*sy2, z2=x*sy2+z*cy;
      const y2=y*cp-z2*sp, z3=y*sp+z2*cp;
      const FOCAL=220;
      return [VIZ_CX+x2*FOCAL/(z3+300), VIZ_CY+y2*FOCAL/(z3+300)];
    }
    const pts2d=corners.map(([x,y,z])=>projRoom(x,y,z));
    const wireEdges=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
    ctx.strokeStyle=K.DIM; ctx.lineWidth=1;
    wireEdges.forEach(([a,b])=>{
      if(pts2d[a][1]>VIZ_Y&&pts2d[b][1]>VIZ_Y){
        ctx.beginPath(); ctx.moveTo(pts2d[a][0],pts2d[a][1]); ctx.lineTo(pts2d[b][0],pts2d[b][1]); ctx.stroke();
      }
    });
    // User dot at origin
    const userP=projRoom(0,0,0);
    fc(userP[0],userP[1],4,K.G);
  }

  // ── Power screen ──
  function drawPower() {
    fr(0,0,240,320,K.BG);
    dr(2,2,236,316,K.RED); dr(4,4,232,312,K.RED);
    ctxt('POWER',120,55,4,K.RED);
    ctxt('OPTIONS',120,90,4,K.RED);
    // RESTART – AMBER
    dr(20,148,200,44,K.AMB); dr(22,150,196,40,K.AMB);
    ctxt('[ RESTART ]',120,162,2,K.AMB);
    ctxt('rescans all devices',120,185,1,K.FAINT);
    // POWER OFF – RED
    dr(20,204,200,44,K.RED); dr(22,206,196,40,K.RED);
    ctxt('[ POWER OFF ]',120,218,2,K.RED);
    ctxt('tap screen to wake',120,241,1,K.FAINT);
    // CANCEL – GREEN_DIM
    dr(20,260,200,44,K.DIM); dr(22,262,196,40,K.DIM);
    ctxt('[ CANCEL ]',120,274,2,K.DIM);
  }

  // ── Click handler ──
  function handleClick(x,y) {
    if(screen==='loading') return;
    if(screen==='menu'){
      if(x>=12&&x<=228&&y>=160&&y<=204)  { screen='radar';    t=0; lastScreen=''; return; }
      if(x>=8 &&x<=116&&y>=206&&y<=236)  { screen='map3d';    t=0; lastScreen=''; return; }
      if(x>=120&&x<=228&&y>=206&&y<=236) { screen='surveyor'; t=0; lastScreen=''; return; }
      if(x>=8 &&x<=116&&y>=238&&y<=264)  { screen='tof'; subTab=0; t=0; lastScreen=''; return; }
      if(x>=120&&x<=228&&y>=238&&y<=264) { screen='imu'; subTab=0; t=0; lastScreen=''; return; }
      if(x>=8 &&x<=116&&y>=266&&y<=290)  { screen='settings'; t=0; lastScreen=''; return; }
      if(x>=120&&x<=228&&y>=266&&y<=290) { screen='battery';  t=0; lastScreen=''; return; }
      if(x>=40&&x<=200&&y>=294&&y<=310)  { screen='power';    t=0; lastScreen=''; return; }
      return;
    }
    // < MENU header button
    if(x>=3&&x<=67&&y>=3&&y<=25) { screen='menu'; t=0; lastScreen=''; return; }
    // Power screen buttons
    if(screen==='power'){
      if(x>=20&&x<=220&&y>=148&&y<=192) { screen='loading'; loadPct=0; t=0; lastScreen=''; return; } // RESTART
      if(x>=20&&x<=220&&y>=204&&y<=248) { screen='loading'; loadPct=0; t=0; lastScreen=''; return; } // POWER OFF
      if(x>=20&&x<=220&&y>=260&&y<=304) { screen='menu';    t=0; lastScreen=''; return; }            // CANCEL
      return;
    }
    // TOF ANGL button
    if(screen==='tof'&&subTab===1&&y>=236&&y<=280){
      anglState=(anglState+1)%3; return;
    }
    // Tab bars
    if(screen==='tof'&&y>=280) { subTab=Math.min(3,Math.floor(x/60)); lastSubTab=-1; return; }
    if(screen==='imu'&&y>=280) { subTab=Math.min(2,Math.floor(x/80)); lastSubTab=-1; return; }
    // Map3d CLEAR
    if(screen==='map3d'&&x>=8&&x<=232&&y>=279&&y<=311) { t=0; return; }
  }

  canvas.addEventListener('click', e=>{
    const rect=canvas.getBoundingClientRect();
    handleClick((e.clientX-rect.left)*(240/rect.width),(e.clientY-rect.top)*(320/rect.height));
  });
  canvas.style.cursor='pointer';

  // ── Main loop ──
  function loop() {
    t++;
    if(screen==='loading'){
      loadPct=Math.min(100,loadPct+1.2);
      drawLoading();
      if(loadPct>=100) setTimeout(()=>{if(screen==='loading'){screen='menu';lastScreen='';}},300);
    } else if(screen==='menu'){
      if(lastScreen!=='menu'){ drawMenu(); lastScreen='menu'; }
    } else if(screen==='radar') {
      drawRadar(t);
    } else if(screen==='tof') {
      if(subTab===1) tickScope(t); // reuse scope buffer for ANGL animation
      drawTof(t,subTab);
      lastScreen='tof'; lastSubTab=subTab;
    } else if(screen==='imu') {
      if(subTab===2) tickScope(t);
      drawIMU(t,subTab);
      lastScreen='imu'; lastSubTab=subTab;
    } else if(screen==='battery') {
      drawBattery(t);
    } else if(screen==='settings') {
      if(lastScreen!=='settings'){ drawSettings(); lastScreen='settings'; }
    } else if(screen==='map3d') {
      drawMap3d(t);
    } else if(screen==='surveyor') {
      drawSurveyor(t);
    } else if(screen==='power') {
      if(lastScreen!=='power'){ drawPower(); lastScreen='power'; }
    }
    _esDemoRAF=requestAnimationFrame(loop);
  }
  loop();
}


// ══════════════════════════════════════════
// CODEC MAIN SCREEN
// Frequencies are sections; the MEMORY panel is the readable menu.
// The Colonel talks with real ripped frames, mouth driven by visemes.
// ══════════════════════════════════════════
const CX_F = n => `${STATIC_URLS.codecBase}/campbell_f${n}.png`;
const SN_F = n => `${STATIC_URLS.codecBase}/snake_f${n}.png`;
// Two codec speakers, each with a neutral face and a closed/half/open/wide
// viseme set of real ripped frames. Lines choose their speaker; default is
// the Colonel. (Left portrait = colonel, right = snake.)
const CX_SPEAKERS = {
  colonel: { imgId: 'campbell', neutral: CX_F('00'),
             pose: [CX_F('10'), CX_F('09'), CX_F('08'), CX_F('08')] },
  snake:   { imgId: 'snake',    neutral: SN_F('00'),
             pose: [SN_F('00'), SN_F('02'), SN_F('07'), SN_F('08')] },
};
let cxSpeaker = CX_SPEAKERS.colonel;

const CX_CONTACTS = [
  { freq:'140.85', name:'COLONEL',
    lines:["Snake, this is Nick Burczyk. A software engineer who dabbles in audio, vision, and embedded systems. He's currently stationed at Sandia National Labs as a TITANS software R&D intern.",
           "Everything we've gathered on him is laid out on this codec. For specific information look through different channels, or open MEMORY for the full contact list."],
    render(){ CMDS.about(); } },
  { freq:'141.12', name:'PROJECTS',
    lines:["His operation records. Twelve declassified projects on file.",
           "Select a target below for the full briefing."],
    render(){ cxRenderProjectIndex(); } },
  { freq:'141.52', name:'MUSIC',
    lines:["He also records as Zero Barbecue. A one-man operation.",
           "First single's out now. Listen below."],
    render(){ CMDS.music(); } },
  { freq:'140.07', name:'MC WORLD',
    lines:["A private Minecraft world: custom modpack, custom server.",
           "We gathered enough information to make a 3D reconstruction. The map below is rendering live."],
    render(){ cxRenderMinecraft(); } },
  { freq:'140.15', name:'CONTACT',
    lines:["These are his direct channels. They're secure. Use them.",
           { text:"Got it. I'll make contact.", speaker:'snake' }],
    render(){ CMDS.contact(); } },
];
let cxIdx = 0;
let cxBooted = false;

// ── talking: typewriter + Qwen3-TTS voice lines + viseme mouth ──
// Each line may carry a voice key (static/audio/codec/<key>.m4a). Typing
// drives the mouth; if the voice runs past the typing, the mouth keeps
// flapping until the audio ends. The next line waits for both.
let cxLastFrame = 0, cxLastSwap = 0, cxTypeTimer = null, cxFlapTimer = null;
let cxQueue = [], cxCurrentLine = '', cxVoice = null;
// extra per-line typing lead (ms before audio end that typing finishes)
const CX_TYPE_LEAD = { 'c0_l1': 1500 };
// One reusable element for all voice lines. It gets 'unlocked' during the
// SELECT click (Safari only allows play() from a user gesture until an
// element has played once), then plays freely for the rest of the session.
const cxVoiceEl = new Audio();
function cxUnlockVoice(){
  cxVoiceEl.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQIAAACAgA==';
  cxVoiceEl.play().catch(() => {});
}
let cxTypeDone = true, cxVoiceDone = true, cxAdvanceTimer = null;

// ── signal-meter VU: wedge reacts to the voice via a precomputed amplitude
// envelope, synced by playback time (no rerouting of the audio element) ──
let cxBarEls = [], cxMeterRAF = null, cxEnvCache = {};
function cxLoadEnvelope(key){
  if (cxEnvCache[key] !== undefined) return Promise.resolve(cxEnvCache[key]);
  return fetch(`${STATIC_URLS.voiceBase}/${key}.m4a`)
    .then(r => r.arrayBuffer())
    .then(b => getAudioCtx().decodeAudioData(b))
    .then(audio => {
      const data = audio.getChannelData(0);
      const hop = Math.max(1, Math.floor(audio.sampleRate * 0.03));  // 30ms frames
      const env = [];
      for (let i = 0; i < data.length; i += hop){
        let s = 0, n = 0;
        for (let j = i; j < i + hop && j < data.length; j++){ s += data[j] * data[j]; n++; }
        env.push(Math.sqrt(s / (n || 1)));
      }
      let peak = 0.0001;
      for (const v of env) if (v > peak) peak = v;
      const e = { frames: env.map(v => v / peak), step: 0.03 };
      cxEnvCache[key] = e;
      return e;
    })
    .catch(() => { cxEnvCache[key] = null; return null; });
}
function cxMeterStart(key){
  if (!cxBarEls.length) return;
  cxLoadEnvelope(key).then(env => {
    if (cxMeterRAF) cancelAnimationFrame(cxMeterRAF);
    const loop = () => {
      if (!cxVoice || cxVoice.paused || cxVoice.ended){ cxMeterStop(); return; }
      let level = 0.45;
      if (env){ const idx = Math.min(env.frames.length - 1, Math.floor(cxVoice.currentTime / env.step)); level = env.frames[idx] || 0; }
      // fill from the bottom up: loud speech lights higher bars, quiet leaves
      // only the bottom lit — bottom is lit most, top least
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
  cxBarEls.forEach(el => { el.style.opacity = el._base; });   // idle: bottom-bright gradient
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
  const img = document.getElementById(cxSpeaker.imgId);
  if (!img) return;
  const v = cxViseme(ch);
  const now = performance.now();
  if (v === cxLastFrame) return;
  if (v !== 0 && now - cxLastSwap < 60) return;
  cxLastFrame = v; cxLastSwap = now;
  img.src = cxSpeaker.pose[v];
}
function cxRest(){
  // both portraits back to neutral so a speaker swap never leaves a stuck mouth
  Object.values(CX_SPEAKERS).forEach(sp => {
    const img = document.getElementById(sp.imgId);
    if (img) img.src = sp.neutral;
  });
  cxLastFrame = 0;
}
function cxStopVoice(){
  if (cxVoice) { cxVoice.pause(); cxVoice = null; }
  if (cxFlapTimer) { clearInterval(cxFlapTimer); cxFlapTimer = null; }
  cxMeterStop();
  cxVoiceDone = true;
}
function cxHardStop(){
  if (cxTypeTimer) { clearInterval(cxTypeTimer); cxTypeTimer = null; }
  if (cxAdvanceTimer) { clearTimeout(cxAdvanceTimer); cxAdvanceTimer = null; }
  cxStopVoice();
  cxQueue = [];
  cxTypeDone = true;
  cxRest();
}
function cxStartFlap(){
  // voice is still speaking after the text finished: keep the mouth going
  if (cxFlapTimer) return;
  cxFlapTimer = setInterval(() => {
    const img = document.getElementById(cxSpeaker.imgId);
    if (!img) return;
    let n;
    do { n = Math.random() < 0.3 ? 0 : 1 + Math.floor(Math.random() * 3); }
    while (n === cxLastFrame);
    cxLastFrame = n;
    img.src = cxSpeaker.pose[n];
  }, 110);
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
  cxTypeDone = false;
  cxStopVoice();
  cxRest();
  dlg.textContent = '';
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
    // pace the typewriter to the voice: finish typing ~0.5s before the
    // audio ends, however long the clip actually is
    a.onloadedmetadata = (() => {
      if (!cxTypeTimer || cxTypeDone || !isFinite(a.duration)) return;
      // finish typing ahead of the audio ending, so the text leads the
      // voice like subtitles. Per-line leads can be tuned in CX_TYPE_LEAD.
      const lead = CX_TYPE_LEAD[item.key] || 1000;
      const remainMs = a.duration * 1000 - (performance.now() - startedAt) - lead;
      const remainChars = cxCurrentLine.length - i;
      if (remainChars > 0 && remainMs > 200) {
        startTicking(Math.min(38, Math.max(10, remainMs / remainChars)));
      }
    });
    a.onended = () => {
      if (cxFlapTimer) { clearInterval(cxFlapTimer); cxFlapTimer = null; }
      cxMeterStop();
      cxVoiceDone = true; cxMaybeAdvance();
    };
    a.onerror = () => { cxVoiceDone = true; cxMaybeAdvance(); };
    a.src = `${STATIC_URLS.voiceBase}/${item.key}.m4a`;
    const vkey = item.key;
    a.play().then(() => cxMeterStart(vkey)).catch(() => { cxVoiceDone = true; });   // file missing: text-only
  }
}
function cxSay(lines, keys){
  cxHardStop();
  cxQueue = lines.map((l, i) => {
    const o = typeof l === 'string' ? { text: l } : l;
    return { text: o.text, key: keys && keys[i],
             speaker: CX_SPEAKERS[o.speaker] || CX_SPEAKERS.colonel };
  });
  cxTypeNext();
}
function skipTyping(){
  const dlg = document.getElementById('cx-dialogue');
  if (!dlg) return;
  if (cxTypeTimer) {
    // finish the text instantly and cut the voice: he goes quiet
    // until the next line starts
    clearInterval(cxTypeTimer); cxTypeTimer = null;
    dlg.textContent = cxCurrentLine;
    cxTypeDone = true;
    cxStopVoice();
    cxRest();
    cxMaybeAdvance();
  } else if (cxQueue.length) {
    // jump to the next line, cutting off the current voice
    if (cxAdvanceTimer) { clearTimeout(cxAdvanceTimer); cxAdvanceTimer = null; }
    cxStopVoice();
    cxTypeNext();
  } else if (!cxVoiceDone) {
    // text done, voice still going: silence him
    cxStopVoice();
    cxRest();
  }
}

// ── tuning ──
function cxOpenContact(i){
  cxIdx = (i + CX_CONTACTS.length) % CX_CONTACTS.length;
  const c = CX_CONTACTS[cxIdx];
  cxHardStop();                 // silence any previous line immediately
  document.getElementById('freq-num').textContent = c.freq;
  document.getElementById('cx-contact-name').textContent = c.name;
  // brief static burst on both portraits, like retuning
  ['cx-portrait-l','cx-portrait-r'].forEach(id => {
    const p = document.getElementById(id);
    p.classList.add('static');
    setTimeout(() => p.classList.remove('static'), 280);
  });
  // content renders immediately; dialogue is flavor, not a gate
  out.innerHTML = '';
  const panel = document.getElementById('cx-content');
  panel.classList.remove('visible');
  c.render();
  requestAnimationFrame(() => panel.classList.add('visible'));
  const idx = cxIdx;
  // longer beat on the very first call so the CRT power-on lands first
  const delay = cxBooted ? 320 : 2000;
  cxBooted = true;
  setTimeout(() => {
    if (idx !== cxIdx) return;  // user already retuned
    cxSay(c.lines, c.lines.map((_, j) => `c${idx}_l${j}`));
  }, delay);
  cxUpdateMemoryHighlight();
}
function tuneStep(dir){
  playClickSound();
  cxOpenContact(cxIdx + dir);
}

// ── memory panel (the readable menu) ──
function cxBuildMemory(){
  const list = document.getElementById('cx-mem-list');
  if (!list) return;
  list.innerHTML = '';
  CX_CONTACTS.forEach((c, i) => {
    const b = document.createElement('button');
    b.className = 'cx-mem-row';
    b.innerHTML = `<span class="cx-mem-freq">${c.freq}</span><span class="cx-mem-name">${c.name}</span>`;
    b.onclick = () => { playClickSound(); cxOpenContact(i); toggleMemory(false); };
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
}

// ── section content ──
function cxRenderProjectIndex(){
  addHtml(`<div class="fade-in">${PROJECTS.map((p, i) => `
    <button class="cx-proj-row" onclick="cxOpenProject('${p.id}')">
      <span class="cx-proj-freq">141.${String(13 + i).padStart(2,'0')}</span>
      <span class="cx-proj-name">${esc(p.name)}</span>
      ${(p.tags||[]).map(t=>`<span class="tag ${TAG_CLASS[t]||''}">${esc(t)}</span>`).join('')}
    </button>`).join('')}</div>`);
}
function cxOpenProject(id){
  playClickSound();
  out.innerHTML = '';
  addHtml(`<button class="cx-back-row" onclick="cxBackToProjects()">◂ ALL PROJECTS</button>`);
  CMDS.project(id);
  document.getElementById('cx-content').scrollIntoView({ behavior:'smooth', block:'start' });
  const p = PROJECTS.find(x => x.id === id);
  // projects open silently: no dialogue, no voice
  cxHardStop();
  const dlg = document.getElementById('cx-dialogue');
  if (dlg) dlg.textContent = '';
}
function cxBackToProjects(){
  playClickSound();
  out.innerHTML = '';
  cxRenderProjectIndex();
}
function cxRenderMinecraft(){
  CMDS.map();
  addHtml(`<div style="padding:0 20px 8px;">
    <a class="proj-link" href="${STATIC_URLS.gallery}">→ SCREENSHOT GALLERY: ALL SEASONS</a>
  </div>`);
}

// ── init ──
function initCodec(){
  // preload talk frames
  Object.values(CX_SPEAKERS).forEach(sp =>
    [sp.neutral, ...sp.pose].forEach(src => { const im = new Image(); im.src = src; }));
  // signal meter: dense stack of horizontal bars whose lengths follow a
  // concave (log-like) curve, top bar longest — matches the real codec
  const bars = document.getElementById('cx-bars');
  cxBarEls = [];   // ordered top -> bottom
  // concave curve: one long bar at the top, dropping fast then leveling off
  const widths = [58, 52, 47, 43, 40, 37, 35, 34, 33, 32, 31, 30, 29];
  if (bars) widths.forEach((w) => {
    const s = document.createElement('span');
    s.style.width = w + 'px';
    s._base = 0.28;                 // dim at rest; bars light up with the audio
    s.style.opacity = s._base;
    bars.appendChild(s);
    cxBarEls.push(s);
  });
  cxBuildMemory();
  document.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft')  tuneStep(-1);
    if (e.key === 'ArrowRight') tuneStep(1);
    if (e.key === 'm' || e.key === 'M') toggleMemory();
    if (e.key === 'Escape') toggleMemory(false);
  });
  cxOpenContact(0);
}