import pytest
from app.events import Event, EventLog


def test_append_assigns_incrementing_seq(tmp_path):
    log = EventLog("run1", tmp_path)
    a = log.append("reasoning", {"text": "first"})
    b = log.append("action", {"name": "click"})
    assert (a.seq, b.seq) == (1, 2)
    assert a.run_id == "run1"
    assert a.payload == {"text": "first"}


def test_append_rejects_unknown_type(tmp_path):
    log = EventLog("run1", tmp_path)
    with pytest.raises(ValueError):
        log.append("not_a_real_type", {})


def test_read_from_returns_only_events_after_seq(tmp_path):
    log = EventLog("run1", tmp_path)
    for i in range(5):
        log.append("reasoning", {"i": i})
    seqs = [e.seq for e in log.read_from(2)]
    assert seqs == [3, 4, 5]


def test_read_from_survives_a_fresh_log_object(tmp_path):
    EventLog("run1", tmp_path).append("done", {"ok": True})
    reopened = EventLog("run1", tmp_path)
    events = list(reopened.read_from(0))
    assert len(events) == 1
    assert events[0].type == "done"
