#!/usr/bin/env python3
"""
Build the word assets for "Guess the Word" (runs once, in the Docker build stage).

Output (--out dir):
  vocab.txt          every guessable word (lemmas), most frequent first
  embeddings.npy     float16 [len(vocab), 384], L2-normalized, row i = vocab[i]
  english_nouns.txt  secret-word pool (common singular nouns)
  meta.json          pools by difficulty, inflection aliases, categories, sources

Sources:
  wordfreq   - word frequencies (code MIT, data CC BY-SA 4.0)
  WordNet    - parts of speech, lemmas, categories (WordNet 3.0 license, permissive)
  better_profanity - profanity list (MIT)
  sentence-transformers/all-MiniLM-L6-v2 - embeddings (Apache 2.0)
"""

import argparse
import json
import os
import re
import time

import numpy as np
from nltk.corpus import wordnet as wn
from wordfreq import top_n_list, zipf_frequency

WORD_RE = re.compile(r"^[a-z]{3,15}$")

# WordNet lexicographer file -> category shown in "category" hints
CATEGORIES = {
    "noun.animal": "ANIMALS", "noun.food": "FOOD", "noun.artifact": "MAN-MADE OBJECTS",
    "noun.location": "PLACES", "noun.person": "PEOPLE", "noun.plant": "PLANTS",
    "noun.body": "THE BODY", "noun.act": "ACTIONS", "noun.feeling": "FEELINGS",
    "noun.event": "EVENTS", "noun.communication": "COMMUNICATION",
    "noun.substance": "MATERIALS", "noun.object": "NATURE", "noun.phenomenon": "NATURE",
    "noun.time": "TIME", "noun.group": "GROUPS", "noun.cognition": "THE MIND",
    "noun.attribute": "QUALITIES", "noun.state": "STATES", "noun.possession": "MONEY",
    "noun.quantity": "MEASUREMENT", "noun.shape": "SHAPES", "noun.process": "PROCESSES",
    "noun.relation": "RELATIONS", "noun.motive": "MOTIVES", "noun.Tops": "THINGS",
}

# difficulty tiers for secret words, by wordfreq zipf frequency
TIERS = {"easy": (4.4, 9.0), "medium": (3.9, 4.4), "hard": (3.4, 3.9)}


# fine to guess, but never chosen as the secret word on a family-friendly stream
SECRET_BLOCK = {
    "abortion", "terrorism", "terrorist", "suicide", "murder", "killer", "genocide", "holocaust",
    "slavery", "slave", "racism", "racist", "cancer", "tumor", "disease", "death", "corpse",
    "funeral", "weapon", "gun", "rifle", "bomb", "bullet", "drug", "alcohol", "cigarette",
    "overdose", "prostitute", "nude", "nudity", "porn", "religion", "jihad", "bible", "church",
    "mosque", "hostage", "assault", "torture", "victim", "abuse", "addiction", "addict", "gunshot",
    "shooting", "massacre", "execution", "prison", "inmate", "divorce", "virgin", "sexuality",
    "vomit", "vomiting", "diarrhea", "diaper", "toilet", "urine", "poop", "fart", "pregnancy",
    "erection", "condom", "lingerie", "bra", "breast", "nipple", "testicle", "ammo", "ammunition",
}


def profanity_set():
    words = set()
    try:
        import better_profanity
        path = os.path.join(os.path.dirname(better_profanity.__file__), "profanity_wordlist.txt")
        with open(path, encoding="utf-8") as f:
            words = {w.strip().lower() for w in f if w.strip()}
    except Exception as e:
        print("[warn] no profanity list:", e)
    words |= {"sex", "porn", "nazi", "rape", "suicide", "drug", "cocaine", "heroin",
              "nigger", "slut", "whore", "penis", "vagina", "anus", "dick", "cock", "pussy"}
    return words


def is_lemma(w):
    """w is a base form of itself for some part of speech."""
    return any(w in (l.name().lower() for l in s.lemmas()) for s in wn.synsets(w))


