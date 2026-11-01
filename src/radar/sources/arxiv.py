"""arXiv：官方 Atom API，cs.AI / cs.SE / cs.LG，按提交时间倒序。"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import feedparser
import httpx

from ..config import Config
from ..models import Item

API = "https://export.arxiv.org/api/query"


async def fetch(cfg: Config) -> list[Item]:
    params = {
        "search_query": "cat:cs.AI OR cat:cs.SE OR cat:cs.LG",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": "30",
    }
    async with httpx.AsyncClient(timeout=25) as client:
        resp = await client.get(API, params=params)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

    items: list[Item] = []
    for entry in feed.entries:
        title = re.sub(r"\s+", " ", entry.get("title", "")).strip().rstrip(".")
        summary = re.sub(r"\s+", " ", entry.get("summary", "")).strip()[:240]
        published = (
            datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if entry.get("published_parsed")
            else None
        )
        items.append(
            Item(
                title=title,
                url=entry.get("link", ""),
                source="arXiv",
                summary=summary,
                published=published,
            )
        )
    return items
