"""Run inside the game image: the Lambda's ranking must equal the game's own (SemanticIndex.ranking).
docker run --rm -w /app -v .../ranker:/app/ranker -e RANKER_ASSETS=/app/assets --entrypoint python \
    ghcr.io/alex-mtl/election-game:latest -m unittest ranker.test_ranker"""

import base64
import gzip
import json
import unittest

import numpy as np

from app.games.guess.semantic import SemanticIndex
from ranker import handler


class RankerTest(unittest.TestCase):
    def call(self, body):
        r = handler.lambda_handler({"headers": {"Authorization": "Bearer x"}, "body": json.dumps(body)}, None)
        return r["statusCode"], json.loads(r["body"])

    def setUp(self):
        import hashlib
        handler._keys.add(hashlib.sha256(b"x").hexdigest())

    def test_same_as_game(self):
        for name, lang, words in [("ru", "ru", ["огурец", "кошка"]), ("ru-easy", "ru", None),
                                  ("en", "en", ["ocean"]), ("en-easy", "en", None),
                                  ("fr", "fr", None), ("es", "es", None)]:
            sem = SemanticIndex("/app/assets/" + name, lang)
            for w in words or [sem.words[123], sem.words[-5]]:
                code, r = self.call({"dict": name, "word": w})
                self.assertEqual(code, 200, (name, w, r))
                rank = np.frombuffer(gzip.decompress(base64.b64decode(r["rank"])), dtype="<u2")
                expect, _ = sem.ranking(w)
                self.assertEqual(r["size"], sem.size)
                self.assertTrue(np.array_equal(rank.astype(np.int32), expect), (name, w))
                print(name, w, "packed", len(r["rank"]) // 1024, "KB")

    def test_errors(self):
        self.assertEqual(self.call({"dict": "ru", "word": "абырвалг"})[0], 404)
        self.assertEqual(self.call({"dict": "../x", "word": "a"})[0], 404)
        r = handler.lambda_handler({"headers": {}, "body": "{}"}, None)
        self.assertEqual(r["statusCode"], 401)


if __name__ == "__main__":
    unittest.main()
