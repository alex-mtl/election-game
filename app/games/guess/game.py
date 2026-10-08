"""Guess the Word: viewers type English words, each gets a semantic rank vs the
secret word. First exact guess wins; on timeout the best rank wins.

Round state machine (explicit, no boolean soup):
    IDLE -> COUNTDOWN -> PLAYING -> WINNER -> REVEAL -> FINISHED -> COUNTDOWN ...
Everything runs on one asyncio loop, so a guess and the timeout can never both
pick a winner: the first one moves PLAYING -> WINNER and the other sees WINNER.
"""

import math
import os
import random
import time
from collections import deque

from ... import config
from ..base import BaseGame, Viewer
from . import hints
from .players import RoundPlayer, SessionStats

IDLE, COUNTDOWN, PLAYING, WINNER, REVEAL, FINISHED = (
    "idle", "countdown", "playing", "winner", "reveal", "finished")

TEMPS = ["PERFECT", "BURNING", "VERY HOT", "HOT", "WARM", "COLD", "FREEZING"]
# (max rank, level) milestones for "close guess" events, best first
CLOSE_LEVELS = [(2, "so_close"), (3, "top3"), (10, "top10"), (50, "top50"), (100, "top100")]
EXACT_WINDOW_SEC = 3          # exact guesses right after the winner still make the podium
MAX_WORDS = 5000              # cap of aggregated words per round (memory guard)
SIM_NAMES = ["Alex", "Mike", "Sarah", "John", "Emma", "Liam", "Olivia", "Noah", "Mia", "Leo"]


def temperature(rank):
    for bound, label in zip(config.TEMPERATURE_BOUNDS, TEMPS):
        if rank <= bound:
            return label
    return TEMPS[-1]


def temp_key(label):
    return label.lower().replace(" ", "")


