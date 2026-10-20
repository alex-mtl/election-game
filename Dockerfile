# ---- stage 1: word lists + embeddings for "Guess the Word" (heavy, cached) ----
FROM python:3.12-slim AS assets

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 \
    NLTK_DATA=/usr/share/nltk_data HF_HOME=/tmp/hf

RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install sentence-transformers wordfreq nltk better-profanity \
 && python -m nltk.downloader -q -d /usr/share/nltk_data wordnet omw-1.4
RUN pip install pymorphy3 pymorphy3-dicts-ru
# French / Spanish: part of speech + lemmas (spaCy), multilingual Wordnet, stopwords
RUN pip install spacy  && python -m spacy download fr_core_news_sm && python -m spacy download es_core_news_sm  && python -m nltk.downloader -q -d /usr/share/nltk_data omw-2.0 stopwords

WORKDIR /build
COPY tools/build_assets.py tools/lang_ru.py ./
# "easy" level = the original dictionary (any part of speech); "normal" = nouns only, bigger
RUN python build_assets.py --lang en --level easy --out /assets/en-easy
RUN python build_assets.py --lang ru --level easy --out /assets/ru-easy
RUN python build_assets.py --lang en --level normal --out /assets/en
RUN python build_assets.py --lang ru --level normal --out /assets/ru
# French / Spanish come last: changes in lang_romance.py don't rebuild the dictionaries above
COPY tools/lang_romance.py ./
RUN python build_assets.py --lang fr --level normal --out /assets/fr
RUN python build_assets.py --lang es --level normal --out /assets/es
# the game itself needs no embeddings (the word-ranker Lambdas rank the words): word lists + metadata only.
# The full /assets (with embeddings) is for the Lambdas and the tests: docker build --target assets
RUN for d in /assets/*; do mkdir -p /assets-game/$(basename $d)  && cp $d/vocab.txt $d/meta.json $d/secret_nouns.txt /assets-game/$(basename $d)/; done

# ---- stage 2: runtime (small: no torch, no model) ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ASSETS_DIR=/app/assets

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --from=assets /assets-game /app/assets
COPY app /app/app

EXPOSE 8765

CMD ["python", "-m", "app"]
