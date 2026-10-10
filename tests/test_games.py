"""Run inside the image (needs the built assets):
    docker run --rm -v "$PWD/tests:/app/tests" election-game python -m unittest discover -s tests -v
"""

import os
import tempfile
import time
import unittest

from app import config
from app.games.base import Viewer
from app.games.battle.game import BattleGame
from app.games.guess import game as guess_mod
from app.games.guess.game import GuessGame
from app.storage import JsonStore

config.GUESS_COOLDOWN_SECONDS = 3
config.COUNTDOWN_SEC = 0


def v(name):
    return Viewer(name.lower(), name, "")


class GuessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()

    def make(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp(dir=self.tmp)))
        self.assertIsNone(g.error, g.error)
        g.tick(time.time())                       # IDLE -> COUNTDOWN
        g.tick(time.time() + 0.01)                # -> PLAYING
        self.assertEqual(g.phase, guess_mod.PLAYING)
        return g

    def rank_of(self, g, word):
        return int(g.rank[g.sem.index[word]])

    def test_semantic_ordering(self):
        g = self.make()
        g.secret = "ocean"
        g.rank, g.order = g.sem.ranking("ocean")
        self.assertEqual(self.rank_of(g, "ocean"), 1)
        near = max(self.rank_of(g, w) for w in ("sea", "water", "wave"))
        far = min(self.rank_of(g, w) for w in ("computer", "banana"))
        self.assertLess(near, far)

    def test_normalize(self):
        g = self.make()
        n = g.sem.normalize
        self.assertEqual(n("  Water! ")[0], "water")
        self.assertEqual(n("the ocean")[0], "ocean")
        self.assertEqual(n("oceans")[0], "ocean")              # plural -> lemma
        self.assertEqual(n("hello there friend"), (None, None))   # chat, not a guess
        self.assertEqual(n("<script>"), ("script", "script"))    # harmless, just a word
        self.assertEqual(n("qwzxv")[0], None)                   # unknown word
        self.assertEqual(n("abc123"), (None, None))

    def test_cooldown_and_duplicates(self):
        g = self.make()
        a = v("Alex")
        g.on_comment(a, "water")
        g.on_comment(a, "fire")                                 # within 3 s -> ignored
        self.assertEqual(g.players["alex"].guesses, 1)
        g.players["alex"].last_t -= 5
        g.on_comment(a, "water")                                # duplicate word -> ignored
        self.assertEqual(g.players["alex"].guesses, 1)
        g.on_comment(v("Mike"), "fire")                         # others not blocked
        self.assertEqual(g.players["mike"].guesses, 1)

    def test_exact_guess_wins_once(self):
        g = self.make()
        g.on_comment(v("Alex"), g.secret)
        self.assertEqual(g.phase, guess_mod.WINNER)
        self.assertEqual(g.winner["name"], "Alex")
        g.on_comment(v("Mike"), g.secret)                       # late exact: podium only
        self.assertEqual(g.winner["name"], "Alex")
        self.assertEqual([p["name"] for p in g.podium][:2], ["Alex", "Mike"])
        g.phase_until = g.ends_at + 100
        g.tick(g.ends_at + 1)                                   # timeout after win: no change
        self.assertEqual(g.phase, guess_mod.WINNER)
        self.assertEqual(g.winner["name"], "Alex")

    def test_timeout_picks_best_rank(self):
        g = self.make()
        far, near = g.sem.words[int(g.order[3000])], g.sem.words[int(g.order[5])]
        g.on_comment(v("Alex"), far)
        g.on_comment(v("Mike"), near)
        g.tick(g.ends_at + 0.1)
        self.assertEqual(g.phase, guess_mod.WINNER)
        self.assertEqual(g.winner["name"], "Mike")
        self.assertEqual(g.winner["reason"], "timeout")
        g.on_comment(v("Sarah"), g.secret)                      # after timeout: no new winner
        self.assertEqual(g.winner["name"], "Mike")

    def test_streak_and_leaderboard(self):
        g = self.make()
        for _ in range(2):
            g.on_comment(v("Alex"), g.secret)
            g.phase = guess_mod.FINISHED
            g.tick(time.time())
            g.tick(time.time() + 0.01)
        self.assertEqual(g.stats.players["alex"]["streak"], 2)
        self.assertEqual(g.stats.leaderboard()[0]["wins"], 2)
        self.assertTrue(any(e["type"] == "streak" for e in g.events))

    def test_secret_not_public_while_playing(self):
        g = self.make()
        self.assertIsNone(g.snapshot()["secretWord"])
        g.on_comment(v("Alex"), g.secret)
        self.assertEqual(g.snapshot()["secretWord"], g.secret.upper())

    def test_persistence_roundtrip(self):
        store = JsonStore(tempfile.mkdtemp(dir=self.tmp))
        g = GuessGame(store)
        g.tick(time.time()); g.tick(time.time() + 0.01)
        g.on_comment(v("Alex"), "water")
        g.save()
        g2 = GuessGame(store)
        self.assertEqual(g2.secret, g.secret)
        self.assertEqual(g2.players["alex"].guesses, 1)
        g2.on_activate()
        self.assertEqual(g2.phase, guess_mod.PLAYING)

    def test_hints(self):
        g = self.make()
        g.last_hint_t = 0
        h = g.give_hint("test")
        self.assertIsNotNone(h)
        self.assertNotEqual(h["word"].lower(), g.secret)


