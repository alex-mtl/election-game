#!/usr/bin/env python3
"""
TikTok LIVE Tug-of-War: RED vs YELLOW.

Viewers vote by chat comments. Each comment with a team keyword = 1 tap.
Red tap  -> red half grows by STEP_PCT.  Yellow tap -> yellow grows.
First team to take 100% of the screen wins the round.
MVP = the player with the most taps on the winning color.

Display: open http://<this-pc-ip>:8765/ in the phone browser (fullscreen)
and stream the phone screen via TikTok "Mobile Gaming" live mode.

Requires: pip install TikTokLive
Run:      python tug_of_war.py
Test:     python tug_of_war.py --simulate   (fake viewers, no TikTok needed)
"""

import argparse
import json
import os
import random
import re
import signal
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# ---------------- config (overridable via env vars, see .env.example) ----------------
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "CHANGE_ME").lstrip("@") or "CHANGE_ME"
STEP_PCT = float(os.getenv("STEP_PCT", "1.0"))                  # screen % gained per tap
TAP_COOLDOWN_SEC = float(os.getenv("TAP_COOLDOWN_SEC", "1.0"))  # min seconds between counted taps of one user
WIN_PAUSE_SEC = float(os.getenv("WIN_PAUSE_SEC", "15"))         # winner banner duration, then next round
PORT = int(os.getenv("PORT", "8765"))
RECONNECT_SEC = float(os.getenv("RECONNECT_SEC", "15"))        # retry delay while offline / after drop
SIMULATE = os.getenv("SIMULATE", "").lower() in ("1", "true", "yes")
STATE_FILE = os.getenv("STATE_FILE", "state.json")             # score survives restarts; delete to reset
GAME_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game.html")

RED_KEYS = {"r", "red", "красный", "красная", "красные", "к"}
YELLOW_KEYS = {"y", "yellow", "желтый", "жёлтый", "желтая", "жёлтая",
               "желтые", "жёлтые", "ж"}


