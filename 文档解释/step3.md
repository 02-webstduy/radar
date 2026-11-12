# step3 · 画像模块（聊天/表单）+ 画像驱动排序 + 标注评测

## 目标
把"关键词排序"升级成"画像驱动排序"，并让用户用聊天或表单确认画像。

## 框架
```text
profile.html(/profile) → profile_routes → Store(profile / profile_facts / profile_chat)
radar/index.html(8767) → app.ensure_today → pipeline.rank_items(profile)
                                        ↘ /api/label → labels → /api/eval → eval.compare
```

## 信息流
1. `src/radar/profile_routes.py:65` 逐题写 `profile_chat`，答完写 `profile` / `profile_facts`
2. `src/radar/profile_flow.py` 用 stack / learning / interests + 受控词表生成关键词
3. `src/radar/app.py` 的 `_fresh` 发现画像比上次抓取新 → 触发 `pipeline.ingest`
4. `src/radar/pipeline.py:64` 按画像词匹配、算分、写 `why`；`:121` 落库并出当日榜单
5. 页面展示 `why`；点「相关/不相关」→ `storage.add_label`；`/api/eval` 比较画像 vs 关键词的 nDCG
6. 表单模式走 `profile_routes.py:85`，和聊天共用 `save_profile`

## 改动落点
- 新增：`src/radar/profile_routes.py`、`profile_flow.py`、`eval.py`、`web/profile.html`
- 修改：`storage.py`、`pipeline.py`、`app.py`、`config.py`、`config.toml`、`__main__.py`、`web/index.html`
- 删除：无
