"""只读页面 + /api/items。"""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.responses import FileResponse

from .config import load
from .pipeline import collect

cfg = load()
app = FastAPI(title=cfg.name, docs_url=None, redoc_url=None)

_cache: dict = {"at": 0.0, "items": []}
_TTL = 300  # 秒


@app.get("/api/items")
async def items() -> dict:
    now = time.time()
    if now - _cache["at"] > _TTL:
        _cache["items"] = [i.to_dict() for i in await collect(cfg)]
        _cache["at"] = now
    return {
        "name": cfg.name,
        "role": cfg.profile.role,
        "updated": _cache["at"],
        "items": _cache["items"],
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(cfg.web_dir / "index.html", headers={"Cache-Control": "no-store"})
