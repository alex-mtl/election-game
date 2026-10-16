// Welcome viewers who join the LIVE, on stream pages (games, streamer overlay):
// a small pill with avatars + a voice greeting. Joins are merged and paced so the stream
// isn't flooded: at most one greeting every GAP_MS, e.g. "Welcome Alex, Mike and 3 more!".
//   Greeter.push(feedEvent)       // from Live.start({onFeed})
window.Greeter = (() => {
  const GAP_MS = 8000, SHOW_MS = 4500;
  const t = (k, p) => I18N.t(k, p);
  const clean = n => (n || '').replace(/[^\p{L}\p{N} ._'-]/gu, '').trim() || '?';
  let pending = [], last = 0, box = null;

  function css() {
    const s = document.createElement('style');
    s.textContent = `
      .greet { position: fixed; left: 50%; bottom: 17vh; transform: translateX(-50%); z-index: 35;
               display: flex; align-items: center; gap: .5em; max-width: 92vw; padding: .45em 1.1em .45em .5em;
               border-radius: 999px; background: rgba(10, 0, 25, .85); color: #fff; pointer-events: none;
               border: 2px solid #ffd84a; box-shadow: 0 0 1.2em rgba(255, 216, 74, .5);
               font: 800 min(4.2vw, 2.4vh) 'Segoe UI', system-ui, sans-serif; white-space: nowrap;
               animation: greetIn .45s cubic-bezier(.2, 1.5, .4, 1), greetOut .4s ease-in ${(SHOW_MS - 400) / 1000}s forwards; }
      .greet .avs { display: flex; }
      .greet .av { width: 2.1em; height: 2.1em; border-radius: 50%; object-fit: cover; border: 2px solid #fff;
                   margin-left: -.6em; display: inline-flex; align-items: center; justify-content: center;
                   font-weight: 900; color: #000; flex: none; }
      .greet .av:first-child { margin-left: 0; }
      .greet .txt { overflow: hidden; text-overflow: ellipsis; }
      @keyframes greetIn { from { opacity: 0; transform: translate(-50%, 1.5em) scale(.7); } }
      @keyframes greetOut { to { opacity: 0; transform: translate(-50%, -1em); } }`;
    document.head.appendChild(s);
  }

  function avatar(name, url) {
    if (url && /^https:\/\//.test(url)) {
      const img = document.createElement('img');
      img.className = 'av'; img.referrerPolicy = 'no-referrer'; img.alt = ''; img.src = url;
      img.onerror = () => img.replaceWith(avatar(name, ''));
      return img;
    }
    const d = document.createElement('span');
    const hue = [...(name || '?')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
    d.className = 'av'; d.textContent = (clean(name)[0] || '?').toUpperCase();
    d.style.background = `hsl(${window.Chroma ? Chroma.hue(hue) : hue} 90% 60%)`;   // no green in chroma key mode
    return d;
  }

  // "Alex" | "Alex and Mike" | "Alex, Mike and Sarah" | "Alex, Mike and 4 more"
  function who(batch) {
    const n = batch.map(e => clean(e.name));
    if (n.length === 1) return n[0];
    if (n.length <= 3) return n.slice(0, -1).join(', ') + t('greet.and') + n[n.length - 1];
    return t('greet.more', { names: n.slice(0, 2).join(', '), n: n.length - 2 });
  }

  function show(batch) {
    if (!box) { css(); box = true; }
    const pill = document.createElement('div');
    pill.className = 'greet';
    const avs = document.createElement('span'); avs.className = 'avs';
    batch.slice(0, 3).forEach(e => avs.appendChild(avatar(e.name, e.avatar)));
    const txt = document.createElement('span'); txt.className = 'txt';
    txt.textContent = '👋 ' + t('greet.pill', { who: who(batch) });
    pill.append(avs, txt);
    document.body.appendChild(pill);
    setTimeout(() => pill.remove(), SHOW_MS + 100);
    // voice only when nothing else is being said (game announcements have priority)
    if (window.AudioKit && AudioKit.ready && !AudioKit.speaking) AudioKit.say(t('greet.voice', { who: who(batch) }));
  }

  setInterval(() => {
    if (!pending.length || Date.now() - last < GAP_MS) return;
    last = Date.now();
    show(pending.splice(0, pending.length));
  }, 500);

  return {
    push(e) {
      if (e.type !== 'join') return;
      pending.push(e);
      if (pending.length > 12) pending.shift();
    },
  };
})();
