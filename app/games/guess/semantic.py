"""Semantic index over the precomputed vocabulary (no model needed at runtime:
every guessable word already has an embedding, built by tools/build_assets.py)."""

import json
import os
import random
import re

import numpy as np

ARTICLES = {"a", "an", "the"}


class SemanticIndex:
    def __init__(self, assets_dir):
        with open(os.path.join(assets_dir, "vocab.txt"), encoding="utf-8") as f:
            self.words = [w.strip() for w in f if w.strip()]
        self.index = {w: i for i, w in enumerate(self.words)}
        emb = np.load(os.path.join(assets_dir, "embeddings.npy")).astype(np.float32)
        emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
        self.emb = emb
        with open(os.path.join(assets_dir, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.aliases = meta.get("aliases", {})
        self.pools = meta.get("pools", {})
        self.categories = meta.get("categories", {})
        self.size = len(self.words)
        print(f"[semantic] {self.size} words, pools "
              f"{ {k: len(v) for k, v in self.pools.items()} }")

    def normalize(self, text):
        """Chat message -> dictionary word, or None if it isn't a single-word guess.
        Returns (word, raw) where word may be None for unknown words."""
        text = (text or "")[:60].strip().lower()
        tokens = re.findall(r"[a-z]+(?:['-][a-z]+)*", text)
        if len(tokens) == 2 and tokens[0] in ARTICLES:
            tokens = tokens[1:]
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

    def ranking(self, secret):
        """rank[i] = 1-based position of vocab word i by similarity to secret."""
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
