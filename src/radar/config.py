"""配置加载：config.toml + config.local.toml（私密）+ 环境变量。"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Profile:
    role: str
    keywords: tuple[str, ...]
    max_items: int
    lookback_days: int


@dataclass(frozen=True)
class Config:
    name: str
    port: int
    profile: Profile
    weights: dict[str, float] = field(default_factory=dict)
    db_path: Path = ROOT / "data" / "radar.db"
    timezone: str = "Asia/Shanghai"
    web_dir: Path = ROOT / "web"


def _read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text("utf-8")) if path.exists() else {}


def load() -> Config:
    p = ROOT / "config.toml"
    raw = _read_toml(p)
    local = _read_toml(p.with_name("config.local.toml"))
    # 简单覆盖：local 的同名键替换
    for section, values in local.items():
        if isinstance(values, dict):
            raw.setdefault(section, {}).update(values)
        else:
            raw[section] = values

    app = raw.get("app", {})
    profile = raw.get("profile", {})
    src = raw.get("source", {})
    storage = raw.get("storage", {})
    db_path = Path(str(storage.get("path", "data/radar.db")))
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    return Config(
        name=str(app.get("name", "技术雷达")),
        port=int(os.environ.get("RADAR_PORT") or app.get("port", 8767)),
        profile=Profile(
            role=str(profile.get("role", "engineer")),
            keywords=tuple(str(k) for k in profile.get("keywords", [])),
            max_items=int(profile.get("max_items", 8)),
            lookback_days=int(profile.get("lookback_days", 7)),
        ),
        weights={str(k): float(v) for k, v in src.get("weights", {}).items()},
        db_path=db_path,
        timezone=str(storage.get("timezone", "Asia/Shanghai")),
    )
