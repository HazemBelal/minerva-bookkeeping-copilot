"""Real coverage of `run_pipeline`'s own concurrency/pause/stop/cap logic.

`test_api.py`'s pause/stop tests monkeypatch the WHOLE `run_pipeline` with a
hand-rolled stub to test the HTTP control-endpoint <-> Run plumbing -- by
design they exercise zero lines of the real orchestrator. These tests fill
that gap: they monkeypatch ONLY the two external calls the orchestrator
makes (`plan_merchants`, `research_merchant`) with controllable async
stubs, then run the REAL `run_pipeline` against a real `Run`, so a
regression in the semaphore, the `wait_if_paused()` placement, the
merchant-cap slice, or the stop-sweep loop would actually fail a test here.

No live LLM, no live browser -- every stub returns instantly or after a
short `asyncio.sleep`.
"""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

import app.orchestrator as orchestrator_module
from app.orchestrator import run_pipeline
from app.planner import MerchantPlan
from app.researcher import VendorFinding
from app.runs import RunStore


def _plan(key: str, needs_research: bool) -> MerchantPlan:
    return MerchantPlan(
        key=key,
        display=key.upper(),
        needs_research=needs_research,
        category="Uncategorized",
        confidence="low",
        reason="test plan",
    )


def _merchant_names(n: int) -> list[str]:
    """`n` distinct two-word merchant keys, deliberately digit-free.

    statement.py's real `merchant_key()` drops any token containing a digit
    (it treats them as store numbers/invoice ids) -- so a naive "merchant 0"
    / "merchant 1" naming scheme would collapse every one of these test
    merchants onto the single key "merchant". Letters instead of digits
    keep each name distinct after the real collapsing logic runs.
    """
    letters = "abcdefghij"
    assert n <= len(letters)
    return [f"merchant {letters[i]}" for i in range(n)]


def _statement_for(keys: list[str]) -> str:
    """One row per key, in a shape `parse_statement`'s real merchant_key()
    collapses right back to `key` -- plain lowercase words, no digits/
    punctuation/processor-prefix tokens -- so the fake planner (keyed by
    merchant_key) lines up with the real rows the pipeline builds.
    """
    lines = [f"2026-07-01, {key.upper()}, -10.00" for key in keys]
    return "\n".join(lines)


@pytest.mark.asyncio
async def test_run_pipeline_never_exceeds_configured_concurrency(tmp_path, monkeypatch):
    keys = _merchant_names(5)
    plans = [_plan(k, needs_research=True) for k in keys]

    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def fake_plan_merchants(txns, goal):
        return plans

    async def fake_research_merchant(key, display, on_event, shots_dir):
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        async with lock:
            active -= 1
        return VendorFinding(merchant=display, what_they_do="x", category="Uncategorized", confidence="low")

    monkeypatch.setattr(orchestrator_module, "plan_merchants", fake_plan_merchants)
    monkeypatch.setattr(orchestrator_module, "research_merchant", fake_research_merchant)

    run = RunStore(tmp_path).create("concurrency-run")
    await asyncio.wait_for(run_pipeline(run, "goal", _statement_for(keys)), timeout=5)

    assert max_active <= orchestrator_module.settings.concurrency
    assert max_active == 2, "expected the run to actually reach the 2-concurrent limit, not just stay under it"
    assert all(row["status"] == "done" for row in run.rows)
    assert run.state == "done"


@pytest.mark.asyncio
async def test_run_pipeline_stop_flag_sweeps_remaining_rows_to_needs_review(tmp_path, monkeypatch):
    keys = _merchant_names(4)
    plans = [_plan(k, needs_research=True) for k in keys]

    call_count = 0

    async def fake_plan_merchants(txns, goal):
        # Deterministic stop: flip stop_flag the moment planning finishes,
        # before any research task has a chance to acquire the semaphore.
        # This exercises exactly the code path under test -- the stop-sweep
        # loop that marks pending/researching rows needs_review -- without
        # a timing-based race against real concurrency.
        run.stop_flag = True
        return plans

    async def fake_research_merchant(key, display, on_event, shots_dir):
        nonlocal call_count
        call_count += 1  # should never be reached once stop_flag is set
        return VendorFinding(merchant=display, what_they_do="x", category="Uncategorized", confidence="low")

    monkeypatch.setattr(orchestrator_module, "plan_merchants", fake_plan_merchants)
    monkeypatch.setattr(orchestrator_module, "research_merchant", fake_research_merchant)

    run = RunStore(tmp_path).create("stop-run")
    await asyncio.wait_for(run_pipeline(run, "goal", _statement_for(keys)), timeout=5)

    assert call_count == 0, "research_merchant must not run once stop_flag is set"
    assert run.state == "stopped"
    assert all(row["status"] == "needs_review" for row in run.rows)
    assert all("stopped by the user" in (row["note"] or "").lower() for row in run.rows)

    done_events = [e for e in run.log.read_from(0) if e.type == "done"]
    assert len(done_events) == 1
    assert done_events[0].payload["state"] == "stopped"


