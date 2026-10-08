"""JSON file storage. Gameplay code only uses load()/save(), so it can be swapped
for SQLite/PostgreSQL later without touching the games."""

import json
import os


class JsonStore:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)
        self._last = {}

    def path(self, name):
        return os.path.join(self.root, name)

    def load(self, name, default=None):
        try:
            with open(self.path(name), encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default
        except Exception as e:
            print(f"[store] can't read {name}: {e}")
            return default

    def save(self, name, data):
        """Atomic write; skipped when nothing changed since the last save."""
        text = json.dumps(data, ensure_ascii=False)
        if self._last.get(name) == text:
            return
        p = self.path(name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(p + ".tmp", p)
        self._last[name] = text
