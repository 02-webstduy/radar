# 技术雷达：架构与信息流

> 目标：每天把 5 个源的新内容收敛成 8 条"与你有关"的，落库留痕，页面可读。
> 这一版只做采集 + 筛选 + 存储 + 展示；反馈与方向分析是下一步。

## 1. 分层

```text
┌─────────────────────────── 浏览器 ───────────────────────────┐
│  web/index.html   卡片 / 来源过滤 / 骨架屏 / 刷新            │
└──────────────────────────────┬───────────────────────────────┘
                               │ GET /api/items · POST /api/feedback
┌──────────────────────────────▼───────────────────────────────┐
│  app.py（FastAPI）                                             │
│    ensure_today()：当天数据是否新鲜（30 分钟）                 │
│    /api/items   /api/feedback   /api/stats   /                 │
└───────────────┬───────────────────────────────┬──────────────┘
                │ 过期才抓                       │ 读
┌───────────────▼──────────────┐   ┌────────────▼──────────────┐
│ pipeline.ingest              │   │ storage.Store             │
│   collect() → 去重 → 筛选 →  │──►│   sources / items / daily │
│   打分 → 落库 → 当日榜单     │   │   feedback / ingest_runs  │
└───────────────┬──────────────┘   └───────────────────────────┘
                │ 并发
   ┌────────────┼────────────┬─────────────┐
 github        arxiv         hn           rss
(Search API)  (Atom API)  (Algolia)   (掘金/少数派)
```

## 2. 模块职责

| 模块 | 职责 | 不该做 |
|---|---|---|
| `web/index.html` | 展示、来源过滤、触发刷新 | 不筛内容、不算分 |
| `app.py` | 路由、缓存判断、JSON 形状 | 不实现采集细节 |
| `pipeline.py` | 编排采集、去重、筛选、打分、落库 | 不写 HTTP 页面 |
| `storage.py` | 建表、upsert、榜单快照、查询 | 不调外部 API |
| `sources/*.py` | 单个源的 API/RSS → `Item` | 不做跨源去重 |
| `urls.py` | URL 归一化（去 utm、排序 query） | 不判断内容质量 |
| `config.py` / `config.toml` | 画像关键词、来源权重、库路径 | 不放密钥 |

## 3. 三条信息流

### 3.1 打开页面（读）

1. 浏览器 `GET /api/items`
2. `app.ensure_today()` 判断：当天有榜单 + 最近成功抓取 < 30 分钟 → 直接读库
3. 否则串行触发 `ingest()`（同一时间只允许一次）
4. `storage.top_items(day)` 做 `daily JOIN items JOIN sources`，按 rank 返回
5. 页面渲染卡片；`updated` 是最近一次抓取完成时间

### 3.2 抓取（写）

1. `pipeline.collect()` 并发拉 4 类源（GitHub / arXiv / HN / RSS），单源异常只记 warning
2. `dedupe()` 用 `urls.canonical()` 做唯一键，去掉重复
3. `score_and_filter()`：标题/摘要命中关键词才保留；分数 = 来源权重 + 命中数 + 标题命中 + 新近度
4. 每条内容 `upsert` 进 `items`（`url_key` 冲突则更新）
5. `snapshot(day, topN)`：先删当天旧榜，再写 rank 1..8
6. `record_run()` 记一条 `ingest_runs`（成功/失败、抓多少、留多少）

### 3.3 反馈（下一步的入口）

1. 页面 `POST /api/feedback` `{item_id, action}`
2. `storage.add_feedback()` 写 `feedback`
3. （待做）按 save/skip 调整 `sources.weight` 与关键词权重，影响下一次排序

## 4. 数据模型

```text
sources(id, name UNIQUE, weight)
   │ 1:N
items(id, source_id FK, url, url_key UNIQUE, title, summary,
      published_at, first_seen_at, last_seen_at, score, matched JSON)
   │ 1:N                    │ 1:N
daily(day, item_id FK, rank, score)   feedback(id, item_id FK, action, created_at)
   PK(day, item_id)
```

- `url_key` 是去重键：同一篇文章从不同入口进来只留一条
- `daily` 是"每天的快照"，不是实时排序；重抓会整体替换当天榜单
- `ingest_runs` 是运维视角：失败原因、抓取量、耗时都能回溯

## 5. 失败与降级

| 情况 | 行为 |
|---|---|
| 单个源超时/403 | 记 warning，其他源照常 |
| 全部源失败 | `ingest_runs` 记 failed；页面继续显示上一次的榜单 |
| GitHub 未配 token | 匿名限流时跳过 GitHub，其余源可用 |
| 数据库写失败 | 请求返回 400/500，不影响已有数据 |
| 重复抓取 | 同一天重抓会替换 `daily`，`items` 靠 `url_key` 幂等 |

## 6. 配置与运行

```bash
# 抓一次并入库
.venv/bin/python -m radar ingest

# 看库里有什么
.venv/bin/python -m radar stats

# 起页面（8767）
.venv/bin/python -m radar serve

# 每天 8:00 自动抓（crontab 示例）
0 8 * * * cd /workspace/code/dsh/radar && .venv/bin/python -m radar ingest >> /tmp/radar.log 2>&1
```

- 数据库：`data/radar.db`（服务器本地文件，git 忽略）
- 关键词/权重：`config.toml`
- 端口：`config.toml [app] port`

## 7. 下一步方向（按性价比）

| 方向 | 做什么 | 价值 |
|---|---|---|
| **反馈驱动排序** | save/skip 落库 → 调整来源与关键词权重 | 让"8 条"越来越准；面试可讲排序闭环 |
| **周报 + 方向卡** | 每周三问（做了什么/卡在哪/下周验证什么）+ 3 条方向建议 | 这是别人没有的"闭环" |
| **定时与推送** | cron + 邮件/飞书 | 从"打开看"变成"每天送到" |
| **评测** | 30 条人工标注，算 nDCG@10 | 证明"变好了"，不是感觉 |
| **网站化** | 存档、搜索、画像页 | 等上面成立再做 |

## 8. 当前限制

- 关键词匹配，不理解语义；同义说法会漏
- 只抓官方 API/RSS，覆盖面受源限制
- 单机单用户；没有登录，只监听 `127.0.0.1`
- 没有"与你有关"的个性化解释（下一步加）