@pytest.mark.asyncio
async def test_run_pipeline_enforces_the_merchant_cap(tmp_path, monkeypatch):
    keys = _merchant_names(4)
    plans = [_plan(k, needs_research=True) for k in keys]
    researched: list[str] = []

    async def fake_plan_merchants(txns, goal):
        return plans

    async def fake_research_merchant(key, display, on_event, shots_dir):
        researched.append(key)
        return VendorFinding(merchant=display, what_they_do="x", category="Uncategorized", confidence="low")

    monkeypatch.setattr(orchestrator_module, "plan_merchants", fake_plan_merchants)
    monkeypatch.setattr(orchestrator_module, "research_merchant", fake_research_merchant)
    # Settings is a frozen dataclass; patch the name the orchestrator module
    # actually reads (its own `settings` global) with a small cap so the
    # test doesn't need 9+ merchants to exercise the cap.
    capped_settings = dataclasses.replace(orchestrator_module.settings, max_merchants=2)
    monkeypatch.setattr(orchestrator_module, "settings", capped_settings)

    run = RunStore(tmp_path).create("cap-run")
    await asyncio.wait_for(run_pipeline(run, "goal", _statement_for(keys)), timeout=5)

    assert len(researched) == 2, "only the first `max_merchants` should ever reach research_merchant"
    by_key = {row["merchant_key"]: row for row in run.rows}
    done_keys = {k for k, r in by_key.items() if r["status"] == "done"}
    capped_keys = {k for k, r in by_key.items() if r["status"] == "needs_review"}

    assert done_keys == set(researched)
    assert capped_keys == {row["merchant_key"] for row in run.rows} - done_keys
    assert len(capped_keys) == 2
    for key in capped_keys:
        assert "cap" in by_key[key]["note"].lower()
        assert "2" in by_key[key]["note"]


@pytest.mark.asyncio
async def test_run_pipeline_marks_failed_research_as_needs_review(tmp_path, monkeypatch):
    plans = [_plan("flaky merchant", needs_research=True)]

    async def fake_plan_merchants(txns, goal):
        return plans

    async def fake_research_merchant(key, display, on_event, shots_dir):
        return None  # the researcher's own documented "couldn't verify" contract

    monkeypatch.setattr(orchestrator_module, "plan_merchants", fake_plan_merchants)
    monkeypatch.setattr(orchestrator_module, "research_merchant", fake_research_merchant)

    run = RunStore(tmp_path).create("failed-research-run")
    await asyncio.wait_for(run_pipeline(run, "goal", _statement_for(["flaky merchant"])), timeout=5)

    row = next(r for r in run.rows if r["merchant_key"] == "flaky merchant")
    assert row["status"] == "needs_review"
    assert row["note"]
    assert "could not verify" in row["note"].lower()
    assert run.state == "done"  # a single failed merchant is not a fatal run


@pytest.mark.asyncio
async def test_run_pipeline_holds_research_while_paused(tmp_path, monkeypatch):
    """Covers the `await run.wait_if_paused()` placement inside `work()`:
    nothing should reach `research_merchant` while paused, and progress
    should resume as soon as the run is unpaused."""
    keys = _merchant_names(2)
    plans = [_plan(k, needs_research=True) for k in keys]
    call_count = 0

    async def fake_plan_merchants(txns, goal):
        return plans

    async def fake_research_merchant(key, display, on_event, shots_dir):
        nonlocal call_count
        call_count += 1
        return VendorFinding(merchant=display, what_they_do="x", category="Uncategorized", confidence="low")

    monkeypatch.setattr(orchestrator_module, "plan_merchants", fake_plan_merchants)
    monkeypatch.setattr(orchestrator_module, "research_merchant", fake_research_merchant)

    run = RunStore(tmp_path).create("pause-run")
    run.pause_event.clear()  # paused before the pipeline even starts

    task = asyncio.create_task(run_pipeline(run, "goal", _statement_for(keys)))
    try:
        await asyncio.sleep(0.05)
        assert call_count == 0, "research_merchant must not run while paused"
        assert all(row["status"] == "pending" for row in run.rows)

        run.pause_event.set()  # resume
        await asyncio.wait_for(task, timeout=5)
    finally:
        if not task.done():
            task.cancel()

    assert call_count == 2
    assert run.state == "done"
    assert all(row["status"] == "done" for row in run.rows)
