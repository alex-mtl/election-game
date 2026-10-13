"""Streamer overlay: a transparent page on top of the streamer's video with reactions.

Like balloons are shared by all pages and live in the hub (app/reactions/balloons.py);
this "game" only gives the overlay its own place in the menu.
"""

import random

from ..base import BaseGame


class StreamerOverlay(BaseGame):
    name = "streamer"
    title = "Streamer"

    def snapshot(self):
        return {}

    def simulate_step(self):
        return random.uniform(0.3, 0.8)      # the hub simulator sends the fake likes
