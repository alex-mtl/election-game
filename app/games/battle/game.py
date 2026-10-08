"""Team Battle (tug of war): RED vs YELLOW.

Chat "R"/"Y" = 1 point for that team. A viewer joining the LIVE gives 1 point
to the team of the last R/Y commenter, credited to that commenter.
First team to push the bar to 100% wins the round.
"""

import random
import re
import time
from collections import defaultdict

from ... import config
from ..base import BaseGame, Viewer

RED_KEYS = {"r", "red", "красный", "красная", "красные", "к"}
YELLOW_KEYS = {"y", "yellow", "желтый", "жёлтый", "желтая", "жёлтая",
               "желтые", "жёлтые", "ж"}


def parse_color(comment):
    """'red' | 'yellow' | None based on the first team keyword in the comment."""
    for w in re.findall(r"\w+", (comment or "").lower()[:200]):
        if w in RED_KEYS:
            return "red"
        if w in YELLOW_KEYS:
            return "yellow"
    return None


class BattleGame(BaseGame):
    name = "battle"
    title = "Team Battle"
    STATE = "battle.json"

    def __init__(self, store):
        super().__init__(store)
        self.round_no = 1
        self.names = {}             # user id -> display name
        self.recruiter = None       # (user, color) of the last R/Y commenter
        self.reset()
        self.load()

    # ---- state ----
    def reset(self):
        self.red_pct = 50.0
        self.taps = defaultdict(lambda: {"red": 0, "yellow": 0})
        self.last_tap = {}
        self.winner = None
        self.mvp = None
        self.mvp_taps = 0
        self.win_until = 0.0
        self.leader = {"red": None, "yellow": None}
        self.dirty = True

    def new_session(self):
        self.round_no = 1
        self.names = {}
        self.recruiter = None
        self.reset()
        self.emit("round", round=1)

    def name_of(self, user):
        return self.names.get(user, user)

    def _push(self, user, color, now):
        """One point to user on color, move the bar, detect leader change / win."""
        self.taps[user][color] += 1
        cur = self.leader[color]
        if cur is None:
            self.leader[color] = user
        elif cur != user and self.taps[user][color] > self.taps[cur][color]:
            self.leader[color] = user
            self.emit("lead", color=color, name=self.name_of(user), prev=self.name_of(cur))
        if color == "red":
            self.red_pct = min(100.0, self.red_pct + config.STEP_PCT)
        else:
            self.red_pct = max(0.0, self.red_pct - config.STEP_PCT)
        if self.red_pct >= 100.0:
            self._finish("red", now)
        elif self.red_pct <= 0.0:
            self._finish("yellow", now)
        self.dirty = True

    def _finish(self, winner, now):
        self.winner = winner
        best, best_n = None, 0
        for user, t in self.taps.items():
            if t[winner] > best_n:
                best, best_n = user, t[winner]
        self.mvp, self.mvp_taps = best, best_n
        self.win_until = now + config.WIN_PAUSE_SEC
        self.emit("win", color=winner, name=self.name_of(best) if best else None)

    def tap(self, user, color, name=None, now=None):
        """Register one tap. Returns True if counted."""
        now = time.time() if now is None else now
        if name:
            self.names[user] = name
        self.recruiter = (user, color)              # next joiners go to this team
        if self.winner:
            return False
        if now - self.last_tap.get(user, 0) < config.TAP_COOLDOWN_SEC:
            return False                            # anti-spam
        if now - self.last_tap.get((user, color), 0) < config.TEAM_COOLDOWN_SEC:
            return False                            # same user + same team: once per N sec
        self.last_tap[user] = now
        self.last_tap[(user, color)] = now
        self.emit("tap", color=color, name=self.name_of(user))
        self._push(user, color, now)
        return True

    def join(self, user, name=None, now=None):
        """Viewer joined: +1 to the last R/Y commenter's team, credited to them."""
        now = time.time() if now is None else now
        if self.winner or not self.recruiter:
            return None
        rec, color = self.recruiter
        if rec == user:
            return None
        self.emit("join", color=color, name=name or user, by=self.name_of(rec))
        self._push(rec, color, now)
        return rec, color

    # ---- hooks ----
    def on_comment(self, viewer: Viewer, text: str):
        color = parse_color(text)
        if color and self.tap(viewer.id, color, viewer.name):
            print(f"[battle] tap {viewer.name} ({viewer.id}) -> {color}")

    def on_join(self, viewer: Viewer):
        res = self.join(viewer.id, viewer.name)
        if res:
            print(f"[battle] join {viewer.name} -> +1 {res[1]} for {self.name_of(res[0])}")

    def tick(self, now):
        if self.winner and now >= self.win_until:
            self.round_no += 1
            self.reset()
            self.emit("round", round=self.round_no)

    def simulate_step(self):
        names = ["anna", "boris", "kira", "den", "eva", "fedor", "gina"]
        if random.random() < 0.15:
            self.join("guest%d" % random.randint(1, 999))
        else:
            n = random.choice(names)
            self.tap(n, random.choice(["red", "yellow", "red", "yellow", "red"]), n.title())
        return random.uniform(0.05, 0.4)

    def debug(self, action, params):
        if action == "reset":
            self.new_session()
        elif action == "tap":
            n = params.get("name") or "tester"
            self.tap(n, params.get("color", "red"), n, now=time.time() + 1e6 * random.random())
        elif action == "join":
            self.join(params.get("name") or "guest%d" % random.randint(1, 999))
        else:
            return super().debug(action, params)
        return {"ok": True}

    def snapshot(self):
        taps_red = sum(t["red"] for t in self.taps.values())
        taps_yellow = sum(t["yellow"] for t in self.taps.values())
        top = lambda c: sorted(((self.name_of(u), t[c]) for u, t in self.taps.items() if t[c]),
                               key=lambda x: -x[1])[:3]
        return {
            "red_pct": round(self.red_pct, 1),
            "yellow_pct": round(100.0 - self.red_pct, 1),
            "round": self.round_no,
            "taps_red": taps_red,
            "taps_yellow": taps_yellow,
            "top_red": top("red"),
            "top_yellow": top("yellow"),
            "winner": self.winner,
            "mvp": self.name_of(self.mvp) if self.mvp else None,
            "mvp_taps": self.mvp_taps,
        }

    # ---- persistence ----
    def save(self):
        self.store.save(self.STATE, {
            "round_no": self.round_no, "names": self.names, "recruiter": self.recruiter,
            "red_pct": self.red_pct, "taps": dict(self.taps), "winner": self.winner,
            "mvp": self.mvp, "mvp_taps": self.mvp_taps, "win_until": self.win_until,
            "leader": self.leader,
        })

    def load(self):
        d = self.store.load(self.STATE) or self.store.load("state.json")  # pre-multigame file
        if not d:
            return
        self.round_no = d.get("round_no", 1)
        self.names = d.get("names", {})
        rec = d.get("recruiter")
        self.recruiter = tuple(rec) if rec else None
        self.red_pct = d.get("red_pct", 50.0)
        for user, t in d.get("taps", {}).items():
            self.taps[user].update(t)
        self.winner = d.get("winner")
        self.mvp = d.get("mvp")
        self.mvp_taps = d.get("mvp_taps", 0)
        self.win_until = d.get("win_until", 0.0)
        self.leader = d.get("leader") or {"red": None, "yellow": None}
        print(f"[battle] restored round {self.round_no}, red {self.red_pct}%")
