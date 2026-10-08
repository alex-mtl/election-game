"""Game registry. To add a game: create app/games/<name>/ with a BaseGame subclass,
a page at app/web/<name>/index.html, and list it here."""

from .battle.game import BattleGame
from .guess.game import GuessGame

GAMES = [BattleGame, GuessGame]
