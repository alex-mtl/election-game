// Interface language. The language is chosen in the menu and stored on the server;
// every page gets it with the live state (live.js calls I18N.set) and reloads if it changes.
//   I18N.t('key', {name: 'Alex'})     text with {placeholders}
//   I18N.n(5, 'win')                  "5 wins" / "5 побед" (plural forms)
//   <span data-i18n="key">            static text, filled by I18N.apply()  (data-i18n-html = trusted HTML)
window.I18N = (() => {
  const D = {
    en: {
      // ---------- common ----------
      'ctl.menu': 'Choose game', 'ctl.rules': 'How to play', 'ctl.voice': 'Next voice', 'ctl.mute': 'Sound on/off',
      'unlock': '🔊 Click to enable sound',
      'voice.hello': 'Hi! I am {name}.',
      // ---------- menu ----------
      'menu.sub': 'CHOOSE WHAT WE PLAY', 'menu.now': 'NOW PLAYING', 'menu.lang': 'LANGUAGE',
      'menu.foot': 'The game screen follows your choice on every device',
      'game.battle': 'TEAM BATTLE', 'game.guess': 'GUESS THE WORD',
      'menu.battle.d': 'Red vs Yellow tug of war. Every comment pulls the bar. New viewers join your team!',
      'menu.battle.chat': 'CHAT:  R  /  Y',
      'menu.guess.d': 'Find the secret word. Every guess shows how close you are. First to find it wins!',
      'menu.guess.chat': 'CHAT:  ANY WORD',
      'game.streamer': 'STREAMER',
      'set.start': '▶ START', 'set.cancel': 'Cancel',
      'set.pause': 'Break between rounds', 'set.pause.v': '{n} s', 'set.pause.none': 'no break',
      'set.round_min': 'Round length', 'set.round_min.v': '{n} min',
      'set.on': 'on', 'set.off': 'off', 'set.save': '✔ SAVE',
      'set.global': 'GENERAL SETTINGS', 'set.global.open': '⚙ GENERAL SETTINGS',
      'set.follow': 'Followers only', 'set.grace': 'Time to follow', 'set.grace.v': '{n} s',
      'set.balloon_likes': 'Balloon every', 'set.balloon_likes.v': '{n} likes',
      'set.plane_auto': 'Plane by itself every', 'set.plane_auto.v': '{n} likes', 'set.plane_auto.none': 'off',
      'set.plane_min': '!likes! from', 'set.plane_min.v': '{n} likes', 'set.plane_min.none': 'any',
      'set.bomber': 'Plane with butterflies every', 'set.bomber.v': '{n} likes', 'set.bomber.none': 'off',
      'set.plane_cooldown': 'Plane pause', 'set.plane_cooldown.v': '{n} s',
      'set.voice_rate': 'Voice speed', 'set.voice_rate.v': '×{n}',
      'set.greet': 'Greet new viewers',
      'set.level': 'Difficulty', 'set.level.1': 'easy (any words)', 'set.level.2': 'normal (nouns)',
      'alert.off': '🔕 STREAM ALERTS: OFF', 'alert.on': '🔔 STREAM ALERTS: ON', 'alert.feed': 'LIVE CHAT', 'alert.armed': '🔔 CLICK TO TURN ALERTS BACK ON',
      'alert.chat': '{name} says: {text}', 'alert.gift': 'Gift from {name}! {gift}',
      'alert.hello': 'Stream alerts are on. I will ring when someone writes in the chat.',
      'alert.join': 'New viewer: {names}', 'alert.joinLine': '👋 {name} joined',
      'greet.pill': 'Welcome, {who}!', 'greet.voice': 'Welcome, {who}!', 'greet.and': ' and ',
      'greet.more': '{names} and {n} more',
      'menu.streamer.d': 'Transparent overlay on top of your video: viewers fill heart balloons with likes and they fly up with their avatar!',
      'menu.streamer.chat': '❤ 100 LIKES = 🎈 BALLOON',
      's.v.balloon': 'Thank you {name} for {n} likes!',
      'plane.banner': '{likes} this stream', 'plane.need': 'needs {need}+ likes, you have {have}',
      'plane.wait': 'plane refuelling, {s} s', 'plane.v': '{name}: {likes} this stream! Thank you!',
      // ---------- battle ----------
      'b.red': 'Red', 'b.yellow': 'Yellow', 'b.typeR': 'Type R', 'b.typeY': 'Type Y', 'b.round': 'Round {n}',
      'b.hint': 'Type <b>R</b> in chat for Red, <b>Y</b> for Yellow. Tap as many times as you want!',
      'b.redWins': '🏆 RED WINS!', 'b.yellowWins': '🏆 YELLOW WINS!', 'b.mvp': 'MVP: {name} — {taps}',
      'b.v.hello': "Sound on. Let's play!",
      'b.v.scores': '{team} team scores, thanks to {name}!', 'b.v.pointTo': 'But the point goes to {name}!',
      'b.v.lead': '{name} takes the lead for Team {team}!', 'b.v.second': '{name} drops to second!',
      'b.v.sum': '{team} team scores {pts}', 'b.v.win': '{team} wins!', 'b.v.mvp': ' MVP: {name}!',
      'b.v.round': 'Round {n}. Go!', 'b.team.red': 'Red', 'b.team.yellow': 'Yellow',
      // ---------- guess ----------
      'g.round': 'ROUND {n}', 'g.speed': ' · SPEED', 'g.secret': 'SECRET WORD', 'g.hunters': 'TOP HUNTERS',
      'g.tk.word': "Last round's word: {w}", 'g.tk.none': '(nobody found it)', 'g.tk.top': 'Stream top:',
      'g.best': 'BEST GUESSES', 'g.cta': 'TYPE ONE WORD IN CHAT', 'g.subs': '🔒 SUBSCRIBERS ONLY',
      'g.hint': '💡 HINT', 'g.noHunters': 'No hunters yet — be the first!',
      'g.noGuesses': 'Type a word in chat to start hunting!', 'g.badgeNew': 'NEW', 'g.badgeUnknown': 'UNKNOWN',
      'g.notInDict': 'NOT IN DICTIONARY', 'g.more': '+{n} more', 'g.follow': '❤ FOLLOW · {n}s', 'g.followShort': '❤ {n}s',
      'g.tag.beat': 'Can you beat {name}? Best is #{rank}', 'g.tag.top100': '{players} are in the TOP 100!',
      'g.tag.streak': '{name} is on a {n} WIN STREAK!', 'g.tag.count': '{guesses} so far',
      'g.tag.default': 'Smaller rank = closer to the secret word',
      'g.rules.title': 'HOW TO PLAY',
      'g.rules.1': 'Type <b>one word</b> in the TikTok chat.',
      'g.rules.2': "You'll see <b>how close</b> your word is.",
      'g.rules.3': 'The <b>smaller the rank</b>, the closer you are.',
      'g.rules.4': 'Find the secret word <b>first</b> to win!',
      'g.rules.burning': '#2–10 BURNING', 'g.rules.hot': '#51–200 HOT', 'g.rules.cold': 'COLD',
      'g.w.title': '🎉 WE HAVE A WINNER!', 'g.w.timeout': "⏰ TIME'S UP!", 'g.w.nobody': '😵 NOBODY FOUND IT',
      'g.w.found': 'found the word:', 'g.w.closest': 'was the closest! The word:', 'g.w.was': 'The word was:',
      'g.w.best': '🏅 best #{n}', 'g.w.streak': '🔥 {n} WIN STREAK',
      'g.r.was': 'THE SECRET WORD WAS', 'g.r.leaders': 'STREAM LEADERS', 'g.r.next': 'NEXT ROUND IN {t}',
      'g.r.noWinners': 'No winners yet — be the first!',
      'g.l.next': 'NEXT ROUND IN', 'g.l.how': 'HOW TO PLAY',
      'g.l.howText': 'Type <b>one word</b> in chat — see how close you are — find the secret word first!',
      'g.t.leader': '🔥 new leader!', 'g.t.comeback': '↩ back in the lead!', 'g.t.massive': '🚀 massive jump!',
      'g.t.big': 'big improvement!', 'g.t.soClose': '😱 so close — one step away!',
      'g.t.top3': '⚡ in the TOP 3!', 'g.t.top10': '🔥 in the TOP 10!', 'g.t.reached': '🌡 {name} reached TOP {n}',
      'g.t.streak': '🔥 {n} wins in a row', 'g.t.gift': '🎁 {name} sent {gift}', 'g.t.followed': '💜 {name} followed — thank you!',
      'g.t.timeUp': "⏰ TIME'S UP!", 'g.t.skipped': '⏭ ROUND SKIPPED',
      'g.t.followNeeded': '❤ {name} — FOLLOW within {n}s to keep your spot!', 'g.t.followToPlay': '❤ {name} — FOLLOW to play and win!',
      'g.t.foundPending': '😱 found the word!', 'g.t.foundPendingSub': 'Follow within {n}s to win!',
      'g.t.thanks': '💜 thank you!', 'g.t.thanksSub': "You're in the game!",
      'g.t.sorry': '😢 sorry —', 'g.t.sorrySub': 'follow to win, then come back!',
      'g.h.semantic': 'A word close to the secret word is:', 'g.h.category': 'The word is related to:',
      'g.h.letter': 'The word starts with', 'g.h.length': 'The word has', 'g.h.lengthWord': '{letters}',
      'g.h.distance': 'The secret word is in the TOP {n} closest words to',
      'g.err': '⚠ Guess the Word is unavailable: ',
      'g.v.hello': "Sound on. Let's find the secret word!",
      'g.v.leader': 'New leader! {name}!', 'g.v.comeback': 'Comeback! {name} is back in the lead!',
      'g.v.massive': 'Massive jump by {name}!', 'g.v.soClose': 'So close! {name} is one step away!',
      'g.v.top3': '{name} is in the top three!', 'g.v.streak': '{name} is on a {n} win streak!',
      'g.v.hint': 'Hint! {text} {word}', 'g.v.timeUp': "Time's up!", 'g.v.skipped': 'Round skipped!',
      'g.v.winner': 'We have a winner! {name} found the word: {word}!',
      'g.v.closest': 'The winner is {name}! The word was {word}.', 'g.v.nobody': 'Nobody found it! The word was {word}.',
      'g.v.round': 'Round {n}. Go!', 'g.v.speed': 'Speed round! Go!',
      'g.v.followNeeded': '{name}, follow to keep your spot!', 'g.v.foundPending': '{name} found the word! Follow now to win!',
      'g.v.thanks': 'Thank you {name}! You are in the game!', 'g.v.sorry': 'Sorry {name}! You need to follow to win!',
      'g.v.break': 'Next round in {t}! Follow and subscribe to join the game!',
      'g.v.soon': 'Next round in 30 seconds! Get ready to type your words!',
      'g.minutes': '{n} {minute}', 'g.seconds': '{n} seconds',
    },
    ru: {
      'ctl.menu': 'Выбор игры', 'ctl.rules': 'Как играть', 'ctl.voice': 'Сменить голос', 'ctl.mute': 'Звук вкл/выкл',
      'unlock': '🔊 Нажми, чтобы включить звук',
      'voice.hello': 'Привет! Я {name}.',
      'menu.sub': 'ВЫБЕРИ ИГРУ', 'menu.now': 'СЕЙЧАС ИГРАЕМ', 'menu.lang': 'ЯЗЫК',
      'menu.foot': 'Экран игры переключается на всех устройствах сразу',
      'game.battle': 'БИТВА КОМАНД', 'game.guess': 'УГАДАЙ СЛОВО',
      'menu.battle.d': 'Красные против жёлтых. Каждый комментарий тянет полосу. Новые зрители усиливают твою команду!',
      'menu.battle.chat': 'ЧАТ:  К  /  Ж',
      'menu.guess.d': 'Найди секретное слово. Каждая догадка показывает, насколько ты близко. Кто первый — тот победил!',
      'menu.guess.chat': 'ЧАТ:  ЛЮБОЕ СЛОВО',
      'game.streamer': 'СТРИМЕР',
      'set.start': '▶ НАЧАТЬ', 'set.cancel': 'Отмена',
      'set.pause': 'Пауза между раундами', 'set.pause.v': '{n} сек', 'set.pause.none': 'без паузы',
      'set.round_min': 'Длина раунда', 'set.round_min.v': '{n} мин',
      'set.on': 'вкл', 'set.off': 'выкл', 'set.save': '✔ СОХРАНИТЬ',
      'set.global': 'ОБЩИЕ НАСТРОЙКИ', 'set.global.open': '⚙ ОБЩИЕ НАСТРОЙКИ',
      'set.follow': 'Только подписчики', 'set.grace': 'Время на подписку', 'set.grace.v': '{n} сек',
      'set.balloon_likes': 'Шарик каждые', 'set.balloon_likes.v': '{n} лайков',
      'set.plane_auto': 'Самолёт сам каждые', 'set.plane_auto.v': '{n} лайков', 'set.plane_auto.none': 'выкл',
      'set.plane_min': '!лайки! от', 'set.plane_min.v': '{n} лайков', 'set.plane_min.none': 'сразу',
      'set.bomber': 'Самолёт с бабочками каждые', 'set.bomber.v': '{n} лайков', 'set.bomber.none': 'выкл',
      'set.plane_cooldown': 'Пауза самолёта', 'set.plane_cooldown.v': '{n} сек',
      'set.voice_rate': 'Скорость голоса', 'set.voice_rate.v': '×{n}',
      'set.greet': 'Приветствовать вошедших',
      'set.level': 'Сложность', 'set.level.1': 'простой (любые слова)', 'set.level.2': 'нормальный (существительные)',
      'alert.off': '🔕 ОПОВЕЩЕНИЯ: ВЫКЛ', 'alert.on': '🔔 ОПОВЕЩЕНИЯ: ВКЛ', 'alert.feed': 'ЧАТ ЭФИРА', 'alert.armed': '🔔 КЛИКНИ, ЧТОБЫ ВЕРНУТЬ ЗВУК',
      'alert.chat': '{name} пишет: {text}', 'alert.gift': '{name} дарит подарок: {gift}!',
      'alert.hello': 'Оповещения включены. Я позвоню, когда кто-то напишет в чат.',
      'alert.join': 'Новый зритель: {names}', 'alert.joinLine': '👋 {name} на стриме',
      'greet.pill': 'Привет, {who}!', 'greet.voice': 'Привет, {who}! Добро пожаловать!',
      'greet.and': ' и ', 'greet.more': '{names} и ещё {n}',
      'menu.streamer.d': 'Прозрачный слой поверх твоего видео: зрители надувают лайками шарики-сердечки, и те взлетают с их аватаром!',
      'menu.streamer.chat': '❤ 100 ЛАЙКОВ = 🎈 ШАРИК',
      's.v.balloon': 'Спасибо, {name}, за {n} лайков!',
      'plane.banner': '{likes} за стрим', 'plane.need': 'нужно {need}+ лайков, у тебя {have}',
      'plane.wait': 'самолёт заправляется, {s} сек', 'plane.v': '{name}: {likes} за стрим! Спасибо!',
      'b.red': 'Красные', 'b.yellow': 'Жёлтые', 'b.typeR': 'Пиши К', 'b.typeY': 'Пиши Ж', 'b.round': 'Раунд {n}',
      'b.hint': 'Пиши в чат <b>К</b> — за красных, <b>Ж</b> — за жёлтых. Можно много раз!',
      'b.redWins': '🏆 ПОБЕДА КРАСНЫХ!', 'b.yellowWins': '🏆 ПОБЕДА ЖЁЛТЫХ!', 'b.mvp': 'MVP: {name} — {taps}',
      'b.v.hello': 'Звук включён. Поехали!',
      'b.v.scores': '{team} получают очко благодаря {name}!', 'b.v.pointTo': 'Но очко достаётся {name}!',
      'b.v.lead': '{name} выходит в лидеры команды {team}!', 'b.v.second': '{name} опускается на второе место!',
      'b.v.sum': '{team}: плюс {pts}', 'b.v.win': '{team} побеждают!', 'b.v.mvp': ' Лучший игрок — {name}!',
      'b.v.round': 'Раунд {n}. Поехали!', 'b.team.red': 'Красные', 'b.team.yellow': 'Жёлтые',
      'g.round': 'РАУНД {n}', 'g.speed': ' · БЫСТРЫЙ', 'g.secret': 'СЕКРЕТНОЕ СЛОВО', 'g.hunters': 'ЛУЧШИЕ ОХОТНИКИ',
      'g.tk.word': 'Слово прошлого раунда: {w}', 'g.tk.none': '(никто не угадал)', 'g.tk.top': 'Топ стрима:',
      'g.best': 'ЛУЧШИЕ ДОГАДКИ', 'g.cta': 'ПИШИ В ЧАТ ОДНО СЛОВО', 'g.subs': '🔒 ТОЛЬКО ДЛЯ ПОДПИСЧИКОВ',
      'g.hint': '💡 ПОДСКАЗКА', 'g.noHunters': 'Охотников пока нет — будь первым!',
      'g.noGuesses': 'Напиши слово в чат, чтобы начать охоту!', 'g.badgeNew': 'НОВОЕ', 'g.badgeUnknown': 'НЕИЗВЕСТНО',
      'g.notInDict': 'НЕТ В СЛОВАРЕ', 'g.more': '+{n} ещё', 'g.follow': '❤ ПОДПИШИСЬ · {n}с', 'g.followShort': '❤ {n}с',
      'g.tag.beat': 'Сможешь обойти {name}? Лучший — #{rank}', 'g.tag.top100': 'В ТОП-100 уже {players}!',
      'g.tag.streak': '{name}: {wins} подряд!', 'g.tag.count': 'Уже {guesses}',
      'g.tag.default': 'Чем меньше номер — тем ближе к секретному слову',
      'g.rules.title': 'КАК ИГРАТЬ',
      'g.rules.1': 'Напиши в чат TikTok <b>одно слово</b>.',
      'g.rules.2': 'Ты увидишь, <b>насколько оно близко</b>.',
      'g.rules.3': '<b>Чем меньше номер</b>, тем ближе ты к секрету.',
      'g.rules.4': 'Угадай секретное слово <b>первым</b> и победи!',
      'g.rules.burning': '#2–10 ГОРЯЧО', 'g.rules.hot': '#51–200 ТЕПЛО', 'g.rules.cold': 'ХОЛОДНО',
      'g.w.title': '🎉 У НАС ЕСТЬ ПОБЕДИТЕЛЬ!', 'g.w.timeout': '⏰ ВРЕМЯ ВЫШЛО!', 'g.w.nobody': '😵 НИКТО НЕ УГАДАЛ',
      'g.w.found': 'угадал(а) слово:', 'g.w.closest': 'был(а) ближе всех! Слово:', 'g.w.was': 'Это было слово:',
      'g.w.best': '🏅 лучший #{n}', 'g.w.streak': '🔥 {winsUp} ПОДРЯД',
      'g.r.was': 'СЕКРЕТНОЕ СЛОВО БЫЛО', 'g.r.leaders': 'ЛИДЕРЫ СТРИМА', 'g.r.next': 'СЛЕДУЮЩИЙ РАУНД ЧЕРЕЗ {t}',
      'g.r.noWinners': 'Победителей пока нет — будь первым!',
      'g.l.next': 'СЛЕДУЮЩИЙ РАУНД ЧЕРЕЗ', 'g.l.how': 'КАК ИГРАТЬ',
      'g.l.howText': 'Пиши в чат <b>одно слово</b> — смотри, насколько оно близко — угадай секрет первым!',
      'g.t.leader': '🔥 новый лидер!', 'g.t.comeback': '↩ снова лидер!', 'g.t.massive': '🚀 огромный скачок!',
      'g.t.big': 'отличный прогресс!', 'g.t.soClose': '😱 почти! в шаге от победы',
      'g.t.top3': '⚡ в тройке лучших!', 'g.t.top10': '🔥 в ТОП-10!', 'g.t.reached': '🌡 {name} в ТОП-{n}',
      'g.t.streak': '🔥 {wins} подряд', 'g.t.gift': '🎁 {name} дарит {gift}', 'g.t.followed': '💜 {name} подписался — спасибо!',
      'g.t.timeUp': '⏰ ВРЕМЯ ВЫШЛО!', 'g.t.skipped': '⏭ РАУНД ПРОПУЩЕН',
      'g.t.followNeeded': '❤ {name} — ПОДПИШИСЬ за {n} сек, чтобы остаться в топе!',
      'g.t.followToPlay': '❤ {name} — ПОДПИШИСЬ, чтобы играть и побеждать!',
      'g.t.foundPending': '😱 угадал слово!', 'g.t.foundPendingSub': 'Подпишись за {n} сек, чтобы победить!',
      'g.t.thanks': '💜 спасибо за подписку!', 'g.t.thanksSub': 'Ты в игре!',
      'g.t.sorry': '😢 увы —', 'g.t.sorrySub': 'чтобы победить, нужно подписаться. Подпишись и возвращайся!',
      'g.h.semantic': 'Близкое к секрету слово:', 'g.h.category': 'Слово связано с темой:',
      'g.h.letter': 'Слово начинается на', 'g.h.length': 'В слове', 'g.h.lengthWord': '{letters}',
      'g.h.distance': 'Секрет — в ТОП-{n} самых близких слов к',
      'g.err': '⚠ Игра недоступна: ',
      'g.v.hello': 'Звук включён. Найдём секретное слово!',
      'g.v.leader': 'Новый лидер! {name}!', 'g.v.comeback': 'Возвращение! {name} снова лидер!',
      'g.v.massive': 'Огромный скачок у {name}!', 'g.v.soClose': 'Почти! {name} в одном шаге от победы!',
      'g.v.top3': '{name} в тройке лучших!', 'g.v.streak': '{name}: {wins} подряд!',
      'g.v.hint': 'Подсказка! {text} {word}', 'g.v.timeUp': 'Время вышло!', 'g.v.skipped': 'Раунд пропущен!',
      'g.v.winner': 'У нас есть победитель! {name} угадывает слово: {word}!',
      'g.v.closest': 'Победитель — {name}! Это было слово {word}.', 'g.v.nobody': 'Никто не угадал! Это было слово {word}.',
      'g.v.round': 'Раунд {n}. Поехали!', 'g.v.speed': 'Быстрый раунд! Поехали!',
      'g.v.followNeeded': '{name}, подпишись, чтобы остаться в топе!', 'g.v.foundPending': '{name} угадал слово! Подпишись, чтобы победить!',
      'g.v.thanks': 'Спасибо, {name}! Ты в игре!', 'g.v.sorry': 'Увы, {name}! Чтобы победить, нужно подписаться!',
      'g.v.break': 'Следующий раунд через {t}! Подписывайтесь, чтобы играть с нами!',
      'g.v.soon': 'Следующий раунд через 30 секунд! Готовьтесь писать слова!',
      'g.minutes': '{n} {minute}', 'g.seconds': '{n} секунд',
    },
  };
  // plural forms: en [one, other], ru [one, few, many]
  const P = {
    en: { win: ['win', 'wins'], podium: ['podium', 'podiums'], guess: ['guess', 'guesses'], player: ['player', 'players'],
          tap: ['tap', 'taps'], point: ['point', 'points'], like: ['like', 'likes'], letter: ['LETTER', 'LETTERS'], minute: ['minute', 'minutes'] },
    ru: { win: ['победа', 'победы', 'побед'], podium: ['пьедестал', 'пьедестала', 'пьедесталов'],
          guess: ['догадка', 'догадки', 'догадок'], player: ['игрок', 'игрока', 'игроков'], tap: ['тап', 'тапа', 'тапов'],
          point: ['очко', 'очка', 'очков'], like: ['лайк', 'лайка', 'лайков'], letter: ['БУКВА', 'БУКВЫ', 'БУКВ'], minute: ['минуту', 'минуты', 'минут'] },
  };
  let lang = null;

  function form(n, word) {
    const f = (P[lang || 'en'] || P.en)[word] || [word, word];
    if ((lang || 'en') !== 'ru') return n === 1 ? f[0] : f[1];
    const a = Math.abs(n) % 100, b = a % 10;
    if (a > 10 && a < 20) return f[2];
    if (b === 1) return f[0];
    if (b >= 2 && b <= 4) return f[1];
    return f[2];
  }
  function t(key, params) {
    let s = (D[lang || 'en'] || D.en)[key];
    if (s === undefined) s = D.en[key] !== undefined ? D.en[key] : key;
    if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => (params[k] !== undefined ? params[k] : m));
    return s;
  }
  function apply(root) {
    (root || document).querySelectorAll('[data-i18n]').forEach(e => { e.textContent = t(e.dataset.i18n); });
    (root || document).querySelectorAll('[data-i18n-html]').forEach(e => { e.innerHTML = t(e.dataset.i18nHtml); });
    (root || document).querySelectorAll('[data-i18n-title]').forEach(e => { e.title = t(e.dataset.i18nTitle); });
    document.documentElement.lang = lang || 'en';
  }
  return {
    t, apply,
    n: (n, word) => n + ' ' + form(n, word),          // "5 wins" / "5 побед"
    form,
    get lang() { return lang; },
    set(l) {
      if (!D[l]) l = 'en';
      if (lang === l) return false;
      const first = lang === null;
      lang = l;
      apply();
      if (window.AudioKit && AudioKit.setLang) AudioKit.setLang(l);
      if (window.I18N_onChange) window.I18N_onChange(l, first);
      return true;
    },
  };
})();
