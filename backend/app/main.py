from __future__ import annotations

import asyncio

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .config import settings
from .events import Event
from .llm import MODEL as LLM_MODEL
from .runs import Run, RunStore

app = FastAPI(title="Bookkeeping Copilot")
store = RunStore(settings.runs_dir, settings.runs_per_ip_per_hour)

app.mount("/shots", StaticFiles(directory=settings.runs_dir), name="shots")

REPLAY_SPEED = 4.0
MAX_GAP_SECONDS = 1.5


class RunRequest(BaseModel):
    goal: str = Field(default="Categorize these transactions.", max_length=500)
    statement: str = Field(max_length=20000)


def sse_frame(event: Event) -> dict:
    return {"id": str(event.seq), "event": "message", "data": event.to_json()}


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "model": LLM_MODEL,
        "provider": settings.llm_base_url,
        "busy": store.lock.locked(),
    }


@app.post("/api/runs")
async def create_run(
    body: RunRequest, request: Request, background: BackgroundTasks
) -> JSONResponse:
    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    # Check "busy" before consuming a rate-limit unit: a 409 means no run was
    # created, so it must not cost the caller part of their hourly quota.
    if store.lock.locked():
        raise HTTPException(
            409, "The agent is busy with another run. Watch the saved run, or try again shortly."
        )
    if not store.rate_limit_ok(ip):
        raise HTTPException(
            429,
            f"Rate limit reached: {settings.runs_per_ip_per_hour} runs per hour. "
            "You can still replay the saved run.",
        )
    run = store.create()
    background.add_task(_execute, run, body.goal, body.statement)
    return JSONResponse({"run_id": run.id}, status_code=201)


async def _execute(run: Run, goal: str, statement: str) -> None:
    from .orchestrator import run_pipeline  # imported late; implemented in Task 8

    async with store.lock:
        try:
            run.state = "running"
            await run_pipeline(run, goal, statement)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, never swallowed
            run.state = "error"
            run.emit("error", {"message": f"{type(exc).__name__}: {exc}", "fatal": True})
            run.emit("done", {"state": "error", "summary": "Run failed"})


@app.post("/api/runs/{run_id}/{action}")
async def control(run_id: str, action: str) -> dict:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(404, "No such run")
    if action == "stop":
        run.stop_flag = True
        run.pause_event.set()
        run.emit("reasoning", {"text": "Stop requested by the user. Finishing the current step."})
    elif action == "pause":
        run.pause_event.clear()
        run.state = "paused"
        run.emit("reasoning", {"text": "Paused by the user."})
    elif action == "resume":
        run.pause_event.set()
        run.state = "running"
        run.emit("reasoning", {"text": "Resumed by the user."})
    else:
        raise HTTPException(400, f"Unknown action: {action}")
    return {"ok": True, "state": run.state}


@app.get("/sse/runs/{run_id}")
async def stream_run(run_id: str, request: Request, from_seq: int = 0) -> EventSourceResponse:
    run = store.get(run_id) or store.load(run_id)
    if run is None:
        raise HTTPException(404, "No such run")

    last_event_id = request.headers.get("last-event-id")
    start = max(from_seq, int(last_event_id) if last_event_id else 0)

    async def generator():
        queue = run.subscribe()
        try:
            # Catch up from disk first so a reload or reconnect loses nothing.
            # This loop awaits on every yield (socket write), so the orchestrator
            # can emit() into the live queue while we're still draining disk —
            # track the highest seq we've sent and skip anything <= it below,
            # so a race here produces no duplicate, only a redundant queue item.
            last_seq = start
            for event in run.log.read_from(start):
                yield sse_frame(event)
                last_seq = event.seq
            if run.finished:
                return
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                if event.seq <= last_seq:
                    continue
                last_seq = event.seq
                yield sse_frame(event)
                if event.type == "done":
                    break
        finally:
            run.unsubscribe(queue)

    return EventSourceResponse(generator())


@app.get("/sse/replay/{run_id}")
async def replay_run(run_id: str, request: Request) -> EventSourceResponse:
    run = store.load(run_id)
    if run is None:
        raise HTTPException(404, "No saved run with that id")

    async def generator():
        previous_ts: float | None = None
        for event in run.log.read_from(0):
            if previous_ts is not None:
                gap = min((event.ts - previous_ts) / REPLAY_SPEED, MAX_GAP_SECONDS)
                if gap > 0:
                    await asyncio.sleep(gap)
            previous_ts = event.ts
            if await request.is_disconnected():
                break
            yield sse_frame(event)

    return EventSourceResponse(generator())


@app.get("/api/runs/latest")
async def latest_saved_run() -> dict:
    """The run the landing page offers for instant replay."""
    golden = settings.runs_dir / "golden" / "events.jsonl"
    if golden.exists():
        return {"run_id": "golden"}
    candidates = sorted(
        (p.parent.name for p in settings.runs_dir.glob("*/events.jsonl")),
        reverse=True,
    )
    return {"run_id": candidates[0] if candidates else None}
