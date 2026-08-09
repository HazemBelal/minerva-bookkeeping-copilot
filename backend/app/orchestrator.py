from __future__ import annotations

import asyncio

from .anomalies import FLAG_LABELS, find_anomalies
from .config import settings
from .planner import plan_merchants
from .researcher import research_merchant
from .runs import Run
from .statement import parse_statement


async def run_pipeline(run: Run, goal: str, statement: str) -> None:
    """Parse -> plan -> research (2 concurrent, capped) -> anomalies -> done.

    Every step streams to `run.emit`. Per-merchant failures degrade to a
    `needs_review` row (never fabricated data, never a silent drop); only
    truly fatal errors (e.g. an exception here itself) propagate to the
    caller in main.py, which reports them and still emits `done`.
    """
    run.emit("reasoning", {"text": "Reading the statement."})
    txns = parse_statement(statement)
    if not txns:
        run.emit("error", {"message": "No transactions found in that text.", "fatal": True})
        run.state = "error"
        run.emit("done", {"state": "error", "summary": "Nothing to categorize"})
        return

    run.rows = [
        {
            "id": t.id,
            "date": t.date,
            "description": t.description,
            "amount": t.amount,
            "merchant_key": t.merchant_key,
            "status": "pending",
            "category": None,
            "merchant": None,
            "confidence": None,
            "source_url": None,
            "source": None,
            "reasoning": None,
            "note": None,
        }
        for t in txns
    ]

    run.emit("reasoning", {"text": f"Found {len(txns)} transactions. Planning."})
    plans = await plan_merchants(txns, goal)

    to_research = [p for p in plans if p.needs_research]
    skipped = to_research[settings.max_merchants :]
    to_research = to_research[: settings.max_merchants]
    known = [p for p in plans if not p.needs_research]

    run.emit(
        "plan",
        {
            "rows": run.rows,
            "goal": goal,
            "research_count": len(to_research),
            "known_count": len(known),
            "text": (
                f"{len(txns)} transactions across {len(plans)} merchants. "
                f"{len(known)} recognised without browsing, "
                f"{len(to_research)} need live research."
            ),
        },
    )

    for plan in known:
        _apply(run, plan.key, {
            "status": "done",
            "merchant": plan.display,
            "category": plan.category,
            "confidence": plan.confidence,
            "source": "model",
            "reasoning": plan.reason,
        })

    for plan in skipped:
        _apply(run, plan.key, {
            "status": "needs_review",
            "note": f"Merchant cap of {settings.max_merchants} reached for this run",
        })

    semaphore = asyncio.Semaphore(settings.concurrency)

    async def work(plan) -> None:
        # The ENTIRE body is guarded, not just the research_merchant call:
        # asyncio.gather() below has no return_exceptions=True, so if any
        # exception escaped this coroutine (e.g. run.emit/_apply raising
        # under disk pressure), gather would propagate it immediately
        # without cancelling sibling in-flight research tasks. Those
        # orphaned tasks would keep running and could append row_status/
        # reasoning events to the log AFTER main.py's fatal-exception
        # handler has already emitted `done` -- and /sse/replay has no
        # done-break guard, so a post-done event would corrupt replay
        # (including the golden run). Catching everything here means
        # gather() always completes normally and `done` is only ever
        # emitted after every research task has truly finished.
        try:
            async with semaphore:
                await run.wait_if_paused()
                if run.stop_flag:
                    return
                _apply(run, plan.key, {"status": "researching"})
                run.emit("reasoning", {"merchant_key": plan.key, "text": f"Researching {plan.display}."})
                try:
                    finding = await research_merchant(
                        plan.key, plan.display, run.emit, run.log.shots_dir
                    )
                except Exception as exc:  # noqa: BLE001 - reported, never swallowed
                    run.emit(
                        "error",
                        {"merchant_key": plan.key, "message": f"{type(exc).__name__}: {exc}", "fatal": False},
                    )
                    finding = None

                if finding is None:
                    _apply(run, plan.key, {
                        "status": "needs_review",
                        "note": (
                            f"Could not verify this merchant within "
                            f"{settings.max_steps_per_merchant} browser steps"
                        ),
                    })
                    return

                _apply(run, plan.key, {
                    "status": "done",
                    "merchant": finding.merchant,
                    "category": finding.category,
                    "confidence": finding.confidence,
                    "source_url": finding.source_url or None,
                    "source": "web",
                    "reasoning": finding.reasoning or finding.what_they_do,
                })
        except Exception as exc:  # noqa: BLE001 - must never escape gather()
            # Best-effort report-and-degrade. Wrapped again: if run.emit/
            # _apply themselves are what failed above, this recovery path
            # must not raise a second time and defeat the whole point.
            try:
                run.emit(
                    "error",
                    {"merchant_key": plan.key, "message": f"{type(exc).__name__}: {exc}", "fatal": False},
                )
                _apply(run, plan.key, {
                    "status": "needs_review",
                    "note": "Unexpected error while researching this merchant",
                })
            except Exception:  # noqa: BLE001 - genuinely nothing more we can do
                pass

    await asyncio.gather(*(work(p) for p in to_research))

    if run.stop_flag:
        for row in run.rows:
            if row["status"] in {"pending", "researching"}:
                _apply(run, row["merchant_key"], {
                    "status": "needs_review",
                    "note": "Run stopped by the user before this merchant was researched",
                })

    flags = find_anomalies(run.rows)
    for flag in flags:
        run.emit("flag", {
            "code": flag.code,
            "row_ids": flag.row_ids,
            "label": FLAG_LABELS.get(flag.code, flag.code),
            "detail": flag.detail,
        })

    unresolved = sum(1 for r in run.rows if r["status"] == "needs_review")
    run.state = "stopped" if run.stop_flag else "done"
    run.emit(
        "done",
        {
            "state": run.state,
            "summary": (
                f"{len(run.rows)} transactions categorized, "
                f"{len(flags)} flag(s) raised, "
                f"{unresolved} row(s) need review."
            ),
            "rows": run.rows,
        },
    )


def _apply(run: Run, merchant_key: str, patch: dict) -> None:
    """Update every row sharing this merchant key and mirror it to the stream."""
    for row in run.rows:
        if row["merchant_key"] == merchant_key:
            row.update(patch)
    run.emit("row_status", {"merchant_key": merchant_key, **patch})
