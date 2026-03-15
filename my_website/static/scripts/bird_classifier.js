// ── CLOCK ──────────────────────────────────────────────────
function tick() {
  const t = new Date().toLocaleTimeString('en-US', { hour12: false });
  document.getElementById('clock').textContent = t;
  document.getElementById('sclk').textContent  = t;
}
tick();
setInterval(tick, 1000);

// ── CAROUSEL ───────────────────────────────────────────────
const CAROUSEL_IMGS = [
  'https://cdn.mos.cms.futurecdn.net/PqHzRT5FnGPSoEUMfmGSWH.jpg',
  'https://feederwatch.org/wp-content/uploads/2020/02/37B77335-C469-4D36-A535-059F40176E4E.jpeg',
  'https://static.wikia.nocookie.net/birds/images/1/15/Am_robin.jpg/revision/latest?cb=20070731192419',
  'https://bpraptorcenter.org/wp-content/uploads/2018/10/Barred-Owl.jpg',
  'https://upload.wikimedia.org/wikipedia/commons/f/f4/Blue_jay_in_PP_%2830960%29.jpg',
  'https://www.nps.gov/chat/learn/nature/images/chickadee.jpg?maxwidth=650&autorotate=false',
  'https://i.natgeofe.com/n/9dfeaf41-ccd8-4234-a59a-e8f107fff63c/carolina-wren_3x4.jpg',
  'https://upload.wikimedia.org/wikipedia/commons/5/5c/Male_northern_cardinal_in_Central_Park_%2852612%29.jpg',
  'https://nestwatch.org/wp-content/uploads/2019/10/EABL_GenaFlanigen-935x1024.jpg',
  'https://www.allaboutbirds.org/guide/assets/photo/60397941-480px.jpg',
  'https://inaturalist-open-data.s3.amazonaws.com/photos/898/large.jpg',
  'https://media.audubon.org/nas_birdapi_hero/aud_gbbc-2016_white-breasted-nuthatch_35889_kk_mi_photo-joan-tisdale_adult-male.jpg',
];

const track  = document.getElementById('carousel-track');
const dotsEl = document.getElementById('carousel-dots');
let cIdx = 0;

CAROUSEL_IMGS.forEach((src, i) => {
  const slide = document.createElement('div');
  slide.className = 'carousel-slide';
  slide.innerHTML = `<img src="${src}" alt="bird ${i + 1}" style="width:100%;height:260px;object-fit:cover;display:block;">`;
  track.appendChild(slide);

  const dot = document.createElement('div');
  dot.className = 'cdot' + (i === 0 ? ' active' : '');
  dot.onclick = () => goSlide(i);
  dotsEl.appendChild(dot);
});

function goSlide(n) {
  cIdx = n;
  track.style.transform = `translateX(-${cIdx * 100}%)`;
  document.querySelectorAll('.cdot').forEach((d, i) => d.classList.toggle('active', i === cIdx));
}

setInterval(() => goSlide((cIdx + 1) % CAROUSEL_IMGS.length), 3500);

