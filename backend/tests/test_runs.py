from app.runs import RunStore


def test_emit_writes_to_the_log_and_fans_out(tmp_path):
    store = RunStore(tmp_path)
    run = store.create("r1")
    q = run.subscribe()
    run.emit("reasoning", {"text": "hello"})
    assert q.qsize() == 1
    assert list(run.log.read_from(0))[0].payload == {"text": "hello"}


def test_rate_limit_allows_up_to_the_cap_then_blocks(tmp_path):
    store = RunStore(tmp_path, runs_per_ip_per_hour=3)
    assert [store.rate_limit_ok("1.2.3.4", now=100 + i) for i in range(4)] == [
        True, True, True, False,
    ]


def test_rate_limit_window_expires(tmp_path):
    store = RunStore(tmp_path, runs_per_ip_per_hour=1)
    assert store.rate_limit_ok("1.2.3.4", now=0) is True
    assert store.rate_limit_ok("1.2.3.4", now=100) is False
    assert store.rate_limit_ok("1.2.3.4", now=4000) is True


def test_rate_limit_is_per_ip(tmp_path):
    store = RunStore(tmp_path, runs_per_ip_per_hour=1)
    assert store.rate_limit_ok("1.1.1.1", now=0) is True
    assert store.rate_limit_ok("2.2.2.2", now=0) is True


def test_load_rehydrates_a_finished_run_from_disk(tmp_path):
    store = RunStore(tmp_path)
    store.create("r1").emit("done", {"summary": "ok"})
    fresh = RunStore(tmp_path)
    assert fresh.get("r1") is None
    loaded = fresh.load("r1")
    assert loaded is not None
    assert [e.type for e in loaded.log.read_from(0)] == ["done"]


def test_load_returns_none_for_an_unknown_run(tmp_path):
    assert RunStore(tmp_path).load("nope") is None
