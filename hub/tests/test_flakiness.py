"""Unit tests for flakiness.analyse — domain logic only."""
from flakiness import analyse


def _run(ts, p, f, flaky=0):
    return {"project_id": "p1", "step": "tests", "ts": ts, "pass": p, "fail": f, "flaky": flaky}


def test_empty_history_is_unknown():
    r = analyse([])
    assert r["verdict"] == "unknown"
    assert r["runs_in_window"] == 0


def test_stable_when_every_run_passes():
    runs = [_run(f"2026-04-{i:02d} 08:00", 10, 0) for i in range(1, 10)]
    r = analyse(runs)
    assert r["verdict"] == "stable"
    assert r["failed_runs"] == 0
    assert r["pass_rate_tests"] == 100.0


def test_warn_band_when_fail_rate_5_to_20_pct():
    # 20 runs, 1 failure = 5% failure rate → warn
    runs = [_run(f"ts-{i}", 10, 0) for i in range(19)] + [_run("ts-fail", 8, 2)]
    r = analyse(runs)
    assert r["verdict"] == "warn"
    assert r["fail_rate_pct"] == 5.0


def test_flaky_when_fail_rate_exceeds_threshold():
    # 4 failures out of 10 = 40% → flaky (interleave so broken rule doesn't fire first)
    runs = []
    for i in range(4):
        runs.append(_run(f"pass-a-{i}", 10, 0))
        runs.append(_run(f"fail-{i}",    5, 5))
    runs.extend(_run(f"pass-b-{i}", 10, 0) for i in range(2))
    r = analyse(runs)
    assert r["verdict"] == "flaky"
    assert r["fail_rate_pct"] == 40.0


def test_broken_when_last_three_runs_fail():
    runs = [_run(f"pass-{i}", 10, 0) for i in range(5)] + [_run(f"fail-{i}", 0, 10) for i in range(3)]
    r = analyse(runs)
    assert r["verdict"] == "broken"
    assert "last 3 consecutive runs all failed" in r["verdict_reason"]


def test_window_limits_runs_analysed():
    runs = [_run(f"pass-{i}", 10, 0) for i in range(50)]
    r = analyse(runs, window=10)
    assert r["runs_in_window"] == 10


def test_fail_clusters_detected():
    runs = [
        _run("ok-1",  10, 0),
        _run("f-1",    0, 10),
        _run("f-2",    0, 10),
        _run("ok-2",  10, 0),
        _run("f-3",    0, 10),
        _run("ok-3",  10, 0),
    ]
    r = analyse(runs)
    lengths = sorted(c["length"] for c in r["fail_clusters"])
    assert lengths == [1, 2]  # one 2-run streak + one isolated


def test_flaky_counter_triggers_flaky_verdict():
    # 20 runs all pass but flaky counter > 0 in 3 of them (15%) → flaky
    runs = [_run(f"ts-{i}", 10, 0, flaky=1 if i < 3 else 0) for i in range(20)]
    r = analyse(runs)
    assert r["verdict"] == "flaky"
    assert "flaky counter non-zero" in r["verdict_reason"]


def test_last_status_reflects_newest_run():
    runs_pass_last = [_run("f-1", 0, 10), _run("ok", 10, 0)]
    assert analyse(runs_pass_last)["last_status"] == "pass"
    runs_fail_last = [_run("ok", 10, 0), _run("f-1", 0, 10)]
    assert analyse(runs_fail_last)["last_status"] == "fail"


# ── Flask integration — /api/flakiness ─────────────────────────────────────

def test_api_flakiness_missing_p_returns_400(client):
    r = client.get("/api/flakiness")
    assert r.status_code == 400


def test_api_flakiness_for_mock_project_returns_shape(client):
    r = client.get("/api/flakiness?p=_mock-full")
    assert r.status_code == 200
    d = r.get_json()
    for key in ("verdict", "verdict_reason", "runs_in_window", "fail_clusters",
                "pass_rate_tests", "project_id"):
        assert key in d
    assert d["project_id"] == "_mock-full"
    assert d["verdict"] in ("stable", "warn", "flaky", "broken", "unknown")
