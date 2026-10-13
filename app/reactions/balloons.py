"""Like balloons, shared by every page (games and the streamer overlay): each viewer inflates
their own heart balloon with likes; at LIKES_PER_BALLOON it takes off with their avatar."""

import time

from .. import config

MAX_INFLATING = 4          # balloons shown at the bottom of the streamer overlay
INFLATE_VISIBLE_SEC = 25   # a balloon stays there this long after the viewer's last like


class LikeBalloons:
    FILE = "balloons.json"

    def __init__(self, store):
        self.store = store
        d = store.load(self.FILE) or store.load("streamer.json") or {}   # old streamer-only file
        self.likes = d.get("likes", {})  # viewer id -> {name, avatar, progress, total, launched, last}
        self.dirty = True

    def on_like(self, viewer, count):
        """Returns the balloons that took off (a big batch of likes may launch several)."""
        u = self.likes.setdefault(viewer.id, {"name": viewer.name, "avatar": viewer.avatar,
                                              "progress": 0, "total": 0, "launched": 0, "last": 0})
        u["name"], u["avatar"] = viewer.name, viewer.avatar or u["avatar"]
        u["total"] += count
        u["progress"] += count
        u["last"] = time.time()
        per = max(1, config.LIKES_PER_BALLOON)
        launches = []
        while u["progress"] >= per:
            u["progress"] -= per
            u["launched"] += 1
            launches.append({"id": viewer.id, "name": u["name"], "avatar": u["avatar"],
                             "n": u["launched"], "total": u["total"], "per": per})
            print(f"[balloons] #{u['launched']} for {u['name']} ({u['total']} likes)")
        self.dirty = True
        return launches

    def new_session(self):
        self.likes = {}
        self.dirty = True

    def tick(self, now):
        if any(u["progress"] and now - u["last"] > INFLATE_VISIBLE_SEC for u in self.likes.values()):
            self.dirty = True                   # someone's balloon fades away from the bottom

    def snapshot(self):
        now = time.time()
        per = max(1, config.LIKES_PER_BALLOON)
        active = [dict(id=k, **u) for k, u in self.likes.items()
                  if u["progress"] and now - u["last"] <= INFLATE_VISIBLE_SEC]
        active.sort(key=lambda u: -u["last"])
        return {"perBalloon": per,
                "totalLikes": sum(u["total"] for u in self.likes.values()),
                "inflating": [{"id": u["id"], "name": u["name"], "avatar": u["avatar"],
                               "progress": u["progress"], "fill": round(u["progress"] / per, 3)}
                              for u in active[:MAX_INFLATING]]}

    def save(self):
        self.store.save(self.FILE, {"likes": self.likes})
