"""进程内共享的配置和数据库连接，避免每个模块各开一份。"""

from __future__ import annotations

from .config import load
from .storage import Store

cfg = load()
store = Store(cfg.db_path)
