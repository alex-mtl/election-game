"""French and Spanish word assets ("normal" level, like Russian): common nouns only, base forms,
plural/feminine/unaccented forms as aliases, no names, no profanity, 2-20 letters.
Used by build_assets.py --lang fr|es.

Sources: wordfreq (frequencies), spaCy fr/es small models (part of speech + lemma of each form),
Open Multilingual Wordnet via NLTK (the lemma must be a common noun there; its English links give
"concrete thing" classes: animals, plants, tools...), NLTK stopwords."""

import re
import unicodedata

LETTERS = {"fr": "a-zàâæçéèêëîïôœùûüÿ", "es": "a-záéíóúüñ"}
OMW = {"fr": "fra", "es": "spa"}
SPACY = {"fr": "fr_core_news_sm", "es": "es_core_news_sm"}
STOPLANG = {"fr": "french", "es": "spanish"}
# 2-letter nouns are mostly junk; these are real
SHORT = {"fr": {"os", "if", "ré"}, "es": {"té", "fe"}}
# interjections / fixed phrases spaCy tags as nouns
EXTRA_STOP = {
    "fr": {"oui", "non", "merci", "salut", "bonjour", "bonsoir", "ok", "okay", "ouais", "mdr", "lol", "svp", "stp"},
    "es": {"sí", "no", "gracias", "hola", "embargo", "través", "vale", "ok", "okay", "jaja", "jajaja", "porfa", "vez"},
}
# infinitives with a verb sense are verbs here (être, pouvoir, haber, poder...) unless they are things
INFINITIVE = {"fr": re.compile(r"(er|ir|re|oir)$"), "es": re.compile(r"(ar|er|ir)$")}
# roots of profanity: neither guessable nor secret
BAD_ROOTS = {
    "fr": ("merde", "putain", "pute", "connard", "connasse", "salope", "enculé", "encule", "nique", "bite", "couille",
           "chatte", "foutre", "branl", "pédé", "pede", "nègre", "negre", "bordel", "baise", "cul", "sexe", "porno"),
    "es": ("mierda", "puta", "puto", "joder", "coño", "cabrón", "cabron", "pendej", "verga", "polla", "culo", "chinga",
           "maric", "zorra", "mamón", "mamon", "follar", "coger", "sexo", "porno", "pinche", "gilipollas"),
}
# fine to guess, never the secret word on a family-friendly stream
SECRET_BLOCK = {
    "fr": {"avortement", "terrorisme", "terroriste", "suicide", "meurtre", "meurtrier", "génocide", "esclavage",
           "esclave", "racisme", "cancer", "tumeur", "maladie", "mort", "cadavre", "funérailles", "arme", "pistolet",
           "fusil", "bombe", "balle", "drogue", "alcool", "cigarette", "prostituée", "religion", "église", "mosquée",
           "otage", "violence", "torture", "victime", "prison", "divorce", "toilettes", "urine", "grossesse",
           "préservatif", "sein", "guerre", "nazisme", "fascisme", "exécution"},
    "es": {"aborto", "terrorismo", "terrorista", "suicidio", "asesinato", "asesino", "genocidio", "esclavitud",
           "esclavo", "racismo", "cáncer", "tumor", "enfermedad", "muerte", "cadáver", "funeral", "arma", "pistola",
           "rifle", "bomba", "bala", "droga", "alcohol", "cigarrillo", "prostituta", "religión", "iglesia",
           "mezquita", "rehén", "violencia", "tortura", "víctima", "cárcel", "prisión", "divorcio", "inodoro",
           "orina", "embarazo", "condón", "pecho", "guerra", "nazismo", "fascismo", "ejecución"},
}
CONCRETE = {"noun.artifact", "noun.animal", "noun.plant", "noun.food", "noun.body", "noun.object", "noun.substance"}
TIERS = {"easy": (4.3, 9.0), "medium": (3.8, 4.3), "hard": (3.3, 3.8)}
CHECKS = {
    "fr": [("océan", ["mer", "eau", "vague"], ["ordinateur", "banane"]),
           ("chien", ["chiot", "chat"], ["volcan", "facture"])],
    "es": [("océano", ["mar", "agua", "ola"], ["computadora", "plátano"]),
           ("perro", ["cachorro", "gato"], ["volcán", "factura"])],
}


def deaccent(w):
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")


