"""Entry point: python -m app [--simulate]"""

import argparse
import sys
import os
import asyncio
import signal

import uvicorn

from . import config
from .hub import Hub
from .server import create_app
from .storage import JsonStore
from .tiktok.client import TikTokConnector


async def run(simulate):
    hub = Hub(JsonStore(config.DATA_DIR))
    server = uvicorn.Server(uvicorn.Config(create_app(hub), host=config.HOST, port=config.PORT,
                                           log_level="warning", ws_ping_interval=20))
    tasks = [hub.ticker(), hub.saver(), hub.broadcaster()]
    if simulate or config.TIKTOK_USERNAME == "CHANGE_ME":
        if not simulate:
            print("[warn] set TIKTOK_USERNAME in .env; running the simulator meanwhile")
        tasks.append(hub.simulator())
    else:
        tasks.append(TikTokConnector(hub, config.TIKTOK_USERNAME).run_forever())
    print(f"[web] open http://localhost:{config.PORT}/ (phone: http://<this-PC-IP>:{config.PORT}/)")

    bg = [asyncio.create_task(t) for t in tasks]
    try:
        await server.serve()                       # returns on SIGTERM / Ctrl+C
    finally:
        # first stop taking events (a TikTok connection may still deliver chat for a few seconds while
        # the process dies: a win then would be lost - it happened once), then the final save
        hub.closed = True
        for t in bg:
            t.cancel()
        for g in hub.games.values():               # final save
            g.save()
        hub.save_session()
        hub.balloons.save()
        print("stopped, state saved.")
        sys.stdout.flush()
        os._exit(0)                                # right away: the TikTok client can keep the loop alive


def main():
    from .logfile import install
    install(config.DATA_DIR)                     # the log also goes to data/logs/YYYY-MM-DD.log
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true", help="fake viewers instead of TikTok")
    args = ap.parse_args()
    asyncio.run(run(args.simulate or config.SIMULATE))
    sys.stdout.flush()
    os._exit(0)                                  # no lingering threads (TikTok client) after the save


if __name__ == "__main__":
    main()
