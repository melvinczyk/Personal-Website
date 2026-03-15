const PROJECTS = [
  { id:"oculosaurus", name:"OCULOSAURUS", badge:"1ST PLACE", bc:"award", tech:"Python / OpenCV / Raspberry Pi / YOLO", img:"https://github.com/melvinczyk/Personal-Website/raw/main/my_website/static/images/oculosarus_example.gif", img2:"https://github.com/melvinczyk/Personal-Website/raw/main/my_website/static/images/CS499OculosarusProject-1.png", desc:"Stereo vision system to assist visually impaired individuals with real-time depth perception. Distributed architecture: Raspberry Pi goggles, cloud compute, mobile notifications. Features live 3D point cloud visualization, proximity warnings, and optional YOLO object recognition.", link:"https://github.com/melvinczyk/StereoCamera-DepthObjectEstimator"},
  { id:"waste-drone", name:"WASTE DETECTION DRONE", badge:"CV", bc:"", tech:"Python / YOLOv5 / Tello SDK", img:"https://github.com/melvinczyk/Waste-detection-drone/raw/main/images/Medium%20model%20frame.png", img2:"https://github.com/melvinczyk/Personal-Website/raw/main/my_website/static/images/model_%20copy.gif", desc:"Autonomous drone for environmental waste monitoring. Custom YOLOv5 model trained on annotated waste datasets. Programmatic flight via Tello SDK with precision navigation, telemetry logging, and automated spatial classification.", link:"https://github.com/melvinczyk/Waste-detection-drone"},
  { id:"bird-classifier", name:"BACKYARD BIRD CLASSIFIER", badge:"LIVE", bc:"live", tech:"Python / CNN / Django / mel-spectrogram", img:"https://github.com/melvinczyk/Personal-Website/raw/main/my_website/static/images/predict.png", img2:"https://github.com/melvinczyk/Personal-Website/raw/main/my_website/static/images/Confusion_matrix.png", desc:"Audio classification CNN identifying 30 Alabama bird species from calls. Applied to mel-spectrograms. Full-stack Django web app: upload a bird call, see the species prediction, top-5 guesses, and a spectrogram visualization.", link:"https://github.com/melvinczyk/Bird-Classifier"},
  { id:"modpack-updater", name:"MINECRAFT MODPACK UPDATER", badge:"TOOL", bc:"", tech:"Java / JavaFX / Amazon S3 / Gradle", img:"https://github.com/user-attachments/assets/db32657d-8d6b-49d9-afe8-498cf750cc41", img2:"https://github.com/user-attachments/assets/a06daa21-547a-404c-8c95-eadcb740e267", desc:"Desktop app using Amazon S3 to host and sync Minecraft modpacks across a friend group. Git-style change tracking with a manifest. Admin panel: push updates, view changelogs, track folders, add new packs. One-click update for clients. Cross-platform.", link:"https://github.com/melvinczyk/ModpackUpdater"},
  { id:"visaudio", name:"VISAUDIO", badge:"TOOL", bc:"", tech:"Python / librosa / PyQt", img:"https://github.com/melvinczyk/VisAudio/blob/main/images/menu.png?raw=true", img2:null, desc:"Desktop app for audio file manipulation: format conversion, bitrate resampling, noise reduction, YouTube audio downloader, mel-spectrogram and waveform visualization. Supports mp3, wav, flac, ogg, m4a, aac.", link:"https://github.com/melvinczyk/VisAudio"},
  { id:"fretwatch", name:"FRETWATCH", badge:"IN DEV", bc:"dev", tech:"Python / OpenCV / PyTorch / librosa", img:"https://i.ibb.co/Wn3Jxd2/Screenshot-2024-10-02-at-5-08-12-PM.png", img2:null, desc:"Live guitar note detection from video and audio. Signal processing extracts audio features to detect notes and chords being played. Combines librosa for audio analysis and OpenCV for live video frame manipulation.", link:"https://github.com/melvinczyk/FretWatch"},
  { id:"born-in-spellbooks", name:"BORN IN SPELLBOOKS MOD", badge:"ALPHA", bc:"dev", tech:"Java / Minecraft Forge 1.20.1", img:"https://i.ibb.co/BPCKZhr/2024-10-07-09-39-39.png", img2:null, desc:"Open source Minecraft Forge compatibility mod combining Iron's Spells & Spellbooks with Born In Chaos. 17+ spells coded with custom rendering, animation layering, entity sharing. Three alpha releases.", link:"https://github.com/melvinczyk/Born_in_spellbooks"},
  { id:"personal-website", name:"NICHOLASBURCZYK.COM", badge:"LIVE", bc:"live", tech:"Django / Tailwind CSS / DaisyUI / Python", img:"https://www.svgrepo.com/show/353657/django-icon.svg", img2:null, desc:"This website. Built on Django for a secure backend, Tailwind CSS + DaisyUI for the frontend, and deployed ML model inference for the bird classifier.", link:"https://github.com/melvinczyk/Personal-Website"},
  { id:"minecraft-server", name:"MINECRAFT SERVER & MODPACK", badge:"ONGOING", bc:"", tech:"Java / JSON / mcscript / Linux server admin", img:"https://i.ibb.co/7KCwNZr/minecraft.png", img2:null, desc:"Custom modpack with curated mods, resource & data packs. Server admin: config management, real-time troubleshooting, networking. Custom data packs with JSON/mcscript for custom mobs, biomes, loot tables, and structure generation.", link:"https://github.com/melvinczyk/Datapacks"},
];

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
  if (e.target.matches('button, a, .qbtn, .sb-btn, .sb-proj-btn')) playHoverBeep();
}, true);
document.addEventListener('click', e => {
  if (e.target.matches('button, a, .qbtn, .sb-btn, .sb-proj-btn') && e.target.id !== 'codec-btn') playClickSound();
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
    screen.classList.add('visible');
    playBuffer(openBuffer, 0.7);
    codec.addEventListener('animationend', () => {
      codec.style.display = 'none';
      setTimeout(playBackgroundMusic, 300);
      bootTerminal();
      document.getElementById('cmd-input').focus();
    }, { once: true });
  }, 1800);
}

