// Shared sound + voice for all games (Web Audio synth, browser speech synthesis)
// and the corner controls (menu, rules, voice, mute). No audio files.
//   AudioKit.mount({rules: fn?})          adds "enable sound" overlay + buttons
//   AudioKit.tone(freq, delay, dur, type, vol, freqEnd)  AudioKit.noise(delay, dur, vol)
//   AudioKit.say(text, {urgent, excited, onend})
window.AudioKit = (() => {
  const qs = new URLSearchParams(location.search);
  const synth = window.speechSynthesis;
  let ctx = null, muted = false, voice = null, lang = 'en';
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
  function femaleVoices() {
    const vs = synth ? synth.getVoices() : [], out = [];
    (lang === 'ru' ? RU_PREFS : VOICE_PREFS).forEach(p => vs.filter(p).forEach(v => { if (!out.includes(v)) out.push(v); }));
    return out;
  }
  const voiceKey = () => (lang === 'en' ? 'voice' : 'voice_' + lang);
  function pickVoice() {
    const vs = synth ? synth.getVoices() : [];
    let want = qs.get('voice');
    if (!want) { try { want = localStorage.getItem(voiceKey()); } catch (e) {} }
    const fits = v => (lang === 'ru' ? /^ru/i : /^(en|zh)/i).test(v.lang);
    voice = (want && vs.find(v => fits(v) && v.name.toLowerCase().includes(want.toLowerCase())))
         || femaleVoices()[0] || vs.find(v => new RegExp('^' + lang, 'i').test(v.lang)) || null;
  }
  if (synth) { pickVoice(); synth.onvoiceschanged = pickVoice; }

  function say(text, o) {
    o = o || {};
    if (!synth || !ctx || muted) { o.onend && setTimeout(o.onend, 0); return; }
    if (o.urgent) synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    if (voice) u.voice = voice;
    u.lang = voice ? voice.lang : (lang === 'ru' ? 'ru-RU' : 'en-US'); u.volume = 1;
    u.rate = o.excited ? 1.2 : 1.05; u.pitch = o.excited ? 1.35 : 1.05;
    if (o.onend) u.onend = o.onend;
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
      const ov = document.createElement('div'); ov.className = 'ctl-unlock';
      const b = document.createElement('button'); b.dataset.i18n = 'unlock'; b.textContent = T('unlock');
      ov.appendChild(b); document.body.appendChild(ov);
      ov.onclick = () => { enable(); ov.remove(); say(T(o.hello || 'b.v.hello')); };
    }
  }

  function setLang(l) {
    lang = l;
    pickVoice();
  }

  return {
    tone, noise, say, mount, enable, setLang,
    get ready() { return !!ctx && !muted; },
    get speaking() { return !!synth && (synth.speaking || synth.pending); },
  };
})();
