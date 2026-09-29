# -*- coding: utf-8 -*-
"""FastAPI 服务：把 Agent 包成 HTTP 接口，用 SSE（Server-Sent Events）流式返回。"""

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import Agent

app = FastAPI(title="My Agent Backend")

# 允许前端（Vite dev server）跨域访问；上线时请收紧为你的域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = Agent()


class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role": "user", "content": "..."}, ...]


@app.get("/api/health")
def health():
    return {"status": "ok", "mock": agent.is_mock, "model": "mock" if agent.is_mock else None}


@app.post("/api/chat")
def chat(req: ChatRequest):
    def event_gen():
        for ev in agent.chat_stream(req.messages):
            # 标准 SSE 格式：data: {json}\n\n
            yield f"data: {ev}\n\n"
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(event_gen(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
