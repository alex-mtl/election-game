"""Fetches the next round's ranking table from the word-ranker Lambdas (one per language) during the break,
so the round starts with a ready table. If it doesn't arrive in time, the game computes it itself.

RANKER_URLS in .env: "en=https://...,ru=https://..." (empty = off); the key is the game key (TG_GAME_KEY)."""

import asyncio
import base64
import gzip
import time

import numpy as np

RETRY_SEC = 15


class RankerClient:
    def __init__(self, hub, urls, key):
        self.hub, self.urls, self.key = hub, urls, key
        self.failed = {}                  # (dict, word) -> time of the last failure

    async def fetch(self, key, word, vocab_hash):
        import httpx
        url = self.urls.get(key.split("-")[0])
        if not url:
            return None
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(url, json={"dict": key, "word": word},
                                 headers={"authorization": "Bearer " + self.key})
            if r.status_code != 200:
                print(f"[ranker] {key}: HTTP {r.status_code}")
                return None
            d = r.json()
            if d.get("vocab") != vocab_hash:             # the Lambda's dictionary differs from ours
                print(f"[ranker] {key}: dictionary differs from the game's ({d.get('vocab')} != {vocab_hash})")
                return None
            return np.frombuffer(gzip.decompress(base64.b64decode(d["rank"])), dtype="<u2")
        except Exception as e:
            print(f"[ranker] {key}: {type(e).__name__}")
            return None

    async def run(self):
        while True:
            g = self.hub.games.get("guess")
            plan = g.planned_next() if g and not self.hub.closed else None
            if plan:
                key, word, vocab_hash = plan
                if (key, word) not in g.ranks and time.time() - self.failed.get((key, word), 0) > RETRY_SEC:
                    t = time.time()
                    rank = await self.fetch(key, word, vocab_hash)
                    if rank is not None:
                        g.put_ranking(key, word, rank)
                        print(f"[ranker] next round's table ready ({key}, {time.time() - t:.1f}s)")
                    else:
                        self.failed[(key, word)] = time.time()
            await asyncio.sleep(2)
