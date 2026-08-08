from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from .config import settings

app = FastAPI(title="Bookkeeping Copilot")

app.mount("/shots", StaticFiles(directory=settings.runs_dir), name="shots")


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": settings.openai_model}


@app.get("/sse/demo")
async def sse_demo() -> EventSourceResponse:
    """Temporary stream used to prove the nginx and Docker path end to end.

    Replaced by the real run stream in Task 4. Kept until then so the
    deployment in Task 3 has something concrete to verify.
    """

    async def generator():
        for seq in range(1, 1000):
            yield {
                "id": str(seq),
                "event": "message",
                "data": (
                    '{"run_id":"demo","seq":%d,"ts":%f,'
                    '"type":"reasoning","payload":{"text":"tick %d"}}'
                    % (seq, time.time(), seq)
                ),
            }
            await asyncio.sleep(1)

    return EventSourceResponse(generator())
