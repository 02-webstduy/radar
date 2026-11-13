"""OpenAI 兼容的对话客户端：画像聊天和抽取共用。"""

from __future__ import annotations

import os

import httpx

from .config import LLMConfig


class LLMError(RuntimeError):
    pass


async def chat(
    cfg: LLMConfig,
    messages: list[dict[str, str]],
    *,
    json_mode: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 600,
) -> str:
    if not cfg.enabled:
        raise LLMError("模型未启用")

    headers = {"Content-Type": "application/json"}
    if cfg.api_key_env and os.environ.get(cfg.api_key_env):
        headers["Authorization"] = f"Bearer {os.environ[cfg.api_key_env]}"

    payload = {
        "model": cfg.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        async with httpx.AsyncClient(timeout=cfg.timeout_s) as client:
            resp = await client.post(
                f"{cfg.base_url}/chat/completions", json=payload, headers=headers
            )
    except httpx.HTTPError as exc:
        raise LLMError(f"连不上模型：{type(exc).__name__}") from exc

    if resp.status_code != 200:
        raise LLMError(f"模型返回 {resp.status_code}：{resp.text[:120]}")
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError("模型返回格式异常") from exc
