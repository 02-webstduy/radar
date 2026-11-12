"""统一条目。所有源都收敛到这个形状，后续排序/筛选/展示只看它。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Item:
    title: str
    url: str
    source: str
    summary: str = ""
    published: datetime | None = None
    score: float = 0.0
    matched: list[str] = field(default_factory=list)
    why: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "summary": self.summary[:240],
            "published": self.published.isoformat() if self.published else None,
            "score": round(self.score, 2),
            "matched": self.matched,
            "why": self.why,
        }
