"""Semantic index over the precomputed vocabulary (no model needed at runtime:
every guessable word already has an embedding, built by tools/build_assets.py)."""

import hashlib
import json
import os
import random
import re

import numpy as np

# "the cat", "le chat", "el gato": the article is dropped
ARTICLES = {"en": {"a", "an", "the"}, "ru": set(),
            "fr": {"le", "la", "les", "un", "une", "des", "du", "de"},
            "es": {"el", "la", "los", "las", "un", "una", "unos", "unas"}}
# letters of a guess per language (anything else in a single-word message = not a guess)
LETTERS = {"en": "a-z", "ru": "а-яё", "fr": "a-zàâæçéèêëîïôœùûüÿ", "es": "a-záéíóúüñ"}
ELISION = re.compile(r"^(?:l|d|j|m|n|s|t|c|qu)'")      # French: l'arbre -> arbre


class SemanticIndex:
    def __init__(self, assets_dir, lang="en"):
        self.lang = lang
        with open(os.path.join(assets_dir, "vocab.txt"), "rb") as f:
            raw = f.read()
        self.words = [w.strip() for w in raw.decode("utf-8").splitlines() if w.strip()]
        self.vocab_hash = hashlib.sha1(raw).hexdigest()[:12]     # the ranker Lambda reports the same
        self.index = {w: i for i, w in enumerate(self.words)}
        # the game image has no embeddings: rankings come from the word-ranker Lambda (tests have them)
        path = os.path.join(assets_dir, "embeddings.npy")
        self.emb = None
        if os.path.exists(path):
            emb = np.load(path).astype(np.float32)
            emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
            self.emb = emb
        with open(os.path.join(assets_dir, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.aliases = meta.get("aliases", {})
        self.pools = meta.get("pools", {})
        self.categories = meta.get("categories", {})
        self.level = meta.get("level", "easy")
        self.hint_limit = meta.get("hint_limit", 0)       # hints prefer words[:hint_limit]
        self.size = len(self.words)
        print(f"[semantic {lang}] {self.size} words, pools "
              f"{ {k: len(v) for k, v in self.pools.items()} }")

    def normalize(self, text):
        """Chat message -> dictionary word, or None if it isn't a single-word guess.
        Returns (word, raw) where word may be None for unknown words."""
        text = (text or "")[:60].strip().lower().replace("ё", "е").replace("’", "'")
        letters = LETTERS.get(self.lang, "a-z")
        tokens = re.findall(rf"[{letters}]+(?:['-][{letters}]+)*", text)
        if len(tokens) == 2 and tokens[0] in ARTICLES.get(self.lang, ()):
            tokens = tokens[1:]
        if self.lang == "fr" and len(tokens) == 1:
            tokens = [ELISION.sub("", tokens[0])]
        if len(tokens) != 1:
            return None, None
        # anything except letters/punctuation (digits, emoji-only...) -> not a guess
        if re.search(r"[0-9]", text):
            return None, None
        raw = tokens[0].replace("'", "").replace("-", "")
        if not (2 <= len(raw) <= 20):
            return None, None
        if raw in self.index:
            return raw, raw
        lemma = self.aliases.get(raw)
        if lemma in self.index:
            return lemma, raw
        return None, raw

    def split_words(self, text, limit=3):
        """A message of 2..limit words (letters only, no digits) -> the words, else None."""
        text = (text or "")[:120].strip().lower().replace("ё", "е").replace("’", "'")
        if re.search(r"[0-9]", text):
            return None
        letters = LETTERS.get(self.lang, "a-z")
        tokens = re.findall(rf"[{letters}]+(?:['-][{letters}]+)*", text)
        if self.lang == "fr":
            tokens = [ELISION.sub("", t) for t in tokens]
        tokens = [t for t in tokens if t not in ARTICLES.get(self.lang, ())]
        return tokens if 2 <= len(tokens) <= limit else None

    def ranking(self, secret):
        """rank[i] = 1-based position of vocab word i by similarity to secret (needs the embeddings)."""
        if self.emb is None:
            raise RuntimeError("no embeddings here: the ranking comes from the word-ranker Lambda")
        sims = self.emb @ self.emb[self.index[secret]]
        order = np.argsort(-sims, kind="stable")
        if order[0] != self.index[secret]:          # exact word is always #1
            order = np.concatenate(([self.index[secret]], order[order != self.index[secret]]))
        rank = np.empty(self.size, dtype=np.int32)
        rank[order] = np.arange(1, self.size + 1, dtype=np.int32)
        return rank, order

    def pick_secret(self, tier, used):
        tiers = [tier] + [t for t in ("easy", "medium", "hard") if t != tier]
        for t in tiers:
            pool = [w for w in self.pools.get(t, []) if w not in used and w in self.index]
            if pool:
                return random.choice(pool), t
        pool = [w for p in self.pools.values() for w in p if w in self.index]
        return random.choice(pool), tier                 # everything used: allow repeats
