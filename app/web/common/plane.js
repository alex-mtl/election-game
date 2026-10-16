// Likes plane (every 1000 likes): a little plane crosses the sky towing a waving banner with the viewer's
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
  .pl-flight { position: absolute; left: 0; top: 0; will-change: transform; transform-origin: 50% 50%;
               animation: pl-fly var(--dur) linear forwards; }
  /* left -> right: banner, rope, plane (mirrored); the pole and the swallowtail swap sides */
  .pl-flight.rev .pl-row { flex-direction: row-reverse; }
  .pl-flight.rev .pl-plane { transform: scaleX(-1); }
  .pl-flight.rev .pl-banner { padding: .3em .45em .3em 1.1em; border-left: calc(var(--ph) * .025) solid #ff2d55;
               border-right: calc(var(--ph) * .05) solid #8a5a2b; }
  .pl-flight.rev .pl-banner::after { right: auto; left: calc(var(--ph) * -.2);
               clip-path: polygon(100% 0, 0 0, 45% 50%, 0 100%, 100% 100%); }
  .pl-bob { animation: pl-bob 2.4s ease-in-out infinite; }
  .pl-row { display: flex; align-items: center; }
  .pl-plane { width: var(--ph); flex: none; filter: drop-shadow(0 .4vh .6vh rgba(0,0,0,.35)); }
  .pl-plane .prop { transform-origin: 9px 30px; animation: pl-prop .09s linear infinite; }
  .pl-rope { width: calc(var(--ph) * .55); height: 2px; flex: none; margin-top: calc(var(--ph) * .02);
             background: repeating-linear-gradient(90deg, rgba(255,255,255,.9) 0 6px, rgba(255,255,255,.55) 6px 9px); }
  .pl-banner { position: relative; display: flex; flex-direction: column; align-items: stretch; flex: none;
               padding: .3em 1.1em .3em .45em; white-space: nowrap;
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
  .pl-banner .top { display: flex; align-items: center; justify-content: center; gap: .5em; }
  .pl-banner .nm { color: #1a1033; text-align: center; margin-top: .15em; font-size: .8em; letter-spacing: .02em; }
  .pl-banner .hearts { color: #ff2d55; }
  .pl-deny { position: absolute; left: 50%; top: 9vh; transform: translateX(-50%); max-width: 94vw;
             padding: .45em 1em; border-radius: 999px; background: rgba(10,0,25,.9); color: #fff;
             border: 2px solid #ff2d55; font: 800 min(3.8vw, 2.2vh) 'Segoe UI', system-ui, sans-serif;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
             animation: pl-note 4s ease forwards; }
  @keyframes pl-note { 0% { opacity: 0; transform: translate(-50%, -1em); } 10%, 85% { opacity: 1; transform: translate(-50%, 0); }
                       100% { opacity: 0; transform: translate(-50%, -.5em); } }
  @keyframes pl-fly { from { transform: translate(var(--x0), var(--y0)) rotate(var(--rot)); }
                      to { transform: translate(var(--x1), var(--y1)) rotate(var(--rot)); } }
  @keyframes pl-bob { 0%, 100% { translate: 0 0; rotate: -1deg; } 50% { translate: 0 calc(var(--ph) * .12); rotate: 1.2deg; } }
  /* bomber: bombs fall, freeze and burst into big butterflies with the viewer's avatar as the head */
  .pl-bomb { position: absolute; left: 0; top: 0; width: var(--bs); height: var(--bs); margin: calc(var(--bs) / -2);
             will-change: transform; }
  .pl-bomb svg { width: 100%; height: 100%; display: block; }
  .pl-bomb.freeze svg { animation: pl-freeze .18s ease-in-out 2; }
  @keyframes pl-freeze { 50% { transform: scale(1.35); filter: brightness(2.2); } }
  .pl-fly { position: absolute; left: 0; top: 0; width: var(--fs); height: calc(var(--fs) * .8);
            margin: calc(var(--fs) * -.4) 0 0 calc(var(--fs) / -2); will-change: transform; }
  .pl-fly .in { position: relative; width: 100%; height: 100%; animation: pl-pop .35s cubic-bezier(.3,1.6,.6,1) both; }
  .pl-fly svg { width: 100%; height: 100%; display: block; overflow: visible; }
  .pl-fly .wings { transform-box: view-box; transform-origin: 100px 80px; animation: pl-flap var(--flap) ease-in-out infinite alternate; }
  .pl-fly .av { position: absolute; left: 50%; top: 25%; width: 17%; height: auto; aspect-ratio: 1; transform: translate(-50%, -50%);
                border-radius: 50%; object-fit: cover; border: calc(var(--fs) * .012) solid #fff;
                display: flex; align-items: center; justify-content: center; color: #fff; font: 900 calc(var(--fs) * .08) 'Segoe UI', sans-serif; }
  @keyframes pl-flap { from { transform: scaleX(1); } to { transform: scaleX(.3); } }
  @keyframes pl-pop { from { transform: scale(0) rotate(-20deg); opacity: 0; } to { transform: scale(1); opacity: 1; } }
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
    const hue = (window.Chroma ? Chroma.hue.bind(Chroma) : x => x)([...(name || '?')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7));
    const d = document.createElement('span');
    d.className = 'av'; d.textContent = (clean(name)[0] || '?').toUpperCase();
    d.style.background = `hsl(${hue} 85% 55%)`;
    return d;
  }

  // engine: a recorded An-2 ("кукурузник") loop, loud when the plane appears, fading by the end,
  // panned from the side it comes from. Recording: "Low passing aeroplane, An-2R (HA-MEN)" by ycbcr,
  // freesound.org/s/350574, CC BY 4.0 (10-16 s cut into a loop).
  const ENGINE = '/common/sounds/an2-loop.mp3';
  function engine(sec, dir) {
    if (!window.AudioKit || !AudioKit.ready || !AudioKit.loop) return;
    AudioKit.loop(ENGINE, sec, { vol: 0.6, rate: 0.93 + Math.random() * 0.14, hold: 0.25,
                                 panFrom: -0.7 * dir, panTo: 0.7 * dir });
  }

  function launch(e, o) {
    flying = true;
    const W = window.innerWidth, H = window.innerHeight;
    const ph = Math.min(W * 0.22, H * 0.13);           // plane size: fits phones and wide windows
    const flight = document.createElement('div');
    flight.className = 'pl-flight';
    flight.style.setProperty('--ph', ph + 'px');
    const dir = Math.random() < 0.5 ? -1 : 1;           // -1: right -> left, 1: left -> right
    if (dir > 0) flight.classList.add('rev');
    const bob = document.createElement('div'); bob.className = 'pl-bob';
    const row = document.createElement('div'); row.className = 'pl-row';
    row.innerHTML = PLANE + '<div class="pl-rope"></div>';
    const banner = document.createElement('div'); banner.className = 'pl-banner';
    const likes = document.createElement('span'); likes.className = 'hearts';
    likes.textContent = '❤ ' + Number(e.total).toLocaleString(I18N.locale);
    const top = document.createElement('div'); top.className = 'top';
    top.append(avatar(e.name, e.avatar), likes);
    const nm = document.createElement('div'); nm.className = 'nm'; nm.textContent = clean(e.name);
    banner.append(top, nm);                               // avatar + likes, the nick under them
    row.appendChild(banner);
    bob.appendChild(row); flight.appendChild(bob);
    flight.style.visibility = 'hidden';
    sky.appendChild(flight);
    const box = row.getBoundingClientRect();
    const width = box.width + ph * 0.3;
    const dx = W + width;                               // from fully off one side to fully off the other
    // start at 20-80% of the height (a bomber: 12-45%, it stays in the upper half), climb or dive
    // up to 15 degrees; the end stays within the band
    const [lo, hi] = e.bomber ? [0.1, 0.48] : [0.1, 0.9];
    const y0 = H * (e.bomber ? 0.12 + Math.random() * 0.33 : 0.2 + Math.random() * 0.6);
    let deg = (Math.random() * 2 - 1) * 15;             // + climbs, - dives
    const endY = d => y0 - dx * Math.tan(d * Math.PI / 180);
    const out = d => endY(d) < H * lo || endY(d) > H * hi;
    if (out(deg)) deg = -deg;                           // turn towards the middle
    const room = Math.max(y0 - H * lo, H * hi - y0);
    deg = Math.sign(deg) * Math.min(Math.abs(deg), Math.atan(room / dx) * 180 / Math.PI);
    if (out(deg)) deg = -deg;
    const speed = Math.max(W, 600) / 8.4;               // crosses a screen width in ~8 s
    const dur = dx / speed;
    const topPx = y => (y - box.height / 2) + 'px';
    flight.style.setProperty('--x0', (dir < 0 ? W : -width) + 'px');
    flight.style.setProperty('--x1', (dir < 0 ? -width : W) + 'px');
    flight.style.setProperty('--y0', topPx(y0));
    flight.style.setProperty('--y1', topPx(endY(deg)));
    flight.style.setProperty('--rot', (-dir * deg).toFixed(1) + 'deg');   // nose follows the path
    flight.style.setProperty('--dur', dur.toFixed(2) + 's');
    flight.style.visibility = '';
    if (o && o.sound && window.AudioKit && AudioKit.ready) {
      engine(dur, dir);
      setTimeout(() => AudioKit.say(t('plane.v', { name: clean(e.name), likes: I18N.n(e.total, 'like') })), 800);
    }
    const bombs = [];
    if (e.bomber) {
      // BOMBS bombs while the plane itself (not the banner it tows) is over the screen: from the
      // moment it flies in to the moment it reaches the opposite edge, one in the middle of each
      // tenth of that stretch
      const plane = row.querySelector('.pl-plane');
      const pr = plane.getBoundingClientRect(), rr = row.getBoundingClientRect();
      const off = pr.left + pr.width / 2 - rr.left;                     // plane centre inside the row
      const X0 = (dir < 0 ? W : -width) + off, X1 = (dir < 0 ? -width : W) + off;
      const at = x => (x - X0) / (X1 - X0) * dur;                       // time the centre passes x
      const m = W * 0.03, tIn = at(dir < 0 ? W - m : m), tOut = at(dir < 0 ? m : W - m);
      for (let k = 0; k < BOMBS; k++) {
        bombs.push(setTimeout(() => drop(flight, e, o), (tIn + (tOut - tIn) * (k + 0.5) / BOMBS) * 1000));
      }
    }
    setTimeout(() => { bombs.forEach(clearTimeout); flight.remove(); flying = false; next(); }, dur * 1000 + 200);
  }
  const BOMBS = 10;                          // per bomber flight (it marks the 10th plane)
  const BOMB = `<svg viewBox="0 0 40 46"><path d="M24 8 C 28 2, 34 2, 36 6" stroke="#b07a3a" stroke-width="2.5" fill="none"/>
    <circle cx="37" cy="5" r="3.5" fill="#ffd84a"/><circle cx="37" cy="5" r="1.6" fill="#fff"/>
    <rect x="17" y="8" width="10" height="7" rx="2" fill="#555"/>
    <circle cx="20" cy="28" r="16" fill="#222"/><ellipse cx="14" cy="22" rx="5" ry="3" fill="#fff" opacity=".35" transform="rotate(-30 14 22)"/></svg>`;

  function butterflySvg() {
    const ch = window.Chroma ? h => Chroma.hue(h) : h => h;           // no green in chroma key mode
    const h1 = ch(Math.floor(Math.random() * 360)), h2 = ch((h1 + 40 + Math.floor(Math.random() * 120)) % 360);
    const id = 'pl-bf' + Math.random().toString(36).slice(2, 8);
    const up = 'M100 74 C 70 -6, -4 0, 12 62 C 22 98, 74 96, 100 84 Z';
    const low = 'M100 88 C 72 96, 26 112, 40 148 C 56 166, 94 134, 100 98 Z';
    const wing = (d, g) => `<path d="${d}" fill="url(#${id}${g})" stroke="#fff" stroke-width="2"/>` +
      `<path d="${d}" fill="url(#${id}${g})" stroke="#fff" stroke-width="2" transform="translate(200 0) scale(-1 1)"/>`;
    return `<svg viewBox="0 0 200 160">
      <defs><radialGradient id="${id}a" cx="30%" cy="35%" r="80%"><stop offset="0" stop-color="hsl(${h1} 100% 88%)"/>
        <stop offset=".55" stop-color="hsl(${h1} 95% 66%)"/><stop offset="1" stop-color="hsl(${h2} 90% 55%)"/></radialGradient>
        <radialGradient id="${id}b" cx="50%" cy="30%" r="80%"><stop offset="0" stop-color="hsl(${h2} 100% 85%)"/>
        <stop offset="1" stop-color="hsl(${h2} 95% 60%)"/></radialGradient>
        <linearGradient id="${id}c" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="hsl(${h2} 90% 62%)"/>
        <stop offset=".5" stop-color="hsl(${h1} 100% 82%)"/><stop offset="1" stop-color="hsl(${h2} 90% 62%)"/></linearGradient></defs>
      <g class="wings">${wing(up, 'a')}${wing(low, 'b')}
        <circle cx="48" cy="44" r="9" fill="#fff" opacity=".55"/><circle cx="152" cy="44" r="9" fill="#fff" opacity=".55"/>
        <circle cx="62" cy="122" r="6" fill="#fff" opacity=".5"/><circle cx="138" cy="122" r="6" fill="#fff" opacity=".5"/>
      </g>
      <path d="M96 36 C 90 18, 82 10, 74 6 M104 36 C 110 18, 118 10, 126 6" stroke="hsl(${h2} 90% 62%)" stroke-width="3" fill="none" stroke-linecap="round"/>
      <circle cx="74" cy="6" r="5" fill="hsl(${h1} 100% 70%)" stroke="#fff" stroke-width="1.5"/>
      <circle cx="126" cy="6" r="5" fill="hsl(${h1} 100% 70%)" stroke="#fff" stroke-width="1.5"/>
      <ellipse cx="100" cy="92" rx="8" ry="44" fill="url(#${id}c)" stroke="#fff" stroke-width="1.5"/>
      <path d="M93 70 H107 M92 84 H108 M92 98 H108 M93 112 H107 M95 124 H105" stroke="hsl(${h2} 90% 55%)" stroke-width="2.5" stroke-linecap="round" opacity=".7"/></svg>`;
  }

  function butterfly(x, y, e) {
    const W = window.innerWidth, H = window.innerHeight;
    const size = Math.min(W * 0.4, H * 0.55);           // 40% of the screen width (not taller than half a screen)
    const f = document.createElement('div');
    f.className = 'pl-fly';
    f.style.setProperty('--fs', size + 'px');
    f.style.setProperty('--flap', (0.16 + Math.random() * 0.1).toFixed(2) + 's');
    const inner = document.createElement('div'); inner.className = 'in';
    inner.innerHTML = butterflySvg();
    inner.appendChild(avatar(e.name, e.avatar));          // the head is the viewer's avatar
    f.appendChild(inner);
    sky.appendChild(f);
    // a wandering path: a few random points, the last one off screen over a random edge
    const pts = [[x, y]];
    let cx = x, cy = y;
    for (let i = 0; i < 3; i++) {
      cx = Math.min(W, Math.max(0, cx + (Math.random() - 0.5) * W * 0.6));
      cy = Math.min(H, Math.max(0, cy + (Math.random() - 0.6) * H * 0.4));
      pts.push([cx, cy]);
    }
    const side = Math.floor(Math.random() * 4), m = size;
    pts.push(side === 0 ? [-m, cy] : side === 1 ? [W + m, cy] : side === 2 ? [cx, -m] : [cx, H + m]);
    const frames = pts.map(([px, py], i) => {
      const qx = pts[Math.min(i + 1, pts.length - 1)][0];
      const tilt = Math.max(-25, Math.min(25, (qx - px) / W * 60));
      return { transform: `translate(${px}px, ${py}px) rotate(${tilt}deg)` };
    });
    const a = f.animate(frames, { duration: 4200 + Math.random() * 2400, easing: 'ease-in-out', delay: 350, fill: 'both' });
    a.onfinish = () => f.remove();
  }

  function drop(flight, e, o) {                   // true if a bomb was dropped (the plane is over the screen)
    const p = flight.querySelector('.pl-plane');
    if (!p) return false;
    const r = p.getBoundingClientRect(), W = window.innerWidth, H = window.innerHeight;
    const x = r.left + r.width / 2, y = r.bottom;
    if (x < 0 || x > W || y < 0 || y > H) return false;
    const b = document.createElement('div');
    b.className = 'pl-bomb';
    b.style.setProperty('--bs', Math.max(18, r.height * 0.45) + 'px');
    b.innerHTML = BOMB;
    sky.appendChild(b);
    const fall = H * (0.08 + Math.random() * 0.22);     // never more than 30% of the screen height
    const drift = (flight.classList.contains('rev') ? 1 : -1) * W * (0.02 + Math.random() * 0.05);
    const spin = (Math.random() < 0.5 ? -1 : 1) * (20 + Math.random() * 40);
    const a = b.animate([
      { transform: `translate(${x}px, ${y}px) rotate(0deg)` },
      { transform: `translate(${x + drift}px, ${y + fall}px) rotate(${spin}deg)` },
    ], { duration: 450 + fall / H * 1500, easing: 'cubic-bezier(.45,0,.9,.6)', fill: 'forwards' });
    a.onfinish = () => {                                 // freeze, flash, become a butterfly
      b.classList.add('freeze');
      setTimeout(() => {
        b.remove(); butterfly(x + drift, y + fall, e);
        if (o && o.sound && window.AudioKit && AudioKit.ready && AudioKit.party)
          AudioKit.party((x + drift) / W * 2 - 1);                     // popper + chime from that side
      }, 360);
    };
    return true;
  }

  function next() {
    if (!flying && queue.length) { const [e, o] = queue.shift(); launch(e, o); }
  }

  return {
    fly(e, o) {                                // one plane at a time, the rest wait their turn
      setup();
      queue.push([e, o]);
      if (queue.length > 3) queue.shift();
      next();
    },
  };
})();
