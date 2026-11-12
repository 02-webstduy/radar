# step4 · 画像入口从独立端口改为 /profile 子路由

## 目标
在同一个站点里进入画像，不再单开端口（8768）。

## 框架
```text
web/index.html「画像」→ GET /profile → web/profile.html
                              ↘ /api/profile/*
app.py ── include_router(profile_routes)
              ↘ runtime.py：cfg + store（单例）
```

## 信息流
1. `web/index.html` 的「画像」链接和未填画像提示都指向 `/profile`
2. `src/radar/profile_routes.py:46` 返回 `web/profile.html`；页面里接口仍是 `/api/profile/*`
3. 聊天结束写 `profile` / `profile_facts`（`:65`）；表单保存 `:85`
4. `src/radar/runtime.py` 让主应用和画像路由共用同一个 `Store`，不再各开连接

## 改动落点
- 新增：`src/radar/profile_routes.py`、`src/radar/runtime.py`
- 修改：`app.py`、`__main__.py`、`config.py`、`config.toml`、`web/index.html`、`web/profile.html`
- 删除：`src/radar/profile_app.py`（8768 的独立应用）
