from __future__ import annotations

import asyncio

from .runs import Run


async def run_pipeline(run: Run, goal: str, statement: str) -> None:
    """Placeholder replaced in Task 8."""
    for i in range(3):
        await run.wait_if_paused()
        if run.stop_flag:
            break
        run.emit("reasoning", {"text": f"stub step {i}"})
        await asyncio.sleep(1)
    run.state = "stopped" if run.stop_flag else "done"
    run.emit("done", {"state": run.state, "summary": "stub complete"})
