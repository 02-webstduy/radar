"""中文 RSS 源：掘金、少数派。"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import feedparser
import httpx

from ..config import Config
from ..models import Item

FEEDS = {
    "掘金": "https://juejin.cn/rss",
    "少数派": "https://sspai.com/feed",
}

_TAG = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG.sub("", text or "").strip()


async def fetch(cfg: Config) -> list[Item]:
    items: list[Item] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for name, url in FEEDS.items():
            resp = await client.get(url)
            if resp.status_code != 200:
                continue
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:30]:
                title = _strip_html(entry.get("title", ""))
                link = entry.get("link", "")
                summary = _strip_html(entry.get("summary") or entry.get("description", ""))[:240]
                published = (
                    datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    if entry.get("published_parsed")
                    else None
                )
                items.append(
                    Item(title=title, url=link, source=name, summary=summary, published=published)
                )
    return items
