"""word-ranker: one AWS Lambda per language (word-ranker-en, -ru, -fr, -es) behind a Function URL.

The game sends the round's secret word; the Lambda ranks the whole dictionary by similarity to it and
returns rank[i] (1-based place of vocab word i) packed as gzip(uint16 little-endian), base64. Same math as
SemanticIndex.ranking in the game, so the game no longer needs the embeddings.

POST /  {"dict": "ru" | "ru-easy", "word": "огурец"}   Authorization: Bearer <game key>
     -> {"dict", "word", "size", "vocab": <sha1 of vocab.txt, 12 hex>, "rank": <base64>}

The package holds assets/<dict>/{vocab.txt, embeddings.npy} for its language only. A game key is valid
if the bot's table (tiktok-tg-bot) has it: GAME#<sha256 of the key>."""

import base64
import gzip
import hashlib
import json
import os

import numpy as np

ASSETS = os.getenv("RANKER_ASSETS") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TABLE = os.getenv("GAMES_TABLE", "tiktok-tg-bot")
_dicts = {}
_keys = set()                       # valid game key hashes seen in this container


def load(name):
    """vocab + normalized embeddings of one dictionary, once per container"""
    if name not in _dicts:
        path = os.path.join(ASSETS, name)
        with open(os.path.join(path, "vocab.txt"), "rb") as f:
            raw = f.read()
        words = [w.strip() for w in raw.decode("utf-8").splitlines() if w.strip()]
        emb = np.load(os.path.join(path, "embeddings.npy")).astype(np.float32)
        emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
        _dicts[name] = {"words": words, "index": {w: i for i, w in enumerate(words)}, "emb": emb,
                        "vocab": hashlib.sha1(raw).hexdigest()[:12]}
    return _dicts[name]


def ranking(d, secret):
    i = d["index"][secret]
    sims = d["emb"] @ d["emb"][i]
    order = np.argsort(-sims, kind="stable")
    if order[0] != i:                                   # the exact word is always #1
        order = np.concatenate(([i], order[order != i]))
    rank = np.empty(len(d["words"]), dtype=np.uint16)
    rank[order] = np.arange(1, len(d["words"]) + 1, dtype=np.uint16)
    return rank


def pack(rank):
    return base64.b64encode(gzip.compress(rank.astype("<u2").tobytes(), 6)).decode()


def key_ok(headers):
    auth = headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    h = hashlib.sha256(auth[7:].strip().encode()).hexdigest()
    if h not in _keys:
        import boto3
        item = boto3.client("dynamodb").get_item(TableName=TABLE, Key={"pk": {"S": "GAME#" + h}},
                                                 ProjectionExpression="pk").get("Item")
        if not item:
            return False
        _keys.add(h)
    return True


def reply(code, body):
    return {"statusCode": code, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def lambda_handler(event, context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if not key_ok(headers):
        return reply(401, {"error": "bad game key"})
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        body = json.loads(raw) if raw else {}
    except ValueError:
        return reply(400, {"error": "bad json"})
    name, word = str(body.get("dict", "")), str(body.get("word", ""))
    if not name or "/" in name or "." in name or not os.path.isdir(os.path.join(ASSETS, name)):
        return reply(404, {"error": "no such dictionary here"})
    d = load(name)
    if word not in d["index"]:
        return reply(404, {"error": "word not in the dictionary"})
    return reply(200, {"dict": name, "word": word, "size": len(d["words"]), "vocab": d["vocab"],
                       "rank": pack(ranking(d, word))})
