"""FastAPI dashboard for Boardroom War Game.

Provides:
- SSE endpoint for real-time structured events (tails events.jsonl)
- REST API to start sessions
- Static HTML dashboard
- File browser for artifacts
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Boardroom Dashboard")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

# Active sessions: session_id -> {status, idea, started_at, events_path}
_sessions: Dict[str, Dict[str, Any]] = {}

# Event queue for SSE broadcasting
_event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_dir(session_id: str) -> Path:
    return Path(os.getenv("BOARDROOM_OUTPUT_DIR", "./boardroom")) / session_id


async def _tail_events(sid: str, events_path: Path) -> None:
    """Tail events.jsonl and broadcast to SSE queue."""
    last_size = 0

    # Wait for the file to appear (up to 30s)
    for _ in range(60):
        if events_path.exists():
            break
        if sid not in _sessions:
            return
        await asyncio.sleep(0.5)

    while True:
        if sid not in _sessions:
            break
        if _sessions[sid]["status"] in ("completed", "failed"):
            # Keep tailing for a few more seconds then exit
            for _ in range(5):
                if events_path.exists() and events_path.stat().st_size > last_size:
                    with events_path.open("r", encoding="utf-8") as f:
                        f.seek(last_size)
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    evt = json.loads(line)
                                    await _event_queue.put(evt)
                                except json.JSONDecodeError:
                                    pass
                        last_size = f.tell()
                await asyncio.sleep(1)
            break

        if events_path.exists():
            current_size = events_path.stat().st_size
            if current_size > last_size:
                with events_path.open("r", encoding="utf-8") as f:
                    f.seek(last_size)
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                evt = json.loads(line)
                                await _event_queue.put(evt)
                            except json.JSONDecodeError:
                                pass
                    last_size = f.tell()
        await asyncio.sleep(0.5)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Serve the main dashboard HTML."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="Dashboard not built")


@app.get("/api/sessions")
async def list_sessions() -> List[Dict[str, Any]]:
    """List all completed / running sessions."""
    out = []
    root = Path(os.getenv("BOARDROOM_OUTPUT_DIR", "./boardroom"))
    if root.exists():
        for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
            if d.is_dir():
                info = {"session_id": d.name, "dir": str(d)}
                transcript = d / "transcript.md"
                if transcript.exists():
                    info["has_transcript"] = True
                memos = list((d / "memos").glob("*.md")) if (d / "memos").exists() else []
                info["memo_count"] = len(memos)
                events = d / "events.jsonl"
                if events.exists():
                    info["has_events"] = True
                out.append(info)
    return out


@app.post("/api/start")
async def start_session(
    idea: str,
    rounds: int = 1,
    session_id: Optional[str] = None,
    mock: bool = False,
    fast: bool = False,
) -> JSONResponse:
    """Start a boardroom simulation."""
    sid = session_id or f"dash-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    session_dir = _session_dir(sid)
    session_dir.mkdir(parents=True, exist_ok=True)
    events_path = session_dir / "events.jsonl"
    _sessions[sid] = {
        "status": "running",
        "idea": idea,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "events_path": str(events_path),
    }

    # Fire subprocess
    asyncio.create_task(_run_session(sid, idea, rounds, mock, fast))
    # Fire event tailer
    asyncio.create_task(_tail_events(sid, events_path))

    return JSONResponse({"session_id": sid, "status": "started"})


async def _run_session(sid: str, idea: str, rounds: int, mock: bool = False, fast: bool = False) -> None:
    """Run main.py in a subprocess."""
    _event_queue.put_nowait({
        "type": "session_start",
        "session_id": sid,
        "idea": idea,
        "ts": datetime.now(timezone.utc).isoformat()
    })

    env = os.environ.copy()
    env["BOARDROOM_OUTPUT_DIR"] = os.getenv("BOARDROOM_OUTPUT_DIR", "./boardroom")

    cmd = [sys.executable, "main.py", "--idea", idea, "--rounds", str(rounds), "--session-id", sid]
    if mock:
        cmd.append("--mock")
    if fast:
        cmd.append("--fast")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
        cwd=Path(__file__).parent,
    )

    # Also stream stdout as raw log events for backward compat
    while proc.stdout is not None and proc.returncode is None:
        try:
            chunk = await asyncio.wait_for(proc.stdout.read(4096), timeout=1.0)
        except asyncio.TimeoutError:
            # No new stdout this second — check if process is still alive
            if proc.returncode is not None:
                break
            continue
        if not chunk:
            break
        text = chunk.decode("utf-8", errors="ignore")
        await _event_queue.put({
            "type": "log",
            "session_id": sid,
            "data": text,
            "ts": datetime.now(timezone.utc).isoformat()
        })

    # Ensure process finishes (may already be done)
    if proc.returncode is None:
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
    _sessions[sid]["status"] = "completed" if proc.returncode == 0 else "failed"
    await _event_queue.put({
        "type": "session_end",
        "session_id": sid,
        "status": _sessions[sid]["status"],
        "ts": datetime.now(timezone.utc).isoformat()
    })


# ---------------------------------------------------------------------------
# SSE
# ---------------------------------------------------------------------------

@app.get("/api/events")
async def events() -> None:
    """SSE endpoint for real-time events."""
    from fastapi.responses import StreamingResponse

    async def _generator():
        while True:
            try:
                evt = await asyncio.wait_for(_event_queue.get(), timeout=30)
                data = json.dumps(evt, ensure_ascii=False)
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

    return StreamingResponse(_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

@app.get("/api/file/{session_id}/{filename:path}")
async def get_file(session_id: str, filename: str) -> FileResponse:
    target = _session_dir(session_id) / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)


@app.get("/api/session/{session_id}")
async def session_detail(session_id: str) -> Dict[str, Any]:
    d = _session_dir(session_id)
    if not d.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    files: Dict[str, str] = {}
    if (d / "transcript.md").exists():
        files["transcript"] = (d / "transcript.md").read_text(encoding="utf-8")
    memos = {}
    if (d / "memos").exists():
        for f in (d / "memos").glob("*.md"):
            memos[f.name] = f.read_text(encoding="utf-8")
    if (d / "RESOLUTION.md").exists():
        files["resolution"] = (d / "RESOLUTION.md").read_text(encoding="utf-8")
    if (d / "SNAPSHOT.json").exists():
        files["snapshot"] = (d / "SNAPSHOT.json").read_text(encoding="utf-8")

    # Also return events for replay
    events = []
    if (d / "events.jsonl").exists():
        with (d / "events.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    return {"session_id": session_id, "files": files, "memos": memos, "events": events}


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    # Use port 8089 (avoid conflict with Docker on 8085)
    uvicorn.run(app, host="0.0.0.0", port=8089)
