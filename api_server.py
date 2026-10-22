"""FastAPI Web 服务：聊天接口（同步 + SSE 流式）+ 会话管理 + 静态前端"""

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chat_service import run_chat, run_chat_stream
from memory import SessionStore

app = FastAPI(title="SmartVoyage 旅游智能体")

app.mount("/static", StaticFiles(directory="static"), name="static")

store = SessionStore()


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        return run_chat(req.session_id, req.message)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_source():
        async for evt in run_chat_stream(req.session_id, req.message):
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@app.get("/api/sessions")
def list_sessions():
    return {"sessions": store.list_sessions()}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    messages = store.get_session(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session_id": session_id, "messages": messages}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    store.delete_session(session_id)
    return {"ok": True}