class RussianTest(unittest.TestCase):
    def test_russian_round(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        self.assertIn("ru", g.sems)
        g.set_lang("ru")
        g.tick(time.time()); g.tick(time.time() + 0.01)
        self.assertEqual(g.round_lang, "ru")
        self.assertRegex(g.secret, r"^[а-я]+$")
        n = g.sem.normalize
        self.assertEqual(n("Кошки!")[0], "кошка")             # inflected form -> lemma
        self.assertEqual(n("ёлка")[0], n("елка")[0])           # ё == е
        self.assertEqual(n("cat"), (None, None))                # latin in RU mode: not a guess
        rank = lambda w: int(g.rank[g.sem.index[w]])
        r, _ = g.sem.ranking("собака")
        idx = g.sem.index
        self.assertLess(r[idx["щенок"]], r[idx["налог"]])
        g.on_comment(Viewer("ivan", "Иван", "", 1), g.secret)  # exact Russian guess wins
        self.assertEqual(g.winner["name"], "Иван")

    def test_switch_language_starts_new_round(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        en_secret = g.secret
        g.set_lang("ru")
        g.tick(time.time())
        self.assertEqual(g.phase, guess_mod.COUNTDOWN)
        self.assertNotEqual(g.secret, en_secret)
        self.assertEqual(g.round_lang, "ru")


class GiftHintTest(unittest.TestCase):
    def test_gift_hint_counts_as_gifter_guess(self):
        config.GIFT_HINT_NAMES = ["rose"]
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        mike = Viewer("mike", "Mike", "", 1)
        g.on_gift(mike, "Rose", 1)
        h = g.hints[-1]
        self.assertEqual(h["type"], "semantic")
        p = g.players["mike"]
        self.assertIn(h["word"].lower(), p.words)
        self.assertEqual(p.best, int(g.rank[g.sem.index[h["word"].lower()]]))
        self.assertEqual(g.snapshot()["topHunters"][0]["name"], "Mike")
        g.on_gift(Viewer("sara", "Sara", "", 1), "Rose", 1)    # no cooldown between gifters
        self.assertEqual(len(g.hints), 2)


class FollowTest(GuessTest):
    def nf(self, name):
        return Viewer(name.lower(), name, "", 0)            # not following

    def test_non_follower_removed_after_grace(self):
        config.FOLLOW_REQUIRED, config.FOLLOW_GRACE_SEC = True, 30
        g = self.make()
        g.on_comment(self.nf("Logan"), "water")
        p = g.players["logan"]
        self.assertTrue(p.pending_until)
        self.assertEqual(g.snapshot()["topHunters"][0]["name"], "Logan")   # shown meanwhile
        g.tick(p.pending_until + 0.1)
        self.assertTrue(p.dq)
        self.assertEqual(g.snapshot()["topHunters"], [])                    # removed
        g.on_follow(self.nf("Logan"))                                       # follows later -> back
        self.assertFalse(p.dq)
        self.assertEqual(g.snapshot()["topHunters"][0]["name"], "Logan")

    def test_non_follower_must_follow_to_win(self):
        config.FOLLOW_REQUIRED, config.FOLLOW_GRACE_SEC = True, 30
        g = self.make()
        g.on_comment(self.nf("Logan"), g.secret)
        self.assertEqual(g.phase, guess_mod.PLAYING)                       # not a win yet
        g.on_follow(self.nf("Logan"))
        self.assertEqual(g.phase, guess_mod.WINNER)
        self.assertEqual(g.winner["name"], "Logan")

    def test_host_and_followers_not_checked(self):
        config.FOLLOW_REQUIRED = True
        g = self.make()
        g.on_comment(Viewer("alex", "Alex", "", 1), "water")
        g.on_comment(Viewer(config.TIKTOK_USERNAME.lower(), "Host", "", 0), "fire")
        self.assertFalse(any(p.pending_until for p in g.players.values()))


class StreamerTest(unittest.TestCase):
    def test_likes_inflate_and_launch(self):
        from app.games.streamer.game import StreamerOverlay
        config.LIKES_PER_BALLOON = 100
        s = StreamerOverlay(JsonStore(tempfile.mkdtemp()))
        mao = Viewer("mao", "Mao", "")
        s.on_like(mao, 60)
        self.assertEqual(s.snapshot()["inflating"][0]["fill"], 0.6)
        self.assertFalse([e for e in s.events if e["type"] == "balloon"])
        s.on_like(mao, 45)                                   # crosses 100 -> lift off, 5 left
        launches = [e for e in s.events if e["type"] == "balloon"]
        self.assertEqual(len(launches), 1)
        self.assertEqual(launches[0]["id"], "mao")
        self.assertEqual(s.snapshot()["inflating"][0]["progress"], 5)
        s.on_like(mao, 250)                                  # big batch -> two more balloons
        self.assertEqual(len([e for e in s.events if e["type"] == "balloon"]), 3)


class BattleTest(unittest.TestCase):
    def test_cooldowns_and_join(self):
        b = BattleGame(JsonStore(tempfile.mkdtemp()))
        self.assertTrue(b.tap("a", "red", "A", now=100))
        self.assertFalse(b.tap("a", "red", "A", now=102))      # same team within 5 s
        self.assertTrue(b.tap("a", "yellow", "A", now=103))    # other team ok
        self.assertEqual(b.join("z", "Z"), ("a", "yellow"))     # joiner credited to last commenter


if __name__ == "__main__":
    unittest.main()
