"""Hints: semantic (a close word), category, first letter, length, distance.
Each hint type returns a dict {type, text, word?} or None if not applicable."""

import random

# semantic hints get closer each time: rank bands for the 1st, 2nd, 3rd... semantic hint
SEMANTIC_BANDS = [(120, 400), (40, 120), (12, 40), (4, 12)]


def semantic(game, n_given):
    lo, hi = SEMANTIC_BANDS[min(n_given, len(SEMANTIC_BANDS) - 1)]
    secret = game.secret
    candidates = []
    for i in game.order[lo - 1:hi]:
        w = game.sem.words[int(i)]
        if w in game.guesses or w == secret or secret in w or w in secret:
            continue
        if any(h.get("word") == w for h in game.hints):
            continue
        candidates.append(w)
    if not candidates:
        return None
    w = random.choice(candidates[:20])
    return {"type": "semantic", "text": "A word close to the secret word is:", "word": w.upper()}


def category(game, n_given):
    cat = game.sem.categories.get(game.secret)
    if not cat or any(h["type"] == "category" for h in game.hints):
        return None
    return {"type": "category", "text": "The word is related to:", "word": cat}


def letter(game, n_given):
    if any(h["type"] == "letter" for h in game.hints):
        if any(h["type"] == "length" for h in game.hints):
            return None
        return {"type": "length", "text": "The word has", "word": f"{len(game.secret)} LETTERS",
                "n": len(game.secret)}
    return {"type": "letter", "text": "The word starts with", "word": game.secret[0].upper()}


def distance(game, n_given):
    """'The secret word is within the TOP N of <best guess>'."""
    best = min((g for g in game.guesses.values() if g["rank"] > 1), key=lambda g: g["rank"], default=None)
    if not best:
        return None
    rank, _ = game.sem.ranking(best["word"])
    pos = int(rank[game.sem.index[game.secret]])
    for n in (10, 50, 100, 500, 1000, 5000):
        if pos <= n:
            return {"type": "distance", "text": f"The secret word is in the TOP {n} closest words to",
                    "word": best["word"].upper(), "n": n}
    return None


TYPES = {"semantic": semantic, "category": category, "letter": letter, "distance": distance}


def make_hint(game, kinds):
    """Try hint types in rotation starting at the next one; first applicable wins."""
    n = len(game.hints)
    for k in range(len(kinds)):
        kind = kinds[(n + k) % len(kinds)]
        fn = TYPES.get(kind)
        if not fn:
            continue
        given = sum(1 for h in game.hints if h["type"] == kind)
        h = fn(game, given)
        if h:
            return h
    return None
