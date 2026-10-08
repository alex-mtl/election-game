"""Per-round player progress and per-stream (session) statistics."""

from dataclasses import dataclass, field


@dataclass
class RoundPlayer:
    id: str
    name: str
    avatar: str = ""
    best: int = 0                 # best rank this round (0 = none yet)
    prev: int = 0                 # previous best
    best_t: float = 0.0           # when best was reached (tie-break)
    best_word: str = ""
    guesses: int = 0
    improvements: int = 0
    last_t: float = 0.0           # last accepted guess (cooldown)
    tier: int = 10**9             # best "close guess" milestone reached
    words: set = field(default_factory=set)

    def to_dict(self):
        d = dict(self.__dict__)
        d["words"] = sorted(self.words)
        return d

    @classmethod
    def from_dict(cls, d):
        p = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        p.words = set(d.get("words", []))
        return p


class SessionStats:
    """Stream leaderboard: survives restarts, reset when a new LIVE starts."""

    FILE = "guess/players.json"

    def __init__(self, store):
        self.store = store
        d = store.load(self.FILE) or {}
        self.players = d.get("players", {})
        self.follows = d.get("follows", 0)

    def reset(self):
        self.players, self.follows = {}, 0

    def get(self, pid, name="", avatar=""):
        s = self.players.setdefault(pid, {
            "name": name or pid, "avatar": avatar, "wins": 0, "podiums": 0, "best": 0,
            "guesses": 0, "rounds": 0, "sum_best": 0, "streak": 0, "best_streak": 0,
        })
        if name:
            s["name"] = name
        if avatar:
            s["avatar"] = avatar
        return s

    def round_finished(self, round_players, winner_id, podium_ids):
        """Update wins/podiums/streaks/averages once per round."""
        for p in round_players:
            s = self.get(p.id, p.name, p.avatar)
            s["rounds"] += 1
            if p.best:
                s["sum_best"] += p.best
                s["best"] = p.best if not s["best"] else min(s["best"], p.best)
        for pid in podium_ids:
            if pid in self.players:
                self.players[pid]["podiums"] += 1
        for pid, s in self.players.items():
            if pid == winner_id:
                s["wins"] += 1
                s["streak"] += 1
                s["best_streak"] = max(s["best_streak"], s["streak"])
            elif winner_id:
                s["streak"] = 0
        return self.players.get(winner_id, {}).get("streak", 0)

    def leaderboard(self, n=5):
        rows = [dict(s, id=pid) for pid, s in self.players.items() if s["wins"] or s["podiums"]]
        rows.sort(key=lambda s: (-s["wins"], -s["podiums"], s["best"] or 10**9))
        out = []
        for s in rows[:n]:
            avg = round(s["sum_best"] / s["rounds"]) if s["rounds"] else 0
            out.append({"name": s["name"], "avatar": s["avatar"], "wins": s["wins"],
                        "podiums": s["podiums"], "best": s["best"], "avg": avg,
                        "streak": s["streak"]})
        return out

    def top_streak(self):
        best = max(self.players.values(), key=lambda s: s["streak"], default=None)
        return {"name": best["name"], "n": best["streak"]} if best and best["streak"] >= 2 else None

    def save(self):
        self.store.save(self.FILE, {"players": self.players, "follows": self.follows})
