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

    def test_guess_sent_before_round_is_ignored(self):
        g = self.make()
        g.on_comment(v("Alex"), "water", ts=g.started_at - 20)   # typed during the break, delivered late
        self.assertNotIn("alex", g.players)
        g.on_comment(v("Alex"), "water", ts=g.started_at + 1)    # typed in the round
        self.assertEqual(g.players["alex"].guesses, 1)

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
        g.on_comment(v("Alex"), "water" if g.secret != "water" else "fire")   # not the secret itself
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

    def test_levels(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        for k in ("en", "ru", "en-easy", "ru-easy"):
            self.assertIn(k, g.sems)
        self.assertEqual(g.get_options()["level"], 2)              # normal by default
        g.set_lang("ru")
        g.tick(time.time()); g.tick(time.time() + 0.01)
        normal = g.sem
        self.assertEqual(normal.level, "normal")
        n = normal.normalize
        for w in ("стамеска", "плоскогубцы", "бурундук", "кит", "роза", "еж", "юг"):
            self.assertIn(w, normal.index)                         # rare / short / name-like nouns
        self.assertEqual(n("бобр")[0], "бобер")
        self.assertEqual(n("ежики")[0], "ежик")
        for w in ("быстро", "красивый", "бежать", "го", "ми"):
            self.assertNotIn(w, normal.index)                      # not nouns / junk
        g.set_option("level", 1)                                   # from the next round
        self.assertIs(g.sem, normal)
        g.on_comment(Viewer("ivan", "Иван", "", 1), g.secret)
        for _ in range(10):                                        # winner -> break -> next round
            if g.phase == guess_mod.COUNTDOWN:
                break
            g.tick(max(time.time(), g.phase_until) + 0.1)
        self.assertEqual(g.sem.level, "easy")
        self.assertIn("быстро", g.sem.index)                       # easy: any part of speech
        self.assertEqual(g.snapshot()["languages"], ["en", "es", "fr", "ru"])

    def test_switch_language_starts_new_round(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        en_secret = g.secret
        g.set_lang("ru")
        g.tick(time.time())
        self.assertEqual(g.phase, guess_mod.COUNTDOWN)
        self.assertNotEqual(g.secret, en_secret)
        self.assertEqual(g.round_lang, "ru")


class RomanceTest(unittest.TestCase):
    def test_french(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        self.assertIn("fr", g.sems)
        g.set_lang("fr")
        g.tick(time.time()); g.tick(time.time() + 0.01)
        n = g.sem.normalize
        self.assertEqual(n("Chiens")[0], "chien")             # plural -> lemma
        self.assertEqual(n("le chat")[0], "chat")             # article dropped
        self.assertEqual(n("l’arbre")[0], "arbre")       # elision, typographic apostrophe
        self.assertEqual(n("ecureuil")[0], "écureuil")        # typed without accents
        for w in ("rapidement", "manger", "courir"):
            self.assertNotIn(w, g.sem.index)                  # not nouns
        r, _ = g.sem.ranking("chien")
        idx = g.sem.index
        self.assertLess(r[idx["chiot"]], r[idx["volcan"]])
        g.on_comment(Viewer("zoe", "Zoé", "", 1), g.secret)
        self.assertEqual(g.winner["name"], "Zoé")

    def test_spanish(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        self.assertIn("es", g.sems)
        g.set_lang("es")
        g.tick(time.time()); g.tick(time.time() + 0.01)
        n = g.sem.normalize
        self.assertEqual(n("los perros")[0], "perro")
        self.assertEqual(n("Árbol")[0], "árbol")
        self.assertEqual(n("arbol")[0], "árbol")               # without accents
        for w in ("rápidamente", "comer", "haber"):
            self.assertNotIn(w, g.sem.index)
        r, _ = g.sem.ranking("perro")
        idx = g.sem.index
        self.assertLess(r[idx["cachorro"]], r[idx["factura"]])
        self.assertEqual(g.snapshot()["languages"], ["en", "es", "fr", "ru"])


class GiftHintTest(unittest.TestCase):
    def test_gift_hint_counts_as_gifter_guess(self):
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

    def test_any_gift_gives_hint(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        g.on_gift(Viewer("eva", "Eva", "", 1), "Mirwas Beat", 1)
        self.assertEqual(len(g.hints), 1)
        self.assertEqual(g.hints[-1]["by"], "Eva")

    def test_hint_credit(self):
        store = JsonStore(tempfile.mkdtemp())
        g = GuessGame(store)
        g.tick(time.time()); g.tick(time.time() + 0.01)
        eva = Viewer("evgenija0101", "Eva", "", 1)
        g.on_comment(Viewer("bob", "Bob", "", 1), "ПодсКАЗКА")           # no credits: an ordinary guess
        self.assertEqual(len(g.hints), 0)
        self.assertEqual(g.add_credits("@Evgenija0101", 1), 1)
        g.on_comment(eva, "ПоДсКаЗкА!")
        self.assertEqual(len(g.hints), 1)
        self.assertEqual(g.hints[-1]["by"], "Eva")
        self.assertIn(g.hints[-1]["word"].lower(), g.players["evgenija0101"].words)
        self.assertEqual(g.credits.get("evgenija0101", 0), 0)             # spent
        self.assertEqual(GuessGame(store).credits, {})                     # saved
        g.on_comment(eva, "подсказка")                                     # no credits left: a guess
        self.assertEqual(len(g.hints), 1)

    def test_gift_combo_goes_on_account_with_cooldown(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        g.set_option("hint_cd", 20)
        eva = Viewer("eva", "Eva", "", 1)
        g.on_gift(eva, "Rose", 5)                          # x5: one hint now, 4 on the account
        self.assertEqual(len(g.hints), 1)
        self.assertEqual(g.credits["eva"], 4)
        g.on_gift(eva, "Rose", 1)                          # within 20 s: on the account
        self.assertEqual(len(g.hints), 1)
        self.assertEqual(g.credits["eva"], 5)
        g.on_comment(eva, "подсказка")                     # too soon: nothing spent
        self.assertEqual(len(g.hints), 1)
        self.assertEqual(g.credits["eva"], 5)
        g.hint_t["eva"] -= 21                              # 21 s later
        g.on_comment(eva, "Подсказка")
        self.assertEqual(len(g.hints), 2)
        self.assertEqual(g.credits["eva"], 4)
        g.on_comment(eva, "подсказка")                     # again too soon
        self.assertEqual(len(g.hints), 2)
        self.assertEqual(g.get_options()["hint_cd"], 20)

    def test_gift_hint_beats_best_guess(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        close = g.sem.words[int(g.order[29])]                 # someone already guessed the #30 word
        g.on_comment(Viewer("ann", "Ann", "", 1), close)
        best = min(x["rank"] for x in g.guesses.values())
        for i in range(3):
            g.on_gift(Viewer(f"v{i}", f"V{i}", "", 1), "Rose", 1)
            h = g.hints[-1]
            self.assertEqual(h["type"], "semantic")
            r = int(g.rank[g.sem.index[h["word"].lower()]])
            self.assertLess(r, best)                           # every paid hint is closer
            best = min(best, r)

    def test_gift_hint_after_second_best_wins(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        g.on_comment(Viewer("ann", "Ann", "", 1), g.sem.words[int(g.order[1])])   # the #2 word
        g.on_gift(Viewer("bob", "Bob", "", 1), "Rose", 1)
        self.assertEqual(g.hints[-1]["word"].lower(), g.secret)                  # only the secret is closer
        self.assertEqual(g.phase, guess_mod.WINNER)
        self.assertEqual(g.exact_order[0], "bob")                                # the gifter wins


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
        self.assertTrue(g.snapshot()["bestGuesses"][0]["pendingUntil"])     # countdown in the row
        g.tick(p.pending_until + 0.1)
        self.assertTrue(p.dq)
        self.assertEqual(g.snapshot()["topHunters"], [])                    # removed
        self.assertEqual(g.snapshot()["bestGuesses"], [])                   # their words hidden too
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


class NonStopTest(unittest.TestCase):
    def test_no_break_goes_straight_to_next_round(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.set_option("break", False)
        g.tick(time.time()); g.tick(time.time() + 0.01)
        first = g.round_id
        g.on_comment(v("Alex"), g.secret)
        self.assertEqual(g.phase, guess_mod.WINNER)
        g.tick(g.phase_until + 0.1)                          # winner card over -> no reveal
        self.assertEqual(g.phase, guess_mod.FINISHED)
        g.tick(time.time())
        self.assertEqual(g.phase, guess_mod.COUNTDOWN)
        self.assertEqual(g.round_id, first + 1)

    def test_pause_and_round_length_options(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.set_option("pause", 30)
        g.set_option("round_min", 20)
        g.set_option("follow", 0)
        g.set_option("grace", 60)
        self.assertEqual(g.get_options(), {"pause": 30, "round_min": 20, "follow": 0, "grace": 60, "level": 2,
                                           "hint_cd": 20, "chroma": 0, "chroma_top": 33,
                                           "frame": 16})
        self.assertFalse(g.follow_required)
        g.tick(time.time()); g.tick(time.time() + 0.01)
        self.assertAlmostEqual(g.ends_at - g.started_at, 20 * 60, delta=1)   # 20-minute round
        g.on_comment(v("Alex"), g.secret)
        g.tick(g.phase_until + 0.1)
        self.assertEqual(g.phase, guess_mod.REVEAL)
        self.assertAlmostEqual(g.phase_until - g.finished_at, 30, delta=1)   # whole break = 30 s

    def test_switch_off_during_break(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        g.on_comment(v("Alex"), g.secret)
        g.tick(g.phase_until + 0.1)
        self.assertEqual(g.phase, guess_mod.REVEAL)          # break on by default
        g.set_option("break", False)
        self.assertEqual(g.phase, guess_mod.FINISHED)


class BalloonsTest(unittest.TestCase):
    def test_likes_inflate_and_launch(self):
        from app.reactions.balloons import LikeBalloons
        config.LIKES_PER_BALLOON = 100
        bl = LikeBalloons(JsonStore(tempfile.mkdtemp()))
        mao = Viewer("mao", "Mao", "")
        self.assertEqual(bl.on_like(mao, 60), [])
        self.assertEqual(bl.snapshot()["inflating"][0]["fill"], 0.6)
        launches = bl.on_like(mao, 45)                       # crosses 100 -> lift off, 5 left
        self.assertEqual(len(launches), 1)
        self.assertEqual(launches[0]["id"], "mao")
        self.assertEqual(bl.snapshot()["inflating"][0]["progress"], 5)
        self.assertEqual(len(bl.on_like(mao, 250)), 2)       # big batch -> two more balloons

    def test_hub_sends_balloons_on_any_game(self):
        from app.hub import Hub
        config.LIKES_PER_BALLOON = 100
        hub = Hub(JsonStore(tempfile.mkdtemp()))
        hub.set_active("guess")
        hub.like(Viewer("mao", "Mao", ""), 100)
        self.assertTrue(any(e["type"] == "balloon" for e in hub.feed))
        self.assertIn("balloons", hub.message("guess"))


class ChromaTest(unittest.TestCase):
    def test_chroma_option(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        self.assertEqual(g.snapshot()["chroma"], 0)
        g.set_option("chroma", 1)
        self.assertEqual(g.snapshot()["chroma"], 33)
        g.set_option("chroma_top", 40)
        self.assertEqual(g.snapshot()["chroma"], 40)
        g.set_option("chroma_top", 77)                      # not a choice: ignored
        self.assertEqual(g.get_options()["chroma_top"], 40)
        g.set_option("frame", 19.5)
        self.assertEqual(g.snapshot()["frame"], 19.5)
        g.set_option("frame", 17)                           # not a choice: ignored
        self.assertEqual(g.get_options()["frame"], 19.5)


class TTLauncherTest(unittest.TestCase):
    def test_bat(self):
        from app.server import tt_bat
        b = tt_bat(8765)
        self.assertIn("http://localhost:8765/guess/?tt=1", b)
        self.assertIn("--autoplay-policy=no-user-gesture-required", b)
        self.assertIn(r"\Google\Chrome\Application\chrome.exe", b)
        self.assertIn("\r\n", b)                                        # Windows line ends


class ChampionsTest(unittest.TestCase):
    def test_places_and_ties(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        st = g.stats
        for pid, w in (("a", 5), ("b", 3), ("c", 3), ("d", 3), ("e", 2), ("f", 1)):
            s = st.get(pid, pid.upper(), "")
            s["wins"] = w
        ch = st.champions()
        self.assertEqual([c["wins"] for c in ch], [5, 3, 2])          # 1st, 2nd (tie of 3), 3rd
        self.assertEqual([c["n"] for c in ch], [1, 3, 1])
        self.assertEqual(ch[0]["players"][0]["name"], "A")
        self.assertIn("champions", g.snapshot())


class LikersTest(unittest.TestCase):
    def test_planes_and_balloon_places(self):
        from app.reactions.balloons import LikeBalloons
        saved = config.PLANE_AUTO_LIKES, config.LIKES_PER_BALLOON
        try:
            config.PLANE_AUTO_LIKES, config.LIKES_PER_BALLOON = 1000, 100
            lb = LikeBalloons(JsonStore(tempfile.mkdtemp()))
            for pid, likes in (("ded", 12500), ("a", 4200), ("b", 4900), ("m", 2100), ("x", 1500),
                               ("lena", 760), ("z", 120)):
                lb.on_like(Viewer(pid, pid.upper(), ""), likes)
            l = lb.likers()
            self.assertEqual([g["count"] for g in l["planes"]], [12, 4, 2])     # 4 planes: a and b tie
            self.assertEqual(l["planes"][1]["n"], 2)
            self.assertEqual(l["balloon"]["count"], 7)                          # 760 likes, no plane yet
            self.assertEqual(l["balloon"]["players"][0]["name"], "LENA")
            self.assertIn("likers", lb.snapshot())
        finally:
            config.PLANE_AUTO_LIKES, config.LIKES_PER_BALLOON = saved


class ChampionWordsTest(unittest.TestCase):
    def test_champions_send_up_to_three_words(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        for pid, w in (("ann", 3), ("bob", 2), ("cat", 2), ("dan", 1), ("eve", 0)):
            g.stats.get(pid, pid.title(), "")["wins"] = w
        words = [w for w in ("water", "fire", "house", "tree") if w != g.secret]
        g.on_comment(Viewer("cat", "Cat", "", 1), " ".join(words[:3]))         # 2nd place (tie): 3 words
        self.assertEqual(g.players["cat"].guesses, 3)
        g.on_comment(Viewer("dan", "Dan", "", 1), "the " + words[3] + " " + words[0])   # 3rd place: article dropped
        self.assertEqual(g.players["dan"].guesses, 2)
        g.on_comment(Viewer("eve", "Eve", "", 1), words[0] + " " + words[1])    # not a champion: ignored
        self.assertNotIn("eve", g.players)
        g.on_comment(Viewer("ann", "Ann", "", 1), " ".join(words))              # 4 words: not a guess
        self.assertNotIn("ann", g.players)

    def test_round_champions_send_up_to_three_words(self):
        g = GuessGame(JsonStore(tempfile.mkdtemp()))
        g.tick(time.time()); g.tick(time.time() + 0.01)
        r = lambda k: g.sem.words[int(g.order[k])]                  # the k+1-th closest word
        first, copycat, other = Viewer("first", "First", "", 1), Viewer("copy", "Copy", "", 1), Viewer("o", "O", "", 1)
        g.on_comment(first, r(10))
        g.on_comment(copycat, r(10))                                 # same word, later: no advantage
        g.on_comment(other, r(500))
        self.assertIn("first", g._round_champion_ids())
        self.assertNotIn("copy", g._round_champion_ids())
        g.players["first"].last_t = 0
        g.on_comment(first, r(20) + " " + r(30))                     # round champion: both words count
        self.assertEqual(g.players["first"].guesses, 3)
        # "first" now holds the table's top 3: the next author down the table is a champion too
        self.assertEqual(g._round_champion_ids(), {"first", "o"})
        g.players["copy"].last_t = 0
        g.on_comment(copycat, r(40) + " " + r(50))                   # not a champion: ignored
        self.assertEqual(g.players["copy"].guesses, 1)


class GiftReceiverTest(unittest.TestCase):
    def test_gift_to_someone_else_gives_no_hint(self):
        from app.hub import Hub
        hub = Hub(JsonStore(tempfile.mkdtemp()))
        hub.set_active("guess")
        g = hub.games["guess"]
        g.tick(time.time()); g.tick(time.time() + 0.01)
        alex = Viewer("alex_mg", "Alex", "", 1)
        hub.gift(alex, "You're awesome", 5, to="someguest")           # to a guest on the stream
        self.assertEqual(len(g.hints), 0)
        hub.gift(alex, "Rose", 1, to=config.TIKTOK_USERNAME.upper())  # to the host
        self.assertEqual(len(g.hints), 1)
        hub.gift(Viewer("bob", "Bob", "", 1), "Rose", 1)               # receiver unknown: the host
        self.assertEqual(len(g.hints), 2)


class NoLikesCommandTest(unittest.TestCase):
    def test_likes_command_is_gone(self):
        from app.hub import Hub
        hub = Hub(JsonStore(tempfile.mkdtemp()))
        mika = Viewer("mika", "Mikaniri", "")
        hub.like(mika, 50)
        hub.comment(mika, "!лайки!")
        hub.comment(mika, "!likes!")
        self.assertEqual([e for e in hub.feed if e["type"] in ("plane", "plane_denied")], [])


class AutoPlaneTest(unittest.TestCase):
    def test_plane_flies_by_itself_every_1000_likes(self):
        from app.hub import Hub
        config.PLANE_AUTO_LIKES = 1000
        hub = Hub(JsonStore(tempfile.mkdtemp()))
        d = Viewer("ded", "DED", "")
        planes = lambda: [e for e in hub.feed if e["type"] == "plane"]
        hub.like(d, 990)
        self.assertEqual(planes(), [])
        hub.like(d, 15)                                          # 1005 -> auto plane
        self.assertEqual(len(planes()), 1)
        self.assertEqual(planes()[-1]["total"], 1005)
        hub.like(d, 500)
        self.assertEqual(len(planes()), 1)                       # next one only at 2000
        hub.like(d, 600)
        self.assertEqual(len(planes()), 2)


class GlobalSettingsTest(unittest.TestCase):
    def test_set_and_validate(self):
        from app.settings import GlobalSettings
        gs, saved = GlobalSettings(), (config.PLANE_AUTO_LIKES, config.GREET_JOINS, config.VOICE_RATE)
        try:
            self.assertTrue(gs.set("plane_auto", 2000))
            self.assertEqual(config.PLANE_AUTO_LIKES, 2000)
            self.assertFalse(gs.set("plane_auto", 1234))             # not one of the choices
            self.assertEqual(config.PLANE_AUTO_LIKES, 2000)
            self.assertTrue(gs.set("greet", 0))
            self.assertIs(config.GREET_JOINS, False) if isinstance(saved[1], bool) else None
            self.assertEqual(gs.values()["greet"], 0)
            self.assertTrue(gs.set("voice_rate", 1.25))
            self.assertEqual(config.VOICE_RATE, 1.25)
        finally:
            config.PLANE_AUTO_LIKES, config.GREET_JOINS, config.VOICE_RATE = saved


class BomberTest(unittest.TestCase):
    def test_bomber_every_10000_likes(self):
        from app.reactions.balloons import LikeBalloons
        saved = config.PLANE_BOMBER_LIKES, config.PLANE_AUTO_LIKES
        try:
            config.PLANE_BOMBER_LIKES, config.PLANE_AUTO_LIKES = 10000, 1000
            lb = LikeBalloons(JsonStore(tempfile.mkdtemp()))
            m = Viewer("mik", "Mik", "", 1)
            planes = []
            for _ in range(250):                        # 250 x 100 likes = 25 000
                before = lb.total_of(m.id)
                lb.on_like(m, 100)
                p = lb.auto_plane(m, before)
                if p:
                    planes.append(p)
            self.assertEqual(len(planes), 25)
            self.assertEqual([i + 1 for i, p in enumerate(planes) if p["bomber"]], [10, 20])   # 10 000, 20 000
        finally:
            config.PLANE_BOMBER_LIKES, config.PLANE_AUTO_LIKES = saved


class BattleKeysTest(unittest.TestCase):
    def test_team_keys_per_language(self):
        from app.games.battle.game import parse_color
        self.assertEqual(parse_color("Y", "en"), "yellow")
        self.assertIsNone(parse_color("I want a win", "en"))        # "a" is not a key in English
        self.assertEqual(parse_color("a", "es"), "yellow")
        self.assertEqual(parse_color("J !", "fr"), "yellow")
        self.assertEqual(parse_color("ж", "ru"), "yellow")
        self.assertIsNone(parse_color("ж", "en"))
        self.assertEqual(parse_color("vamos rojo", "en"), "red")    # colour words: any language
        self.assertEqual(parse_color("allez les jaunes", "es"), "yellow")


class BattleTest(unittest.TestCase):
    def test_cooldowns_and_join(self):
        b = BattleGame(JsonStore(tempfile.mkdtemp()))
        self.assertTrue(b.tap("a", "red", "A", now=100))
        self.assertFalse(b.tap("a", "red", "A", now=102))      # same team within 5 s
        self.assertTrue(b.tap("a", "yellow", "A", now=103))    # other team ok
        self.assertEqual(b.join("z", "Z"), ("a", "yellow"))     # joiner credited to last commenter


if __name__ == "__main__":
    unittest.main()
