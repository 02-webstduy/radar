"""管线：并行采集 → 去重 → 关键词筛选 → 打分排序 → top N。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlsplit

from .config import Config, load
from .models import Item
from .sources import arxiv, github, hn, rss

logger = logging.getLogger("radar")
_SKIP_QUERY = {"utm_source", "utm_medium", "utm_campaign", "ref", "spm"}


def _canonical(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path.rstrip("/")
    query = sorted(
        (k, v) for k, v in parse_qsl(parts.query) if k not in _SKIP_QUERY
    )
    return f"{host}{path}?{query}" if query else f"{host}{path}"


def dedupe(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    out: list[Item] = []
    for it in items:
        key = _canonical(it.url) or it.title.strip().lower()
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
    return out[: cfg.profile.max_items]


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
