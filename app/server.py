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

import hashlib
import os

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config
from .games.base import Viewer

WEB = os.path.join(os.path.dirname(__file__), "web")


def web_version():
    """Hash of all page files: open overlays reload themselves when it changes."""
    h = hashlib.sha1()
    for root, _, files in sorted(os.walk(WEB)):
        for f in sorted(files):
            with open(os.path.join(root, f), "rb") as fh:
                h.update(f.encode() + fh.read())
    return h.hexdigest()[:12]



def tt_bat(port):
    """Windows launcher: Chrome as a bare 9:16 app window with sound allowed, on the TT mode page."""
    chrome = "\\Google\\Chrome\\Application\\chrome.exe"
    return "\r\n".join([
        "@echo off",
        "rem Live Games - TT mode: a Chrome window without tabs/toolbars, 9:16, sound without a click",
        f"set URL=http://localhost:{port}/guess/?tt=1",
        f"set CH=%ProgramFiles%{chrome}",
        f'if not exist "%CH%" set CH=%ProgramFiles(x86)%{chrome}',
        f'if not exist "%CH%" set CH=%LocalAppData%{chrome}',
        'start "" "%CH%" --app=%URL% --window-size=540,960 --autoplay-policy=no-user-gesture-required'
        ' --user-data-dir="%LocalAppData%\\LiveGamesTT"',
        "",
    ])

def create_app(hub):
    app = FastAPI(title="TikTok LIVE games", docs_url=None, redoc_url=None)
    hub.web_version = web_version()

    @app.middleware("http")
    async def no_cache(request, call_next):
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-cache"   # always revalidate -> never a stale overlay
        return resp

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
        return {"active": hub.active, "games": hub.menu(), "lang": hub.lang,
                "languages": config.LANGUAGES, "options": hub.options(),
                "global": {"options": hub.global_settings.schema(), "values": hub.global_settings.values()}}

    @app.post("/api/settings")
    async def settings(req: Request):
        body = await req.json()
        if body.get("game") in hub.games or body.get("game") == "global":
            hub.set_options(body["game"], body.get("options") or {})
        if "lang" in body:
            if body["lang"] not in config.LANGUAGES:
                raise HTTPException(400, "unknown language")
            hub.set_lang(body["lang"])
        return {"lang": hub.lang, "options": hub.options()}

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
    def api_state(game: str | None = None, since: int | None = None, fsince: int | None = None):
        name = game if game in hub.games else hub.active
        return hub.message(name, since, fsince)

    @app.post("/api/client-log")
    async def client_log(req: Request):
        """Pages report what happens in the browser (alerts on/off, speech errors)."""
        try:
            d = await req.json()
            print(f"[client] {str(d.get('page'))[:20]}: {str(d.get('msg'))[:2000]}")
        except Exception:
            pass
        return {"ok": True}

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
        params = params if isinstance(params, dict) else {}
        name = (params.get("name") or "Tester")[:30]
        if action == "chat":                         # as if it came from TikTok: feed + active game
            hub.comment(Viewer(name.lower(), name, ""), params.get("text") or params.get("word") or "hello!")
            return {"ok": True}
        if action == "like":
            hub.like(Viewer(name.lower(), name, ""), int(params.get("n") or 10))
            return {"ok": True}
        if action == "balloon":
            hub.like(Viewer(name.lower(), name, ""), config.LIKES_PER_BALLOON)
            return {"ok": True}
        if action == "join":
            hub.join(Viewer(name.lower(), name, ""))
            return {"ok": True}
        if action == "gift":
            hub.gift(Viewer(name.lower(), name, ""), params.get("gift") or "Rose", 1)
            return {"ok": True}
        return JSONResponse(hub.game.debug(action, params))

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

    @app.post("/api/tg/host-link")
    async def tg_host_link():
        """One-time link that makes whoever opens it in the messenger the host of this game (menu only)."""
        if not hub.tg:
            raise HTTPException(404, "bot not configured")
        r = await hub.tg.api("/game/host_code")
        if not r.get("link"):
            raise HTTPException(502, "bot unavailable")
        return r

    @app.get("/api/tt.bat")
    def tt_launcher(req: Request):
        return Response(tt_bat(req.url.port or 8765), media_type="application/octet-stream",
                        headers={"Content-Disposition": 'attachment; filename="LiveGames-TT.bat"'})

    @app.get("/{game}")
    def game_no_slash(game: str):
        return RedirectResponse(f"/{game}/")

    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app
