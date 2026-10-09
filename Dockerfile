# ---- stage 1: word lists + embeddings for "Guess the Word" (heavy, cached) ----
FROM python:3.12-slim AS assets

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 \
    NLTK_DATA=/usr/share/nltk_data HF_HOME=/tmp/hf

RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install sentence-transformers wordfreq nltk better-profanity \
 && python -m nltk.downloader -q -d /usr/share/nltk_data wordnet omw-1.4
RUN pip install pymorphy3 pymorphy3-dicts-ru

WORKDIR /build
COPY tools/build_assets.py tools/lang_ru.py ./
RUN python build_assets.py --lang en --out /assets/en
RUN python build_assets.py --lang ru --out /assets/ru

# ---- stage 2: runtime (small: no torch, no model) ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ASSETS_DIR=/app/assets

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --from=assets /assets /app/assets
COPY app /app/app

EXPOSE 8765

CMD ["python", "-m", "app"]
