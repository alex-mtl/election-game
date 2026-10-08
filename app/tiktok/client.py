"""TikTok LIVE connection. No game logic here: it turns TikTok events into
Viewer + text/gift/join/follow calls on the hub, and keeps the connection alive."""

import asyncio
import time
from collections import deque

from .. import config
from ..games.base import Viewer


def viewer_of(user):
    uid = str(getattr(user, "unique_id", None) or getattr(user, "nickname", None) or "anon")
    name = (getattr(user, "nickname", None) or uid)[:40]
    avatar = ""
    try:
        urls = user.avatar_thumb.url_list or []
        avatar = next((u for u in urls if u.startswith("https://")), "")
    except Exception:
        pass
    return Viewer(uid, name, avatar)


class TikTokConnector:
    def __init__(self, hub, username):
        self.hub = hub
        self.username = username
        self.seen = deque(maxlen=5000)            # msg ids: drop duplicates
        self.seen_set = set()
        # Chat history TikTok replays on (re)connect: anything sent before the app started is
        # old; after a reconnect, messages sent during the gap are kept (already-seen ones are
        # dropped by msg id), so nothing typed during a short disconnect is lost.
        self.cutoff = time.time() - 3

    def _fresh(self, event):
        """False for chat history from before the app started and for duplicate messages."""
        common = getattr(event, "common", None)
        ct = getattr(common, "create_time", 0) or 0
        if ct > 1e12:
            ct /= 1000
        if ct and ct < self.cutoff:
            if config.LOG_CHAT:
                print(f"[chat] skipped old message ({type(event).__name__})")
            return False
        mid = getattr(common, "msg_id", 0)
        if mid:
            if mid in self.seen_set:
                if config.LOG_CHAT:
                    print(f"[chat] skipped duplicate ({type(event).__name__})")
                return False
            if len(self.seen) == self.seen.maxlen:
                self.seen_set.discard(self.seen[0])
            self.seen.append(mid)
            self.seen_set.add(mid)
        return True

    async def run_forever(self):
        from TikTokLive.client.errors import UserOfflineError
        while True:
            was_live = False
            try:
                await self._run_once()
                print("[tiktok] disconnected")
                was_live = True
            except UserOfflineError:
                print(f"[tiktok] @{self.username} is not live yet, retry in {config.RECONNECT_SEC:.0f}s")
            except Exception as e:
                print(f"[tiktok] error: {type(e).__name__}: {e}")
                was_live = self.hub.tiktok_status == "connected"
            self.hub.tiktok_status = "offline"
            await asyncio.sleep(2 if was_live else config.RECONNECT_SEC)   # dropped mid-stream: come back fast

    async def _run_once(self):
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import (CommentEvent, ConnectEvent, FollowEvent, GiftEvent,
                                       JoinEvent)

        client = TikTokLiveClient(unique_id=self.username)
        hub = self.hub

        def safe(fn):
            async def handler(event):
                try:
                    if self._fresh(event):
                        fn(event)
                except Exception as e:            # never kill the listener on a bad event
                    print(f"[tiktok] handler error ({fn.__name__}): {type(e).__name__}: {e}")
            return handler

        @client.on(ConnectEvent)
        async def on_connect(event):
            hub.tiktok_status = "connected"
            print(f"[tiktok] connected to @{self.username} LIVE")
            hub.new_live(str(getattr(client, "room_id", None) or ""))

        def comment(event):
            v, text = viewer_of(event.user), (getattr(event, "comment", "") or "")[:200]
            if config.LOG_CHAT:
                print(f"[chat] {v.name} (@{v.id}): {text!r}")
            hub.comment(v, text)

        def join(event):
            hub.join(viewer_of(event.user))

        def gift(event):
            if event.streaking:                   # wait for the end of a combo
                return
            name = getattr(event.gift, "name", "") or "Gift"
            hub.gift(viewer_of(event.user), name, int(getattr(event, "repeat_count", 1) or 1))

        def follow(event):
            hub.follow(viewer_of(event.user))

        client.on(CommentEvent)(safe(comment))
        client.on(JoinEvent)(safe(join))
        client.on(GiftEvent)(safe(gift))
        client.on(FollowEvent)(safe(follow))

        # TikTok often blocks the profile-HTML lookup the library uses by default
        # ("you might be blocked") and then reports the user offline; the API lookup works.
        rid = None
        try:
            rid = await client.web.fetch_room_id_from_api(self.username)
        except Exception as e:
            print(f"[tiktok] room id via API failed ({type(e).__name__}), trying HTML")
        print(f"[tiktok] connecting to @{self.username} (room {rid or '?'}) ...")
        await client.connect(room_id=rid)
