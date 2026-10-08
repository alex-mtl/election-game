"""Hub: owns the games, knows which one is active, routes TikTok events to it,
runs ticks/simulation, saves state and pushes updates to overlays."""

import asyncio
import json
import time

from . import config
from .games import GAMES
from .games.base import Viewer


class Hub:
    SESSION = "session.json"

    def __init__(self, store):
        self.store = store
        self.games = {G.name: G(store) for G in GAMES}
        s = store.load(self.SESSION) or {}
        self.room_id = s.get("room_id") or (store.load("state.json") or {}).get("room_id")
        self.active = s.get("active") if s.get("active") in self.games else config.DEFAULT_GAME
        self.clients = set()                      # websockets
        self.sent_seq = {name: g.seq for name, g in self.games.items()}
        self.tiktok_status = "offline"
        self.game.on_activate()

    @property
    def game(self):
        return self.games[self.active]

    def menu(self):
        return [{"name": g.name, "title": g.title} for g in self.games.values()]

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

    def save_session(self):
        self.store.save(self.SESSION, {"room_id": self.room_id, "active": self.active})

    # ---- TikTok -> active game ----
    def new_live(self, room_id):
        if room_id and room_id != self.room_id:
            self.room_id = room_id
            for g in self.games.values():
                g.new_session()
            self.save_session()
            print(f"[hub] new LIVE (room {room_id}) -> all games reset")

    def comment(self, v: Viewer, text):
        self.game.on_comment(v, text)

    def join(self, v: Viewer):
        self.game.on_join(v)

    def gift(self, v: Viewer, gift, count):
        self.game.on_gift(v, gift, count)

    def follow(self, v: Viewer):
        self.game.on_follow(v)

    # ---- state for overlays ----
    def message(self, name, since=None):
        g = self.games[name]
        return {"active": self.active, "game": name, "seq": g.seq, "now": time.time(),
                "tiktok": self.tiktok_status, "version": getattr(self, "web_version", ""),
                "events": g.events_since(since) if since is not None else [],
                "state": g.snapshot()}

    # ---- background loops ----
    async def ticker(self):
        while True:
            try:
                self.game.tick(time.time())
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
            self.save_session()

    async def broadcaster(self):
        """Push the active game's state + new events to websocket clients (<=10/s)."""
        while True:
            await asyncio.sleep(0.1)
            g = self.game
            if not g.dirty or not self.clients:
                g.dirty = False
                self.sent_seq[g.name] = g.seq
                continue
            g.dirty = False
            msg = json.dumps(self.message(g.name, self.sent_seq[g.name]), ensure_ascii=False)
            self.sent_seq[g.name] = g.seq
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
            except Exception as e:
                print("[sim] error:", type(e).__name__, e)
                delay = 1
            await asyncio.sleep(delay)
