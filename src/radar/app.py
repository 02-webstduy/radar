"""HTTP 层：页面、当日榜单、反馈、统计。数据从 SQLite 读。"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal

from .config import load
from .pipeline import ingest, local_day
from .storage import Store

logger = logging.getLogger("radar")
cfg = load()
store = Store(cfg.db_path)
app = FastAPI(title=cfg.name, docs_url=None, redoc_url=None)

STALE_SECONDS = 1800  # 半小时内抓过就不重复抓
_ingest_lock = asyncio.Lock()


def _epoch(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return None


def _fresh(day: str) -> bool:
    """当天有榜单，且最近一次成功抓取在半小时内。"""
    if not store.top_items(day):
        return False
    last = store.last_run()
    if not last or last["status"] != "ok":
        return False
    at = _epoch(last["finished_at"])
    return bool(at) and time.time() - at < STALE_SECONDS


async def ensure_today() -> None:
    """当天没数据、或上次抓取超过半小时，就重新抓一次。失败保留旧数据。"""
    day = local_day(cfg)
    if _fresh(day):
        return
    async with _ingest_lock:
        if _fresh(day):
            return
        try:
            await ingest(cfg, store)
        except Exception as exc:  # noqa: BLE001
            logger.warning("抓取失败，继续用旧数据：%s", exc)


@app.get("/api/items")
async def items() -> dict:
    await ensure_today()
    day = local_day(cfg)
    last = store.last_run()
    rows = store.top_items(day)
    items = [
        {
            "id": r["id"],
            "title": r["title"],
            "url": r["url"],
            "source": r["source"],
            "summary": r["summary"],
            "published": r["published_at"],
            "score": r["score"],
            "matched": r["matched"],
        }
        for r in rows
    ]
    return {
        "name": cfg.name,
        "role": cfg.profile.role,
        "day": day,
        "updated": _epoch(last["finished_at"]) if last else None,
        "items": items,
    }


class FeedbackIn(BaseModel):
    item_id: int = Field(gt=0)
    action: Literal["save", "skip", "read"]


@app.post("/api/feedback")
async def feedback(payload: FeedbackIn) -> dict:
    try:
        store.add_feedback(payload.item_id, payload.action)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="写入反馈失败") from exc
    return {"ok": True}


@app.get("/api/stats")
async def stats() -> dict:
    return {"stats": store.stats(), "last_run": store.last_run()}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(cfg.web_dir / "index.html", headers={"Cache-Control": "no-store"})
