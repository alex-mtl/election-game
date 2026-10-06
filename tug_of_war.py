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
import random
import re
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------- config ----------------
TIKTOK_USERNAME = "CHANGE_ME"   # <-- put your TikTok @username here (without @)
STEP_PCT = 1.0                  # screen % gained per tap
TAP_COOLDOWN_SEC = 1.0          # min seconds between counted taps of one user
WIN_PAUSE_SEC = 15              # winner banner duration, then next round
PORT = 8765

RED_KEYS = {"r", "red", "красный", "красная", "красные", "к"}
YELLOW_KEYS = {"y", "yellow", "желтый", "жёлтый", "желтая", "жёлтая",
               "желтые", "жёлтые", "ж"}


# ---------------- game state ----------------
class Game:
    def __init__(self):
        self.lock = threading.Lock()
        self.round_no = 1
        self.reset()

    def reset(self):
        self.red_pct = 50.0
        self.taps = defaultdict(lambda: {"red": 0, "yellow": 0})
        self.last_tap = {}
        self.winner = None          # "red" | "yellow" | None
        self.mvp = None
        self.mvp_taps = 0
        self.win_until = 0.0

    def tap(self, user, color, now=None):
        """Register one tap. Returns True if counted."""
        if color not in ("red", "yellow"):
            return False
        now = time.time() if now is None else now
        with self.lock:
            if self.winner:                     # round over, ignore taps
                return False
            if now - self.last_tap.get(user, 0) < TAP_COOLDOWN_SEC:
                return False                    # anti-spam cooldown
            self.last_tap[user] = now
            self.taps[user][color] += 1
            if color == "red":
                self.red_pct = min(100.0, self.red_pct + STEP_PCT)
            else:
                self.red_pct = max(0.0, self.red_pct - STEP_PCT)
            if self.red_pct >= 100.0:
                self._finish("red", now)
            elif self.red_pct <= 0.0:
                self._finish("yellow", now)
            return True

    def _finish(self, winner, now):
        self.winner = winner
        best, best_n = None, 0
        for user, t in self.taps.items():
            if t[winner] > best_n:
                best, best_n = user, t[winner]
        self.mvp, self.mvp_taps = best, best_n
        self.win_until = now + WIN_PAUSE_SEC

    def maybe_next_round(self):
        with self.lock:
            if self.winner and time.time() >= self.win_until:
                self.round_no += 1
                self.reset()

    def snapshot(self):
        with self.lock:
            taps_red = sum(t["red"] for t in self.taps.values())
            taps_yellow = sum(t["yellow"] for t in self.taps.values())
            top_red = sorted(((u, t["red"]) for u, t in self.taps.items()
                              if t["red"]), key=lambda x: -x[1])[:3]
            top_yellow = sorted(((u, t["yellow"]) for u, t in self.taps.items()
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
                "mvp": self.mvp,
                "mvp_taps": self.mvp_taps,
            }


game = Game()


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
        if self.path == "/state.json":
            self._send(json.dumps(game.snapshot(), ensure_ascii=False),
                        "application/json")
        else:
            try:
                with open("game.html", "rb") as f:
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
    from TikTokLive.events import CommentEvent

    client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)

    @client.on(CommentEvent)
    async def on_comment(event):
        try:
            user = (getattr(event.user, "unique_id", None)
                    or getattr(event.user, "nickname", None) or "anon")
            color = parse_color(getattr(event, "comment", "") or "")
            if color:
                game.tap(str(user), color)
        except Exception as e:  # never kill the listener on a bad comment
            print("[tiktok] handler error:", e)

    print(f"[tiktok] connecting to @{TIKTOK_USERNAME} ...")
    client.run()


# ---------------- fake viewers (offline test) ----------------
def simulator():
    names = ["anna", "boris", "kira", "den", "eva", "fedor", "gina"]
    print("[sim] fake viewers tapping (no TikTok needed)")
    while True:
        time.sleep(random.uniform(0.05, 0.4))
        game.tap(random.choice(names),
                 random.choice(["red", "yellow", "red", "yellow", "red"]))


# ---------------- main ----------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true",
                    help="fake viewers instead of real TikTok comments")
    args = ap.parse_args()

    threading.Thread(target=serve_forever, daemon=True).start()
    if args.simulate or TIKTOK_USERNAME == "CHANGE_ME":
        if TIKTOK_USERNAME == "CHANGE_ME" and not args.simulate:
            print("[warn] set TIKTOK_USERNAME in tug_of_war.py; "
                  "running simulator meanwhile")
        threading.Thread(target=simulator, daemon=True).start()
    else:
        threading.Thread(target=tiktok_listener, daemon=True).start()

    print("[game] tug-of-war running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopped.")
