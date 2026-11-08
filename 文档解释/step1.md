# step1 · 雷达 P0：多源采集 + 关键词筛选 + 只读页面（本轮补界面）

## 目标
把 5 个源当天的新内容收敛成 8 条可读条目，先验证「筛选」有没有用；本轮只改前端呈现。

## 框架
```text
web/index.html ──GET /api/items──► app.py（5 分钟缓存）
                                      │
                                 pipeline.collect
                    ┌─────────────┬──┴──────────┬─────────────┐
                 github          arxiv          hn           rss
              (Search API)     (Atom API)   (Algolia API)  (掘金/少数派)
                    └─────────────┴──┬──────────┴─────────────┘
                                      ▼
                          去重 → 关键词筛选 → 打分 → top 8
```

## 信息流
1. `web/index.html` 加载后请求 `/api/items`，先显示骨架屏。
2. `src/radar/app.py:20` 缓存未过期直接返回；过期才调用 `collect()`。
3. `src/radar/pipeline.py:64` 并发拉 4 类源，单源异常只记 warning，不拖垮整体。
4. `src/radar/sources/*.py` 把各自响应统一成 `Item`（标题 / 链接 / 摘要 / 时间）。
5. `pipeline.py:28` 按 URL 规范化去重；`pipeline.py:40` 关键词命中 + 新近度 + 来源权重打分，截前 8。
6. 浏览器渲染卡片，并按来源过滤（`web/index.html` 的 `renderFilters`）。

## 改动落点
- 新增：`src/radar/sources/{github,arxiv,hn,rss}.py`、`src/radar/pipeline.py`、`src/radar/app.py`、`web/index.html`
- 修改：`config.toml`（关键词 / 来源权重）；本轮 `web/index.html`（卡片、来源过滤、骨架屏）
- 删除：无
