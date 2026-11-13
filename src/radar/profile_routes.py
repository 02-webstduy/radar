"""画像页面与接口：自由聊天 → 抽取 → 用户确认；表单作为备用入口。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import llm
from .profile_chat import GREETING, SYSTEM, extract, is_ready
from .profile_flow import QUESTIONS, build_narrative, derive_keywords
from .runtime import cfg, store

router = APIRouter()

MAX_TURNS = 12


class SendIn(BaseModel):
    id: str
    text: str


class DraftIn(BaseModel):
    id: str


class SaveIn(BaseModel):
    facts: dict[str, str]
    narrative: str = ""


@router.get("/profile")
async def profile_page() -> FileResponse:
    return FileResponse(cfg.web_dir / "profile.html", headers={"Cache-Control": "no-store"})


@router.get("/api/profile")
async def get_profile() -> dict:
    profile = store.get_profile()
    profile["questions"] = [q.__dict__ for q in QUESTIONS]
    return profile


@router.post("/api/profile/chat/start")
async def start_chat() -> dict:
    chat_id = uuid.uuid4().hex
    store.start_chat(chat_id)
    store.add_message(chat_id, "assistant", GREETING)
    return {"id": chat_id, "reply": GREETING}


@router.post("/api/profile/chat/send")
async def send(payload: SendIn) -> dict:
    if not store.chat_exists(payload.id):
        raise HTTPException(status_code=404, detail="会话不存在")
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="空消息")

    store.add_message(payload.id, "user", text)
    messages = store.get_messages(payload.id, limit=24)
    turns = sum(1 for m in messages if m["role"] == "user")

    if is_ready(text, turns) or turns >= MAX_TURNS:
        reply = "好，我来整理画像。"
        store.add_message(payload.id, "assistant", reply)
        try:
            draft = await extract(cfg, store.get_messages(payload.id, limit=50))
        except llm.LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"reply": reply, "ready": True, "draft": draft}

    convo = [{"role": "system", "content": SYSTEM}] + messages[-16:]
    try:
        reply = await llm.chat(cfg.llm, convo, temperature=0.7, max_tokens=300)
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    reply = reply.strip()
    store.add_message(payload.id, "assistant", reply)
    return {"reply": reply, "ready": False}


@router.post("/api/profile/draft")
async def draft(payload: DraftIn) -> dict:
    if not store.chat_exists(payload.id):
        raise HTTPException(status_code=404, detail="会话不存在")
    try:
        return await extract(cfg, store.get_messages(payload.id, limit=50))
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/api/profile/save")
async def save(payload: SaveIn) -> dict:
    facts = {k: str(v).strip() for k, v in payload.facts.items() if str(v).strip()}
    narrative = payload.narrative.strip() or build_narrative(facts)
    facts["keywords"] = ",".join(derive_keywords(facts, cfg))
    store.save_profile(facts, narrative, source="chat")
    return {"ok": True, "facts": facts, "narrative": narrative}
