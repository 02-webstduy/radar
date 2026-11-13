"""画像抽取的离线评测：给定对话和标准答案，量字段准确率 / 幻觉。

    .venv/bin/python scripts/eval_profile.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from radar.config import load  # noqa: E402
from radar.profile_chat import FIELDS, extract  # noqa: E402

CASES = [
    {
        "name": "求职者",
        "turns": [
            "我在做一个求职匹配的项目，卡在数据源",
            "我用 Python 和 RAG，评测不太会",
            "每周大概 10 小时，想 3 个月内找 AI 应用岗",
            "想多看 agent 和评测，不想看前端",
            "喜欢看工程博客，中文的",
        ],
        "gold": {
            "goal": "3 个月内找 AI 应用岗", "project": "求职匹配项目",
            "stack": "Python,RAG", "learning": "评测", "hours": "10",
            "interests": "agent,评测", "avoid": "前端", "format": "工程博客,中文",
        },
    },
    {
        "name": "读研/科研",
        "turns": [
            "我在准备读研，想申多模态方向",
            "做过 PyTorch 的项目，但论文复现不太会",
            "每周 20 小时左右",
            "想多看多模态和推理，不想看招聘广告",
            "喜欢看论文，英文的",
        ],
        "gold": {
            "goal": "读研,多模态", "project": "论文复现",
            "stack": "PyTorch", "learning": "论文复现", "hours": "20",
            "interests": "多模态,推理", "avoid": "招聘广告", "format": "论文,英文",
        },
    },
    {
        "name": "转岗",
        "turns": [
            "我想从后端转到 AI 应用",
            "现在在公司做内部工具，卡在没真实项目",
            "会 Java 和一点 Python",
            "每周 5 小时，想多看 agent 和系统设计，不想看算法竞赛",
            "中文博客就行",
        ],
        "gold": {
            "goal": "转 AI 应用", "project": "内部工具",
            "stack": "Java,Python", "learning": "", "hours": "5",
            "interests": "agent,系统设计", "avoid": "算法竞赛", "format": "中文博客",
        },
    },
]


def norm(text: str) -> str:
    return re.sub(r"[\s,，、;；/]+", "", str(text).lower())


def tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[,，、;；/\s]+", str(text)) if t}


def field_ok(key: str, pred: str, gold: str) -> bool:
    if not gold:
        return not pred
    if not pred:
        return False
    if key == "hours":
        pd, gd = re.findall(r"\d+", pred), re.findall(r"\d+", gold)
        return bool(pd and gd and pd[0] == gd[0])
    p, g = norm(pred), norm(gold)
    if g in p or p in g:
        return True
    gt = tokens(gold)
    if gt and all(norm(t) in p for t in gt):
        return True

    def bigrams(s: str) -> set[str]:
        return {s[i:i + 2] for i in range(len(s) - 1)}

    bg = bigrams(g)
    return bool(bg) and len(bg & bigrams(p)) / len(bg) >= 0.6


async def main() -> None:
    cfg = load()
    total = 0
    correct = 0
    hallucinated = 0
    for case in CASES:
        messages = [{"role": "user", "content": t} for t in case["turns"]]
        draft = await extract(cfg, messages)
        facts = draft["facts"]
        bad = [k for k in FIELDS if not field_ok(k, facts[k], case["gold"].get(k, ""))]
        hall = [k for k in FIELDS if facts[k] and not case["gold"].get(k)]
        good = len(FIELDS) - len(bad)
        total += len(FIELDS)
        correct += good
        hallucinated += len(hall)
        print(f"{case['name']}: {good}/{len(FIELDS)} 正确; 错: {','.join(bad) or '无'}; "
              f"臆造: {','.join(hall) or '无'}")
        for k in bad[:3]:
            print(f"   {k}: 预测={facts[k]!r} 标准={case['gold'].get(k)!r}")

    print(f"\n总字段准确率: {correct}/{total} = {correct / total:.1%}")
    print(f"臆造字段数: {hallucinated}")


if __name__ == "__main__":
    asyncio.run(main())
