#!/bin/sh
# Build build/word-ranker-<lang>.zip: handler + numpy (Linux wheel) + that language's dictionaries,
# taken from the game image (ghcr.io/alex-mtl/election-game:latest, built by `docker compose build`).
cd "$(dirname "$0")" && rm -rf build && mkdir -p build
id=$(docker create ghcr.io/alex-mtl/election-game:latest) && docker cp "$id:/app/assets" build/assets >/dev/null && docker rm "$id" >/dev/null
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W)":/w -w /w python:3.12-slim sh -c '
pip install -q --no-cache-dir --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12 numpy -t build/numpy-pkg 2>&1 | grep -v "^\[notice\]"
python - <<PY
import glob, os, zipfile
for lang in ("en", "ru", "fr", "es"):
    out = f"build/word-ranker-{lang}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write("handler.py", "handler.py")
        for f in glob.glob("build/numpy-pkg/**", recursive=True):
            if os.path.isfile(f) and "__pycache__" not in f:
                z.write(f, os.path.relpath(f, "build/numpy-pkg"))
        for d in (lang, lang + "-easy"):
            for name in ("vocab.txt", "embeddings.npy"):
                p = f"build/assets/{d}/{name}"
                if os.path.exists(p):
                    z.write(p, f"assets/{d}/{name}")
    print(out, round(os.path.getsize(out) / 2**20, 1), "MB")
PY'
