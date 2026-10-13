// "!likes!" plane: a little plane crosses the sky towing a waving banner with the viewer's
// avatar and the number of likes this stream. Works on every page (games + streamer overlay).
//   Plane.fly({name, avatar, total}, {sound: true})
window.Plane = (() => {
  const t = (k, p) => (window.I18N ? I18N.t(k, p) : k);
  const clean = n => (n || '').replace(/[^\p{L}\p{N} ._'-]/gu, '').trim() || '?';
  let ready = false, sky = null;
  const queue = [];
  let flying = false;

  const CSS = `
  .pl-sky { position: fixed; inset: 0; pointer-events: none; overflow: hidden; z-index: 1000; }   /* above everything: dialogs, greetings, overlays */
  .pl-flight { position: absolute; left: 0; top: var(--top); will-change: transform;
               animation: pl-fly var(--dur) linear forwards; }
  .pl-bob { animation: pl-bob 2.4s ease-in-out infinite; }
  .pl-row { display: flex; align-items: center; }
  .pl-plane { width: var(--ph); flex: none; filter: drop-shadow(0 .4vh .6vh rgba(0,0,0,.35)); }
  .pl-plane .prop { transform-origin: 9px 30px; animation: pl-prop .09s linear infinite; }
  .pl-rope { width: calc(var(--ph) * .55); height: 2px; flex: none; margin-top: calc(var(--ph) * .02);
             background: repeating-linear-gradient(90deg, rgba(255,255,255,.9) 0 6px, rgba(255,255,255,.55) 6px 9px); }
  .pl-banner { position: relative; display: flex; align-items: center; gap: .5em; flex: none;
               height: calc(var(--ph) * .52); padding: 0 1.1em 0 .45em; white-space: nowrap;
               font: 900 calc(var(--ph) * .19) 'Segoe UI', system-ui, sans-serif; color: #c4002f;
               background: linear-gradient(180deg, #fffdf6, #ffe9ef);
               border: calc(var(--ph) * .025) solid #ff2d55; border-left: calc(var(--ph) * .05) solid #8a5a2b;
               box-shadow: 0 .5vh 1.2vh rgba(0,0,0,.35); filter: url(#pl-wave); }
  .pl-banner::after { content: ''; position: absolute; right: calc(var(--ph) * -.2); top: -3%; height: 106%;
               width: calc(var(--ph) * .2); background: linear-gradient(180deg, #fffdf6, #ffe9ef);
               clip-path: polygon(0 0, 100% 0, 55% 50%, 100% 100%, 0 100%); }
  .pl-banner .av { width: calc(var(--ph) * .4); height: calc(var(--ph) * .4); border-radius: 50%; object-fit: cover;
               border: 2px solid #ff2d55; flex: none; display: inline-flex; align-items: center; justify-content: center;
               color: #fff; font-size: calc(var(--ph) * .2); }
  .pl-banner .nm { color: #1a1033; }
  .pl-banner .hearts { color: #ff2d55; }
  .pl-deny { position: absolute; left: 50%; top: 9vh; transform: translateX(-50%); max-width: 94vw;
             padding: .45em 1em; border-radius: 999px; background: rgba(10,0,25,.9); color: #fff;
             border: 2px solid #ff2d55; font: 800 min(3.8vw, 2.2vh) 'Segoe UI', system-ui, sans-serif;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
             animation: pl-note 4s ease forwards; }
  @keyframes pl-note { 0% { opacity: 0; transform: translate(-50%, -1em); } 10%, 85% { opacity: 1; transform: translate(-50%, 0); }
                       100% { opacity: 0; transform: translate(-50%, -.5em); } }
  @keyframes pl-fly { from { transform: translateX(var(--from)); } to { transform: translateX(var(--to)); } }
  @keyframes pl-bob { 0%, 100% { translate: 0 0; rotate: -1deg; } 50% { translate: 0 calc(var(--ph) * .12); rotate: 1.2deg; } }
  @keyframes pl-prop { from { transform: scaleY(1); } 50% { transform: scaleY(.15); } to { transform: scaleY(1); } }`;

  // cartoon plane facing left (it flies right -> left), propeller at the nose
  const PLANE = `<svg class="pl-plane" viewBox="0 0 120 60">
    <path d="M100 30 L118 12 L112 30 Z" fill="#ff2d55"/>
    <path d="M98 30 L116 40 L108 30 Z" fill="#d1003a"/>
    <ellipse cx="58" cy="31" rx="46" ry="12" fill="#ff2d55"/>
    <ellipse cx="56" cy="27" rx="40" ry="5" fill="#ff7a98" opacity=".7"/>
    <path d="M14 31 C 14 24, 20 21, 26 21 L 26 41 C 20 41, 14 38, 14 31 Z" fill="#ffd84a"/>
    <path d="M44 33 L74 33 L86 52 L64 52 Z" fill="#c4002f"/>
    <path d="M46 29 L70 29 L80 12 L60 12 Z" fill="#e0183f"/>
    <circle cx="36" cy="28" r="3.6" fill="#a8e8ff" stroke="#fff" stroke-width="1"/>
    <circle cx="48" cy="28" r="3.2" fill="#a8e8ff" stroke="#fff" stroke-width="1"/>
    <circle cx="11" cy="31" r="3" fill="#333"/>
    <g class="prop"><ellipse cx="9" cy="31" rx="2.2" ry="16" fill="#555" opacity=".85"/></g>
  </svg>`;

  // cloth-like waving banner: animated turbulence -> displacement
  const WAVE = `<svg width="0" height="0" style="position:absolute"><filter id="pl-wave" x="-5%" y="-20%" width="110%" height="140%">
    <feTurbulence type="fractalNoise" baseFrequency="0.012 0.06" numOctaves="1" seed="3" result="n">
      <animate attributeName="baseFrequency" dur="2.2s" values="0.012 0.06;0.016 0.09;0.012 0.06" repeatCount="indefinite"/>
    </feTurbulence>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="7" xChannelSelector="R" yChannelSelector="G"/>
  </filter></svg>`;

  function setup() {
    if (ready) return;
    ready = true;
    const s = document.createElement('style'); s.textContent = CSS; document.head.appendChild(s);
    const w = document.createElement('div'); w.innerHTML = WAVE; document.body.appendChild(w.firstChild);
    sky = document.createElement('div'); sky.className = 'pl-sky'; document.body.appendChild(sky);
  }

  function avatar(name, url) {
    if (url && /^https:\/\//.test(url)) {
      const img = document.createElement('img');
      img.className = 'av'; img.referrerPolicy = 'no-referrer'; img.alt = ''; img.src = url;
      img.onerror = () => img.replaceWith(avatar(name, ''));
      return img;
    }
    const hue = [...(name || '?')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
    const d = document.createElement('span');
    d.className = 'av'; d.textContent = (clean(name)[0] || '?').toUpperCase();
    d.style.background = `hsl(${hue} 85% 55%)`;
    return d;
  }

  function drone(sec) {                      // propeller hum fading in and out
    if (!window.AudioKit || !AudioKit.ready) return;
    for (let i = 0; i < sec * 4; i++) {
      const v = 0.05 * Math.sin(Math.PI * i / (sec * 4));
      AudioKit.tone(95 + 6 * Math.sin(i / 2), i * 0.25, 0.3, 'sawtooth', Math.max(0.002, v));
    }
  }

  function launch(e, o) {
    flying = true;
    const W = window.innerWidth, H = window.innerHeight;
    const ph = Math.min(W * 0.22, H * 0.13);           // plane size: fits phones and wide windows
    const flight = document.createElement('div');
    flight.className = 'pl-flight';
    flight.style.setProperty('--ph', ph + 'px');
    flight.style.setProperty('--top', (H * (0.12 + Math.random() * 0.14)) + 'px');
    const bob = document.createElement('div'); bob.className = 'pl-bob';
    const row = document.createElement('div'); row.className = 'pl-row';
    row.innerHTML = PLANE + '<div class="pl-rope"></div>';
    const banner = document.createElement('div'); banner.className = 'pl-banner';
    const likes = document.createElement('span'); likes.className = 'hearts';
    likes.textContent = '❤ ' + Number(e.total).toLocaleString(I18N.lang === 'ru' ? 'ru-RU' : 'en-US');
    banner.append(avatar(e.name, e.avatar), likes);       // just the avatar and the number
    row.appendChild(banner);
    bob.appendChild(row); flight.appendChild(bob);
    flight.style.visibility = 'hidden';
    sky.appendChild(flight);
    const width = row.getBoundingClientRect().width + ph * 0.3;
    const speed = Math.max(W, 600) / 4.2;               // crosses a screen width in ~4 s
    const dur = (W + width) / speed;
    flight.style.setProperty('--from', W + 'px');
    flight.style.setProperty('--to', -width + 'px');
    flight.style.setProperty('--dur', dur.toFixed(2) + 's');
    flight.style.visibility = '';
    if (o && o.sound && window.AudioKit && AudioKit.ready) {
      drone(dur);
      setTimeout(() => AudioKit.say(t('plane.v', { name: clean(e.name), likes: I18N.n(e.total, 'like') })), 800);
    }
    setTimeout(() => { flight.remove(); flying = false; next(); }, dur * 1000 + 200);
  }
  function next() {
    if (!flying && queue.length) { const [e, o] = queue.shift(); launch(e, o); }
  }

  // "!likes!" refused: a short note at the top so the viewer knows why nothing flies
  function deny(e) {
    setup();
    const note = document.createElement('div');
    note.className = 'pl-deny';
    note.textContent = '✈ ' + clean(e.name) + ': ' + (e.deny === 'cooldown'
      ? t('plane.wait', { s: e.wait })
      : t('plane.need', { need: e.need, have: e.have }));
    sky.appendChild(note);
    setTimeout(() => note.remove(), 4200);
  }

  return {
    deny,
    fly(e, o) {                                // one plane at a time, the rest wait their turn
      setup();
      queue.push([e, o]);
      if (queue.length > 3) queue.shift();
      next();
    },
  };
})();
