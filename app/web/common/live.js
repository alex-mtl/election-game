// Live connection to the server: WebSocket, falls back to polling /api/state.
// Live.start({game, onState(state, msg), onEvent(event), onFeed(streamEvent)})
// - game: null = page not tied to a game (menu): only onFeed (comments / gifts of the stream)
// - follows the active game: if another game is picked in the menu, this page navigates there
// - Live.now() = server clock in seconds (timers stay in sync with the server)
// TikTok chroma key mode (html.chroma): the top of the screen is pure green and gets keyed out in
// LIVE Studio, so nothing else may be green - random colours skip the green hues.
window.Chroma = {
  // alpha mode (transparent camera zone, no key filter) needs no colour restrictions
  get on() { const c = document.documentElement.classList; return c.contains('chroma') && !c.contains('alpha'); },
  hue(h) { return this.on && h >= 65 && h <= 175 ? (h + 110) % 360 : h; },   // green -> cyan / blue / violet
};

window.Live = (() => {
  let opts, lastSeq = null, feedSeq = null, offset = 0, ws = null, pollTimer = null, wsRetry = null, version = null;

  function handle(msg) {
    offset = msg.now * 1000 - Date.now();
    // pages were updated on the server -> reload so the overlay never shows an old version
    if (msg.version) {
      if (version && msg.version !== version) { location.reload(); return; }
      version = msg.version;
    }
    if (msg.voiceRate && window.AudioKit) AudioKit.setRate(msg.voiceRate);
    if (msg.lang && window.I18N) {                 // language picked in the menu
      if (I18N.lang && I18N.lang !== msg.lang) { location.reload(); return; }
      I18N.set(msg.lang);
    }
    if (msg.feedSeq !== undefined) {               // stream feed: comments / gifts
      if (feedSeq === null || msg.feedSeq < feedSeq) feedSeq = msg.feedSeq;   // no replay on (re)load
      else {
        (msg.feed || []).filter(e => e.seq > feedSeq).forEach(e => {
          try { opts.onFeed && opts.onFeed(e); } catch (err) { console.error(err); }
        });
        feedSeq = Math.max(feedSeq, msg.feedSeq);
      }
    }
    if (opts.game && msg.active && msg.active !== opts.game) {
      location.href = '/' + msg.active + '/' + location.search;
      return;
    }
    if (msg.game !== opts.game) return;
    if (lastSeq === null || msg.seq < lastSeq) {
      lastSeq = msg.seq;                 // first message / server restart: no replay
    } else {
      (msg.events || []).filter(e => e.seq > lastSeq).forEach(e => {
        try { opts.onEvent && opts.onEvent(e); } catch (err) { console.error(err); }
      });
      lastSeq = Math.max(lastSeq, msg.seq);
    }
    try { opts.onState && opts.onState(msg.state, msg); } catch (err) { console.error(err); }
  }

  async function poll() {
    try {
      const q = '?game=' + (opts.game || '') + (lastSeq === null ? '' : '&since=' + lastSeq) +
                (feedSeq === null ? '' : '&fsince=' + feedSeq);
      handle(await (await fetch('/api/state' + q, { cache: 'no-store' })).json());
    } catch (e) { /* server unreachable: keep last state on screen */ }
  }

  function startPolling() {
    if (!pollTimer) pollTimer = setInterval(poll, 500);
  }

  function connect() {
    if (new URLSearchParams(location.search).get('poll') === '1') { startPolling(); return; }
    try {
      ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
    } catch (e) { startPolling(); return; }
    ws.onopen = () => { clearInterval(pollTimer); pollTimer = null; };
    ws.onmessage = ev => { try { handle(JSON.parse(ev.data)); } catch (e) { console.error(e); } };
    ws.onclose = () => {
      startPolling();                      // keep the overlay alive meanwhile
      clearTimeout(wsRetry);
      wsRetry = setTimeout(connect, 3000);
    };
  }
  setInterval(() => { try { ws && ws.readyState === 1 && ws.send('ping'); } catch (e) {} }, 20000);

  return {
    start(o) { opts = o; poll(); connect(); },
    now() { return (Date.now() + offset) / 1000; },
  };
})();
