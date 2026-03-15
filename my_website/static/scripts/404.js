function tick() {
  const t = new Date().toLocaleTimeString('en-US', { hour12: false });
  document.getElementById('clock').textContent = t;
  document.getElementById('sclk').textContent  = t;
}
tick();
setInterval(tick, 1000);

const KP_LINES = [
  { t:'[  0.000000] Kernel panic — not syncing: Attempted to access invalid address', c:'red',    d:0   },
  { t:'[  0.000001] CPU: 0 PID: 404 Comm: nginx Not tainted 6.6.0-custom',           c:'',       d:80  },
  { t:"[  0.000002] Hardware name: Nick's Server Box / UAB-CS-Lab",                  c:'',       d:160 },
  { t:'[  0.000003] Call trace:',                                                     c:'yellow', d:240 },
  { t:'[  0.000004]  __die+0x1c/0x68',                                               c:'dim',    d:300 },
  { t:'[  0.000005]  page_fault_oops+0x14c/0x220',                                   c:'dim',    d:360 },
  { t:'[  0.000006]  do_user_addr_fault+0x1a8/0x620',                                c:'dim',    d:420 },
  { t:'[  0.000007]  exc_page_fault+0x70/0x190',                                     c:'dim',    d:480 },
  { t:'[  0.000008] RIP: route_lookup+0x0 <path: /blog/coming-soon>',                c:'red',    d:560 },
  { t:'[  0.000009] Code: NULL pointer dereference — address 0x000000000000',        c:'red',    d:640 },
  { t:'[  0.000010] ---[ end Kernel panic ]---',                                     c:'bright', d:740 },
];

const kpOut = document.getElementById('kp-output');
KP_LINES.forEach(({ t, c, d }) => {
  setTimeout(() => {
    const div = document.createElement('div');
    div.className = `kp-line ${c}`;
    div.style.animation = 'fadeIn .2s ease forwards';
    div.textContent = t;
    kpOut.appendChild(div);
  }, d);
});

// Typewriter message
const MSG = "Page doesnt exist rn.";
const tw = document.getElementById('tw-msg');
let i = 0;
function typeNext() {
  if (i < MSG.length) {
    tw.textContent += MSG[i++];
    setTimeout(typeNext, MSG[i - 1] === '.' ? 120 : 28);
  }
}
setTimeout(typeNext, 900);

// Glitch the 404 number
const errNum = document.getElementById('errnum');
const glitchNums = ['4O4', '404', '40₄', 'ᗺ04', '404', '4Ø4', '404'];
setInterval(() => {
  if (Math.random() < 0.15) {
    errNum.textContent = glitchNums[Math.floor(Math.random() * glitchNums.length)];
    errNum.style.animation = 'shake .3s ease, rgb-split 0.3s, glitch-skew 0.3s';
    setTimeout(() => {
      errNum.textContent = '404';
      errNum.style.animation = 'rgb-split 3s infinite, glitch-skew 4s infinite';
    }, 200);
  }
}, 2500);