// ── UPLOAD FORM LOGIC ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const startBtn     = document.getElementById('start-recording');
  const stopBtn      = document.getElementById('stop-recording');
  const playback     = document.getElementById('audio-playback');
  const recInput     = document.getElementById('recorded-audio');
  const fileInput    = document.getElementById('file-input');
  const fileNameEl   = document.getElementById('file-name');
  const uploadBtn    = document.getElementById('upload-btn');
  const resetBtn     = document.getElementById('reset-form');
  const recIndicator = document.getElementById('rec-indicator');
  const dropZone     = document.getElementById('drop-zone');

  let mediaRecorder, recordedChunks = [], recordedBlob;
  const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);

  if (isSafari) {
    document.getElementById('safari-warning').style.display = 'block';
    startBtn.disabled = true;
    stopBtn.disabled  = true;
    if (!localStorage.getItem('safariWarn')) {
      alert('Live recording is disabled on Safari. Please use Chrome for best performance.');
      localStorage.setItem('safariWarn', '1');
    }
  }

  // File input
  fileInput.addEventListener('change', function () {
    if (this.files.length > 0) {
      fileNameEl.textContent = '▸ ' + this.files[0].name;
      fileNameEl.style.color = 'var(--mgs-cyan)';
      if (!isSafari) startBtn.disabled = true;
      stopBtn.disabled = true;
      recInput.value   = '';
      playback.classList.add('hidden');
      playback.src = '';
    } else {
      fileNameEl.textContent = 'no file selected';
      fileNameEl.style.color = '';
      if (!isSafari) startBtn.disabled = false;
    }
  });

  // Drag and drop
  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      fileInput.dispatchEvent(new Event('change'));
    }
  });

  // Recording
  startBtn.addEventListener('click', async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    fileInput.value    = '';
    fileInput.disabled = true;
    fileNameEl.textContent = 'no file selected';
    fileNameEl.style.color = '';
    recordedChunks = [];

    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) recordedChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      recordedBlob = new Blob(recordedChunks, { type: 'audio/mpeg' });
      const url = URL.createObjectURL(recordedBlob);
      playback.src = url;
      playback.classList.remove('hidden');
      const file = new File([recordedBlob], 'user_recording.wav', { type: 'audio/wav' });
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files   = dt.files;
      recInput.value    = url;
      fileInput.disabled = false;
      recIndicator.style.display = 'none';
    };

    mediaRecorder.start();
    startBtn.disabled = true;
    stopBtn.disabled  = false;
    recIndicator.style.display = 'inline-flex';
  });

  stopBtn.addEventListener('click', () => {
    mediaRecorder.stop();
    startBtn.disabled = false;
    stopBtn.disabled  = true;
  });

  // Reset
  resetBtn.addEventListener('click', () => {
    fileInput.value    = '';
    fileInput.disabled = false;
    fileNameEl.textContent = 'no file selected';
    fileNameEl.style.color = '';
    if (!isSafari) startBtn.disabled = false;
    stopBtn.disabled = true;
    recInput.value   = '';
    playback.classList.add('hidden');
    playback.src = '';
    recIndicator.style.display = 'none';
    document.querySelectorAll('.term-alert-err').forEach(el => el.style.display = 'none');
  });

  // Submit loading state
  document.getElementById('upload-form').addEventListener('submit', () => {
    uploadBtn.style.display = 'none';
    document.getElementById('loading-btn').style.display = 'inline-flex';
  });
});

// ── BIRD TABLE FILTER ─────────────────────────────────────
function filterBirds() {
  const q    = document.getElementById('bird-search').value.toLowerCase();
  const rows = document.querySelectorAll('#bird-tbody tr');
  let shown  = 0;
  rows.forEach(r => {
    const name = r.getAttribute('data-bird') || '';
    const vis  = name.includes(q);
    r.style.display = vis ? '' : 'none';
    if (vis) shown++;
  });
  document.getElementById('bird-count').textContent = `showing ${shown} bird${shown !== 1 ? 's' : ''}`;
}

// ── AUDIO PLAY/STOP ───────────────────────────────────────
let currentAudio = null, currentBtn = null;

function togglePlay(audioId, btnId) {
  const audio = document.getElementById(audioId);
  const btn   = document.getElementById(btnId);

  if (currentAudio && currentAudio !== audio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    if (currentBtn) { currentBtn.innerHTML = '▶ PLAY'; currentBtn.classList.remove('playing'); }
  }

  if (audio.paused) {
    audio.play();
    btn.innerHTML = '■ STOP';
    btn.classList.add('playing');
    currentAudio = audio;
    currentBtn   = btn;
    audio.onended = () => {
      btn.innerHTML = '▶ PLAY';
      btn.classList.remove('playing');
      currentAudio = null;
      currentBtn   = null;
    };
  } else {
    audio.pause();
    audio.currentTime = 0;
    btn.innerHTML = '▶ PLAY';
    btn.classList.remove('playing');
    currentAudio = null;
    currentBtn   = null;
  }
}