"""Hacker News：官方 Algolia API，取首页故事。"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..config import Config
from ..models import Item

API = "https://hn.algolia.com/api/v1/search"


async def fetch(cfg: Config) -> list[Item]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(API, params={"tags": "front_page", "hitsPerPage": 30})
        resp.raise_for_status()
        hits = resp.json().get("hits", [])

    items: list[Item] = []
    for h in hits:
        title = h.get("title") or ""
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        points = h.get("points", 0)
        comments = h.get("num_comments", 0)
        summary = f"{points} 分 · {comments} 讨论"
        created = h.get("created_at_i")
        items.append(
            Item(
                title=title,
                url=url,
                source="HN",
                summary=summary,
                published=datetime.fromtimestamp(created, tz=timezone.utc) if created else None,
            )
        )
    return items