def secret_noun_ok(w, vocab_set):
    """Common singular noun suitable as a secret word."""
    syns = wn.synsets(w)
    nouns = [s for s in syns if s.pos() == "n"]
    if not nouns or wn.morphy(w, wn.NOUN) != w:
        return False
    if all(s.instance_hypernyms() for s in nouns):  # proper names only (paris...)
        return False
    if len(nouns) > 12:                           # too ambiguous ("set", "run")
        return False
    if not re.search(r"[aeiouy]", w):             # abbreviations (cps, ptx)
        return False
    if w.endswith("s") and (w[:-1] in vocab_set or w[:-2] in vocab_set):
        return False                              # plural-only entries (tears, brakes)
    if w.endswith("ing") and wn.morphy(w, wn.VERB):
        return False                              # gerunds (beating, shining)
    noun_n = other_n = 0
    for s in syns:
        for lem in s.lemmas():
            if lem.name().lower() != w:
                continue
            if lem.name()[0].isupper():           # also a proper noun (John, Czech)
                return False
            if s.pos() == "n":
                noun_n += lem.count()
            else:
                other_n += lem.count()
    return noun_n >= 1 and noun_n >= 2 * other_n  # noun is the dominant use (SemCor)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets")
    ap.add_argument("--vocab-size", type=int, default=30000)
    ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()

    bad = profanity_set()
    vocab, aliases, seen = [], {}, set()
    for w in top_n_list("en", 120000):
        if not WORD_RE.match(w) or w in bad or w in seen:
            continue
        seen.add(w)
        if is_lemma(w):
            if len(vocab) < args.vocab_size:
                vocab.append(w)
        else:
            lemma = wn.morphy(w)
            if lemma and lemma != w:
                aliases[w] = lemma
    vocab_set = set(vocab)
    aliases = {k: v for k, v in aliases.items() if v in vocab_set}
    print(f"[vocab] {len(vocab)} words, {len(aliases)} aliases ({time.time() - t0:.0f}s)")

    pools = {k: [] for k in TIERS}
    categories = {}
    for w in vocab:
        if len(w) > 12 or w in SECRET_BLOCK or not secret_noun_ok(w, vocab_set):
            continue
        z = zipf_frequency(w, "en")
        for tier, (lo, hi) in TIERS.items():
            if lo <= z < hi:
                pools[tier].append(w)
                lex = next(s for s in wn.synsets(w) if s.pos() == "n").lexname()
                categories[w] = CATEGORIES.get(lex, "THINGS")
                break
    print("[pools]", {k: len(v) for k, v in pools.items()})

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(args.model, device="cpu")
    emb = model.encode(vocab, batch_size=512, normalize_embeddings=True,
                       show_progress_bar=False, convert_to_numpy=True)
    np.save(os.path.join(args.out, "embeddings.npy"), emb.astype(np.float16))
    print(f"[embeddings] {emb.shape} ({time.time() - t0:.0f}s)")

    with open(os.path.join(args.out, "vocab.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(vocab) + "\n")
    with open(os.path.join(args.out, "english_nouns.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(w for t in TIERS for w in pools[t]) + "\n")
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({
            "model": args.model,
            "sources": ["wordfreq (MIT / CC BY-SA 4.0)", "WordNet 3.0",
                        "better_profanity (MIT)", args.model + " (Apache 2.0)"],
            "pools": pools, "aliases": aliases, "categories": categories,
        }, f)

    # semantic sanity check (ordering, not exact ranks)
    idx = {w: i for i, w in enumerate(vocab)}
    e = emb.astype(np.float32)
    for secret, near, far in [("ocean", ["sea", "water", "wave"], ["computer", "banana"]),
                              ("dog", ["puppy", "cat"], ["volcano", "invoice"])]:
        if secret not in idx:
            continue
        sims = e @ e[idx[secret]]
        rank = np.empty(len(vocab), dtype=np.int32)
        rank[np.argsort(-sims)] = np.arange(1, len(vocab) + 1)
        r = {w: int(rank[idx[w]]) for w in near + far if w in idx}
        ok = max(r.get(w, 0) for w in near) < min(r.get(w, 10**9) for w in far)
        print(f"[check] {secret}: {r} -> {'OK' if ok else 'WARN'}")
    print(f"[done] {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
