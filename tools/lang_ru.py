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
    return vocab, aliases, pools, {}, sources, checks
