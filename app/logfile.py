"""Everything the game prints also goes to DATA_DIR/logs/YYYY-MM-DD.log (one file per day), so the log
survives container rebuilds (DATA_DIR is the mounted ./data folder in docker-compose)."""

import os
import sys
import threading
import time


class DailyTee:
    def __init__(self, stream, folder):
        self.stream, self.folder = stream, folder
        self.day, self.file = None, None
        self.lock = threading.Lock()
        os.makedirs(folder, exist_ok=True)

    def _target(self):
        day = time.strftime("%Y-%m-%d")
        if day != self.day:
            if self.file:
                self.file.close()
            self.day = day
            self.file = open(os.path.join(self.folder, day + ".log"), "a", encoding="utf-8", buffering=1)
        return self.file

    def write(self, text):
        self.stream.write(text)
        try:
            with self.lock:
                f = self._target()
                if text.strip():
                    stamp = time.strftime("%H:%M:%S ")
                    text = "".join(stamp + line if line.strip() else line for line in text.splitlines(True))
                f.write(text)
        except Exception:
            pass
        return len(text)

    def flush(self):
        self.stream.flush()
        try:
            if self.file:
                self.file.flush()
        except Exception:
            pass

    def __getattr__(self, name):              # isatty, fileno, encoding... from the real stream
        return getattr(self.stream, name)


def install(data_dir):
    folder = os.path.join(data_dir, "logs")
    sys.stdout = DailyTee(sys.stdout, folder)
    sys.stderr = DailyTee(sys.stderr, folder)
