"""SQLite 存储层：建表、写入、查询。所有 SQL 都用参数化，不拼字符串。

表关系：
  sources 1 ── N items        一个来源下有多条内容
  items   1 ── N daily        一条内容可以出现在多天的榜单里
  items   1 ── N feedback     一条内容可以有多条反馈
  ingest_runs                 每次抓取的运行记录（不挂外键）
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .urls import canonical

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  name    TEXT NOT NULL UNIQUE,
  weight  REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id     INTEGER NOT NULL REFERENCES sources(id),
  url           TEXT NOT NULL,
  url_key       TEXT NOT NULL UNIQUE,
  title         TEXT NOT NULL,
  summary       TEXT NOT NULL DEFAULT '',
  published_at  TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL,
  score         REAL NOT NULL DEFAULT 0,
  matched       TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS daily (
  day      TEXT NOT NULL,
  item_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  rank     INTEGER NOT NULL,
  score    REAL NOT NULL,
  PRIMARY KEY (day, item_id)
);

CREATE TABLE IF NOT EXISTS feedback (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  action     TEXT NOT NULL CHECK (action IN ('save', 'skip', 'read')),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  status      TEXT NOT NULL DEFAULT 'running',
  fetched     INTEGER NOT NULL DEFAULT 0,
  kept        INTEGER NOT NULL DEFAULT 0,
  error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_id);
CREATE INDEX IF NOT EXISTS idx_daily_day_rank ON daily(day, rank);
CREATE INDEX IF NOT EXISTS idx_feedback_item ON feedback(item_id);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.Lock()
        with self.conn:
            self.conn.executescript(SCHEMA)

    # ---------------------------------------------------------- 写入

    def source_id(self, name: str, weight: float) -> int:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO sources (name, weight) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET weight = excluded.weight",
                (name, weight),
            )
            row = self.conn.execute("SELECT id FROM sources WHERE name = ?", (name,)).fetchone()
            return int(row["id"])

    def upsert_item(self, item, source_id: int) -> int:
        now = utcnow()
        url_key = canonical(item.url) or item.title.strip().lower()
        published = item.published.isoformat(timespec="seconds") if item.published else None
        matched = json.dumps(item.matched, ensure_ascii=False)
        with self._lock, self.conn:
            row = self.conn.execute(
                """
                INSERT INTO items
                  (source_id, url, url_key, title, summary, published_at,
                   first_seen_at, last_seen_at, score, matched)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url_key) DO UPDATE SET
                  title = excluded.title,
                  summary = excluded.summary,
                  published_at = excluded.published_at,
                  last_seen_at = excluded.last_seen_at,
                  score = excluded.score,
                  matched = excluded.matched
                RETURNING id
                """,
                (
                    source_id, item.url, url_key, item.title, item.summary,
                    published, now, now, item.score, matched,
                ),
            ).fetchone()
            return int(row["id"])

    def snapshot(self, day: str, ranked: list[tuple[int, float]]) -> None:
        """把某天的榜单整体替换掉，保证同一天多次抓取不会重复。"""
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM daily WHERE day = ?", (day,))
            self.conn.executemany(
                "INSERT INTO daily (day, item_id, rank, score) VALUES (?, ?, ?, ?)",
                [(day, item_id, rank, score) for rank, (item_id, score) in enumerate(ranked, 1)],
            )

    def record_run(self, started_at: str, fetched: int, kept: int, status: str = "ok",
                   error: str | None = None) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO ingest_runs (started_at, finished_at, status, fetched, kept, error) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (started_at, utcnow(), status, fetched, kept, error),
            )

    def add_feedback(self, item_id: int, action: str) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO feedback (item_id, action, created_at) VALUES (?, ?, ?)",
                (item_id, action, utcnow()),
            )

    # ---------------------------------------------------------- 查询

    def top_items(self, day: str) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT i.id, i.title, i.url, i.summary, i.published_at,
                       i.score, i.matched, s.name AS source
                FROM daily d
                JOIN items i ON i.id = d.item_id
                JOIN sources s ON s.id = i.source_id
                WHERE d.day = ?
                ORDER BY d.rank
                """,
                (day,),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["matched"] = json.loads(item["matched"])
            except json.JSONDecodeError:
                item["matched"] = []
            out.append(item)
        return out

    def last_run(self) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def stats(self) -> dict:
        with self._lock:
            sources = self.conn.execute(
                """
                SELECT s.name, COUNT(i.id) AS n
                FROM sources s LEFT JOIN items i ON i.source_id = s.id
                GROUP BY s.id ORDER BY n DESC
                """
            ).fetchall()
            total = self.conn.execute("SELECT COUNT(*) AS n FROM items").fetchone()["n"]
            days = self.conn.execute("SELECT COUNT(DISTINCT day) AS n FROM daily").fetchone()["n"]
        return {"items": total, "days": days, "sources": [dict(r) for r in sources]}

    def close(self) -> None:
        self.conn.close()
