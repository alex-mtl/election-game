// Like balloons, shared by all pages (streamer overlay + games).
//   Balloons.mount({ground, width, sound})
//     ground: show inflating balloons at the bottom (true) or only lift-offs (false)
//     area:   element to put the ground row in (e.g. the 9:16 game column); default the whole window
//     bottom: where the ground row stands inside it (CSS length, default 5vh)
//     width:  CSS width of a balloon on the ground (default 20vw); it grows 1.5x while rising
//     sound:  whoosh + "thank you" voice on lift-off
//   Balloons.render(msg.balloons)   inflating balloons (from the live state)
//   Balloons.launch(feedEvent)      a viewer reached 100 likes: lift off
window.Balloons = (() => {
  let opts = {}, ground = null, sky = null, per = 100;
  const onGround = new Map();               // viewer id -> balloon element
  const clean = n => (n || '').replace(/[^\p{L}\p{N} ._'-]/gu, '').trim() || '?';

  const CSS = `
  .bl-ground { position: fixed; left: 0; right: 0; bottom: 5vh; height: 40vh; pointer-events: none; z-index: 28; }
  .bl-sky { position: fixed; inset: 0; pointer-events: none; overflow: hidden; z-index: 29; }
  .balloon { position: relative; width: var(--bw); flex: none; transform-origin: 50% 100%; }
  .balloon .body { position: relative; width: 100%; filter: drop-shadow(0 0 calc(var(--bw) * .06) rgba(255, 60, 140, .55)); }
  .balloon svg { display: block; width: 100%; height: auto; overflow: visible; }
  .balloon .av { position: absolute; left: 27%; top: 20%; width: 46%; height: auto; aspect-ratio: 1; border-radius: 50%;
                 object-fit: cover; border: calc(var(--bw) * .0225) solid #fff; box-shadow: 0 0 calc(var(--bw) * .05) rgba(0,0,0,.35);
                 display: flex; align-items: center; justify-content: center; color: #fff;
                 font: 900 calc(var(--bw) * .2) 'Segoe UI', sans-serif; }
  .balloon .tag { position: absolute; left: 50%; top: 63%; transform: translateX(-50%); max-width: 92%;
                  padding: .15em .6em; border-radius: 999px; background: rgba(0,0,0,.55); color: #fff;
                  font: 800 calc(var(--bw) * .085) 'Segoe UI', sans-serif; white-space: nowrap;
                  overflow: hidden; text-overflow: ellipsis; }
  /* inflating at the bottom: grows with likes, wobbles; each viewer gets a random spot (--x in % of the width) */
  .balloon.inflating { position: absolute; bottom: 0; left: calc(var(--x, 50) * 1%); margin-left: calc(var(--bw) / -2);
                       transition: transform .35s cubic-bezier(.3, 1.6, .5, 1), opacity .6s;
                       animation: bl-wobble 2.6s ease-in-out infinite; }
  .balloon .meter { position: absolute; left: 50%; bottom: calc(var(--bw) * -.08); transform: translateX(-50%);
                    font: 900 calc(var(--bw) * .1) 'Segoe UI', sans-serif; color: #fff;
                    text-shadow: 0 0 calc(var(--bw) * .03) #ff2d75, 0 0 2px #000; white-space: nowrap; }
  .balloon.leaving { opacity: 0; }
  @keyframes bl-wobble { 0%, 100% { rotate: -2deg; } 50% { rotate: 2deg; } }
  /* lift off: rise to the top, swaying around its own vertical axis and growing 1.5x while climbing */
  .bl-flyer { position: absolute; bottom: 0;
              animation: bl-rise var(--dur) cubic-bezier(.45, .05, .6, 1) forwards, bl-grow var(--dur) ease-out forwards; }
  .bl-flyer .sway { animation: bl-sway var(--period) ease-in-out infinite alternate; }
  .bl-flyer .meter { display: none; }
  @keyframes bl-rise { 0% { transform: translateY(0) scale(1); } 8% { transform: translateY(-3vh) scale(1.08); }
                       100% { transform: translateY(-130vh) scale(1); } }
  @keyframes bl-grow { from { scale: 1; } 42%, to { scale: var(--grow, 1.5); } }
  @keyframes bl-sway { from { transform: translateX(calc(var(--amp) * -1)) rotate(calc(var(--tilt) * -1)); }
                       to { transform: translateX(var(--amp)) rotate(var(--tilt)); } }
  .bl-burst { position: absolute; font: 900 calc(var(--bw) * .2) 'Segoe UI', sans-serif; color: #fff; pointer-events: none;
              text-shadow: 0 0 calc(var(--bw) * .05) #ff2d75, 0 0 2px #000; animation: bl-burst 1.6s ease-out forwards; white-space: nowrap; }
  @keyframes bl-burst { from { opacity: 0; transform: translate(-50%, 0) scale(.6); }
                        20% { opacity: 1; transform: translate(-50%, -2vh) scale(1.1); }
                        to { opacity: 0; transform: translate(-50%, -10vh) scale(1); } }`;

  // every balloon gets its own colour when it appears: a random rainbow hue, light and bright
  // (pastel with a little neon) - never dark navy / green / purple
  let gid = 0;
  function svg() {
    const id = 'bl-g' + (++gid), h = Chroma.hue(Math.floor(Math.random() * 360));
    const sat = 90 + Math.floor(Math.random() * 10);
    // blue / violet look darker at the same lightness: lift them so they stay pastel
    const up = h >= 205 && h <= 295 ? 9 : (h >= 180 && h < 205) || (h > 295 && h <= 320) ? 4 : 0;
    const light = `hsl(${h} ${sat}% ${90 + up / 3}%)`, main = `hsl(${h} ${sat}% ${70 + up}%)`,
          edge = `hsl(${h} 80% ${60 + up}%)`;
    return `<svg viewBox="0 0 100 150">
      <defs><radialGradient id="${id}" cx="35%" cy="30%" r="75%">
        <stop offset="0" stop-color="${light}"/><stop offset=".45" stop-color="${main}"/><stop offset="1" stop-color="${edge}"/>
      </radialGradient></defs>
      <path d="M50 92 C 22 72, 2 52, 6 30 C 10 10, 36 4, 50 22 C 64 4, 90 10, 94 30 C 98 52, 78 72, 50 92 Z" fill="url(#${id})"/>
      <ellipse cx="27" cy="27" rx="9" ry="5" fill="#fff" opacity=".45" transform="rotate(-35 27 27)"/>
      <path d="M45 97 L50 91 L55 97 Z" fill="${edge}"/>
      <path d="M50 97 C 44 108, 56 118, 49 128 C 44 136, 54 142, 50 150" stroke="#fff" stroke-opacity=".75"
            stroke-width="1.1" fill="none"/></svg>`;
  }

  function avatar(name, url) {
    if (url && /^https:\/\//.test(url)) {
      const img = document.createElement('img');
      img.className = 'av'; img.referrerPolicy = 'no-referrer'; img.alt = ''; img.src = url;
      img.onerror = () => img.replaceWith(avatar(name, ''));
      return img;
    }
    const hue = Chroma.hue([...(name || '?')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7));
    const d = document.createElement('div');
    d.className = 'av'; d.textContent = (clean(name)[0] || '?').toUpperCase();
    d.style.background = `hsl(${hue} 85% 55%)`;
    return d;
  }
  function makeBalloon(u) {
    const b = document.createElement('div');
    b.className = 'balloon';
    b.innerHTML = '<div class="sway"><div class="body">' + svg() + '<div class="tag"></div></div></div><div class="meter"></div>';
    b.querySelector('.body').insertBefore(avatar(u.name, u.avatar), b.querySelector('.tag'));
    b.querySelector('.tag').textContent = u.name;
    return b;
  }

  // A free spot for a new balloon: random, its whole box at least 10% away from the edges
  // (centre 20..80%), and the farthest of a few candidates from balloons already there.
  function pickX() {
    const taken = [...onGround.values()].map(el => parseFloat(el.dataset.x));
    let best = 50, bestGap = -1;
    for (let i = 0; i < 12; i++) {
      const x = 20 + Math.random() * 60;
      const gap = taken.length ? Math.min(...taken.map(t => Math.abs(t - x))) : 100;
      if (gap > bestGap) { best = x; bestGap = gap; }
    }
    return best.toFixed(1);
  }

  function mount(o) {
    opts = o || {};
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);
    document.documentElement.style.setProperty('--bw', opts.width || '20vw');
    sky = document.createElement('div'); sky.className = 'bl-sky';
    document.body.appendChild(sky);
    if (opts.ground) {
      ground = document.createElement('div'); ground.className = 'bl-ground';
      if (opts.area) ground.style.position = 'absolute';
      if (opts.bottom) ground.style.bottom = opts.bottom;
      (opts.area || document.body).appendChild(ground);
    }
  }

  function render(s) {
    if (!s) return;
    per = s.perBalloon || per;
    if (!ground) return;
    const seen = new Set();
    (s.inflating || []).forEach(u => {
      seen.add(u.id);
      let b = onGround.get(u.id);
      if (!b) {
        b = makeBalloon(u);
        b.classList.add('inflating');
        b.dataset.x = pickX();
        b.style.setProperty('--x', b.dataset.x);
        b.style.transform = 'scale(.45)';
        ground.appendChild(b);
        onGround.set(u.id, b);
      }
      b.style.transform = 'scale(' + (0.45 + 0.55 * Math.min(1, u.fill)).toFixed(3) + ')';
      b.querySelector('.meter').textContent = '❤ ' + u.progress + '/' + per;
    });
    onGround.forEach((b, id) => {              // owner stopped liking -> fade away
      if (!seen.has(id)) {
        onGround.delete(id);
        b.classList.add('leaving');
        setTimeout(() => b.remove(), 700);
      }
    });
  }

  function launch(e) {
    if (!sky) return;
    per = e.per || per;
    let b = onGround.get(e.id), x;
    const W = window.innerWidth;
    if (b) {                                   // take the inflating balloon off the ground
      const r = b.getBoundingClientRect();
      x = r.left + r.width / 2;
      onGround.delete(e.id);
      b.remove();
      b.classList.remove('inflating');
      b.style.transform = '';
    } else {
      b = makeBalloon(e);
      x = W / 2;
    }
    x = Math.min(Math.max(x, W * 0.2), W * 0.8);   // 1.5x wide at the top + sway must stay on screen
    const rnd = (a, z) => a + Math.random() * (z - a);
    const fly = document.createElement('div');
    fly.className = 'bl-flyer';
    fly.style.setProperty('--dur', rnd(6.5, 8.5).toFixed(2) + 's');
    fly.style.setProperty('--period', rnd(1.3, 2.1).toFixed(2) + 's');
    fly.style.setProperty('--tilt', rnd(3, 8).toFixed(1) + 'deg');
    fly.appendChild(b);
    sky.appendChild(fly);
    const bw = b.getBoundingClientRect().width;
    fly.style.setProperty('--amp', (bw * rnd(0.12, 0.3)).toFixed(1) + 'px');
    fly.style.left = (x - bw / 2) + 'px';
    const burst = document.createElement('div');
    burst.className = 'bl-burst'; burst.textContent = '❤ ' + per + '  ' + clean(e.name);
    burst.style.left = x + 'px'; burst.style.bottom = '22vh';
    sky.appendChild(burst);
    setTimeout(() => burst.remove(), 1700);
    setTimeout(() => fly.remove(), 9000);
    if (opts.sound && window.AudioKit && AudioKit.ready) {
      AudioKit.tone(400, 0, 0.6, 'sine', 0.12, 1200);
      [880, 1175, 1568].forEach((f, i) => AudioKit.tone(f, 0.15 + i * 0.08, 0.3, 'sine', 0.1));
      AudioKit.say(I18N.t('s.v.balloon', { name: clean(e.name), n: per }));
    }
  }

  return { mount, render, launch };
})();
