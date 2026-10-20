"""Hub: owns the games, knows which one is active, routes TikTok events to it,
runs ticks/simulation, saves state and pushes updates to overlays."""

import asyncio
import json
import os
import random
import time
from collections import deque

from . import config
from .games import GAMES
from .games.base import Viewer
from .reactions.balloons import LikeBalloons
from .settings import GlobalSettings


class Hub:
    SESSION = "session.json"

    def __init__(self, store):
        self.store = store
        self.games = {G.name: G(store) for G in GAMES}
        s = store.load(self.SESSION) or {}
        self.room_id = s.get("room_id") or (store.load("state.json") or {}).get("room_id")
        self.active = s.get("active") if s.get("active") in self.games else config.DEFAULT_GAME
        self.lang = s.get("lang") or config.LANGUAGE
        # per-game settings from the menu dialog: {game: {key: value}}
        self.global_settings = GlobalSettings()
        saved = s.get("options", {})
        for k, v in (saved.pop("global", None) or {}).items():
            self.global_settings.set(k, v)
        if "break" in saved:                          # old single on/off switch for guess
            saved = {"guess": {"break": saved.pop("break")}, **saved}
        for name, opts in saved.items():
            if name in self.games and isinstance(opts, dict):
                for k, v in opts.items():
                    self.games[name].set_option(k, v)
        for g in self.games.values():
            g.set_lang(self.lang)
        self.clients = set()                      # websockets
        self.sent_seq = {name: g.seq for name, g in self.games.items()}
        self.tiktok_status = "offline"
        self.tg = None                                # TelegramLink when the bot is configured
        # stream feed (comments, gifts) for the menu page's alerts, independent of the game
        self.feed = deque(maxlen=100)
        self.feed_seq = 0
        self.feed_sent = 0
        self.greeted = set()                      # viewers already welcomed this stream
        self.names = {}                           # viewer id -> their TikTok nickname as of their last event
        for g in self.games.values():
            g.names = self.names
        self.balloons = LikeBalloons(store)       # like balloons fly over every page
        self.closed = False                       # set on shutdown: incoming events are ignored
        self.game.on_activate()

    @property
    def game(self):
        return self.games[self.active]

    def menu(self):
        return [{"name": g.name, "title": g.title, "options": g.OPTIONS, "values": g.get_options()}
                for g in self.games.values()]

    def set_active(self, name):
        if name not in self.games or name == self.active:
            return
        self.game.on_deactivate()
        self.active = name
        self.game.on_activate()
        self.game.dirty = True
        self.sent_seq[name] = self.game.seq           # don't replay events from before
        self.save_session()
        print(f"[hub] active game -> {name}")

    def set_lang(self, lang):
        if lang not in config.LANGUAGES or lang == self.lang:
            return
        self.lang = lang
        for g in self.games.values():
            g.set_lang(lang)
            g.dirty = True
        self.save_session()
        print(f"[hub] language -> {lang}")

    def save_session(self):
        self.store.save(self.SESSION, {"room_id": self.room_id, "active": self.active, "lang": self.lang,
                                       "options": self.options()})

    def options(self):
        out = {n: g.get_options() for n, g in self.games.items() if g.OPTIONS}
        out["global"] = self.global_settings.values()
        return out

    def set_options(self, name, opts):
        if name == "global":
            for k, v in (opts or {}).items():
                self.global_settings.set(k, v)
            self.save_session()
            self.game.dirty = True                    # pages get the new voice rate etc.
            print(f"[hub] global settings -> {self.global_settings.values()}")
            return
        g = self.games.get(name)
        if not g:
            return
        for k, v in (opts or {}).items():
            if k in g.OPTIONS and v in g.OPTIONS[k]:
                g.set_option(k, v)
        g.dirty = True
        self.save_session()
        print(f"[hub] {name} settings -> {g.get_options()}")

    # ---- TikTok -> active game ----
    def new_live(self, room_id):
        if room_id and room_id != self.room_id:
            self.room_id = room_id
            for g in self.games.values():
                g.new_session()
            self.greeted = set()
            self.balloons.new_session()
            self.save_session()
            print(f"[hub] new LIVE (room {room_id}) -> all games reset")

    def _feed(self, **e):
        self.feed_seq += 1
        e.update(seq=self.feed_seq, t=time.time())
        self.feed.append(e)

    def _seen(self, v):
        """nicknames change: every event carries the current one"""
        if v.id and v.name:
            self.names[v.id.lower()] = v.name

    def comment(self, v: Viewer, text, ts=None):
        if self.closed:                               # shutting down: nothing changes any more
            return
        self._seen(v)
        self._feed(type="chat", name=v.name, avatar=v.avatar, text=text[:200], sent=ts,
                   host=v.id.lower() == config.TIKTOK_USERNAME.lower())
        if self.tg and self.tg.on_comment(v, text):  # "настроить связь" / a Telegram key: not a guess
            return
        self.game.on_comment(v, text, ts)

    def join(self, v: Viewer):
        if self.closed:                               # shutting down: nothing changes any more
            return
        self._seen(v)
        # welcome each viewer once per stream (pages throttle and merge the greetings)
        if config.GREET_JOINS and v.id not in self.greeted and v.id.lower() != config.TIKTOK_USERNAME.lower():
            if len(self.greeted) > 20000:
                self.greeted.clear()
            self.greeted.add(v.id)
            self._feed(type="join", name=v.name, avatar=v.avatar)
        self.game.on_join(v)

    def gift(self, v: Viewer, gift, count, to=""):
        """A gift on the stream. Only gifts to the host count in the game (hints); a gift to a guest
        or co-host on the same live is just shown."""
        if self.closed:                               # shutting down: nothing changes any more
            return
        self._seen(v)
        self._feed(type="gift", name=v.name, avatar=v.avatar, gift=gift, count=count, to=to)
        self._journal_gift(v, gift, count, to)
        if to and to.lower() != config.TIKTOK_USERNAME.lower():
            print(f"[gift] {v.name}: {gift} went to @{to}, not to the host -> no game action")
            return
        self.game.on_gift(v, gift, count)

    def _journal_gift(self, v, gift, count, to):
        """Every gift, one JSON line in data/gifts.jsonl (kept across rebuilds: the data folder is mounted)."""
        try:
            line = json.dumps({"t": int(time.time()), "time": time.strftime("%Y-%m-%d %H:%M:%S"), "id": v.id,
                               "name": v.name, "gift": gift, "count": count, "to": to or None,
                               "game": self.active}, ensure_ascii=False)
            with open(os.path.join(config.DATA_DIR, "gifts.jsonl"), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            print(f"[gift] journal error: {e}")

    def follow(self, v: Viewer):
        if self.closed:                               # shutting down: nothing changes any more
            return
        self._seen(v)
        self.game.on_follow(v)

    def like(self, v: Viewer, count):
        if self.closed:                               # shutting down: nothing changes any more
            return
        self._seen(v)
        before = self.balloons.total_of(v.id)
        for b in self.balloons.on_like(v, count):  # 100 likes -> lift off, on whatever page is open
            self._feed(type="balloon", **b)
        plane = self.balloons.auto_plane(v, before)  # every PLANE_AUTO_LIKES likes -> the plane flies by itself
        if plane:
            print(f"[plane] {v.name}: {plane['total']} likes -> auto plane")
            self._feed(type="plane", **plane)
        self.game.on_like(v, count)

    # ---- state for overlays ----
    def message(self, name, since=None, feed_since=None):
        g = self.games[name]
        return {"active": self.active, "game": name, "seq": g.seq, "now": time.time(),
                "feedSeq": self.feed_seq,
                "feed": [e for e in self.feed if e["seq"] > feed_since] if feed_since is not None else [],
                "tiktok": self.tiktok_status, "tgBot": self.tg.bot if self.tg and self.tg.word else "",
                "version": getattr(self, "web_version", ""),
                "lang": self.lang, "voiceRate": config.VOICE_RATE,
                "events": g.events_since(since) if since is not None else [],
                "balloons": self.balloons.snapshot(),
                "state": g.snapshot()}

    # ---- background loops ----
    async def ticker(self):
        while True:
            try:
                self.game.tick(time.time())
                self.balloons.tick(time.time())
            except Exception as e:
                print("[hub] tick error:", type(e).__name__, e)
            await asyncio.sleep(0.25)

    async def saver(self):
        while True:
            await asyncio.sleep(1)
            for g in self.games.values():
                try:
                    g.save()
                except Exception as e:
                    print(f"[hub] save error ({g.name}):", e)
            self.balloons.save()
            self.save_session()

    async def broadcaster(self):
        """Push the active game's state + new events to websocket clients (<=10/s)."""
        while True:
            await asyncio.sleep(0.1)
            g = self.game
            feed_new = self.feed_seq != self.feed_sent or self.balloons.dirty
            if not (g.dirty or feed_new) or not self.clients:
                g.dirty = self.balloons.dirty = False
                self.sent_seq[g.name] = g.seq
                self.feed_sent = self.feed_seq
                continue
            g.dirty = self.balloons.dirty = False
            msg = json.dumps(self.message(g.name, self.sent_seq[g.name], self.feed_sent), ensure_ascii=False)
            self.sent_seq[g.name] = g.seq
            self.feed_sent = self.feed_seq
            for ws in list(self.clients):
                try:
                    await ws.send_text(msg)
                except Exception:
                    self.clients.discard(ws)

    async def simulator(self):
        print("[sim] fake viewers are playing (no TikTok needed)")
        while True:
            try:
                delay = self.game.simulate_step()
                if random.random() < 0.25:            # fake likes -> balloons on every page
                    n = random.choice(["Alex", "Mike", "Sarah", "Emma"])
                    self.like(Viewer(n.lower(), n, ""), random.choice([3, 5, 8, 15]))
            except Exception as e:
                print("[sim] error:", type(e).__name__, e)
                delay = 1
            await asyncio.sleep(delay)
