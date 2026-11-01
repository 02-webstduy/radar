"""GitHub：官方 Search API，按近 N 天新建 + 星数排序，主题限 AI。

需要 `GITHUB_TOKEN`（无 token 时匿名额度极低、易被共享出口 IP 限流）。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from ..config import Config
from ..models import Item

logger = logging.getLogger("radar.github")
API = "https://api.github.com"


async def fetch(cfg: Config) -> list[Item]:
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "radar"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    since = (
        datetime.now(timezone.utc) - timedelta(days=cfg.profile.lookback_days)
    ).strftime("%Y-%m-%d")
    # GitHub 的 q 里 OR 跨多个 topic 容易 422，拆成两条查询更稳
    queries = [
        f"created:>{since} stars:>10 topic:agent",
        f"created:>{since} stars:>10 topic:llm",
    ]

    seen: set[str] = set()
    items: list[Item] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for query in queries:
            resp = await client.get(
                f"{API}/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 20},
                headers=headers,
            )
            if resp.status_code == 403:
                logger.warning("GitHub 限流或未配 token，跳过（403）")
                return items
            if resp.status_code == 422:
                continue
            resp.raise_for_status()
            for repo in resp.json().get("items", []):
                full_name = repo.get("full_name", "")
                if full_name in seen:
                    continue
                seen.add(full_name)
                desc = repo.get("description") or ""
                topics = repo.get("topics") or []
                summary = f"⭐{repo.get('stargazers_count', 0)} · {desc}"
                if topics:
                    summary += f" · #{' #'.join(topics[:4])}"
                published = repo.get("created_at")
                items.append(
                    Item(
                        title=full_name,
                        url=repo.get("html_url", ""),
                        source="GitHub",
                        summary=summary[:240],
                        published=datetime.fromisoformat(published.replace("Z", "+00:00"))
                        if published
                        else None,
                    )
                )
    return items
