"""FastAPI server for swarm1 — Dynamic Swarm Boardroom deliberation.

Port 8091. Tunneled to swarm1.neil.ro.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_llm import EventEmitter, HumanSessionStore, get_session, resume_human, HumanGate
from orchestrator import run_deliberation

app = FastAPI(title="Swarm1 — Dynamic Swarm Boardroom")

BASE_DIR = Path(__file__).parent
SESSIONS_DIR = BASE_DIR / "sessions"
STATIC_DIR = BASE_DIR / "static"
SESSIONS_DIR.mkdir(exist_ok=True)

_emitter = EventEmitter()
_store = HumanSessionStore()
_sessions: dict[str, dict] = {}


# ============================================================================
# Human-in-the-loop API
# ============================================================================

@app.post("/api/deliberations")
async def create_deliberation(
    topic: str = Query(...),
    user_role: str = Query(...),
    output_expectations: str = Query(""),
    swarm_type: str = Query("dynamic"),
):
    """Create a new human-in-the-loop deliberation session."""
    session = _store.create(topic, user_role, output_expectations, swarm_type)
    return JSONResponse(session.to_dict())


@app.get("/api/deliberations/{sid}")
async def get_deliberation(sid: str):
    session = _store.get(sid)
    if not session:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(session.to_dict())


@app.post("/api/deliberations/{sid}/start")
async def start_deliberation(sid: str):
    session = _store.get(sid)
    if not session:
        return JSONResponse({"error": "not found"}, status_code=404)
    if session.status == "complete":
        return JSONResponse({"error": "already complete"}, status_code=409)

    session_dir = SESSIONS_DIR / sid
    session_dir.mkdir(parents=True, exist_ok=True)

    async def _run():
        events_path = session_dir / "events.jsonl"
        q = _emitter.subscribe()
        try:
            async def _write_events():
                with open(events_path, "a", encoding="utf-8") as f:
                    while True:
                        try:
                            event = await asyncio.wait_for(q.get(), timeout=0.5)
                            f.write(json.dumps(event) + "\n")
                            f.flush()
                        except asyncio.TimeoutError:
                            s = _store.get(sid)
                            if not s or s.status == "complete":
                                break
            writer_task = asyncio.create_task(_write_events())
            session.status = "running"
            await run_deliberation(
                session.topic, sid, str(session_dir),
                emitter=_emitter,
                human_session=session,
            )
            session.status = "complete"
            await asyncio.sleep(1)
            writer_task.cancel()
        except Exception as e:
            session.status = f"error: {e}"
            _emitter.emit({"type": "error", "message": str(e), "session_id": sid})
        finally:
            _emitter.unsubscribe(q)

    asyncio.create_task(_run())
    return JSONResponse({"status": "started"})


@app.get("/api/deliberations/{sid}/stream")
async def stream_deliberation(sid: str, request: Request):
    async def _generate():
        q = _emitter.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    event["session_id"] = sid
                    yield {"data": json.dumps(event), "event": "message"}
                except asyncio.TimeoutError:
                    yield {"data": json.dumps({"type": "heartbeat"}), "event": "message"}
        finally:
            _emitter.unsubscribe(q)
    return EventSourceResponse(_generate())


@app.post("/api/deliberations/{sid}/respond")
async def respond_deliberation(sid: str, gate_id: str = Query(...), response_text: str = Query(...)):
    session = _store.get(sid)
    if not session:
        return JSONResponse({"error": "not found"}, status_code=404)
    if session.status != "awaiting_human":
        return JSONResponse({"error": "not awaiting human", "status": session.status}, status_code=409)
    gate = session.pending_gate
    if not gate or gate.gate_id != gate_id:
        return JSONResponse({"error": "gate_id mismatch"}, status_code=409)
    ok = await resume_human(sid, gate_id, response_text)
    if not ok:
        return JSONResponse({"error": "resume failed"}, status_code=500)
    return JSONResponse({"status": "running"})


# ============================================================================
# Legacy API (non-human-in-the-loop, backwards-compatible)
# ============================================================================


@app.get("/api/sessions")
async def list_sessions():
    sessions = []
    for d in sorted(SESSIONS_DIR.iterdir(), reverse=True):
        if d.is_dir():
            events_file = d / "events.jsonl"
            has_events = events_file.exists()
            has_transcript = (d / "transcript.md").exists()
            event_count = 0
            if has_events:
                with open(events_file) as f:
                    event_count = sum(1 for _ in f)
            sessions.append({
                "session_id": d.name,
                "has_transcript": has_transcript,
                "has_events": has_events,
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
        events_path = session_dir / "events.jsonl"
        q = _emitter.subscribe()
        try:
            async def _write_events():
                with open(events_path, "a", encoding="utf-8") as f:
                    while True:
                        try:
                            event = await asyncio.wait_for(q.get(), timeout=0.5)
                            f.write(json.dumps(event) + "\n")
                            f.flush()
                        except asyncio.TimeoutError:
                            if _sessions.get(sid, {}).get("status") == "done":
                                break
            writer_task = asyncio.create_task(_write_events())
            await run_deliberation(idea, sid, str(session_dir), emitter=_emitter)
            _sessions[sid]["status"] = "done"
            await asyncio.sleep(1)
            writer_task.cancel()
        except Exception as e:
            _sessions[sid]["status"] = f"error: {e}"
        finally:
            _emitter.unsubscribe(q)

    asyncio.create_task(_run())
    return JSONResponse({"session_id": sid, "status": "started"})


@app.get("/api/events")
async def stream_events(request: Request):
    async def _generate():
        q = _emitter.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield {"data": json.dumps(event), "event": "message"}
                except asyncio.TimeoutError:
                    yield {"data": json.dumps({"type": "heartbeat"}), "event": "message"}
        finally:
            _emitter.unsubscribe(q)

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
                line = line.strip()
                if line:
                    events.append(json.loads(line))

    transcript = None
    transcript_file = session_dir / "transcript.md"
    if transcript_file.exists():
        with open(transcript_file, encoding="utf-8") as f:
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