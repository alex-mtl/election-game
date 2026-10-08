// Guess the Word overlay. All user text goes through textContent (no HTML injection).
(() => {
  const $ = id => document.getElementById(id);
  const A = AudioKit;
  const fmt = n => Number(n).toLocaleString('en-US');
  const clean = n => (n || '').replace(/[^\p{L}\p{N} ._'-]/gu, '').trim() || 'Someone';
  const tKey = t => (t || '').toLowerCase().replace(/\s/g, '');
  let S = null;                       // last state
  let vocab = 30000;

  // Put text into a big headline and shrink the font until it fits its container's width
  // (long words like APPLICATION on the winner / reveal screens). Re-measures only on change.
  function fitText(node, text) {
    const parent = node.parentElement;
    const key = text + '|' + parent.clientWidth;
    if (node.dataset.fit === key) return;
    node.dataset.fit = key;
    node.textContent = text;
    node.style.fontSize = '';
    node.style.display = 'inline-block';
    node.style.whiteSpace = 'nowrap';
    node.style.maxWidth = 'none';
    const anim = node.style.animation;
    node.style.animation = 'none';                       // measure without the letter-spacing intro
    const cs = getComputedStyle(parent);
    const avail = parent.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    let size = parseFloat(getComputedStyle(node).fontSize);
    while (avail > 0 && node.scrollWidth > avail && size > 8) {
      size *= 0.92;
      node.style.fontSize = size + 'px';
    }
    node.style.animation = anim;
  }

  // Same for a fixed-width cell (word in BEST GUESSES); the fitted size is cached per word.
  const cellSize = new Map();
  function fitCell(node) {
    const key = node.textContent + '|' + node.clientWidth;
    if (cellSize.has(key)) { node.style.fontSize = cellSize.get(key); return; }
    let size = parseFloat(getComputedStyle(node).fontSize);
    while (node.clientWidth > 0 && node.scrollWidth > node.clientWidth && size > 8) {
      size *= 0.92;
      node.style.fontSize = size + 'px';
    }
    cellSize.set(key, node.style.fontSize);
    if (cellSize.size > 500) cellSize.clear();
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  // avatar <img> or a colored initial when TikTok gives none / it fails to load
  function avatar(name, url) {
    const hue = [...(name || '?')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
    const fallback = () => {
      const d = el('span', 'av', (clean(name)[0] || '?').toUpperCase());
      d.style.background = `hsl(${hue} 90% 60%)`;
      return d;
    };
    if (!url || !/^https:\/\//.test(url)) return fallback();
    const img = el('img', 'av');
    img.referrerPolicy = 'no-referrer'; img.alt = ''; img.src = url;
    img.onerror = () => img.replaceWith(fallback());
    return img;
  }
  // non-linear closeness: #2 >> #20 >> #200 >> #2000
  const closeness = r => Math.max(0.03, 1 - Math.log(Math.max(1, r)) / Math.log(vocab));

  // ------------------------------------------------------------ sounds
  const FX = {
    guess(temp) {                        // blip, hotter = higher
      const f = { perfect: 1320, burning: 1046, veryhot: 880, hot: 740, warm: 587, cold: 440, freezing: 330 }[temp] || 500;
      A.tone(f, 0, 0.12, 'triangle', 0.12, f * 1.25);
    },
    leader() { A.tone(330, 0, 0.35, 'sawtooth', 0.08, 1320); A.tone(1320, 0.3, 0.2, 'sine', 0.2); A.tone(1760, 0.42, 0.35, 'sine', 0.18); },
    close(level) {                       // rising arpeggio, longer when closer
      const n = { so_close: 6, top3: 5, top10: 4, top50: 3, top100: 2 }[level] || 3;
      for (let i = 0; i < n; i++) A.tone(523 * Math.pow(1.26, i), i * 0.07, 0.22, 'square', 0.09);
    },
    jump(kind) { A.tone(200, 0, kind === 'massive' ? 0.5 : 0.3, 'sawtooth', 0.12, kind === 'massive' ? 2400 : 1200); A.noise(0, 0.25, 0.15); },
    gift() { [1568, 2093, 2637, 3136].forEach((f, i) => A.tone(f, i * 0.05, 0.3, 'sine', 0.1)); },
    follow() { A.tone(880, 0, 0.15, 'sine', 0.12); A.tone(1320, 0.1, 0.25, 'sine', 0.12); },
    hint() { for (let i = 0; i < 8; i++) A.tone(880 + i * 180, i * 0.04, 0.2, 'sine', 0.07); },
    tick(n) { A.tone(n <= 3 ? 1200 : 900, 0, 0.08, 'square', 0.1); },
    count(go) { go ? A.tone(1320, 0, 0.45, 'square', 0.16) : A.tone(660, 0, 0.18, 'square', 0.14); },
    winner() {
      [[523, 0], [659, .15], [784, .3], [1047, .45]].forEach(([f, d]) => { A.tone(f, d, 0.35, 'square', 0.14); A.tone(f / 2, d, 0.35, 'triangle', 0.18); });
      [523, 659, 784, 1047].forEach(f => A.tone(f, 0.65, 1.5, 'sawtooth', 0.06));
      A.noise(0.65, 0.6, 0.25);
    },
    timeout() { A.tone(220, 0, 0.6, 'sawtooth', 0.15, 110); A.tone(233, 0, 0.6, 'square', 0.08, 116); },
    streak(n) { [392, 523, 659, 784, 1047].slice(0, Math.min(5, 2 + n)).forEach((f, i) => A.tone(f, i * 0.09, 0.4, 'sawtooth', 0.08)); },
  };
  let lastBlip = 0;
  function fx(kind, arg) {
    if (!A.ready) return;
    if (kind === 'guess') {               // don't machine-gun blips
      const t = performance.now(); if (t - lastBlip < 90) return; lastBlip = t;
    }
    FX[kind](arg);
  }
  // voice: important moments only; low-priority lines are skipped while speaking
  function voice(text, prio) {
    if (!A.ready) return;
    if (prio === 'urgent') A.say(text, { urgent: true, excited: true });
    else if (prio === 'high' || !A.speaking) A.say(text, { excited: true });
  }

  // ------------------------------------------------------------ big toasts (queued, 1-3 s)
  const queue = []; let showing = false;
  function toast(head, sub, color, opts) {
    opts = opts || {};
    if (queue.length >= 3) queue.splice(queue.findIndex(q => !q.important), 1);   // drop the least important
    queue.push({ head, sub, color, huge: opts.huge, important: opts.important, hold: opts.hold || 1.6 });
    if (!showing) nextToast();
  }
  function nextToast() {
    const t = queue.shift();
    if (!t) { showing = false; return; }
    showing = true;
    const c = el('div', 'tcard' + (t.huge ? ' huge' : ''));
    c.style.setProperty('--c', t.color);
    c.style.setProperty('--hold', t.hold + 's');
    c.append(el('div', 'h', t.head));
    if (t.sub) c.append(el('div', 's', t.sub));
    $('toast').replaceChildren(c);
    c.querySelectorAll('.h, .s').forEach(n => fitText(n, n.textContent));
    setTimeout(() => { $('toast').replaceChildren(); nextToast(); }, (t.hold + 0.4) * 1000);
  }
  function mini(text, cls) {
    const m = el('div', 'mini ' + (cls || ''), text);
    const box = $('miniToasts');
    box.appendChild(m);
    while (box.children.length > 2) box.firstChild.remove();
    setTimeout(() => m.remove(), 2900);
  }

  // ------------------------------------------------------------ events from the server
  function onEvent(e) {
    const name = clean(e.name);
    switch (e.type) {
      case 'guess': fx('guess', tKey(e.temp)); addFresh(e); break;
      case 'new_leader':
        fx('leader');
        toast(e.comeback ? '↩ COMEBACK!' : '🔥 NEW LEADER!', name.toUpperCase() + ' — #' + fmt(e.rank), 'var(--magenta)', { important: true });
        voice((e.comeback ? 'Comeback! ' : 'New leader! ') + name + ', rank ' + e.rank + '!');
        break;
      case 'jump':
        fx('jump', e.kind);
        if (e.kind === 'massive') {
          toast('🚀 MASSIVE JUMP!', name + '  #' + fmt(e.frm) + ' → #' + fmt(e.to), 'var(--lime)', { huge: true, important: true, hold: 2 });
          voice('Massive jump by ' + name + '!');
        } else toast('BIG IMPROVEMENT!', name + '  #' + fmt(e.frm) + ' → #' + fmt(e.to), 'var(--lime)');
        break;
      case 'close':
        fx('close', e.level);
        if (e.level === 'so_close') {
          toast('😱 SO CLOSE!', name + ' is ONE STEP AWAY — #2', 'var(--pink)', { huge: true, important: true, hold: 2.2 });
          voice('So close! ' + name + ' is one step away!', 'high');
        } else if (e.level === 'top3') {
          toast('⚡ TOP 3!', name + ' — #' + e.rank, 'var(--orange)', { important: true });
          voice(name + ' is in the top three!');
        } else if (e.level === 'top10') {
          toast('🔥 TOP 10!', name + ' — #' + e.rank, 'var(--orange)');
        } else {
          mini('🌡 ' + name + ' reached ' + (e.level === 'top50' ? 'TOP 50' : 'TOP 100') + ' — #' + e.rank, 'small');
        }
        break;
      case 'streak':
        fx('streak', e.n);
        toast('🔥 ' + e.n + ' WIN STREAK', name, 'var(--orange)', { huge: e.n >= 3, important: true, hold: e.n >= 5 ? 2.8 : 2 });
        voice(name + ' is on a ' + e.n + ' win streak!', 'high');
        break;
      case 'gift':
        fx('gift');
        mini('🎁 ' + name + ' sent ' + clean(e.gift) + (e.count > 1 ? ' ×' + e.count : ''), 'gift');
        break;
      case 'follow':
        fx('follow');
        mini('💜 ' + name + ' followed — thank you!', 'follow');
        break;
      case 'unknown':
        mini('❓ ' + clean(e.word) + ' — not in my dictionary', 'unknown');
        break;
      case 'hint':
        fx('hint');
        toast('💡 HINT', (e.text + ' ' + e.word).trim(), 'var(--yellow)', { important: true, hold: 2.4 });
        voice('Hint! ' + e.text + ' ' + e.word.toLowerCase(), 'high');
        break;
      case 'timeout':
        fx('timeout');
        toast(e.reason === 'skip' ? '⏭ ROUND SKIPPED' : "⏰ TIME'S UP!", '', 'var(--orange)', { huge: true, important: true, hold: 1.4 });
        voice(e.reason === 'skip' ? 'Round skipped!' : "Time's up!", 'urgent');
        break;
      case 'winner':
        fx('winner');
        if (e.reason === 'exact') voice('We have a winner! ' + name + ' found the word: ' + e.word.toLowerCase() + '!', 'urgent');
        else if (e.name) voice('The winner is ' + name + '! The word was ' + e.word.toLowerCase() + '.', 'high');
        else voice('Nobody found it! The word was ' + e.word.toLowerCase() + '.', 'high');
        break;
      case 'round_start':
        voice((e.roundType === 'speed' ? 'Speed round! ' : 'Round ' + e.round + '. ') + 'Go!', 'urgent');
        break;
    }
  }

  // ------------------------------------------------------------ render state
  let prevWords = new Map(), prevHunters = new Map(), prevHintCount = 0;

  function renderHunters(list) {
    const box = $('hunterList');
    box.replaceChildren();
    if (!list.length) { box.append(el('li', 'hrow empty', 'No hunters yet — be the first!')); return; }
    const medals = ['🥇', '🥈', '🥉', '4', '5'];
    list.forEach((h, i) => {
      const li = el('li', 'hrow' + (h.leader ? ' leader' : ''));
      const before = prevHunters.get(h.name);
      if (before && h.rank < before) li.classList.add('up');
      li.append(el('span', 'pos', medals[i]), avatar(h.name, h.avatar), el('span', 'nm', h.name),
                el('span', 'rk t-' + h.tempKey, '#' + fmt(h.rank)));
      box.append(li);
    });
    prevHunters = new Map(list.map(h => [h.name, h.rank]));
  }

  function guessRow(g, cls) {
    const row = el('div', 'grow ' + (cls || ''));
    // [rank] [word / proximity bar] [big avatar + name] — the player is the star of the row
    const bar = el('div', 'bar t-' + g.tempKey); const fill = el('i');
    fill.style.width = Math.round(closeness(g.rank) * 100) + '%';
    bar.append(fill);
    const who = el('div', 'who');
    const nm = el('div', 'nm');
    nm.append(el('span', 'n', g.name));
    if (g.count > 1) nm.append(el('span', 'cnt', '+' + (g.count - 1) + ' more'));
    who.append(avatar(g.name, g.avatar), nm);
    row.append(el('div', 'rk t-' + g.tempKey, '#' + fmt(g.rank)), el('div', 'wd', g.word), who, bar);
    return row;
  }

  // Closest words sorted by rank: a good guess stays on top until someone beats it.
  // A brand-new guess is shown on top for FRESH_MS ("NEW"), then drops to its place by rank
  // (or leaves the list if it isn't among the best).
  const FRESH_MS = 5000, MAX_FRESH = 2;
  let fresh = [], lastBest = [];
  function addFresh(e) {
    fresh = fresh.filter(f => f.word !== e.word);
    fresh.unshift({ word: e.word, rank: e.rank, temp: e.temp, tempKey: tKey(e.temp), count: e.count,
                    name: e.name, avatar: e.avatar, at: Date.now() });
    fresh = fresh.slice(0, MAX_FRESH);
    renderGuesses(lastBest);
  }
  function renderGuesses(best) {
    lastBest = best;
    const now = Date.now();
    fresh = fresh.filter(f => now - f.at < FRESH_MS);
    const box = $('guessList');
    box.replaceChildren();
    if (!best.length && !fresh.length) { box.append(el('div', 'empty-hint', 'Type a word in chat to start hunting!')); return; }
    const mark = g => {
      const before = prevWords.get(g.word);
      return before === undefined ? 'new' : g.count > before ? 'more' : '';
    };
    fresh.forEach(f => { box.append(guessRow(f, 'fresh' + (f.shown ? '' : ' new'))); f.shown = true; });
    const shown = new Set(fresh.map(f => f.word));
    best.filter(g => !shown.has(g.word)).slice(0, 7 - fresh.length).forEach(g => box.append(guessRow(g, mark(g))));
    box.querySelectorAll('.wd').forEach(fitCell);
    prevWords = new Map(best.map(g => [g.word, g.count]));
  }
  setInterval(() => {                       // let expired "NEW" rows drop into place
    if (fresh.some(f => Date.now() - f.at >= FRESH_MS)) renderGuesses(lastBest);
  }, 300);

  let taglineI = 0, taglineT = 0;
  function tagline(s) {
    const lines = [];
    if (s.leader) lines.push('Can you beat ' + s.leader.name + '? Best is #' + fmt(s.leader.rank));
    if (s.stats.top100 >= 2) lines.push(s.stats.top100 + ' players are in the TOP 100!');
    if (s.streak) lines.push(s.streak.name + ' is on a ' + s.streak.n + ' WIN STREAK!');
    if (s.stats.guesses) lines.push(fmt(s.stats.guesses) + ' guesses so far');
    if (!lines.length) lines.push('Smaller rank = closer to the secret word');
    const now = Date.now();
    if (now - taglineT > 5000) { taglineI++; taglineT = now; $('tagline').classList.remove('swap'); void $('tagline').offsetWidth; $('tagline').classList.add('swap'); }
    $('tagline').textContent = lines[taglineI % lines.length];
  }

  function renderWinner(s) {
    const w = s.winner;
    const title = $('wTitle');
    $('wAvatar').replaceChildren();
    $('wChips').replaceChildren();
    if (w && w.reason === 'exact') {
      title.textContent = '🎉 WE HAVE A WINNER!'; title.className = 'wtitle';
    } else {
      title.textContent = w ? "⏰ TIME'S UP!" : '😵 NOBODY FOUND IT'; title.className = 'wtitle timeout';
    }
    if (w) {
      $('wAvatar').append(avatar(w.name, w.avatar));
      fitText($('wName'), w.name);
      $('wSub').textContent = w.reason === 'exact' ? 'found the word:' : 'was the closest! The word:';
      const chips = ['⏱ ' + Math.floor(w.seconds / 60) + ':' + String(w.seconds % 60).padStart(2, '0'),
                     '🎯 ' + w.guesses + ' guesses', '🏅 best #' + fmt(w.best)];
      chips.forEach(c => $('wChips').append(el('span', 'chip', c)));
      if (w.streak >= 2) $('wChips').append(el('span', 'chip streak', '🔥 ' + w.streak + ' WIN STREAK'));
    } else {
      $('wName').textContent = ''; $('wSub').textContent = 'The word was:';
    }
    fitText($('wWord'), s.secretWord || '');
  }

  function renderReveal(s) {
    fitText($('rWord'), s.secretWord || '');
    const pod = $('podium'); pod.replaceChildren();
    const order = [1, 0, 2];                         // 2nd, 1st, 3rd
    order.forEach(i => {
      const p = s.podium[i];
      if (!p) return;
      const col = el('div', 'pcol p' + (i + 1));
      col.append(avatar(p.name, p.avatar), el('div', 'nm', p.name), el('div', 'rk', '#' + fmt(p.rank)),
                 el('div', 'step', String(i + 1)));
      pod.append(col);
    });
    const best = $('rBest'); best.replaceChildren();
    s.bestGuesses.slice(0, 6).forEach(g => {
      const l = el('div', 'line t-' + g.tempKey);
      l.append(el('span', '', g.word), el('span', '', '#' + fmt(g.rank)));
      best.append(l);
    });
    if (!s.bestGuesses.length) best.append(el('div', 'line', '—'));
    const st = $('rStream'); st.replaceChildren();
    s.streamLeaderboard.slice(0, 5).forEach((p, i) => {
      const l = el('div', 'line');
      l.append(el('span', '', ['🥇', '🥈', '🥉', '4.', '5.'][i] + ' ' + p.name),
               el('span', '', p.wins ? p.wins + (p.wins === 1 ? ' win' : ' wins')
                                     : p.podiums + (p.podiums === 1 ? ' podium' : ' podiums')));
      st.append(l);
    });
    if (!s.streamLeaderboard.length) st.append(el('div', 'line', 'No winners yet'));
  }

  function render(s) {
    S = s;
    vocab = s.vocabSize || vocab;
    $('error').hidden = !s.error;
    if (s.error) { $('errText').textContent = '⚠ Guess the Word is unavailable: ' + s.error; return; }

    const chip = $('roundChip');
    chip.textContent = 'ROUND ' + s.roundId + (s.roundType === 'speed' ? ' · SPEED' : '');
    chip.classList.toggle('speed', s.roundType === 'speed');
    $('playersChip').textContent = '👥 ' + s.stats.players;
    fitText($('secretWord'), s.secretWord || '? ? ?');
    $('subs').hidden = !s.subscribersOnly;
    if (s.goal) {
      $('goal').hidden = false;
      $('goalLabel').textContent = s.goal.label;
      $('goalVal').textContent = s.goal.value + '/' + s.goal.target;
      $('goalFill').style.width = Math.min(100, 100 * s.goal.value / s.goal.target) + '%';
    }
    renderHunters(s.topHunters);
    renderGuesses(s.bestGuesses);
    tagline(s);

    const h = s.hints[s.hints.length - 1];
    $('hintCard').hidden = !h;
    if (h) {
      $('hintText').textContent = h.text; $('hintWord').textContent = h.word;
      if (s.hints.length !== prevHintCount) { $('hintCard').classList.remove('new'); void $('hintCard').offsetWidth; $('hintCard').classList.add('new'); }
    }
    prevHintCount = s.hints.length;

    $('winner').hidden = s.phase !== 'winner';
    $('reveal').hidden = s.phase !== 'reveal';
    if (s.phase === 'winner') renderWinner(s);
    if (s.phase === 'reveal') renderReveal(s);
    if (s.phase === 'countdown') { prevWords = new Map(); prevHunters = new Map(); }
  }

  // ------------------------------------------------------------ clock: timer, countdown, last 10 s
  let lastBig = null;
  function bigNum(text, cls) {
    if (text === lastBig) return;
    lastBig = text;
    const b = $('bigNum');
    b.className = cls || '';
    b.replaceChildren();
    if (text !== '') b.append(el('span', '', text));
  }
  function clock() {
    if (!S || S.error) return;
    const now = Live.now();
    const t = $('timer');
    if (S.phase === 'playing') {
      const left = Math.max(0, Math.ceil(S.endsAt - now));
      t.textContent = Math.floor(left / 60) + ':' + String(left % 60).padStart(2, '0');
      t.classList.toggle('low', left <= 10);
      if (left <= 10 && left > 0) {
        if (lastBig !== String(left)) fx('tick', left);
        bigNum(String(left), 'final');
      } else bigNum('');
    } else if (S.phase === 'countdown') {
      const left = Math.ceil(S.phaseUntil - now);
      t.textContent = '0:00'; t.classList.remove('low');
      const label = left > 1 ? String(left - 1) : 'GO!';
      if (lastBig !== label) fx('count', label === 'GO!');
      bigNum(label, label === 'GO!' ? 'go' : 'cd');
    } else {
      t.classList.remove('low');
      if (S.phase === 'reveal') {
        const left = Math.max(0, Math.ceil(S.phaseUntil - now));
        $('rNext').textContent = 'NEW ROUND IN ' + left + '...';
      }
      if (lastBig !== 'GO!' || S.phase !== 'playing') bigNum('');
    }
  }
  setInterval(clock, 150);

  // ------------------------------------------------------------ rules + start
  function showRules(ms) {
    $('rules').hidden = false;
    clearTimeout(showRules.t);
    showRules.t = setTimeout(() => { $('rules').hidden = true; }, ms || 8000);
  }
  $('rules').onclick = () => { $('rules').hidden = true; };
  A.mount({ rules: () => ($('rules').hidden ? showRules(12000) : ($('rules').hidden = true)),
            hello: 'Sound on. Let\'s find the secret word!' });
  showRules(7000);
  Live.start({ game: 'guess', onState: render, onEvent });
})();
