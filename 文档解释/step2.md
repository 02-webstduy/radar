# step2 · 接入 SQLite：抓取落库 + 当日榜单 + 反馈接口

## 目标
从"内存里算完就丢"改成"落库 + 按天出榜"，页面读库；同时留出反馈入口。

## 框架
```text
web/index.html → /api/items → app.ensure_today
                                 ├─ 新鲜 → store.top_items(day)
                                 └─ 过期 → pipeline.ingest
                                              ├─ collect() 四源
                                              └─ Store: sources/items/daily/ingest_runs
```

## 信息流
1. `src/radar/app.py:48` 判断当天榜单是否新鲜（30 分钟内成功抓过）
2. `src/radar/pipeline.py:75` 调 `collect()` 拿全部命中项 → 筛选/打分
3. `src/radar/storage.py:91` 写 `sources`；`:101` upsert `items`（`url_key` 唯一）
4. `storage.py:129` 重写当日 `daily`（rank 1..8）
5. `storage.py:138` 记 `ingest_runs`；`app.py:63` 用 `daily JOIN items JOIN sources` 返回
6. `storage.py:147` 写 `feedback`（save / skip / read），暂未参与排序

## 改动落点
- 新增：`src/radar/storage.py`、`src/radar/urls.py`、`docs/SQL.md`、`docs/ARCHITECTURE.md`
- 修改：`src/radar/pipeline.py`、`src/radar/app.py`、`src/radar/__main__.py`、`config.toml`、`src/radar/config.py`
- 删除：无