class GuessGame(BaseGame):
    name = "guess"
    title = "Guess the Word"
    STATE = "guess/state.json"
    USED = "guess/used_words.json"
    ROUNDS = "guess/rounds.json"

    def __init__(self, store):
        super().__init__(store)
        self.sem, self.error = None, None
        try:
            from .semantic import SemanticIndex
            self.sem = SemanticIndex(config.ASSETS_DIR)
        except Exception as e:
            self.error = f"semantic engine unavailable: {type(e).__name__}: {e}"
            print("[guess]", self.error)
        self.stats = SessionStats(store)
        self.used = set(store.load(self.USED, []))
        self.history = store.load(self.ROUNDS, [])
        self.round_id = 0
        self.difficulty = []          # (solved, seconds, best rank) of recent rounds
        self.tier = "easy"
        self.paused_at = None
        self._clear_round()
        self.phase = IDLE
        self.load()

    # ------------------------------------------------------------------ round
    def _clear_round(self):
        self.secret = None
        self.rank = self.order = None
        self.round_type = "normal"
        self.started_at = self.ends_at = self.phase_until = 0.0
        self.guesses = {}             # word -> aggregated guess
        self.recent = deque(maxlen=10)
        self.players = {}             # id -> RoundPlayer
        self.leader_id = None
        self.past_leaders = set()
        self.winner = None
        self.podium = []
        self.exact_order = []
        self.hints = []
        self.last_hint_t = 0.0
        self.auto_hint_done = False
        self.finished_at = 0.0
        self.unknown_t = 0.0

    def _start_countdown(self, now):
        self._clear_round()
        self.round_id += 1
        every = config.SPEED_ROUND_EVERY
        self.round_type = "speed" if every and self.round_id % every == 0 else "normal"
        self.secret, self.tier = self.sem.pick_secret(self._next_tier(), self.used)
        self.used.add(self.secret)
        self.store.save(self.USED, sorted(self.used))
        self.rank, self.order = self.sem.ranking(self.secret)
        self.phase = COUNTDOWN
        self.phase_until = now + config.COUNTDOWN_SEC
        self.emit("countdown", round=self.round_id, roundType=self.round_type)
        print(f"[guess] round {self.round_id} ({self.round_type}, {self.tier}), "
              f"secret has {len(self.secret)} letters")

    def _start_playing(self, now):
        self.phase = PLAYING
        dur = config.SPEED_ROUND_DURATION if self.round_type == "speed" else config.ROUND_DURATION
        self.started_at, self.ends_at = now, now + dur
        self.emit("round_start", round=self.round_id, roundType=self.round_type, duration=dur)

    def _next_tier(self):
        """Dynamic difficulty: quick wins -> harder words, nobody close -> easier."""
        if not config.DYNAMIC_DIFFICULTY or not self.difficulty:
            return self.tier
        tiers = ["easy", "medium", "hard"]
        i = tiers.index(self.tier) if self.tier in tiers else 0
        last = self.difficulty[-2:]
        if len(last) == 2 and all(solved and secs < 45 for solved, secs, _ in last):
            i = min(i + 1, 2)
        elif not last[-1][0] and last[-1][2] > 300:
            i = max(i - 1, 0)
        return tiers[i]

    def _finish(self, now, reason, player=None):
        """PLAYING -> WINNER. reason: exact | timeout | skip. Atomic by construction."""
        if self.phase != PLAYING:
            return
        self.phase = WINNER
        self.finished_at = now
        self.phase_until = now + config.WINNER_SEC
        if reason != "exact":
            self.emit("timeout", reason=reason)
            ranked = sorted((p for p in self.players.values() if p.best),
                            key=lambda p: (p.best, p.best_t))
            player = ranked[0] if ranked else None
        self.podium = self._podium()
        podium_ids = [p["id"] for p in self.podium]
        streak = self.stats.round_finished(self.players.values(),
                                           player.id if player else None, podium_ids)
        self.stats.save()
        if player:
            self.winner = {"id": player.id, "name": player.name, "avatar": player.avatar,
                           "word": self.secret.upper(), "reason": reason,
                           "seconds": round(now - self.started_at), "guesses": player.guesses,
                           "best": player.best, "streak": streak}
        self.emit("winner", reason=reason, word=self.secret.upper(),
                  name=player.name if player else None,
                  avatar=player.avatar if player else "", streak=streak)
        if player and streak >= 2:
            self.emit("streak", name=player.name, n=streak)
        best_rank = min((p.best for p in self.players.values() if p.best), default=10**9)
        self.difficulty = (self.difficulty + [(reason == "exact", now - self.started_at, best_rank)])[-5:]
        self.history = (self.history + [{
            "round": self.round_id, "type": self.round_type, "tier": self.tier,
            "word": self.secret, "reason": reason, "winner": player.name if player else None,
            "seconds": round(now - self.started_at), "players": len(self.players),
            "guesses": sum(p.guesses for p in self.players.values()), "at": int(now)}])[-300:]
        self.store.save(self.ROUNDS, self.history)
        print(f"[guess] round {self.round_id} {reason}: word={self.secret} "
              f"winner={player.name if player else '-'}")

    def _podium(self):
        out, seen = [], set()
        for pid in self.exact_order:
            if pid in self.players and pid not in seen:
                out.append(self.players[pid]); seen.add(pid)
        rest = sorted((p for p in self.players.values() if p.best and p.id not in seen),
                      key=lambda p: (p.best, p.best_t))
        out += rest
        return [{"id": p.id, "name": p.name, "avatar": p.avatar, "rank": p.best}
                for p in out[:3]]

    # ------------------------------------------------------------------ guesses
    def on_comment(self, viewer: Viewer, text: str):
        if not self.sem or self.phase not in (PLAYING, WINNER):
            return
        now = time.time()
        word, raw = self.sem.normalize(text)
        if raw is None:
            return                                       # ordinary chat, not a guess
        if self.phase == WINNER:                         # late exact guesses -> podium only
            if word == self.secret and now - self.finished_at <= EXACT_WINDOW_SEC \
                    and viewer.id not in self.exact_order:
                p = self.players.setdefault(viewer.id, RoundPlayer(viewer.id, viewer.name, viewer.avatar))
                p.best, p.best_t = 1, now
                self.exact_order.append(viewer.id)
                self.podium = self._podium()
                self.dirty = True
            return
        if word is None:
            if now - self.unknown_t > 1.0:               # throttle the toast
                self.unknown_t = now
                self.emit("unknown", word=raw.upper(), name=viewer.name, avatar=viewer.avatar)
            print(f"[guess] rejected (unknown) {viewer.name}: {raw}")
            return
        p = self.players.get(viewer.id)
        if p is None:
            p = self.players[viewer.id] = RoundPlayer(viewer.id, viewer.name, viewer.avatar)
        p.name, p.avatar = viewer.name, viewer.avatar or p.avatar
        if word in p.words:
            return                                       # same word again: ignore
        if now - p.last_t < config.GUESS_COOLDOWN_SECONDS:
            print(f"[guess] rejected (cooldown) {viewer.name}: {word}")
            return
        self._accept(p, word, now)

    def _accept(self, p, word, now):
        r = int(self.rank[self.sem.index[word]])
        p.last_t = now
        p.words.add(word)
        p.guesses += 1
        self.stats.get(p.id, p.name, p.avatar)["guesses"] += 1

        g = self.guesses.get(word)
        if g is None and len(self.guesses) < MAX_WORDS:
            g = self.guesses[word] = {"word": word, "rank": r, "count": 0, "name": p.name,
                                      "avatar": p.avatar, "t": now}
        if g is not None:
            g["count"] += 1
            g["last"] = p.name
            g["t"] = now
            if word in self.recent:
                self.recent.remove(word)
            self.recent.appendleft(word)
        temp = temperature(r)
        self.emit("guess", word=word.upper(), rank=r, temp=temp, name=p.name,
                  avatar=p.avatar, count=g["count"] if g else 1)
        print(f"[guess] {p.name}: {word} #{r} {temp}")

        if not p.best or r < p.best:
            prev = p.best
            p.prev, p.best, p.best_t, p.best_word = prev, r, now, word
            if prev:
                p.improvements += 1
                if prev >= 100 and r * 10 <= prev:
                    self.emit("jump", kind="massive", name=p.name, avatar=p.avatar, frm=prev, to=r)
                elif prev >= 30 and r * 3 <= prev:
                    self.emit("jump", kind="big", name=p.name, avatar=p.avatar, frm=prev, to=r)
            for bound, level in CLOSE_LEVELS:
                if 1 < r <= bound and bound < p.tier:
                    p.tier = bound
                    self.emit("close", level=level, name=p.name, avatar=p.avatar, rank=r)
                    break
            self._update_leader()
        if r == 1:
            self.exact_order.append(p.id)
            self._finish(now, "exact", p)
        self.dirty = True

    def _update_leader(self):
        ranked = sorted((p for p in self.players.values() if p.best), key=lambda p: (p.best, p.best_t))
        if not ranked or ranked[0].id == self.leader_id:
            return
        new, prev = ranked[0], self.players.get(self.leader_id)
        self.leader_id = new.id
        if prev is not None and new.best > 1:
            self.emit("new_leader", name=new.name, avatar=new.avatar, rank=new.best,
                      prev=prev.name, comeback=new.id in self.past_leaders)
        self.past_leaders.add(new.id)

    # ------------------------------------------------------------------ hints / gifts
    def give_hint(self, source, now=None):
        now = now or time.time()
        if self.phase != PLAYING or not self.secret:
            return None
        if now - self.last_hint_t < config.HINT_COOLDOWN_SEC:
            return None
        h = hints.make_hint(self, config.HINT_TYPES)
        if not h:
            return None
        h["by"] = source
        self.hints.append(h)
        self.last_hint_t = now
        self.emit("hint", kind=h["type"], text=h["text"], word=h["word"], by=source)
        print(f"[guess] hint ({h['type']}) by {source}")
        return h

    def on_gift(self, viewer: Viewer, gift: str, count: int):
        self.emit("gift", name=viewer.name, avatar=viewer.avatar, gift=gift, count=count)
        print(f"[guess] gift {gift} x{count} from {viewer.name}")
        g = gift.lower()
        if g in config.GIFT_NEW_ROUND_NAMES and self.phase == PLAYING:
            self._finish(time.time(), "skip")
        elif g in config.GIFT_HINT_NAMES:
            self.give_hint(viewer.name)

    def on_follow(self, viewer: Viewer):
        self.stats.follows += 1
        self.emit("follow", name=viewer.name, avatar=viewer.avatar)

    # ------------------------------------------------------------------ lifecycle
    def on_activate(self):
        now = time.time()
        if self.paused_at:                                # resume timers where they stopped
            shift = now - self.paused_at
            self.started_at += shift
            self.ends_at += shift
            self.phase_until += shift
            self.paused_at = None
        self.dirty = True

    def on_deactivate(self):
        self.paused_at = time.time()

    def new_session(self):
        self.stats.reset()
        self.stats.save()
        self.used = set()
        self.store.save(self.USED, [])
        self.round_id = 0
        self.difficulty = []
        self.tier = "easy"
        self._clear_round()
        self.phase = IDLE
        self.dirty = True

    def tick(self, now):
        if not self.sem or self.paused_at:
            return
        if self.phase in (IDLE, FINISHED):
            self._start_countdown(now)
        elif self.phase == COUNTDOWN and now >= self.phase_until:
            self._start_playing(now)
        elif self.phase == PLAYING:
            if now >= self.ends_at:
                self._finish(now, "timeout")
            elif config.AUTO_HINT and not self.auto_hint_done and \
                    now - self.started_at > 0.55 * (self.ends_at - self.started_at):
                best = min((p.best for p in self.players.values() if p.best), default=10**9)
                self.auto_hint_done = True
                if best > 300:
                    self.give_hint("auto", now)
        elif self.phase == WINNER and now >= self.phase_until:
            self.phase = REVEAL
            self.phase_until = now + config.REVEAL_SEC
            self.emit("reveal", word=self.secret.upper())
        elif self.phase == REVEAL and now >= self.phase_until:
            self.phase = FINISHED
            self.dirty = True

    # ------------------------------------------------------------------ simulation / debug
    def simulate_step(self):
        if self.phase != PLAYING:
            return 0.5
        now = time.time()
        progress = (now - self.started_at) / max(1, self.ends_at - self.started_at)
        name = random.choice(SIM_NAMES)
        v = Viewer(name.lower(), name, "")
        roll = random.random()
        if roll < 0.03:
            self.on_gift(v, random.choice(["Rose", "Heart", "GG"]), random.randint(1, 5))
        elif roll < 0.05:
            self.on_comment(v, random.choice(["qwzx", "blorp", "zzzt"]))
        elif roll < 0.06:
            self.on_follow(v)
        else:
            hi = math.log(self.sem.size) * (1 - 0.75 * progress)
            r = max(1, int(math.exp(random.uniform(math.log(1.6), max(1.0, hi)))))
            if r == 1 and progress < 0.35:
                r = 2 + random.randint(0, 5)
            self.on_comment(v, self.sem.words[int(self.order[min(r, self.sem.size) - 1])])
        return random.uniform(0.25, 0.9)

    def debug(self, action, params):
        now = time.time()
        name = (params.get("name") or "Tester")[:30]
        v = Viewer(name.lower(), name, "")
        if action == "start_round":
            if self.phase == PLAYING:
                self._finish(now, "skip")
            else:
                self._start_countdown(now)
        elif action == "finish_round":
            self._finish(now, "timeout")
        elif action == "force_winner":
            if self.phase == PLAYING:
                p = self.players.setdefault(v.id, RoundPlayer(v.id, v.name))
                p.last_t = 0
                self._accept(p, self.secret, now)
        elif action == "send_guess":
            p = self.players.get(v.id)
            if p:
                p.last_t = 0
            self.on_comment(v, params.get("word", ""))
        elif action == "send_gift":
            self.on_gift(v, params.get("gift") or "Rose", 1)
        elif action == "hint":
            self.last_hint_t = 0
            return {"hint": self.give_hint(name, now)}
        elif action == "trigger_new_leader":
            self.emit("new_leader", name=name, avatar="", rank=17, prev="Mike", comeback=False)
        elif action == "trigger_massive_jump":
            self.emit("jump", kind="massive", name=name, avatar="", frm=4210, to=37)
        elif action == "trigger_close_guess":
            self.emit("close", level=params.get("level") or "so_close", name=name, avatar="", rank=2)
        elif action == "trigger_streak":
            self.emit("streak", name=name, n=int(params.get("n") or 3))
        elif action == "secret":
            return {"secret": self.secret, "phase": self.phase}
        elif action == "reset":
            self.new_session()
        else:
            return super().debug(action, params)
        return {"ok": True}

    # ------------------------------------------------------------------ public state
    def _row(self, g):
        temp = temperature(g["rank"])
        return {"word": g["word"].upper(), "rank": g["rank"], "temp": temp, "tempKey": temp_key(temp),
                "count": g["count"], "name": g.get("last") or g["name"], "first": g["name"],
                "avatar": g["avatar"]}

    def snapshot(self):
        now = time.time()
        players = sorted((p for p in self.players.values() if p.best), key=lambda p: (p.best, p.best_t))
        reveal = self.phase in (WINNER, REVEAL, FINISHED)
        hunters = []
        for p in players[:5]:
            t = temperature(p.best)
            hunters.append({"name": p.name, "avatar": p.avatar, "rank": p.best, "temp": t,
                            "tempKey": temp_key(t), "guesses": p.guesses, "prev": p.prev,
                            "leader": p.id == self.leader_id})
        best = sorted(self.guesses.values(), key=lambda g: g["rank"])
        return {
            "error": self.error,
            "phase": self.phase,
            "roundId": self.round_id,
            "roundType": self.round_type,
            "tier": self.tier,
            "startedAt": self.started_at,
            "endsAt": self.ends_at,
            "phaseUntil": self.phase_until,
            "now": now,
            "paused": bool(self.paused_at),
            "secretWord": self.secret.upper() if reveal and self.secret else None,
            "guesses": [self._row(self.guesses[w]) for w in self.recent if w in self.guesses],
            "bestGuesses": [self._row(g) for g in best[:10] if g["rank"] > 1 or reveal],
            "topHunters": hunters,
            "leader": hunters[0] if hunters else None,
            "winner": self.winner if reveal else None,
            "podium": self.podium if reveal else [],
            "hints": self.hints,
            "stats": {"players": len(self.players),
                      "top100": sum(1 for p in players if p.best <= 100),
                      "guesses": sum(p.guesses for p in self.players.values())},
            "streamLeaderboard": self.stats.leaderboard(),
            "streak": self.stats.top_streak(),
            "vocabSize": self.sem.size if self.sem else 0,
            "temps": dict(zip(TEMPS, config.TEMPERATURE_BOUNDS + [None])),
            "subscribersOnly": config.SUBSCRIBERS_ONLY,
            "breakSec": config.REVEAL_SEC, "resultsSec": config.RESULTS_SEC,
            "promo": config.PROMO_LINES,
            "goal": {"label": config.GOAL_LABEL, "value": self.stats.follows,
                     "target": config.GOAL_TARGET} if config.GOAL_TARGET else None,
        }

    # ------------------------------------------------------------------ persistence
    def save(self):
        self.stats.save()
        self.store.save(self.STATE, {
            "phase": self.phase, "round_id": self.round_id, "round_type": self.round_type,
            "tier": self.tier, "secret": self.secret, "started_at": self.started_at,
            "ends_at": self.ends_at, "phase_until": self.phase_until,
            "guesses": self.guesses, "recent": list(self.recent),
            "players": {k: p.to_dict() for k, p in self.players.items()},
            "leader_id": self.leader_id, "past_leaders": sorted(self.past_leaders),
            "winner": self.winner, "podium": self.podium, "exact_order": self.exact_order,
            "hints": self.hints, "auto_hint_done": self.auto_hint_done,
            "finished_at": self.finished_at, "difficulty": self.difficulty,
            "saved_at": self.paused_at or time.time(),
        })

    def load(self):
        d = self.store.load(self.STATE)
        if not d or not self.sem:
            return
        try:
            self.round_id = d["round_id"]
            self.tier = d.get("tier", "easy")
            self.difficulty = [tuple(x) for x in d.get("difficulty", [])]
            secret = d.get("secret")
            if not secret or secret not in self.sem.index:
                return
            self.phase = d["phase"]
            self.round_type = d.get("round_type", "normal")
            self.secret = secret
            self.rank, self.order = self.sem.ranking(secret)
            self.started_at, self.ends_at = d["started_at"], d["ends_at"]
            self.phase_until = d["phase_until"]
            self.guesses = d.get("guesses", {})
            self.recent = deque(d.get("recent", []), maxlen=10)
            self.players = {k: RoundPlayer.from_dict(v) for k, v in d.get("players", {}).items()}
            self.leader_id = d.get("leader_id")
            self.past_leaders = set(d.get("past_leaders", []))
            self.winner = d.get("winner")
            self.podium = d.get("podium", [])
            self.exact_order = d.get("exact_order", [])
            self.hints = d.get("hints", [])
            self.auto_hint_done = d.get("auto_hint_done", False)
            self.finished_at = d.get("finished_at", 0.0)
            self.paused_at = d.get("saved_at")         # timers resume on activation
            print(f"[guess] restored round {self.round_id} ({self.phase})")
        except Exception as e:
            print(f"[guess] can't restore state ({e}), starting fresh")
            self._clear_round()
            self.phase = IDLE
