from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

EVENT_TYPES = {
    "plan",
    "row_status",
    "reasoning",
    "action",
    "screenshot",
    "flag",
    "error",
    "done",
}


@dataclass
class Event:
    run_id: str
    seq: int
    ts: float
    type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(line: str) -> "Event":
        return Event(**json.loads(line))


class EventLog:
    """Append-only JSONL log for one run.

    This file is the single source of truth for a run. The live SSE stream,
    replay, and mid-run reconnection all read the same records, so there is
    exactly one code path to get wrong.
    """

    def __init__(self, run_id: str, root: Path) -> None:
        self.run_id = run_id
        self.dir = Path(root) / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.shots_dir = self.dir / "shots"
        self.shots_dir.mkdir(exist_ok=True)
        self.path = self.dir / "events.jsonl"
        self._seq = self._last_seq_on_disk()

    def _last_seq_on_disk(self) -> int:
        if not self.path.exists():
            return 0
        last = 0
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = json.loads(line)["seq"]
        return last

    def append(self, type: str, payload: dict[str, Any] | None = None) -> Event:
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {type}")
        self._seq += 1
        event = Event(self.run_id, self._seq, time.time(), type, payload or {})
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(event.to_json() + "\n")
        return event

    def read_from(self, from_seq: int = 0) -> Iterator[Event]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                event = Event.from_json(line)
                if event.seq > from_seq:
                    yield event