setInterval(() => {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('en-US',{hour12:false});
}, 1000);

// ══════════════════════════════════════════
// TERMINAL HELPERS
// ══════════════════════════════════════════
let hist=[], hIdx=-1;
const out = document.getElementById('output');
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function ln(html='',cls='line'){const d=document.createElement('div');d.className=`line ${cls} fade-in`;d.innerHTML=html;out.appendChild(d);out.scrollTop=out.scrollHeight;}
function bl(){const d=document.createElement('div');d.className='blank fade-in';out.appendChild(d);out.scrollTop=out.scrollHeight;}
function addHtml(h){const d=document.createElement('div');d.className='fade-in';d.innerHTML=h;out.appendChild(d);out.scrollTop=out.scrollHeight;}
function echo(cmd){ln(`<span style="color:var(--mgs-border)">nick@burczyk:~$</span> <span style="color:var(--mgs-cyan)">${esc(cmd)}</span>`);}

// ══════════════════════════════════════════
// COMMANDS
// ══════════════════════════════════════════
const CMDS = {
help(){
  bl();
  ln('╔══════════════════════════════════════════════════════════╗','green');
  ln('║                  NICK BURCZYK — COMMANDS                        ║','green');
  ln('╚══════════════════════════════════════════════════════════╝','green');
  bl();
  [['whoami','about me'],['ls projects','list all projects'],['cat project [id]','view a project'],['music','Zero Barbecue — Spotify / Bandcamp'],['contact','links and socials'],['map','live Minecraft server map'],['bird-classifier','launch the bird classifier'],['clear','clear terminal'],['help','this menu']].forEach(([c,d])=>{
    ln(`  <span style="color:var(--mgs-cyan);display:inline-block;min-width:200px">${esc(c)}</span><span style="color:var(--mgs-border)">${d}</span>`);
  });
},

whoami(){
  bl();
  addHtml(`<div class="who-card fade-in">
    <div class="who-photo"><img src="https://github.com/melvinczyk/Personal-Website/raw/main/my_website/static/images/nick.jpg" onerror="this.style.display='none'" alt="Nick"></div>
    <div class="who-info">
      <div class="who-name">NICK BURCZYK</div>
      <div class="who-row"><span class="who-key">school</span><span class="who-val">MSCS @ UAB — Spring 2027</span></div>
      <div class="who-row"><span class="who-key">work</span><span class="who-val">Software Developer @ Viper Imaging</span></div>
      <div class="who-row"><span class="who-key">teaching</span><span class="who-val">TA — Software Development @ UAB</span></div>
      <div class="who-row"><span class="who-key">interests</span><span class="who-val">complex software, hardware integration, embedded systems</span></div>
      <div class="who-row"><span class="who-key">learning</span><span class="who-val">C/C++ — embedded, performance computing, low-level work</span></div>
      <div class="who-row"><span class="who-key">music</span><span class="who-val">Zero Barbecue — producer / artist</span></div>
      <div class="who-row"><span class="who-key">gaming</span><span class="who-val">Minecraft — modding, custom server, Forge mods</span></div>
      <div class="who-row"><span class="who-key">location</span><span class="who-val">Birmingham, AL</span></div>
      <div class="who-status">
        <div class="who-status-label">STATUS</div>
        <div class="who-status-value">● LEARNING EMBEDDED SYSTEMS</div>
      </div>
    </div>
  </div>`);
  bl();
  ln(`  type <span style="color:var(--mgs-cyan)">ls projects</span> to explore work`,'dim');
  bl();
},

'ls projects'(){
  bl();
  ln(`total ${PROJECTS.length}  <span style="color:var(--mgs-border)">(click a name or: cat project [id])</span>`,'dim');
  bl();
  PROJECTS.forEach((p,i)=>{
    const n=String(i+1).padStart(2,'0');
    const badge=p.badge?` <span style="color:var(--mgs-border)">[${esc(p.badge)}]</span>`:'';
    ln(`  <span style="color:#225544">${n}</span>  <span style="color:var(--mgs-cyan);cursor:pointer;text-decoration:underline" onclick="runCmd('cat project ${p.id}')">${p.id.padEnd(22)}</span><span style="color:#559988">${esc(p.name)}</span>${badge}`);
  });
  bl();
},

'cat project'(id){
  id=(id||'').trim().toLowerCase();
  if(!id){ln(`  Usage: cat project [id]  — run <span style="color:var(--mgs-cyan)">ls projects</span>`,'red');return;}
  const p=PROJECTS.find(x=>x.id===id||x.name.toLowerCase().includes(id));
  if(!p){ln(`  not found: ${esc(id)}. Run <span style="color:var(--mgs-cyan)">ls projects</span>`,'red');return;}
  bl();
  const img2html=p.img2?`<img src="${p.img2}" alt="secondary" style="width:100%;margin-top:8px;max-height:120px;object-fit:cover;border:2px solid var(--mgs-border);filter:grayscale(0.3) contrast(1.1);">` :'';
  addHtml(`<div class="proj-card">
    <div class="proj-card-header"><span class="proj-name">${esc(p.name)}</span><span class="badge ${p.bc}">${esc(p.badge)}</span></div>
    <div class="proj-card-body">
      <div class="proj-img-wrap"><div style="width:100%"><img src="${p.img}" alt="${esc(p.name)}" onerror="this.parentElement.style.display='none'">${img2html}</div></div>
      <div class="proj-info">
        <div class="proj-tech">stack: <span style="color:#99ddcc">${esc(p.tech)}</span></div>
        <div class="proj-desc">${esc(p.desc)}</div>
        <a class="proj-link" href="${p.link}" target="_blank">→ GITHUB: ${p.link.replace('https://github.com/','')}</a>
      </div>
    </div>
  </div>`);
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
  ln('  Live Bluemap render — real-time world data','white');
  ln('  Full view → <a class="tl" href="http://servermap.minecraft.bz:8100" target="_blank">servermap.minecraft.bz:8100</a>');
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

CMDS['ls']=CMDS['ls projects'];
CMDS['projects']=CMDS['ls projects'];
CMDS['classifier']=CMDS['bird-classifier'];
CMDS['classify']=CMDS['bird-classifier'];
CMDS['gallery']=CMDS['gallery'];
CMDS['mc-gallery']=CMDS['gallery'];

// ══════════════════════════════════════════
// COMMAND RUNNER
// ══════════════════════════════════════════
function runCmd(raw){
  const input=document.getElementById('cmd-input');
  const trimmed=raw!==undefined?raw:input.value.trim();
  if(raw===undefined) input.value='';
  echo(trimmed);
  if(!trimmed){bl();return;}
  hist.push(trimmed); hIdx=hist.length;
  const lo=trimmed.toLowerCase();
  if(lo.startsWith('cat project')){ CMDS['cat project'](trimmed.slice('cat project'.length).trim()); return; }
  const fn=CMDS[lo]||CMDS[lo.split(' ')[0]];
  if(fn){ fn(trimmed.split(' ').slice(1).join(' ')); }
  else { playErrorSound(); ln(`  command not found: <span style="color:#ff5555">${esc(trimmed)}</span>  — type <span style="color:var(--mgs-cyan)">help</span>`); bl(); }
}

// ══════════════════════════════════════════
// TAB COMPLETION
// ══════════════════════════════════════════
const ALL_CMDS=['help','whoami','cat project ','ls projects','music','contact','map','bird-classifier','gallery','clear'];
const PIDS=PROJECTS.map(p=>p.id);
function tabComp(v){
  const lo=v.toLowerCase();
  if(lo.startsWith('cat project ')){const frag=lo.slice('cat project '.length);const m=PIDS.find(id=>id.startsWith(frag));return m?'cat project '+m:v;}
  const m=ALL_CMDS.find(c=>c.startsWith(lo)&&c!==lo);
  return m||v;
}

// ══════════════════════════════════════════
// INPUT
// ══════════════════════════════════════════
document.getElementById('cmd-input').addEventListener('keydown',e=>{
  const inp=e.target;
  if(e.key==='Enter'){runCmd();}
  else if(e.key==='Tab'){e.preventDefault();inp.value=tabComp(inp.value);}
  else if(e.key==='ArrowUp'){e.preventDefault();if(hIdx>0){hIdx--;inp.value=hist[hIdx];}}
  else if(e.key==='ArrowDown'){e.preventDefault();if(hIdx<hist.length-1){hIdx++;inp.value=hist[hIdx];}else{hIdx=hist.length;inp.value='';}}
});
document.addEventListener('click',e=>{
  if(!e.target.closest('a')&&!e.target.closest('button')&&!e.target.closest('iframe'))
    document.getElementById('cmd-input').focus();
});

// ══════════════════════════════════════════
// BOOT TERMINAL
// ══════════════════════════════════════════
function bootTerminal(){
  setTimeout(()=>{
    ln('loading...','dim');
    setTimeout(()=>{
      ln('████████████████████████████████  100%','line');
      setTimeout(()=>{
        bl();
        addHtml(`<div class="fade-in" style="padding:0 4px;">
          <pre class="ascii" style="line-height:1.2;">
 ███╗   ██╗██╗ ██████╗██╗  ██╗
 ████╗  ██║██║██╔════╝██║ ██╔╝
 ██╔██╗ ██║██║██║     █████╔╝
 ██║╚██╗██║██║██║     ██╔═██╗
 ██║ ╚████║██║╚██████╗██║  ██╗
 ╚═╝ ╚════╝╚═╝╚═════╝╚═╝  ╚═╝</pre>
          <div style="margin-top:10px;padding-left:2px;border-left:3px solid var(--mgs-cyan);">
            <div style="font-family:'Orbitron',monospace;font-size:13px;font-weight:700;color:var(--mgs-cyan);letter-spacing:3px;padding-left:10px;">NICHOLAS BURCZYK</div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:11px;color:var(--mgs-border);margin-top:5px;padding-left:10px;">Software Engineer · Vision · ML · Audio · Embedded</div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:10px;color:rgba(0,170,136,0.45);margin-top:3px;padding-left:10px;">UAB MSCS · Viper Imaging · Birmingham AL</div>
          </div>
        </div>`);
        bl();
      }, 400);
    }, 300);
  }, 100);
}