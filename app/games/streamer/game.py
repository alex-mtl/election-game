"""Streamer overlay: a transparent page on top of the streamer's video with reactions.

Like balloons: every viewer has their own heart balloon that inflates with their likes
(shown at the bottom); at LIKES_PER_BALLOON likes it takes off with their avatar inside.
"""

import random
import time

from ... import config
from ..base import BaseGame, Viewer

MAX_INFLATING = 4          # balloons visible at the bottom at once
INFLATE_VISIBLE_SEC = 25   # a balloon stays at the bottom this long after the viewer's last like
SIM_NAMES = ["Alex", "Mike", "Sarah", "John", "Emma", "Liam", "Olivia", "Noah", "Mia", "Leo"]


class StreamerOverlay(BaseGame):
    name = "streamer"
    title = "Streamer"
    STATE = "streamer.json"

    def __init__(self, store):
        super().__init__(store)
        self.likes = {}        # viewer id -> {name, avatar, progress, total, launched, last}
        self.load()

    # ---- likes -> balloons ----
    def on_like(self, viewer: Viewer, count: int):
        now = time.time()
        u = self.likes.setdefault(viewer.id, {"name": viewer.name, "avatar": viewer.avatar,
                                              "progress": 0, "total": 0, "launched": 0, "last": 0})
        u["name"], u["avatar"] = viewer.name, viewer.avatar or u["avatar"]
        u["total"] += count
        u["progress"] += count
        u["last"] = now
        per = max(1, config.LIKES_PER_BALLOON)
        while u["progress"] >= per:              # 100 likes -> lift off (a big batch may launch several)
            u["progress"] -= per
            u["launched"] += 1
            self.emit("balloon", id=viewer.id, name=u["name"], avatar=u["avatar"], n=u["launched"], total=u["total"])
            print(f"[streamer] balloon #{u['launched']} for {u['name']} ({u['total']} likes)")
        self.dirty = True

    def new_session(self):
        self.likes = {}
        self.dirty = True

    def tick(self, now):
        # balloons fade away from the bottom when their owner stops liking
        if any(u["progress"] and now - u["last"] > INFLATE_VISIBLE_SEC for u in self.likes.values()):
            self.dirty = True

    def snapshot(self):
        now = time.time()
        per = max(1, config.LIKES_PER_BALLOON)
        active = [dict(id=k, **u) for k, u in self.likes.items()
                  if u["progress"] and now - u["last"] <= INFLATE_VISIBLE_SEC]
        active.sort(key=lambda u: -u["last"])
        inflating = [{"id": u["id"], "name": u["name"], "avatar": u["avatar"],
                      "progress": u["progress"], "fill": round(u["progress"] / per, 3)}
                     for u in active[:MAX_INFLATING]]
        return {"inflating": inflating, "perBalloon": per,
                "totalLikes": sum(u["total"] for u in self.likes.values())}

    # ---- simulation / debug ----
    def simulate_step(self):
        name = random.choice(SIM_NAMES[:6])
        self.on_like(Viewer(name.lower(), name, ""), random.choice([1, 3, 5, 8, 15]))
        return random.uniform(0.2, 0.7)

    def debug(self, action, params):
        name = (params.get("name") or "Tester")[:30]
        if action == "like":
            self.on_like(Viewer(name.lower(), name, ""), int(params.get("n") or 10))
        elif action == "balloon":
            self.on_like(Viewer(name.lower(), name, ""), config.LIKES_PER_BALLOON)
        elif action == "reset":
            self.new_session()
        else:
            return super().debug(action, params)
        return {"ok": True}

    # ---- persistence ----
    def save(self):
        self.store.save(self.STATE, {"likes": self.likes})

    def load(self):
        d = self.store.load(self.STATE) or {}
        self.likes = d.get("likes", {})
