# 技术雷达（radar）

每天从 GitHub / arXiv / Hacker News / 掘金 / 少数派 抓一次，按关键词筛出 8 条，落 SQLite，网页只读展示。

## 快速开始

画像聊天用的是 OpenAI 兼容接口，模型在 `config.toml [llm]`；换 DeepSeek 只改 base_url/model，key 写 `.env` 的 `XIAOMAN_API_KEY`。

```bash
cd radar
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m radar ingest     # 抓一次并入库
.venv/bin/python -m radar serve      # 雷达 http://127.0.0.1:8767
```

可选：`GITHUB_TOKEN=...` 写进 `.env`，GitHub 源更稳（匿名额度低）。需要翻墙的源可以 `HTTPS_PROXY=http://127.0.0.1:17890`。

## 目录

```
src/radar/
├── sources/       github / arxiv / hn / rss 四个适配器
├── pipeline.py    采集 → 去重 → 筛选 → 打分 → 落库 → 当日榜单
├── storage.py     SQLite：sources / items / daily / feedback / ingest_runs
├── urls.py        URL 归一化（去重键）
├── app.py         /api/items · /api/feedback · /api/stats
└── __main__.py    run / ingest / serve / stats
web/index.html     卡片、来源过滤、骨架屏
data/radar.db      SQLite（git 忽略）
```

## 文档

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)：分层、三条信息流、数据模型、下一步
- [docs/SQL.md](docs/SQL.md)：库表设计、DDL、查询、练习题（课程/考试用）
- [docs/PROFILE_AND_MATCHING.md](docs/PROFILE_AND_MATCHING.md)：画像字段、分层匹配、进度闭环、两周计划
- [docs/PROFILE_EVAL.md](docs/PROFILE_EVAL.md)：画像抽取评测（3 案例，87.5%）
- [docs/PROGRESS.md](docs/PROGRESS.md)：进度接入口、准确性校验、第一版设计
- `文档解释/`：每轮代码改动的框架与信息流

## 当前状态

P0：采集 + 画像驱动排序 + 落库 + 只读页面 + 标注评测。
画像有自由聊天 + 表单两种入口（右上角「画像」，即 /profile）；聊天由 LLM 抽取画像，带置信度/依据，可改。
