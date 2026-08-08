from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .events import Event, EventLog


@dataclass
class Run:
    id: str
    log: EventLog
    state: str = "queued"  # queued | running | paused | stopped | done | error
    rows: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None
    stop_flag: bool = False
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    _subs: set[asyncio.Queue] = field(default_factory=set)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def emit(self, type: str, payload: dict[str, Any] | None = None) -> Event:
        event = self.log.append(type, payload)
        for q in list(self._subs):
            q.put_nowait(event)
        return event

    async def wait_if_paused(self) -> None:
        await self.pause_event.wait()

    @property
    def finished(self) -> bool:
        return self.state in {"stopped", "done", "error"}


class RunStore:
    def __init__(self, root: Path, runs_per_ip_per_hour: int = 3) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs: dict[str, Run] = {}
        self.lock = asyncio.Lock()
        self.runs_per_ip_per_hour = runs_per_ip_per_hour
        self._ip_hits: dict[str, list[float]] = {}

    def rate_limit_ok(self, ip: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        hits = [t for t in self._ip_hits.get(ip, []) if now - t < 3600]
        if len(hits) >= self.runs_per_ip_per_hour:
            self._ip_hits[ip] = hits
            return False
        hits.append(now)
        self._ip_hits[ip] = hits
        return True

    def create(self, run_id: str | None = None) -> Run:
        rid = run_id or uuid.uuid4().hex[:12]
        run = Run(id=rid, log=EventLog(rid, self.root))
        run.pause_event.set()  # set means "not paused"
        self.runs[rid] = run
        return run

    def get(self, run_id: str) -> Run | None:
        return self.runs.get(run_id)

    def load(self, run_id: str) -> Run | None:
        """Rehydrate a completed run from disk so replay survives a restart."""
        if run_id in self.runs:
            return self.runs[run_id]
        if not (self.root / run_id / "events.jsonl").exists():
            return None
        run = Run(id=run_id, log=EventLog(run_id, self.root), state="done")
        run.pause_event.set()
        self.runs[run_id] = run
        return run
