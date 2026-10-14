"""Russian word assets: vocabulary of lemmas (pymorphy3), inflection aliases,
secret-word pools of common singular nouns. Used by build_assets.py --lang ru."""

import re

RU_WORD_RE = re.compile(r"^[а-я]{3,15}$")
RU_PROPER = {"Name", "Surn", "Patr", "Geox", "Orgn", "Trad", "Abbr", "Init"}
# roots of Russian profanity: such words are neither guessable nor secret
RU_BAD_ROOTS = ("хуй", "хуе", "хуя", "пизд", "ебл", "ебат", "ебан", "ебу", "бля", "сука", "суки",
                "мудак", "мудил", "жоп", "говн", "дерьм", "срать", "сран", "шлюх", "пидор", "пидар",
                "гандон", "залуп", "манда", "дроч", "ублюд", "трах", "секс", "порн")
# fine to guess, but never chosen as the secret word on a family-friendly stream
RU_SECRET_BLOCK = {
    "аборт", "терроризм", "террорист", "самоубийство", "суицид", "убийство", "убийца", "геноцид",
    "холокост", "рабство", "раб", "расизм", "рак", "опухоль", "болезнь", "смерть", "труп", "похороны",
    "оружие", "пистолет", "винтовка", "бомба", "пуля", "наркотик", "алкоголь", "сигарета",
    "проститутка", "религия", "церковь", "мечеть", "заложник", "насилие", "пытка", "жертва",
    "зависимость", "наркоман", "тюрьма", "заключенный", "развод", "девственница", "моча", "туалет",
    "беременность", "презерватив", "грудь", "война", "фашизм", "нацизм", "казнь", "расстрел",
    "сволочь", "мосгорсуд", "хаус", "реал", "дума", "киллер", "поп", "мент", "бомж",
}
RU_TIERS = {"easy": (4.3, 9.0), "medium": (3.8, 4.3), "hard": (3.3, 3.8)}


def norm(w):
    return w.replace("ё", "е")


def bad(w):
    return any(r in w for r in RU_BAD_ROOTS)


def build_ru(vocab_size):
    import pymorphy3
    from wordfreq import top_n_list, zipf_frequency
    morph = pymorphy3.MorphAnalyzer()
    vocab, aliases, seen = [], {}, set()
    for raw in top_n_list("ru", 400000):
        w = norm(raw)
        if not RU_WORD_RE.match(w) or w in seen or bad(w):
            continue
        seen.add(w)
        p = morph.parse(w)[0]
        if RU_PROPER & set(p.tag.grammemes):
            continue
        lemma = norm(p.normal_form)
        if lemma == w:
            if len(vocab) < vocab_size:
                vocab.append(w)
        elif RU_WORD_RE.match(lemma):
            aliases[w] = lemma                    # кошки -> кошка
    vocab_set = set(vocab)
    aliases = {k: v for k, v in aliases.items() if v in vocab_set}
    print(f"[vocab ru] {len(vocab)} words, {len(aliases)} aliases")
    return (vocab, aliases) + ru_pools(vocab, morph)


# words of 2 letters are mostly junk (notes, letters, units); these are real nouns
RU_SHORT = {"ад", "ас", "еж", "ил", "ум", "уж", "ус", "щи", "юг", "яд", "як"}
RU_NOUN_RE = re.compile(r"^[а-я]{3,20}$")


def common_noun(morph, w):
    """First parse of w that is a common noun (кит, роза, лев are also names: still nouns)."""
    for p in morph.parse(w):
        if p.tag.POS == "NOUN" and not RU_PROPER & set(p.tag.grammemes):
            return p
    return None


def build_ru_normal(vocab_size):
    """'Normal' level: nouns only, as many as the frequency list has (rare animals, plants,
    tools, science terms included), so more of what viewers type gets a rank."""
    import pymorphy3
    from wordfreq import top_n_list
    morph = pymorphy3.MorphAnalyzer()
    ok = lambda w: (RU_NOUN_RE.match(w) or w in RU_SHORT) and not bad(w)
    vocab, aliases, seen = [], {}, set()
    for raw in top_n_list("ru", 2_000_000, wordlist="large"):
        w = norm(raw)
        if not re.match(r"^[а-я]{2,20}$", w):
            continue
        p = common_noun(morph, w)
        if p is None:
            continue
        lemma = norm(p.normal_form)
        if not ok(lemma) or not morph.word_is_known(lemma) or common_noun(morph, lemma) is None:
            continue
        if lemma not in seen:
            seen.add(lemma)
            if len(vocab) < vocab_size:
                vocab.append(lemma)
        if w != lemma:
            aliases.setdefault(w, lemma)              # кошки -> кошка, бобр -> бобер
    vocab_set = set(vocab)
    aliases = {k: v for k, v in aliases.items() if v in vocab_set and k not in vocab_set}
    print(f"[vocab ru normal] {len(vocab)} nouns, {len(aliases)} aliases")
    return (vocab, aliases) + ru_pools(vocab, morph)


def ru_pools(vocab, morph):
    from wordfreq import zipf_frequency
    pools = {k: [] for k in RU_TIERS}
    for w in vocab:
        if len(w) > 12 or w in RU_SECRET_BLOCK:
            continue
        parses = morph.parse(w)
        p = parses[0]
        if p.tag.POS != "NOUN" or p.score < 0.6 or "sing" not in p.tag or "nomn" not in p.tag:
            continue                              # common singular nouns only
        if any(RU_PROPER & set(q.tag.grammemes) for q in parses[:3]):
            continue
        z = zipf_frequency(w, "ru")
        for tier, (lo, hi) in RU_TIERS.items():
            if lo <= z < hi:
                pools[tier].append(w)
                break
    print("[pools ru]", {k: len(v) for k, v in pools.items()})
    checks = [("океан", ["море", "вода", "волна"], ["компьютер", "банан"]),
              ("собака", ["щенок", "кошка"], ["вулкан", "налог"]),
              ("машина", ["автомобиль", "колесо"], ["облако", "любовь"])]
    sources = ["wordfreq (MIT / CC BY-SA 4.0)", "pymorphy3 + OpenCorpora dictionaries (MIT / CC BY-SA)"]
    return pools, {}, sources, checks
