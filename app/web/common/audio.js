// Shared sound + voice for all games (Web Audio synth, browser speech synthesis)
// and the corner controls (menu, rules, voice, mute). Recorded loops live in common/sounds/.
//   AudioKit.mount({rules: fn?})          adds "enable sound" overlay + buttons
//   AudioKit.tone(freq, delay, dur, type, vol, freqEnd)  AudioKit.noise(delay, dur, vol)
//   AudioKit.say(text, {urgent, excited, onend})
window.AudioKit = (() => {
  const qs = new URLSearchParams(location.search);
  const synth = window.speechSynthesis;
  let ctx = null, muted = false, voice = null, lang = 'en', rateMul = 1;   // rateMul: VOICE_RATE from .env
  const T = (k, p) => (window.I18N ? I18N.t(k, p) : k);
  try { muted = localStorage.getItem('muted') === '1'; } catch (e) {}
  if (qs.get('sound') === '0') muted = true;

  // ---------- synth primitives ----------
  function tone(freq, delay, dur, type, vol, freqEnd) {
    if (!ctx || muted) return;
    const t0 = ctx.currentTime + (delay || 0);
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type || 'sine'; o.frequency.setValueAtTime(freq, t0);
    if (freqEnd) o.frequency.exponentialRampToValueAtTime(freqEnd, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol || 0.2, t0 + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g).connect(ctx.destination); o.start(t0); o.stop(t0 + dur + 0.02);
  }
  // a recorded loop (e.g. the plane engine) played for `dur` seconds: loud at once, fading out by
  // the end; optional stereo pan from one side to the other and a playback-rate tweak
  const buffers = {};
  function loadBuffer(url) {
    if (!buffers[url]) buffers[url] = fetch(url).then(r => r.arrayBuffer()).then(a => ctx.decodeAudioData(a));
    return buffers[url];
  }
  async function loop(url, dur, o = {}) {
    if (!ctx || muted) return;
    let buf;
    try { buf = await loadBuffer(url); } catch (e) { delete buffers[url]; return; }
    const t0 = ctx.currentTime, end = t0 + dur, vol = o.vol || 0.5;
    const s = ctx.createBufferSource(), g = ctx.createGain();
    s.buffer = buf; s.loop = true; s.playbackRate.value = o.rate || 1;
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol, t0 + Math.min(0.5, dur / 4));        // appears: full volume
    g.gain.setValueAtTime(vol, t0 + dur * (o.hold || 0.25));
    g.gain.linearRampToValueAtTime(0.0001, end);                                  // fades away to the end
    let node = s.connect(g);
    if (ctx.createStereoPanner && o.panFrom !== undefined) {
      const p = ctx.createStereoPanner();
      p.pan.setValueAtTime(o.panFrom, t0); p.pan.linearRampToValueAtTime(o.panTo || 0, end);
      node = node.connect(p);
    }
    node.connect(ctx.destination);
    s.start(t0, Math.random() * buf.duration);                                   // a different bit each time
    s.stop(end + 0.05);
  }
  // ---------- "party": a rich party-popper pop + a magic chime (butterflies from the bomber plane)
  // layered: crack + low thump + confetti rustle, then an ascending bell arpeggio with an octave
  // overtone and a detuned twin per note (shimmer), spread in stereo and sent to a soft reverb
  let reverb = null;
  function room() {
    if (reverb) return reverb;
    const len = ctx.sampleRate * 1.8, ir = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let c = 0; c < 2; c++) {
      const d = ir.getChannelData(c);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3);
    }
    const conv = ctx.createConvolver(), wet = ctx.createGain();
    conv.buffer = ir; wet.gain.value = 0.35;
    conv.connect(wet).connect(ctx.destination);
    reverb = conv;
    return reverb;
  }
  function party(pan = 0, vol = 0.5) {
    if (!ctx || muted) return;
    const t0 = ctx.currentTime + 0.01, out = ctx.createGain(), p = ctx.createStereoPanner ? ctx.createStereoPanner() : null;
    out.gain.value = vol;
    if (p) { p.pan.value = Math.max(-0.8, Math.min(0.8, pan)); out.connect(p).connect(ctx.destination); }
    else out.connect(ctx.destination);
    out.connect(room());
    const burst = (dur, type, freq, q, v, at = 0) => {         // filtered noise burst
      const b = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * dur), ctx.sampleRate), d = b.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      const s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
      f.type = type; f.frequency.value = freq; f.Q.value = q;
      g.gain.setValueAtTime(v, t0 + at); g.gain.exponentialRampToValueAtTime(0.0001, t0 + at + dur);
      s.buffer = b; s.connect(f).connect(g).connect(out); s.start(t0 + at);
    };
    burst(0.05, 'highpass', 1400, 0.7, 0.9);                    // crack of the popper
    burst(0.12, 'bandpass', 2600, 1.2, 0.5);
    const th = ctx.createOscillator(), tg = ctx.createGain();   // low "puff"
    th.frequency.setValueAtTime(170, t0); th.frequency.exponentialRampToValueAtTime(55, t0 + 0.12);
    tg.gain.setValueAtTime(0.7, t0); tg.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.16);
    th.connect(tg).connect(out); th.start(t0); th.stop(t0 + 0.2);
    for (let i = 0; i < 6; i++) burst(0.05, 'bandpass', 5000 + Math.random() * 4000, 3, 0.06, 0.05 + i * 0.05 + Math.random() * 0.03);  // confetti
    // magic chime: major pentatonic run upwards from a random key
    const base = 1046.5 * Math.pow(2, Math.floor(Math.random() * 5) / 12), steps = [0, 4, 7, 9, 12, 16, 19];
    steps.forEach((st, i) => {
      const at = t0 + 0.07 + i * 0.065, f = base * Math.pow(2, st / 12), np = ctx.createStereoPanner ? ctx.createStereoPanner() : null;
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(0.16, at + 0.008);
      g.gain.exponentialRampToValueAtTime(0.0001, at + 0.9);
      if (np) { np.pan.value = Math.max(-1, Math.min(1, pan + (i % 2 ? 0.35 : -0.35))); g.connect(np).connect(out); } else g.connect(out);
      [[f, 'sine', 1], [f * 1.004, 'sine', 0.6], [f * 2, 'triangle', 0.25], [f * 3.01, 'sine', 0.08]].forEach(([fr, ty, v]) => {
        const o = ctx.createOscillator(), og = ctx.createGain();
        o.type = ty; o.frequency.value = fr; og.gain.value = v;
        o.connect(og).connect(g); o.start(at); o.stop(at + 1);
      });
    });
  }
  function noise(delay, dur, vol, hp) {
    if (!ctx || muted) return;
    const t0 = ctx.currentTime + (delay || 0);
    const b = ctx.createBuffer(1, Math.max(1, ctx.sampleRate * dur), ctx.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length);
    const s = ctx.createBufferSource(), g = ctx.createGain(), f = ctx.createBiquadFilter();
    f.type = 'highpass'; f.frequency.value = hp || 1500; g.gain.value = vol || 0.2;
    s.buffer = b; s.connect(f).connect(g).connect(ctx.destination); s.start(t0);
  }

  // ---------- voice: female, Chinese-speaker accent preferred ----------
  // Edge online voices: Luna (en-SG), Xiaoxiao (zh-CN), Yan (en-HK); fallback female English.
  const RU_PREFS = [                              // Russian: female voices (Edge online / Windows / macOS)
    ...['svetlana', 'dariya', 'irina', 'ekaterina', 'milena', 'alena', 'yuliya', 'female']
      .map(n => v => /^ru/i.test(v.lang) && v.name.toLowerCase().includes(n)),
    v => /^ru/i.test(v.lang),
  ];
  const VOICE_PREFS = [
    v => /luna/i.test(v.name) && /en-SG/i.test(v.lang),
    v => /xiaoxiao|xiaoyi/i.test(v.name),
    v => /yan/i.test(v.name) && /en-HK/i.test(v.lang),
    v => /en-(HK|SG)/i.test(v.lang) && !/sam|wayne/i.test(v.name),
    v => /zh-(CN|TW|HK)/i.test(v.lang) && /huihui|hsiaochen|hsiaoyu|hiugaai|tracy|yaoyao/i.test(v.name),
    ...['zira', 'aria', 'jenny', 'ava', 'emma', 'michelle', 'samantha', 'hazel', 'susan', 'female', 'linda']
      .map(n => v => /^en/i.test(v.lang) && v.name.toLowerCase().includes(n)),
  ];
  // French / Spanish: female voices (Edge online / Windows / macOS / Android)
  const FR_PREFS = [
    ...['denise', 'vivienne', 'eloise', 'hortense', 'julie', 'brigitte', 'amelie', 'audrey', 'marie', 'female']
      .map(n => v => /^fr/i.test(v.lang) && v.name.toLowerCase().includes(n)),
    v => /^fr-FR/i.test(v.lang), v => /^fr/i.test(v.lang),
  ];
  const ES_PREFS = [
    ...['elvira', 'ximena', 'dalia', 'helena', 'laura', 'sabina', 'paloma', 'monica', 'paulina', 'female']
      .map(n => v => /^es/i.test(v.lang) && v.name.toLowerCase().includes(n)),
    v => /^es-ES/i.test(v.lang), v => /^es/i.test(v.lang),
  ];
  const PREFS = { ru: RU_PREFS, fr: FR_PREFS, es: ES_PREFS };
  function femaleVoices() {
    const vs = synth ? synth.getVoices() : [], out = [];
    (PREFS[lang] || VOICE_PREFS).forEach(p => vs.filter(p).forEach(v => { if (!out.includes(v)) out.push(v); }));
    return out;
  }
  const voiceKey = () => (lang === 'en' ? 'voice' : 'voice_' + lang);
  function pickVoice() {
    const vs = synth ? synth.getVoices() : [];
    let want = qs.get('voice');
    if (!want) { try { want = localStorage.getItem(voiceKey()); } catch (e) {} }
    const fits = v => (PREFS[lang] ? new RegExp('^' + lang, 'i') : /^(en|zh)/i).test(v.lang);
    voice = (want && vs.find(v => fits(v) && v.name.toLowerCase().includes(want.toLowerCase())))
         || femaleVoices()[0] || vs.find(v => new RegExp('^' + lang, 'i').test(v.lang)) || null;
  }
  if (synth) { pickVoice(); synth.onvoiceschanged = pickVoice; }
  // TT mode (TikTok LIVE Studio / launcher): tell the server which voices this browser has, so we can
  // see what Studio's built-in browser offers (it is not Chrome)
  let voicesReported = false;
  function reportVoices(final) {
    if (voicesReported || qs.get('tt') !== '1') return;
    const vs = synth ? synth.getVoices() : [];
    if (!vs.length && !final) return;
    voicesReported = true;
    const msg = 'voices (' + lang + '): ' + (synth ? '' : 'NO speechSynthesis; ') +
      (vs.map(v => v.name + ' [' + v.lang + ']').join('; ') || 'none') +
      ' | chosen: ' + (voice ? voice.name : '-') + ' | ua: ' + navigator.userAgent;
    try {
      fetch('/api/client-log', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                 body: JSON.stringify({ page: location.pathname, msg }) });
    } catch (e) {}
  }
  if (synth) synth.addEventListener && synth.addEventListener('voiceschanged', () => setTimeout(() => reportVoices(false), 300));
  setTimeout(() => reportVoices(false), 1500);
  setTimeout(() => reportVoices(true), 5000);

  function say(text, o) {
    o = o || {};
    if (!synth || !ctx || muted) { o.onend && setTimeout(o.onend, 0); return; }
    if (o.urgent) synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    if (voice) u.voice = voice;
    u.lang = voice ? voice.lang : ({ ru: 'ru-RU', fr: 'fr-FR', es: 'es-ES' }[lang] || 'en-US'); u.volume = 1;
    // one speed for all lines (excited ones differ only by pitch); o.rate = exact speed, e.g. 1 for key phrases
    u.rate = o.rate || Math.min(10, 1.05 * rateMul); u.pitch = o.pitch || (o.excited ? 1.35 : 1.05);
    if (o.onend) u.onend = o.onend;
    u.onerror = ev => { if (window.clientLog) clientLog('speech error: ' + (ev.error || '?')); if (o.onend) o.onend(); };
    synth.speak(u);
  }
  function nextVoice() {
    const list = femaleVoices();
    if (!list.length) return;
    voice = list[(list.indexOf(voice) + 1) % list.length];
    try { localStorage.setItem(voiceKey(), voice.name); } catch (e) {}
    say(T('voice.hello', { name: voice.name.replace(/Microsoft|Online|\(Natural\)|-.*$/g, '').trim() }), { urgent: true });
  }

  // ---------- controls ----------
  let muteBtn = null;
  function setMuted(m) {
    muted = m;
    if (muteBtn) muteBtn.textContent = m ? '🔇' : '🔊';
    try { localStorage.setItem('muted', m ? '1' : '0'); } catch (e) {}
    if (m && synth) synth.cancel();
  }
  function enable() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    ctx.resume();
  }
  function btn(icon, titleKey, onclick) {
    const b = document.createElement('button');
    b.className = 'ctl-btn'; b.textContent = icon; b.dataset.i18nTitle = titleKey; b.title = T(titleKey);
    b.onclick = onclick;
    return b;
  }
  function mount(o) {
    o = o || {};
    const bar = document.createElement('div'); bar.className = 'ctl-bar';
    bar.appendChild(btn('☰', 'ctl.menu', () => { location.href = '/'; }));
    if (o.rules) bar.appendChild(btn('?', 'ctl.rules', o.rules));
    bar.appendChild(btn('🗣', 'ctl.voice', () => { enable(); setMuted(false); nextVoice(); }));
    muteBtn = btn('🔊', 'ctl.mute', () => { enable(); setMuted(!muted); });
    bar.appendChild(muteBtn);
    document.body.appendChild(bar);
    setMuted(muted);
    if (!muted) {
      // try without a click first: TikTok LIVE Studio / OBS sources and Chrome (for a site where sound was
      // used often) allow it; only if the browser refuses, ask for one click
      try { enable(); } catch (e) {}
      setTimeout(() => {
        if (ctx && ctx.state === 'running') return;      // sound already works: no overlay
        if (qs.get('tt') === '1') return;                // TT mode: never cover the stream picture
        const ov = document.createElement('div'); ov.className = 'ctl-unlock';
        const b = document.createElement('button'); b.dataset.i18n = 'unlock'; b.textContent = T('unlock');
        ov.appendChild(b); document.body.appendChild(ov);
        ov.onclick = () => { enable(); ov.remove(); say(T(o.hello || 'b.v.hello'), { rate: o.helloRate }); };
      }, 400);
    }
  }

  function setRate(r) { if (r > 0) rateMul = r; }
  function setLang(l) {
    lang = l;
    pickVoice();
  }

  return {
    tone, noise, loop, party, say, mount, enable, setLang, setRate,
    get ready() { return !!ctx && !muted; },
    get speaking() { return !!synth && (synth.speaking || synth.pending); },
    get running() { return !!ctx && ctx.state === 'running'; },      // browser actually allows sound
    resetSpeech() { if (synth) synth.cancel(); },
    suspend() { if (ctx) ctx.suspend(); if (synth) synth.cancel(); },   // silence now, incl. already scheduled tones
    ignoreMute() { muted = false; },          // menu alerts: independent of the games' 🔇 button
  };
})();
