"""Like balloons, shared by every page (games and the streamer overlay): each viewer inflates
their own heart balloon with likes; at LIKES_PER_BALLOON it takes off with their avatar."""

import time

from .. import config

MAX_INFLATING = 4          # balloons shown at the bottom of the streamer overlay
INFLATE_VISIBLE_SEC = 25   # a balloon stays there this long after the viewer's last like



def bomber(total, before):
    """The plane that marks every new PLANE_BOMBER_LIKES likes this stream (10 000, 20 000, ...)
    drops bombs that turn into butterflies with the viewer's avatar."""
    step = config.PLANE_BOMBER_LIKES
    return bool(step) and total // step > before // step

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

    def total_of(self, viewer_id):
        u = self.likes.get(viewer_id)
        return u["total"] if u else 0

    def auto_plane(self, viewer, before):
        """Plane without a command when the viewer crosses 1000, 2000, ... likes this stream."""
        step = config.PLANE_AUTO_LIKES
        u = self.likes.get(viewer.id)
        if not step or not u or u["total"] // step <= before // step:
            return None
        return {"id": viewer.id, "name": u["name"], "avatar": u["avatar"], "total": u["total"], "auto": True,
                "bomber": bomber(u["total"], before)}

    def new_session(self):
        self.likes = {}
        self.dirty = True

    def tick(self, now):
        if any(u["progress"] and now - u["last"] > INFLATE_VISIBLE_SEC for u in self.likes.values()):
            self.dirty = True                   # someone's balloon fades away from the bottom

    def likers(self, places=3, per_place=6):
        """Top likers of the stream (TT mode block): 1st-3rd place by planes (one per PLANE_AUTO_LIKES
        likes) and the 1st place by balloons among those without a plane yet. A tie shares the place.
        One function on purpose: the ranking rules will change (activity-based)."""
        step = config.PLANE_AUTO_LIKES or 1000
        per = max(1, config.LIKES_PER_BALLOON)

        def group(rows, key, limit):
            groups = {}
            for u in rows:
                k = key(u)
                if k > 0:
                    groups.setdefault(k, []).append(u)
            out = []
            for k in sorted(groups, reverse=True)[:limit]:
                ps = sorted(groups[k], key=lambda u: -u["total"])
                out.append({"count": k, "n": len(ps),
                            "players": [{"name": u["name"], "avatar": u["avatar"]} for u in ps[:per_place]]})
            return out

        rows = list(self.likes.values())
        planes = group(rows, lambda u: u["total"] // step, places)
        balloons = group([u for u in rows if u["total"] < step], lambda u: u["total"] // per, 1)
        return {"planes": planes, "balloon": balloons[0] if balloons else None}

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
                              for u in active[:MAX_INFLATING]],
                "likers": self.likers()}

    def save(self):
        self.store.save(self.FILE, {"likes": self.likes})
