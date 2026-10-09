"""Common interface for all games. The TikTok layer only calls the on_* hooks;
the web layer only reads snapshot()/events. Adding a game = subclass + register."""

import time
from collections import deque
from dataclasses import dataclass


@dataclass
class Viewer:
    id: str              # stable TikTok @unique_id
    name: str            # display nickname
    avatar: str = ""     # https avatar url or ""
    follows: int = -1    # follow status towards the host: 0 no, 1 follower, 2 friends, -1 unknown


class BaseGame:
    name = "base"        # url slug: /<name>/
    title = "Game"

    def __init__(self, store):
        self.store = store
        self.events = deque(maxlen=200)
        self.seq = 0
        self.dirty = True            # state changed -> broadcast

    # ---- events for the overlay (sounds, animations, voice) ----
    def emit(self, type, **data):
        self.seq += 1
        data.update(type=type, seq=self.seq, t=time.time())
        self.events.append(data)
        self.dirty = True

    def events_since(self, seq):
        return [e for e in self.events if e["seq"] > seq]

    # ---- hooks (override what the game needs) ----
    def on_activate(self):
        """Game was selected in the menu (or is the active one at startup)."""

    def on_deactivate(self):
        """Another game was selected: pause timers."""

    def on_comment(self, viewer: Viewer, text: str):
        pass

    def on_join(self, viewer: Viewer):
        pass

    def on_gift(self, viewer: Viewer, gift: str, count: int):
        pass

    def on_follow(self, viewer: Viewer):
        pass

    def set_lang(self, lang):
        """Interface/word language changed in the menu."""

    def new_session(self):
        """A new TikTok LIVE started: reset per-stream data."""

    def tick(self, now):
        """Called ~4 times per second while the game is active."""

    def simulate_step(self):
        """One fake-viewer action (simulation mode). Returns seconds until the next one."""
        return 1.0

    def debug(self, action, params):
        return {"error": f"unknown action {action}"}

    def snapshot(self):
        return {}

    def save(self):
        pass
