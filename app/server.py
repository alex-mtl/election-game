"""HTTP + WebSocket API and static pages.

  GET  /                     game menu
  GET  /<game>/              game overlay (battle, guess, ...)
  GET  /debug/               debug controls
  GET  /state.json           active game state (polling fallback / debug)
  GET  /api/state?game=&since=
  GET  /health
  WS   /ws                   pushes {active, game, state, events}
  POST /api/active {game}    switch game
  POST /reset                new session for the active game (score to zero)
  POST /api/debug/<action>   debug controls for the active game
"""

import os

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config

WEB = os.path.join(os.path.dirname(__file__), "web")


def create_app(hub):
    app = FastAPI(title="TikTok LIVE games", docs_url=None, redoc_url=None)

    @app.get("/")
    def menu():
        return FileResponse(os.path.join(WEB, "index.html"))

    @app.get("/health")
    def health():
        return {"ok": True, "active": hub.active, "tiktok": hub.tiktok_status,
                "simulate": config.SIMULATE,
                "games": {n: {"error": getattr(g, "error", None)} for n, g in hub.games.items()}}

    @app.get("/api/games")
    def games():
        return {"active": hub.active, "games": hub.menu()}

    @app.post("/api/active")
    async def set_active(req: Request):
        name = (await req.json()).get("game")
        if name not in hub.games:
            raise HTTPException(404, "unknown game")
        hub.set_active(name)
        return {"active": hub.active}

    @app.get("/state.json")
    def state_json(since: int | None = None):
        return hub.message(hub.active, since)

    @app.get("/api/state")
    def api_state(game: str | None = None, since: int | None = None):
        name = game if game in hub.games else hub.active
        return hub.message(name, since)

    @app.post("/reset")
    def reset():
        hub.game.new_session()
        print(f"[hub] manual reset of {hub.active}")
        return {"ok": True}

    @app.post("/api/debug/{action}")
    async def debug(action: str, req: Request):
        if not config.DEBUG_CONTROLS:
            raise HTTPException(403, "debug controls disabled (DEBUG_CONTROLS=0)")
        try:
            params = await req.json()
        except Exception:
            params = {}
        return JSONResponse(hub.game.debug(action, params if isinstance(params, dict) else {}))

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        hub.clients.add(websocket)
        try:
            await websocket.send_json(hub.message(hub.active))      # snapshot, no event replay
            while True:
                await websocket.receive_text()                       # keepalive pings
        except WebSocketDisconnect:
            pass
        finally:
            hub.clients.discard(websocket)

    @app.get("/{game}")
    def game_no_slash(game: str):
        return RedirectResponse(f"/{game}/")

    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app
