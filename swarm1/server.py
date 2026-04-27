"""FastAPI server for swarm1 — LangGraph boardroom deliberation.

Port 8091. Tunneled to swarm1.neil.ro.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

load_dotenv(Path(__file__).parent.parent / ".env")

from app import run_deliberation

app = FastAPI(title="Swarm1 — LangGraph Boardroom")

BASE_DIR = Path(__file__).parent
SESSIONS_DIR = BASE_DIR / "sessions"
STATIC_DIR = BASE_DIR / "static"
SESSIONS_DIR.mkdir(exist_ok=True)

_sessions: dict[str, dict] = {}
_event_queues: list[asyncio.Queue] = []


def _emit(event: dict) -> None:
    event["ts"] = datetime.now(timezone.utc).isoformat()
    for q in _event_queues:
        q.put_nowait(event)


@app.get("/api/sessions")
async def list_sessions():
    sessions = []
    for d in sorted(SESSIONS_DIR.iterdir(), reverse=True):
        if d.is_dir():
            events_file = d / "events.jsonl"
            transcript_file = d / "transcript.md"
            event_count = 0
            if events_file.exists():
                with open(events_file) as f:
                    event_count = sum(1 for _ in f)
            sessions.append({
                "session_id": d.name,
                "has_transcript": transcript_file.exists(),
                "has_events": events_file.exists(),
                "event_count": event_count,
            })
    return sessions


@app.post("/api/start")
async def start_session(idea: str = Query(...), session_id: Optional[str] = Query(None)):
    sid = session_id or f"s1-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    session_dir = SESSIONS_DIR / sid
    session_dir.mkdir(parents=True, exist_ok=True)
    _sessions[sid] = {"idea": idea, "status": "running", "dir": str(session_dir)}

    async def _run():
        try:
            result = await run_deliberation(idea, sid, str(session_dir))
            _sessions[sid]["status"] = "done"
            # Replay events to SSE
            for ev in result.get("events", []):
                _emit(ev)
        except Exception as e:
            _sessions[sid]["status"] = f"error: {e}"
            _emit({"type": "error", "message": str(e), "session_id": sid})
        finally:
            _emit({"type": "session_done", "session_id": sid})

    asyncio.create_task(_run())
    return JSONResponse({"session_id": sid, "status": "started"})


@app.get("/api/events")
async def stream_events(request: Request):
    from starlette.requests import Request
    async def _generate():
        q: asyncio.Queue = asyncio.Queue()
        _event_queues.append(q)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield {"data": json.dumps(event), "event": "message"}
                except asyncio.TimeoutError:
                    yield {"data": json.dumps({"type": "heartbeat"}), "event": "message"}
        finally:
            if q in _event_queues:
                _event_queues.remove(q)

    return EventSourceResponse(_generate())


@app.get("/api/session/{sid}")
async def get_session(sid: str):
    session_dir = SESSIONS_DIR / sid
    if not session_dir.exists():
        return JSONResponse({"error": "not found"}, status_code=404)

    events = []
    events_file = session_dir / "events.jsonl"
    if events_file.exists():
        with open(events_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))

    transcript = None
    if (session_dir / "transcript.md").exists():
        with open(session_dir / "transcript.md", encoding="utf-8") as f:
            transcript = f.read()

    return {"session_id": sid, "events": events, "transcript": transcript}


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SWARM1_PORT", "8091"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")