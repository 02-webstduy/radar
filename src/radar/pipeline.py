"""管线：采集 → 去重 → 画像匹配打分 → 落库 + 当日榜单。"""

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


def _split(value: str) -> list[str]:
    return [x.strip() for x in str(value).replace("，", ",").split(",") if x.strip()]


def profile_terms(profile: dict, cfg: Config) -> list[str]:
    facts = profile.get("facts", {})
    terms: list[str] = []
    for key in ("keywords", "stack", "learning", "interests"):
        terms.extend(_split(facts.get(key, "")))
    if not terms:
        terms.extend(cfg.profile.keywords)
    out: list[str] = []
    for term in terms:
        if term.lower() not in [x.lower() for x in out]:
            out.append(term)
    return out


def _why(text: str, hits: list[str], ghits: list[str], facts: dict, fresh: bool) -> str:
    parts: list[str] = []
    learning = [x.lower() for x in _split(facts.get("learning", ""))]
    learn_hits = [x for x in learning if x and x in text]
    if learn_hits:
        parts.append("补你在学的 " + learn_hits[0])
    if hits:
        parts.append("命中关注：" + "、".join(hits[:3]))
    elif ghits:
        parts.append("关键词：" + "、".join(ghits[:3]))
    if fresh:
        parts.append("24h 内")
    return " · ".join(parts)


def rank_items(items: list[Item], cfg: Config, profile: dict) -> list[Item]:
    facts = profile.get("facts", {})
    terms = [t.lower() for t in profile_terms(profile, cfg)]
    avoid = [a.lower() for a in _split(facts.get("avoid", ""))]
    now = datetime.now(timezone.utc)
    out: list[Item] = []
    for it in items:
        text = f"{it.title} {it.summary}".lower()
        if any(a and a in text for a in avoid):
            continue
        hits = [t for t in terms if t in text]
        ghits = [k for k in cfg.profile.keywords if k.lower() in text]
        if not hits and not ghits:
            continue
        title_hit = any(t in it.title.lower() for t in terms)
        score = cfg.weights.get(it.source, 1.0)
        score += len(hits) * 1.5 + len(ghits) * 0.8 + (2.0 if title_hit else 0.0)
        fresh = False
        if it.published:
            hours = (now - it.published).total_seconds() / 3600
            if 0 <= hours < 24:
                score += 2.0
                fresh = True
            elif hours < 72:
                score += 1.0
        matched: list[str] = []
        for word in hits + ghits:
            if word not in matched:
                matched.append(word)
        it.matched = matched[:5]
        it.score = score
        it.why = _why(text, hits, ghits, facts, fresh)
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
    return dedupe(items)


async def ingest(cfg: Config, store: Store) -> dict:
    started = utcnow()
    try:
        items = await collect(cfg)
    except Exception as exc:  # noqa: BLE001
        store.record_run(started, 0, 0, status="failed", error=str(exc)[:200])
        raise

    profile = store.get_profile()
    ranked = rank_items(items, cfg, profile)

    rows: list[tuple[int, float]] = []
    for it in ranked:
        source_id = store.source_id(it.source, cfg.weights.get(it.source, 1.0))
        item_id = store.upsert_item(it, source_id)
        rows.append((item_id, it.score))

    day = local_day(cfg)
    top = rows[: cfg.profile.max_items]
    store.snapshot(day, top)
    store.record_run(started, len(items), len(top))
    return {"day": day, "fetched": len(items), "kept": len(top), "profile": bool(profile["facts"])}
