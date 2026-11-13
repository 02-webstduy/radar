"""画像对话：提示词、就绪判断、抽取结果归一化。"""

from __future__ import annotations

import json
import re

from .config import Config
from .profile_flow import build_narrative
from . import llm

FIELDS: dict[str, str] = {
    "goal": "想达成的目标、截止时间",
    "project": "正在做的项目、阶段、卡点",
    "stack": "已经会用的技术（哪怕只提一句也要填）",
    "learning": "正在学、还不熟的",
    "hours": "每周可投入小时数",
    "interests": "想多看到的内容主题（不是形式）",
    "avoid": "不想看的内容",
    "format": "偏好的形式或语言",
}

SYSTEM = """你是「画像助手」，通过聊天了解用户，最后画出一份可编辑的画像。

尽量在对话里自然覆盖这些字段（一次只问一个）：
- goal：想达成什么、截止时间
- project：正在做的项目、阶段、卡点
- stack：已经会用的技术
- learning：正在学、还不熟的
- hours：每周能投入多少小时
- interests：想多看到的内容主题
- avoid：不想看的内容
- format：偏好的形式 / 语言

规则：
1. 一次只问一个问题，不超过 60 字。
2. 先问具体的（最近在做什么、卡在哪），不要像问卷；不要重复问已经知道的。
3. 不要列清单、不要总结陈词；像正常人聊天。
4. 用户说「差不多了 / 总结吧 / 可以了」时，回一句「好，我来整理画像」，然后停止提问。
5. 尽量 6–8 轮内把主要字段问清楚；不确定就直接问。
6. 不要编造。"""

GREETING = "你好，我是画像助手。先随便聊聊：你最近在做什么？"


def is_ready(text: str, turns: int) -> bool:
    if any(k in text for k in ("差不多了", "总结吧", "可以了", "就这样", "够了", "整理画像")):
        return True
    return turns >= 8


def extraction_messages(conversation: str) -> list[dict[str, str]]:
    schema = {
        "facts": {k: "" for k in FIELDS},
        "confidence": {k: 0 for k in FIELDS},
        "evidence": {k: "" for k in FIELDS},
        "missing": [],
        "narrative": "",
    }
    prompt = f"""根据对话抽取用户画像，只输出 JSON，结构如下：
{json.dumps(schema, ensure_ascii=False)}

字段含义：
{json.dumps(FIELDS, ensure_ascii=False)}

规则：
- 只写对话里出现过的信息；没提到的字段留空，并放进 missing。
- evidence 必须是对话里的原话片段（10–40 字），不能改写。
- confidence 取 0–1：原话明确给 0.9；合理推断最多 0.5；没依据给 0。
- narrative 用 2–3 句话写一段自述，只能用对话里的事实。
- 注意区分：interests 是内容主题，format 是形式/语言；不要把形式填进 interests。
- goal 要把用户说的目标和方向都写进去，不要只写一半。

对话：
{conversation}"""
    return [
        {"role": "system", "content": "你是信息抽取器，只输出合法 JSON。"},
        {"role": "user", "content": prompt},
    ]


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_draft(data: dict, conversation: str) -> dict:
    facts_raw = data.get("facts") or {}
    conf_raw = data.get("confidence") or {}
    ev_raw = data.get("evidence") or {}
    haystack = re.sub(r"\s+", "", conversation).lower()

    facts: dict[str, str] = {}
    confidence: dict[str, float] = {}
    evidence: dict[str, str] = {}
    for key in FIELDS:
        fact = str(facts_raw.get(key, "") or "").strip()[:200]
        conf = _clamp(float(conf_raw.get(key, 0) or 0))
        ev = str(ev_raw.get(key, "") or "").strip()[:80]

        if ev:
            needle = re.sub(r"\s+", "", ev).lower()
            if needle not in haystack:
                ev = ""
                conf = min(conf, 0.4)  # 找不到原话，降置信度
        if not fact:
            conf = 0.0
            ev = ""
        facts[key] = fact
        confidence[key] = round(conf, 2)
        evidence[key] = ev

    missing = [k for k in FIELDS if not facts[k]]
    narrative = str(data.get("narrative", "") or "").strip() or build_narrative(facts)
    return {
        "facts": facts,
        "confidence": confidence,
        "evidence": evidence,
        "missing": missing,
        "narrative": narrative,
    }


async def extract(cfg: Config, messages: list[dict]) -> dict:
    conversation = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}：{m['content']}" for m in messages
    )
    raw = await llm.chat(
        cfg.llm, extraction_messages(conversation), json_mode=True, temperature=0.1, max_tokens=900
    )
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        data = {}
    return normalize_draft(data, conversation)