# ---------------- game state ----------------
class Game:
    def __init__(self):
        self.lock = threading.Lock()
        self.round_no = 1
        self.names = {}             # user id -> display name (TikTok nickname)
        self.recruiter = None       # (user, color) of the last R/Y commenter
        self.events = deque(maxlen=100)  # recent events for page sounds/voice
        self.seq = 0
        self.reset()

    def _event(self, **ev):
        """Append an event for the page (sounds / voice). Lock must be held."""
        self.seq += 1
        ev["seq"] = self.seq
        self.events.append(ev)

    def to_dict(self):
        with self.lock:
            return {
                "round_no": self.round_no,
                "names": self.names,
                "recruiter": self.recruiter,
                "red_pct": self.red_pct,
                "taps": dict(self.taps),
                "winner": self.winner,
                "mvp": self.mvp,
                "mvp_taps": self.mvp_taps,
                "win_until": self.win_until,
            }

    def load(self, d):
        with self.lock:
            self.round_no = d.get("round_no", 1)
            self.names = d.get("names", {})
            rec = d.get("recruiter")
            self.recruiter = tuple(rec) if rec else None
            self.red_pct = d.get("red_pct", 50.0)
            self.taps.clear()
            for user, t in d.get("taps", {}).items():
                self.taps[user].update(t)
            self.winner = d.get("winner")
            self.mvp = d.get("mvp")
            self.mvp_taps = d.get("mvp_taps", 0)
            self.win_until = d.get("win_until", 0.0)

    def reset(self):
        self.red_pct = 50.0
        self.taps = defaultdict(lambda: {"red": 0, "yellow": 0})
        self.last_tap = {}
        self.winner = None          # "red" | "yellow" | None
        self.mvp = None
        self.mvp_taps = 0
        self.win_until = 0.0

    def _push(self, user, color, now):
        """Give one point to user on color and move the bar. Lock must be held."""
        self.taps[user][color] += 1
        if color == "red":
            self.red_pct = min(100.0, self.red_pct + STEP_PCT)
        else:
            self.red_pct = max(0.0, self.red_pct - STEP_PCT)
        if self.red_pct >= 100.0:
            self._finish("red", now)
        elif self.red_pct <= 0.0:
            self._finish("yellow", now)

    def tap(self, user, color, name=None, now=None):
        """Register one tap. Returns True if counted."""
        if color not in ("red", "yellow"):
            return False
        now = time.time() if now is None else now
        with self.lock:
            if name:
                self.names[user] = name
            self.recruiter = (user, color)      # next joiners go to this team
            if self.winner:                     # round over, ignore taps
                return False
            if now - self.last_tap.get(user, 0) < TAP_COOLDOWN_SEC:
                return False                    # anti-spam cooldown
            self.last_tap[user] = now
            self._event(type="tap", color=color, name=self.name(user))
            self._push(user, color, now)
            return True

    def join(self, user, name=None, now=None):
        """Viewer joined the LIVE: +1 point to the last R/Y commenter's team,
        credited to that commenter. Returns (recruiter, color) or None."""
        now = time.time() if now is None else now
        with self.lock:
            if self.winner or not self.recruiter:
                return None
            rec, color = self.recruiter
            if rec == user:
                return None
            self._event(type="join", color=color, name=name or user,
                        by=self.name(rec))
            self._push(rec, color, now)
            return rec, color

    def name(self, user):
        return self.names.get(user, user)

    def _finish(self, winner, now):
        self.winner = winner
        best, best_n = None, 0
        for user, t in self.taps.items():
            if t[winner] > best_n:
                best, best_n = user, t[winner]
        self.mvp, self.mvp_taps = best, best_n
        self.win_until = now + WIN_PAUSE_SEC
        self._event(type="win", color=winner,
                    name=self.name(best) if best else None)

    def maybe_next_round(self):
        with self.lock:
            if self.winner and time.time() >= self.win_until:
                self.round_no += 1
                self.reset()
                self._event(type="round", round=self.round_no)

    def snapshot(self, since=0):
        with self.lock:
            taps_red = sum(t["red"] for t in self.taps.values())
            taps_yellow = sum(t["yellow"] for t in self.taps.values())
            top_red = sorted(((self.name(u), t["red"]) for u, t in self.taps.items()
                              if t["red"]), key=lambda x: -x[1])[:3]
            top_yellow = sorted(((self.name(u), t["yellow"]) for u, t in self.taps.items()
                                 if t["yellow"]), key=lambda x: -x[1])[:3]
            return {
                "red_pct": round(self.red_pct, 1),
                "yellow_pct": round(100.0 - self.red_pct, 1),
                "round": self.round_no,
                "taps_red": taps_red,
                "taps_yellow": taps_yellow,
                "top_red": top_red,
                "top_yellow": top_yellow,
                "winner": self.winner,
                "mvp": self.name(self.mvp) if self.mvp else None,
                "mvp_taps": self.mvp_taps,
                "seq": self.seq,
                "events": [e for e in self.events if e["seq"] > since],
            }


game = Game()


# ---------------- persistence ----------------
_last_saved = None


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            game.load(json.load(f))
        print(f"[state] restored round {game.round_no}, red {game.red_pct}% from {STATE_FILE}")
    except FileNotFoundError:
        print(f"[state] no {STATE_FILE}, starting fresh")
    except Exception as e:
        print(f"[state] can't read {STATE_FILE} ({e}), starting fresh")


def save_state():
    """Write state atomically if it changed since the last save."""
    global _last_saved
    data = json.dumps(game.to_dict(), ensure_ascii=False)
    if data == _last_saved:
        return
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, STATE_FILE)
    _last_saved = data


def saver():
    while True:
        time.sleep(1)
        try:
            save_state()
        except Exception as e:
            print("[state] save error:", e)


def parse_color(comment):
    """Return 'red' | 'yellow' | None based on first keyword found."""
    words = re.findall(r"\w+", (comment or "").lower())
    first = None
    for w in words:
        if w in RED_KEYS:
            return "red"
        if w in YELLOW_KEYS:
            return "yellow"
    return None


