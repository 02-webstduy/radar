"""管线：并行采集 → 去重 → 关键词筛选 → 打分 → 落库 + 生成当日榜单。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import Config, load
from .models import Item
from .sources import arxiv, github, hn, rss
from .storage import Store, utcnow
from .urls import canonical

logger = logging.getLogger("radar")


def dedupe(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    out: list[Item] = []
    for it in items:
        key = canonical(it.url) or it.title.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def score_and_filter(items: list[Item], cfg: Config) -> list[Item]:
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    for it in items:
        text = f"{it.title} {it.summary}".lower()
        matched = [k for k in cfg.profile.keywords if k.lower() in text]
        if not matched:
            continue
        title_hit = any(k.lower() in it.title.lower() for k in cfg.profile.keywords)
        score = cfg.weights.get(it.source, 1.0)
        score += len(matched) * 1.5 + (2.0 if title_hit else 0.0)
        if it.published:
            hours = (now - it.published).total_seconds() / 3600
            if 0 <= hours < 24:
                score += 2.0
            elif hours < 72:
                score += 1.0
        it.score = score
        it.matched = matched[:5]
        out.append(it)
    out.sort(key=lambda x: x.score, reverse=True)
    return out


def local_day(cfg: Config) -> str:
    return datetime.now(ZoneInfo(cfg.timezone)).date().isoformat()


async def collect(cfg: Config | None = None) -> list[Item]:
    cfg = cfg or load()
    names = ["github", "arxiv", "hn", "rss"]
    results = await asyncio.gather(
        github.fetch(cfg), arxiv.fetch(cfg), hn.fetch(cfg), rss.fetch(cfg),
        return_exceptions=True,
    )
    items: list[Item] = []
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            logger.warning("%s 失败：%s", name, result)
            continue
        items.extend(result)
    return score_and_filter(dedupe(items), cfg)


async def ingest(cfg: Config, store: Store) -> dict:
    """抓一次、写一次库、重排当天榜单。失败也记一条 ingest_runs。"""
    started = utcnow()
    try:
        items = await collect(cfg)
    except Exception as exc:  # noqa: BLE001 - 一次失败不能把页面打挂
        store.record_run(started, 0, 0, status="failed", error=str(exc)[:200])
        raise

    ranked: list[tuple[int, float]] = []
    for it in items:
        source_id = store.source_id(it.source, cfg.weights.get(it.source, 1.0))
        item_id = store.upsert_item(it, source_id)
        ranked.append((item_id, it.score))

    day = local_day(cfg)
    top = ranked[: cfg.profile.max_items]
    store.snapshot(day, top)
    store.record_run(started, len(items), len(top))
    return {"day": day, "fetched": len(items), "kept": len(top)}
