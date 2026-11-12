# SQL 速成：雷达的库表设计（课程设计 / 考试用）

> 先看关系，再看建表，最后跑查询。代码在 `src/radar/storage.py`，这份文档只讲你考试要用的部分。

## 1. 为什么用 SQLite

- **嵌入式**：没有独立数据库服务，整个库就是一个文件 `data/radar.db`
- 单机、单用户足够；备份 = 复制文件
- 语法和 MySQL / PostgreSQL 大部分相通，学到的能迁移

## 2. 五张表与关系

```text
sources 1 ────< items 1 ────< daily        （同一条内容可上多天榜单）
                         └──< feedback     （同一条内容可有多条反馈）
ingest_runs                                  （每次抓取的运行记录，独立）
```

- 一个来源有多条内容：`sources.id` → `items.source_id`，**一对多**
- 一条内容可以出现在多天：`daily(day, item_id)`，**多对多**（用复合主键实现）
- 一条内容可以有多条反馈：`items.id` → `feedback.item_id`，**一对多**
- `ingest_runs` 是日志表，不挂外键

## 3. 概念对照

| 概念 | 在这套表里 | 作用 |
|---|---|---|
| 主键 PK | `sources.id`、`items.id`、`feedback.id` | 唯一标识一行 |
| 复合主键 | `daily(day, item_id)` | 同一天同一条只能上榜一次 |
| 外键 FK | `items.source_id → sources.id` | 保证来源存在；必须开 `PRAGMA foreign_keys=ON` |
| 唯一约束 UNIQUE | `items.url_key` | 去重；`ON CONFLICT` 依赖它 |
| 检查约束 CHECK | `feedback.action` | 只允许 save / skip / read |
| 索引 | `idx_items_published`、`idx_daily_day_rank` | 加速按天、按来源查询 |
| 事务 | `with conn:` | 一组写操作要么全成、要么全败 |
| WAL | `PRAGMA journal_mode=WAL` | 读写并发更好，页面查询不被写入阻塞 |

## 4. 建表（精简版，和代码一致）

```sql
CREATE TABLE sources (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  name    TEXT NOT NULL UNIQUE,
  weight  REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id     INTEGER NOT NULL REFERENCES sources(id),
  url           TEXT NOT NULL,
  url_key       TEXT NOT NULL UNIQUE,   -- 归一化后的 URL，用来去重
  title         TEXT NOT NULL,
  summary       TEXT NOT NULL DEFAULT '',
  published_at  TEXT,                   -- ISO8601 文本
  first_seen_at TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL,
  score         REAL NOT NULL DEFAULT 0,
  matched       TEXT NOT NULL DEFAULT '[]'  -- JSON 数组
);

CREATE TABLE daily (
  day     TEXT NOT NULL,
  item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  rank    INTEGER NOT NULL,
  score   REAL NOT NULL,
  PRIMARY KEY (day, item_id)
);

CREATE TABLE feedback (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  action     TEXT NOT NULL CHECK (action IN ('save','skip','read')),
  created_at TEXT NOT NULL
);

CREATE TABLE ingest_runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  status      TEXT NOT NULL DEFAULT 'running',
  fetched     INTEGER NOT NULL DEFAULT 0,
  kept        INTEGER NOT NULL DEFAULT 0,
  error       TEXT
);

CREATE INDEX idx_items_published ON items(published_at DESC);
CREATE INDEX idx_items_source    ON items(source_id);
CREATE INDEX idx_daily_day_rank  ON daily(day, rank);
CREATE INDEX idx_feedback_item   ON feedback(item_id);
```

### 画像与标注（后加的四张表）

```sql
CREATE TABLE profile (            -- 只有一行，id 固定为 1
  id INTEGER PRIMARY KEY CHECK (id = 1),
  narrative TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

CREATE TABLE profile_facts (      -- 键值对：goal / stack / learning ...
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0.8,
  source TEXT NOT NULL DEFAULT 'chat',
  updated_at TEXT NOT NULL
);

CREATE TABLE profile_chat (       -- 聊天会话的进度
  id TEXT PRIMARY KEY,
  step INTEGER NOT NULL DEFAULT 0,
  answers TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);

CREATE TABLE labels (             -- 人工标注：1 相关 / 0 不相关
  item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  relevant INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
```

关系：`profile 1—N profile_facts`（键值对，没有外键）、`items 1—1 labels`。
`profile_chat` 是过程表，答完才写 `profile_facts`。

## 5. 三条必会查询

```sql
-- 今日榜单：三表 JOIN
SELECT d.rank, s.name AS source, i.title, ROUND(d.score, 1) AS score
FROM daily d
JOIN items i   ON i.id = d.item_id
JOIN sources s ON s.id = i.source_id
WHERE d.day = '2026-11-08'
ORDER BY d.rank;

-- 每个来源多少条：GROUP BY + 聚合
SELECT s.name, COUNT(*) AS n
FROM items i
JOIN sources s ON s.id = i.source_id
GROUP BY s.id
ORDER BY n DESC;

-- 被收藏过的条目：JOIN + DISTINCT
SELECT DISTINCT i.title, s.name
FROM feedback f
JOIN items i   ON i.id = f.item_id
JOIN sources s ON s.id = i.source_id
WHERE f.action = 'save';
```

## 6. 参数化：别用字符串拼接

```python
# 对：? 占位，驱动会转义
conn.execute("SELECT id FROM sources WHERE name = ?", (name,))

# 错：SQL 注入 + 引号地狱
conn.execute(f"SELECT id FROM sources WHERE name = '{name}'")
```

## 7. 练习题（考试型）

1. 查「arXiv 来源里命中 agent、且分数 > 7」的标题，按分数倒序。
2. 统计每个来源的平均分、最高分（`AVG` / `MAX` + `GROUP BY`）。
3. 找出「被 save 过、但当天没有进前 8」的条目（`feedback` + `daily` 的 `LEFT JOIN ... WHERE d.item_id IS NULL`）。

## 8. 常见坑

- 外键默认是关的，必须 `PRAGMA foreign_keys=ON`，否则删父表不会报错。
- 时间存 ISO8601 字符串，同一时区下字符串排序 = 时间排序。
- 不要 `SELECT *`，字段多了以后很慢；只取要用的列。
- `INSERT ... ON CONFLICT(url_key) DO UPDATE` 是 SQLite 的 upsert，去重的关键。
