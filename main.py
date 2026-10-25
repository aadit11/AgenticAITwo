"""FastAPI entrypoint.

Serves static/ and POST /api/chat as a Server-Sent Events stream.
The server does not store history. The browser sends it on each request.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.graph import invoke_graph
from app.publish import bind_sink, reset_sink
from tools.chroma_retriever import corpus_count

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"

app = FastAPI()


class HistoryTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str
    history: list[HistoryTurn] = Field(default_factory=list)


def _frame(kind: str, payload: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "chroma_count": corpus_count(),
        "providers_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip())
        and bool(os.environ.get("GOOGLE_API_KEY", "").strip()),
    }


@app.post("/api/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    history = [turn.model_dump() for turn in body.history]

    async def frames():
        yield ": ping\n\n"
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        sentinel = object()

        def sink(kind: str, payload: dict) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, (kind, payload))

        def run() -> None:
            token = bind_sink(sink)
            try:
                invoke_graph(query, history)
            finally:
                reset_sink(token)
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        worker = asyncio.create_task(asyncio.to_thread(run))
        try:
            while True:
                item = await queue.get()
                if item is sentinel:
                    break
                kind, payload = item
                yield _frame(kind, payload)
            await worker
        except Exception as exc:
            yield _frame(
                "error",
                {
                    "agent": "graph",
                    "message": f"{type(exc).__name__}; the failure was recovered",
                    "recovered": True,
                },
            )
        yield _frame("done", {})

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="assets")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="site")
