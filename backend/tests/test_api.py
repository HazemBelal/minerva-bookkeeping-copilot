"""Real coverage of the HTTP/control surface and the SSE resume logic.

Control endpoints (create/pause/resume/stop) are hit through the actual
FastAPI app via httpx's ASGITransport (in-process, no sockets, no mocks) --
the same code path a browser would drive.

The SSE reconnect/dedup test drives the real `stream_run` route function and
its real generator directly rather than through the full ASGI dispatch. That
is a deliberate, narrow exception: sse_starlette's EventSourceResponse spins
up its own concurrent `_listen_for_disconnect` task that also calls
`receive()`, and under httpx.ASGITransport that collides with this app's own
`request.is_disconnected()` call on the same channel and hangs forever (a
harness/library interaction, confirmed independent of this app's code --
`request.is_disconnected()` alone, with a single reader, never hangs; add
sse_starlette's second concurrent reader and it always does, reproduced with
a minimal FastAPI app with no application code at all). None of the logic
under test here -- the disk catch-up loop, the live queue, the dedup fix --
lives in sse_starlette; it is entirely inside the `generator()` closure this
test drives, so calling the route function directly and iterating its
`body_iterator` still exercises 100% real production code, just without the
ASGI header/framing plumbing (which is library code, already verified
end-to-end by hand against a real uvicorn server).
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from starlette.requests import Request

import app.main as main_module
from app.main import app
from app.runs import RunStore


def _fresh_store(tmp_path, monkeypatch, **kwargs) -> RunStore:
    """Give each test an isolated RunStore so runs/rate-limit state never
    leaks between tests (the module-level `store` in app.main is a shared
    global otherwise)."""
    store = RunStore(tmp_path, **kwargs)
    monkeypatch.setattr(main_module, "store", store)
    return store


async def _stub_pipeline(run, goal, statement):
    """Fast, deterministic double for the real `run_pipeline` (Task 8 wires
    it up to a live LLM planner and a real browser researcher). The
    pause/stop tests below exercise the control-endpoint <-> Run plumbing
    (pause_event, stop_flag, the global run lock) -- not orchestrator
    internals -- so they swap this in rather than depending on Ollama/a
    browser being up, or waiting minutes for a real research pass. This is
    the same shape as the pre-Task-8 orchestrator stub the tests were
    originally written against.
    """
    for i in range(3):
        await run.wait_if_paused()
        if run.stop_flag:
            break
        run.emit("reasoning", {"text": f"stub step {i}"})
        await asyncio.sleep(1)
    run.state = "stopped" if run.stop_flag else "done"
    run.emit("done", {"state": run.state, "summary": "stub complete"})


async def _never_resolving_receive():
    await asyncio.sleep(10_000)
    return {"type": "http.request"}  # pragma: no cover - never reached


def _fake_request(headers: dict[str, str] | None = None) -> Request:
    """A minimal real Starlette Request for calling route functions directly.

    Its `receive` never resolves, which is exactly what `is_disconnected()`
    needs to correctly report "not disconnected" without ever blocking (it
    wraps the receive call in an already-cancelled anyio scope) -- this is
    the same non-blocking pattern a real, still-connected client produces.
    """
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {"type": "http", "headers": raw_headers, "method": "GET", "path": "/sse/runs/x"}
    return Request(scope, receive=_never_resolving_receive)


async def _drain_seqs(body_iterator, max_events: int, per_item_timeout: float = 1.0) -> list[int]:
    """Pull up to `max_events` real event seq numbers out of the generator,
    stopping early if nothing new arrives within `per_item_timeout`."""
    seqs: list[int] = []
    try:
        while len(seqs) < max_events:
            item = await asyncio.wait_for(body_iterator.__anext__(), timeout=per_item_timeout)
            data = item.get("data")
            if not data:
                continue
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            if "seq" in payload:
                seqs.append(payload["seq"])
    except (asyncio.TimeoutError, StopAsyncIteration):
        pass
    return seqs


@pytest.mark.asyncio
async def test_reconnect_stream_does_not_double_deliver_a_racing_emit(tmp_path, monkeypatch):
    """Regression test for Finding I1.

    `stream_run` subscribes to the live queue BEFORE draining the on-disk
    backlog. Each `yield sse_frame(event)` in that backlog loop is a real
    await point, so if a new event is emitted while the backlog loop is
    still running, it lands in BOTH the disk (picked up by the still-open
    `read_from` iteration) and the live queue (already subscribed) --
    without de-duplication that is a genuine double delivery.

    We force this deterministically (no flaky timing) by monkeypatching
    `sse_frame`, the exact synchronous formatting step the backlog loop
    calls right before each yield, to emit a second event on its first
    invocation -- simulating the orchestrator racing in mid-catchup.
    """
    store = _fresh_store(tmp_path, monkeypatch)
    run = store.create("race1")
    run.emit("reasoning", {"text": "already on disk"})  # seq 1

    original_sse_frame = main_module.sse_frame
    injected = {"done": False}

    def sse_frame_with_race(event):
        frame = original_sse_frame(event)
        if not injected["done"] and event.seq == 1:
            injected["done"] = True
            # Simulate the orchestrator emitting seq 2 while we are still
            # mid-way through yielding seq 1 back over the wire.
            run.emit("reasoning", {"text": "raced in during catchup"})  # seq 2
        return frame

    monkeypatch.setattr(main_module, "sse_frame", sse_frame_with_race)

    resp = await main_module.stream_run(run_id="race1", request=_fake_request(), from_seq=0)
    # Ask for up to 3 events: [1, 2] is correct; a pre-fix server also sends
    # a duplicate 2 as a 3rd frame with no extra delay (it was already
    # sitting in the queue), so a short per-item timeout is enough to catch
    # it without waiting out the 15s ping.
    seqs = await _drain_seqs(resp.body_iterator, max_events=3, per_item_timeout=1.0)

    assert seqs[:2] == [1, 2], f"expected normal delivery of seq 1 then 2, got {seqs}"
    assert len(seqs) == len(set(seqs)), f"seq delivered more than once: {seqs}"


@pytest.mark.asyncio
async def test_pause_blocks_progress_and_resume_continues(tmp_path, monkeypatch):
    """Drives pause/resume through real ASGI HTTP calls to the control
    endpoints. Execution itself is launched via our own asyncio.Task rather
    than `POST /api/runs`: under httpx.ASGITransport, Starlette runs
    `BackgroundTasks` inline as part of the same coroutine `client.post()`
    awaits (there's no real socket to decouple "response sent" from "server
    keeps working" the way a live uvicorn process does), so awaiting the
    create call would not return until the whole ~3s stub run had already
    finished -- too late to pause or stop anything. This still exercises the
    real Run/RunStore/orchestrator concurrency under test (the pause_event,
    the stop_flag, the global lock); only the control endpoints go over real
    ASGI HTTP, which is where Findings I1/I2's actual HTTP-surface risk
    lives.
    """
    store = _fresh_store(tmp_path, monkeypatch)
    monkeypatch.setattr("app.orchestrator.run_pipeline", _stub_pipeline)
    run = store.create("pause-run")
    task = asyncio.create_task(main_module._execute(run, "test", "s"))
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Let the stub emit its first step, then pause.
            await asyncio.sleep(0.4)
            pause_resp = await client.post(f"/api/runs/{run.id}/pause")
            assert pause_resp.json() == {"ok": True, "state": "paused"}

            # While paused, the second stub step must not appear for a while.
            await asyncio.sleep(1.5)
            texts_while_paused = [e.payload.get("text", "") for e in run.log.read_from(0)]
            assert not any(
                "stub step 1" in t for t in texts_while_paused
            ), "run progressed while paused"
            assert any("Paused by the user" in t for t in texts_while_paused)

            resume_resp = await client.post(f"/api/runs/{run.id}/resume")
            assert resume_resp.json() == {"ok": True, "state": "running"}

        await asyncio.wait_for(task, timeout=5)
    finally:
        if not task.done():
            task.cancel()

    assert run.state == "done"
    types = [e.type for e in run.log.read_from(0)]
    assert types[-1] == "done"
    all_texts = [e.payload.get("text", "") for e in run.log.read_from(0)]
    assert any("stub step 1" in t for t in all_texts)
    assert any("stub step 2" in t for t in all_texts)


@pytest.mark.asyncio
async def test_stop_short_circuits_the_run(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch)
    monkeypatch.setattr("app.orchestrator.run_pipeline", _stub_pipeline)
    run = store.create("stop-run")
    task = asyncio.create_task(main_module._execute(run, "test", "s"))
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await asyncio.sleep(0.4)
            stop_resp = await client.post(f"/api/runs/{run.id}/stop")
            assert stop_resp.status_code == 200

        await asyncio.wait_for(task, timeout=5)
    finally:
        if not task.done():
            task.cancel()

    assert run.state == "stopped"
    texts = [e.payload.get("text", "") for e in run.log.read_from(0)]
    # Stop cut the loop short after the first step -- steps 1 and 2 never ran.
    assert not any("stub step 1" in t for t in texts)
    assert not any("stub step 2" in t for t in texts)
    types = [e.type for e in run.log.read_from(0)]
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_fourth_run_within_the_hour_returns_429(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch, runs_per_ip_per_hour=3)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Under ASGITransport, request.client.host is always "127.0.0.1".
        for _ in range(3):
            assert store.rate_limit_ok("127.0.0.1") is True

        resp = await client.post("/api/runs", json={"goal": "test", "statement": "s"})

    assert resp.status_code == 429
    assert "Rate limit reached" in resp.json()["detail"]
