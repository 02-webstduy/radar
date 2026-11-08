"""URL 归一化：去重和数据库唯一键都用它。"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit

_SKIP_QUERY = {"utm_source", "utm_medium", "utm_campaign", "ref", "spm"}


def canonical(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path.rstrip("/")
    query = sorted((k, v) for k, v in parse_qsl(parts.query) if k not in _SKIP_QUERY)
    return f"{host}{path}?{query}" if query else f"{host}{path}"
