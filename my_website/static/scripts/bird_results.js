function tick() {
  const t = new Date().toLocaleTimeString('en-US', { hour12: false });
  document.getElementById('clock').textContent = t;
  document.getElementById('sclk').textContent  = t;
}
tick();
setInterval(tick, 1000);

window.addEventListener('load', () => {
  setTimeout(() => {
    const bar = document.getElementById('confbar');
    if (bar) bar.style.width = bar.dataset.confidence + '%';
  }, 300);
});

const sel = document.getElementById('accuracy-select');
const inp = document.getElementById('feedback-input');
const btn = document.getElementById('upload-btn');

function updateBtn() {
  const v = sel.value;
  if (!v) { btn.disabled = true; return; }
  if (v === 'no' && !inp.value.trim()) { btn.disabled = true; return; }
  btn.disabled = false;
}

sel.addEventListener('change', function () {
  if (this.value === 'no') { inp.disabled = false; inp.focus(); }
  else { inp.disabled = true; inp.value = ''; }
  updateBtn();
});
inp.addEventListener('input', updateBtn);

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('upload-form').addEventListener('submit', () => {
    btn.style.display = 'none';
    document.getElementById('loading-btn').style.display = 'inline-flex';
  });
});

// Lightbox
function openLightbox(src, label) {
  document.getElementById('lb-img').src = src;
  document.getElementById('lb-img').alt = label;
  document.getElementById('lightbox').classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('open');
  document.body.style.overflow = '';
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });