"""All settings come from environment variables (.env in Docker, see .env.example)."""

import os


def _f(name, default):
    return float(os.getenv(name, default))


def _i(name, default):
    return int(float(os.getenv(name, default)))


def _b(name, default="0"):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _list(name, default=""):
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


# ---- platform ----
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "CHANGE_ME").lstrip("@") or "CHANGE_ME"
SIMULATE = _b("SIMULATE")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = _i("PORT", 8765)
DATA_DIR = os.getenv("DATA_DIR", "data")
ASSETS_DIR = os.getenv("ASSETS_DIR", "assets")
RECONNECT_SEC = _f("RECONNECT_SEC", 15)
DEBUG_CONTROLS = _b("DEBUG_CONTROLS", "1")     # /debug page + /api/debug/*
DEFAULT_GAME = os.getenv("DEFAULT_GAME", "battle")

# ---- battle (tug of war) ----
STEP_PCT = _f("STEP_PCT", 1.0)
TAP_COOLDOWN_SEC = _f("TAP_COOLDOWN_SEC", 1.0)
TEAM_COOLDOWN_SEC = _f("TEAM_COOLDOWN_SEC", 5)
WIN_PAUSE_SEC = _f("WIN_PAUSE_SEC", 15)

# ---- guess the word ----
ROUND_DURATION = _i("ROUND_DURATION", 210)
SPEED_ROUND_DURATION = _i("SPEED_ROUND_DURATION", 75)
SPEED_ROUND_EVERY = _i("SPEED_ROUND_EVERY", 4)          # every Nth round is SPEED (0 = never)
COUNTDOWN_SEC = _i("COUNTDOWN_SEC", 4)                  # 3, 2, 1, GO
WINNER_SEC = _i("WINNER_SEC", 5)                        # winner card
REVEAL_SEC = _i("REVEAL_SEC", 9)                        # podium + best guesses + "new round in"
GUESS_COOLDOWN_SECONDS = _f("GUESS_COOLDOWN_SECONDS", 3)
# rank upper bounds: PERFECT, BURNING, VERY HOT, HOT, WARM, COLD (rest = FREEZING)
TEMPERATURE_BOUNDS = [int(x) for x in _list("TEMPERATURE_BOUNDS", "1,10,50,200,1000,5000")]
DYNAMIC_DIFFICULTY = _b("DYNAMIC_DIFFICULTY", "1")
AUTO_HINT = _b("AUTO_HINT", "1")                        # hint when nobody gets close
HINT_TYPES = _list("HINT_TYPES", "semantic,category,letter,semantic")
HINT_COOLDOWN_SEC = _f("HINT_COOLDOWN_SEC", 20)
GIFT_HINT_NAMES = [g.lower() for g in _list("GIFT_HINT_NAMES", "Rose")]
GIFT_NEW_ROUND_NAMES = [g.lower() for g in _list("GIFT_NEW_ROUND_NAMES", "")]
SUBSCRIBERS_ONLY = _b("SUBSCRIBERS_ONLY")
GOAL_LABEL = os.getenv("GOAL_LABEL", "FOLLOW GOAL")
GOAL_TARGET = _i("GOAL_TARGET", 0)                       # follows this stream; 0 hides the goal bar