def build_romance(lang, vocab_size):
    import spacy
    from nltk.corpus import stopwords
    from nltk.corpus import wordnet as wn
    from wordfreq import top_n_list, zipf_frequency

    word_re = re.compile(rf"^[{LETTERS[lang]}]{{3,20}}$")
    ok = lambda w: (word_re.match(w) or w in SHORT[lang]) and not any(r in w for r in BAD_ROOTS[lang])
    stop = set(stopwords.words(STOPLANG[lang])) | EXTRA_STOP[lang]
    omw = OMW[lang]
    noun_cache = {}

    def noun_kind(w):
        """None (not a common noun), 'thing' (animal/plant/object...) or 'noun'."""
        if w not in noun_cache:
            ns = [s for s in wn.synsets(w, pos=wn.NOUN, lang=omw) if not s.instance_hypernyms()]
            if not ns:
                noun_cache[w] = None
            elif any(s.lexname() in CONCRETE for s in ns):
                noun_cache[w] = "thing"
            elif INFINITIVE[lang].search(w) and wn.synsets(w, pos=wn.VERB, lang=omw):
                noun_cache[w] = None                  # être, pouvoir, haber, poder
            else:
                noun_cache[w] = "noun"
        return noun_cache[w]

    nlp = spacy.load(SPACY[lang], disable=["parser", "ner"])
    # every form votes (est/sont/était make "être" a verb), stopwords are skipped only when choosing
    forms = [w for w in top_n_list(lang, 2_000_000, wordlist="large")
             if re.match(rf"^[{LETTERS[lang]}]{{2,20}}$", w)]
    tagged = []
    votes = {}                                        # lemma -> [noun forms, other forms] in the whole list
    for w, doc in zip(forms, nlp.pipe(forms, batch_size=2000)):
        if len(doc) != 1:
            continue
        t = doc[0]
        lemma = t.lemma_.lower()
        tagged.append((w, t.pos_, lemma))
        v = votes.setdefault(lemma, [0, 0])
        if t.pos_ == "NOUN":
            v[0] += 1
        elif t.pos_ in ("VERB", "AUX", "ADJ", "ADV", "PROPN", "DET", "PRON", "ADP", "NUM"):
            v[1] += 1
    # mostly a noun among its own forms (être/sommes/est..., beau/belle/beaux... are not)
    mostly_noun = lambda l: votes.get(l, [0, 0])[0] >= votes.get(l, [0, 0])[1]
    vocab, aliases, seen = [], {}, set()
    for w, pos, lemma in tagged:
        if w in stop:
            continue
        if pos == "NOUN" and ok(lemma) and lemma not in stop and noun_kind(lemma) \
                and (mostly_noun(lemma) or noun_kind(lemma) == "thing"):
            pass                                      # spaCy and Wordnet agree: a noun (lemma)
        elif pos in ("NOUN", "PROPN", "X") and ok(w) and noun_kind(w) == "thing":
            lemma = w                                 # spaCy unsure, Wordnet: an animal / tool / plant
        elif pos == "NOUN" and ok(w) and w not in stop and noun_kind(w) and mostly_noun(w):
            lemma = w                                 # lemma unknown to Wordnet, the form itself is a noun
        else:
            continue
        if lemma not in seen:
            seen.add(lemma)
            if len(vocab) < vocab_size:
                vocab.append(lemma)
        if w != lemma:
            aliases.setdefault(w, lemma)              # chiens -> chien, perros -> perro
    vocab_set = set(vocab)
    # typed without accents: "cancion" -> canción, "ecureuil" -> écureuil (if not ambiguous)
    plain = {}
    for w in list(vocab) + list(aliases):
        p = deaccent(w)
        if p != w:
            plain.setdefault(p, set()).add(aliases.get(w, w))
    for p, targets in plain.items():
        if len(targets) == 1 and p not in vocab_set:
            aliases.setdefault(p, next(iter(targets)))
    aliases = {k: v for k, v in aliases.items() if v in vocab_set and k not in vocab_set}
    print(f"[vocab {lang} normal] {len(vocab)} nouns, {len(aliases)} aliases")

    pools = {k: [] for k in TIERS}
    for w in vocab:
        if len(w) > 12 or len(w) < 3 or w in SECRET_BLOCK[lang] or noun_kind(w) is None:
            continue
        doc = nlp(w)
        if doc[0].pos_ != "NOUN":                    # secrets: clearly a noun on its own
            continue
        z = zipf_frequency(w, lang)
        for tier, (lo, hi) in TIERS.items():
            if lo <= z < hi:
                pools[tier].append(w)
                break
    print(f"[pools {lang}]", {k: len(v) for k, v in pools.items()})
    sources = ["wordfreq (MIT / CC BY-SA 4.0)", f"spaCy {SPACY[lang]} (CC BY-SA / MIT)",
               "Open Multilingual Wordnet (various open licenses)", "NLTK stopwords"]
    return vocab, aliases, pools, {}, sources, CHECKS[lang]
