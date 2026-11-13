# step5 · 画像自由聊天：AI 提问 → 抽取 → 用户确认

## 目标
不再靠固定问卷；像聊天一样说，AI 从对话里画画像，并给出置信度和依据让用户改。

## 框架
```text
profile.html → /api/profile/chat/{start,send} → profile_chat(SYSTEM 提示词)
                                  ↘ llm.chat（vLLM 或 API）
                                  ↘ extract(JSON) → normalize_draft
profile.html ← facts / confidence / evidence → 用户修改 → /api/profile/save
```

## 信息流
1. `src/radar/profile_routes.py:56` 存用户消息，带 SYSTEM + 最近 16 条调 `llm.chat`
2. 触发整理：说「差不多了」/ 满 8 轮 / 点「生成画像」→ `profile_chat.extract`
3. `profile_chat.py:131` 用 JSON 模式抽 facts / confidence / evidence / missing
4. `profile_chat.py:94` 校验 evidence 能否在对话原文找到；找不到就降置信度
5. 页面显示字段 + 置信度 + 原话依据；保存写 `profile` / `profile_facts`
6. `scripts/eval_profile.py` 用 3 段对话 + 标准答案量准确率和臆造

## 改动落点
- 新增：`src/radar/llm.py`、`profile_chat.py`、`scripts/eval_profile.py`
- 修改：`profile_routes.py`、`storage.py`、`config.py`、`config.toml`、`web/profile.html`
- 删除：旧的 8 问聊天接口（表单保留）
