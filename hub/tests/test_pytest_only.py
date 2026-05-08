"""Integration tests for pytest-only project type.

Uses the live registered desktop-automation / mobile-automation projects
under C:\\Automation\\internal\\. Tests are read-only against the running
hub fixture.
"""


def test_pytest_only_appears_in_projects_list(client):
    r = client.get("/api/projects")
    assert r.status_code == 200
    types = {p["id"]: p["type"] for p in r.get_json()}
    # Both pytest-only repos should be registered
    assert types.get("desktop-automation") == "pytest-only"
    assert types.get("mobile-automation") == "pytest-only"


def test_release_gate_pytest_only_has_6_criteria(client):
    r = client.get("/api/release-gate?p=desktop-automation")
    assert r.status_code == 200
    d = r.get_json()
    assert d["project_type"] == "pytest-only"
    assert d["summary"]["total"] == 6
    crit_ids = {c["id"] for c in d["criteria"]}
    assert "test_executed" in crit_ids
    assert "run_scope" in crit_ids
    assert "pass_rate" in crit_ids
    assert "no_critical_bug" in crit_ids
    assert "no_high_bug" in crit_ids
    assert "has_screenshots" in crit_ids
    # Must NOT have the TS-Playwright-specific HTML report criterion
    assert "pw_report_ready" not in crit_ids


def test_release_gate_pytest_only_planning_skipped(client):
    """mobile-automation has phase=planning → gate verdict = SKIP_PLANNING."""
    r = client.get("/api/release-gate?p=mobile-automation")
    assert r.status_code == 200
    d = r.get_json()
    assert d["project_type"] == "pytest-only"
    assert d["phase"] == "planning"
    assert d["verdict"] == "SKIP_PLANNING"
    assert d["go"] is False


def test_status_pytest_only_only_returns_relevant_stages(client):
    r = client.get("/api/status?p=desktop-automation")
    assert r.status_code == 200
    d = r.get_json()
    # All stages present in shape (frontend depends on them)
    for s in ("s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9"):
        assert s in d
    # Stages 1-4, 6 are always not-ok for pytest-only (no Excel TCM)
    assert d["s1"]["ok"] is False
    assert d["s2"]["ok"] is False
    assert d["s4"]["ok"] is False


def test_run_log_accepts_pytest_only_project(client):
    """Logging a run for a pytest-only project succeeds and appends history."""
    payload = {
        "project_id": "desktop-automation",
        "step":       "tests",
        "pass":       1,
        "fail":       0,
        "tag":        "smoke",
        "env":        "uat",
        "rc":         0,
    }
    r = client.post("/api/run/log", json=payload)
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    ts = body["ts"]

    h = client.get("/api/run/history?p=desktop-automation").get_json()
    assert any(e["ts"] == ts and e["pass"] == 1 and e["tag"] == "smoke" for e in h)

    # Cleanup
    client.post("/api/run/history/delete",
                json={"project_id": "desktop-automation", "ts": ts})


def test_info_pytest_only_includes_pw_keys(client):
    """/api/info for pytest-only exposes the pw_* keys the dashboard expects."""
    r = client.get("/api/info?p=desktop-automation")
    assert r.status_code == 200
    d = r.get_json()
    assert d["project_meta"]["type"] == "pytest-only"
    assert "pw_report_ok" in d
    if d.get("pw_history"):
        assert "pw_last" in d
        assert {"pass", "fail", "total", "pct", "tag", "ts"} <= set(d["pw_last"].keys())
