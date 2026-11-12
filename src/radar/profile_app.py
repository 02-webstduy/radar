"""画像入口：独立端口 8768，聊天/表单两种方式，结果写同一个 SQLite。"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import load
from .profile_flow import QUESTIONS, build_narrative, derive_keywords, question_at
from .storage import Store

cfg = load()
store = Store(cfg.db_path)
app = FastAPI(title=f"{cfg.name} · 画像", docs_url=None, redoc_url=None)


class AnswerIn(BaseModel):
    id: str
    answer: str = ""


class SaveIn(BaseModel):
    facts: dict[str, str]
    narrative: str = ""


def _question_payload(step: int) -> dict:
    q = question_at(step)
    if q is None:
        return {"done": True, "step": step, "total": len(QUESTIONS)}
    return {
        "done": False,
        "step": step + 1,
        "total": len(QUESTIONS),
        "question": {
            "key": q.key,
            "text": q.text,
            "hint": q.hint,
            "options": list(q.options),
            "multi": q.multi,
        },
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(cfg.web_dir / "profile.html", headers={"Cache-Control": "no-store"})


@app.get("/api/profile")
async def get_profile() -> dict:
    profile = store.get_profile()
    profile["questions"] = [q.__dict__ for q in QUESTIONS]
    return profile


@app.post("/api/profile/chat/start")
async def start_chat() -> dict:
    chat_id = uuid.uuid4().hex
    store.start_chat(chat_id)
    return {"id": chat_id, **_question_payload(0)}


@app.post("/api/profile/chat/answer")
async def answer(payload: AnswerIn) -> dict:
    chat = store.get_chat(payload.id)
    if not chat:
        raise HTTPException(status_code=404, detail="会话不存在")
    q = question_at(chat["step"])
    if q is None:
        raise HTTPException(status_code=400, detail="会话已结束")
    answers = chat["answers"]
    answers[q.key] = payload.answer.strip()
    step = chat["step"] + 1
    store.save_chat(payload.id, step, answers)
    if step >= len(QUESTIONS):
        facts = dict(answers)
        facts["keywords"] = ",".join(derive_keywords(facts, cfg))
        store.save_profile(facts, build_narrative(facts), source="chat")
        return {"done": True, "facts": facts, "narrative": build_narrative(facts)}
    return _question_payload(step)


@app.post("/api/profile/save")
async def save(payload: SaveIn) -> dict:
    facts = {k: str(v).strip() for k, v in payload.facts.items() if str(v).strip()}
    narrative = payload.narrative.strip() or build_narrative(facts)
    facts["keywords"] = ",".join(derive_keywords(facts, cfg))
    store.save_profile(facts, narrative, source="form")
    return {"ok": True, "facts": facts, "narrative": narrative}