# ---------------- web server ----------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        game.maybe_next_round()
        url = urlparse(self.path)
        if url.path == "/state.json":
            try:
                since = int(parse_qs(url.query).get("since", ["0"])[0])
            except ValueError:
                since = 0
            self._send(json.dumps(game.snapshot(since), ensure_ascii=False),
                        "application/json")
        else:
            try:
                with open(GAME_HTML, "rb") as f:
                    data = f.read()
            except FileNotFoundError:
                data = b"<h1>game.html not found next to tug_of_war.py</h1>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


def serve_forever():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[web] open http://<this-PC-IP>:{PORT}/ on your phone browser")
    srv.serve_forever()


# ---------------- TikTok listener ----------------
def tiktok_listener():
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import CommentEvent, ConnectEvent, JoinEvent

    client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)

    started_at = time.time()

    def is_old(event):
        """On connect TikTok replays recent chat history - skip anything sent
        before we started listening (small margin for clock skew)."""
        ct = getattr(getattr(event, "common", None), "create_time", 0) or 0
        if ct > 1e12:               # milliseconds
            ct /= 1000
        return bool(ct) and ct < started_at - 3

    def who(u):
        """(stable user id, display nickname)"""
        uid = str(getattr(u, "unique_id", None) or getattr(u, "nickname", None) or "anon")
        return uid, (getattr(u, "nickname", None) or uid)

    @client.on(ConnectEvent)
    async def on_connect(event):
        print(f"[tiktok] connected to @{TIKTOK_USERNAME} LIVE, listening to chat")

    @client.on(CommentEvent)
    async def on_comment(event):
        try:
            user, name = who(event.user)
            color = parse_color(getattr(event, "comment", "") or "")
            if color and is_old(event):
                print(f"[skip] old comment from {name} ({color}) sent before connect")
                return
            if color and game.tap(user, color, name):
                print(f"[tap] {name} ({user}) -> {color}")
        except Exception as e:  # never kill the listener on a bad comment
            print("[tiktok] handler error:", e)

    @client.on(JoinEvent)
    async def on_join(event):
        try:
            if is_old(event):
                return
            user, name = who(event.user)
            res = game.join(user, name)
            if res:
                print(f"[join] {name} joined -> +1 {res[1]} for {game.name(res[0])}")
        except Exception as e:
            print("[tiktok] join handler error:", e)

    print(f"[tiktok] connecting to @{TIKTOK_USERNAME} ...")
    client.run()


def tiktok_listener_forever():
    """Keep (re)connecting: waits for the LIVE to start, reconnects on drops."""
    from TikTokLive.client.errors import UserOfflineError
    while True:
        try:
            tiktok_listener()
            print("[tiktok] disconnected")
        except UserOfflineError:
            print(f"[tiktok] @{TIKTOK_USERNAME} is not live yet, "
                  f"retry in {RECONNECT_SEC:.0f}s")
        except Exception as e:
            print(f"[tiktok] error: {type(e).__name__}: {e}")
        time.sleep(RECONNECT_SEC)


# ---------------- fake viewers (offline test) ----------------
def simulator():
    names = ["anna", "boris", "kira", "den", "eva", "fedor", "gina"]
    print("[sim] fake viewers tapping (no TikTok needed)")
    while True:
        time.sleep(random.uniform(0.05, 0.4))
        if random.random() < 0.15:
            game.join("guest%d" % random.randint(1, 999))
        else:
            game.tap(random.choice(names),
                     random.choice(["red", "yellow", "red", "yellow", "red"]))


# ---------------- main ----------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true",
                    help="fake viewers instead of real TikTok comments")
    args = ap.parse_args()
    simulate = args.simulate or SIMULATE

    # docker stop sends SIGTERM: turn it into a clean exit so the score gets saved
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt))
    load_state()
    threading.Thread(target=saver, daemon=True).start()
    threading.Thread(target=serve_forever, daemon=True).start()
    if simulate or TIKTOK_USERNAME == "CHANGE_ME":
        if TIKTOK_USERNAME == "CHANGE_ME" and not simulate:
            print("[warn] set TIKTOK_USERNAME (in .env); "
                  "running simulator meanwhile")
        threading.Thread(target=simulator, daemon=True).start()
    else:
        threading.Thread(target=tiktok_listener_forever, daemon=True).start()

    print("[game] tug-of-war running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        save_state()
        print("\nstopped, score saved.")
