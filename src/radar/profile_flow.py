"""画像问答：题目、选项、摘要、关键词派生。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import Config

_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9.+#_-]{1,}")


@dataclass(frozen=True)
class Question:
    key: str
    text: str
    hint: str = ""
    options: tuple[str, ...] = ()
    multi: bool = False


QUESTIONS: tuple[Question, ...] = (
    Question(
        "goal",
        "你现在最想达成的目标是什么？有截止时间吗？",
        "例：3 个月内拿到 AI 应用岗 offer；或做一个能写进简历的项目",
        ("3 个月内找工作", "半年内转岗", "做一个能写进简历的项目", "准备科研/读研"),
    ),
    Question(
        "project",
        "手头在做的项目是什么？现在卡在哪一步？",
        "没有项目也可以直接说「还没有」",
        ("还没有项目", "刚起步", "有 demo，缺数据", "卡在评测/部署", "快做完了"),
    ),
    Question(
        "stack",
        "你已经会的技术栈有哪些？（可多选，也可以自己补）",
        "",
        ("Python", "TypeScript", "Java", "PyTorch", "RAG", "Agent", "后端", "前端", "部署", "评测"),
        multi=True,
    ),
    Question(
        "learning",
        "最近在学什么？（1–3 个关键词）",
        "例：Agent 评测、RAG、推理部署",
        ("Agent", "RAG", "评测", "推理部署", "多模态", "系统设计"),
    ),
    Question(
        "hours",
        "每周能投入多少小时？",
        "",
        ("5", "10", "20", "40"),
    ),
    Question(
        "interests",
        "想多看到哪些主题？（可多选）",
        "",
        ("agent", "rag", "评测", "推理部署", "多模态", "数据工程", "产品"),
        multi=True,
    ),
    Question(
        "avoid",
        "哪些内容不想看？（可多选，也可以跳过）",
        "",
        ("前端", "区块链", "算法竞赛", "招聘广告", "课程推广"),
        multi=True,
    ),
    Question(
        "format",
        "偏好什么形式、什么语言？（可多选）",
        "",
        ("论文", "工程博客", "开源项目", "视频", "中文", "英文", "混合"),
        multi=True,
    ),
)

TOTAL = len(QUESTIONS)


def question_at(step: int) -> Question | None:
    return QUESTIONS[step] if 0 <= step < TOTAL else None


def _csv(value: str) -> str:
    return "、".join([x.strip() for x in str(value).split(",") if x.strip()])


def build_narrative(facts: dict) -> str:
    goal = facts.get("goal") or "还没想好目标"
    project = facts.get("project") or "还没开始项目"
    stack = _csv(facts.get("stack", "")) or "还没填"
    learning = _csv(facts.get("learning", "")) or "还没填"
    hours = facts.get("hours") or "未定"
    interests = _csv(facts.get("interests", "")) or "还没填"
    avoid = _csv(facts.get("avoid", "")) or "无"
    fmt = _csv(facts.get("format", "")) or "不限"
    return (
        f"我想{goal}。目前在{project}；会 {stack}，正在学 {learning}；"
        f"每周能投入 {hours} 小时。想多看到 {interests}，不想看 {avoid}；偏好 {fmt}。"
    )


def _split(value: str) -> list[str]:
    return [x.strip() for x in str(value).replace("，", ",").split(",") if x.strip()]


def derive_keywords(facts: dict, cfg: Config) -> list[str]:
    """关键词只从「明确字段」和「受控词表」来，避免从目标里抽出 ai/offer 这种泛词。"""
    words: list[str] = []
    for key in ("stack", "learning", "interests"):
        for token in _split(facts.get(key, "")):
            if token.lower() not in [w.lower() for w in words]:
                words.append(token)

    text = " ".join(str(facts.get(k, "")) for k in ("goal", "project", "learning")).lower()
    for keyword in cfg.profile.keywords:
        if keyword.lower() in text and keyword.lower() not in [w.lower() for w in words]:
            words.append(keyword)
    return words[:30]
