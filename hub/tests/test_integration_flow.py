"""End-to-end flow tests — the kind of regression a new contributor would
cause if they touched the shared paths: log a run, read history, see the
release gate change, validate every registered project.

All tests clean up after themselves so they can run against a live
run_history.json without polluting it.
"""


# ── Projects registry round-trip ────────────────────────────────────────────

def test_every_registered_project_has_valid_release_gate(client, hub):
    """Every project in /api/projects should return a well-formed gate response."""
    projects = client.get("/api/projects").get_json()
    assert projects, "no projects registered — cannot validate"

    for p in projects:
        pid = p["id"]
        r = client.get(f"/api/release-gate?p={pid}")
        # Either 200 (gate computed) or 404 (path missing) — both are valid
        # outcomes; we only fail if the endpoint crashes with 500.
        assert r.status_code in (200, 404), f"{pid} returned {r.status_code}"
        if r.status_code == 200:
            d = r.get_json()
            assert d["project_id"] == pid
            assert d["project_type"] in ("full-pipeline", "manual-testing", "playwright-only", "pytest-only")
            assert d["verdict"] in ("GO", "NOGO", "NOT_READY", "SKIP_PLANNING", "SKIP_PAUSED")
            assert isinstance(d["go"], bool)


# ── Run log + history round-trip ────────────────────────────────────────────

def _cleanup_run(client, project_id, ts):
    """Remove a run entry by (project_id, ts). Safe to call multiple times."""
    client.post("/api/run/history/delete", json={"project_id": project_id, "ts": ts})


def test_run_log_appends_to_history_and_can_be_deleted(client):
    """Logging a run adds it to history; deleting it removes it."""
    pid = "_mock-full"
    payload = {"project_id": pid, "step": "tests", "pass": 7, "fail": 0, "tag": "smoke", "env": "uat"}

    # Capture history length before
    before = client.get(f"/api/run/history?p={pid}").get_json()
    before_len = len(before)

    # Log the run
    r = client.post("/api/run/log", json=payload)
    assert r.status_code == 200
    logged = r.get_json()
    assert logged.get("ok") is True
    ts = logged.get("ts")
    assert ts, "expected response to include the new entry's ts"

    try:
        # History should have grown by exactly one entry
        after = client.get(f"/api/run/history?p={pid}").get_json()
        assert len(after) == before_len + 1

        # The new entry should match what we logged — history is returned
        # in insertion order (oldest-first within the last-50 window)
        newest = after[-1]
        assert newest["project_id"] == pid
        assert newest["pass"] == 7 and newest["fail"] == 0
        assert newest["tag"] == "smoke"
        assert newest["env"] == "uat"
    finally:
        _cleanup_run(client, pid, ts)

    # Cleanup verified
    final = client.get(f"/api/run/history?p={pid}").get_json()
    assert len(final) == before_len


def test_run_log_rejects_missing_project_id(client):
    """POST without project_id is a client error, not a silent accept."""
    r = client.post("/api/run/log", json={"step": "tests", "pass": 1, "fail": 0})
    assert r.status_code == 400


# ── Release gate reacts to new run data ─────────────────────────────────────

def test_logging_a_passing_run_flips_pass_rate_criterion(client):
    """After logging a clean pass, the pass_rate gate criterion should be satisfied."""
    pid = "_mock-full"

    # Log a clearly-passing run
    payload = {"project_id": pid, "step": "tests", "pass": 20, "fail": 0, "tag": "e2e", "env": "uat"}
    r = client.post("/api/run/log", json=payload)
    assert r.status_code == 200
    ts = r.get_json()["ts"]

    try:
        gate = client.get(f"/api/release-gate?p={pid}").get_json()
        pass_crit = next((c for c in gate["criteria"] if c["id"] == "pass_rate"), None)
        assert pass_crit is not None
        assert pass_crit["ok"] is True
        assert pass_crit["warn"] is False
    finally:
        _cleanup_run(client, pid, ts)


# ── Release gate endpoint contract (CI-facing) ──────────────────────────────

# ── Hub health endpoint (Session B 1.3) ───────────────────────────────────

def test_hub_health_returns_full_shape(client):
    r = client.get("/api/hub/health")
    assert r.status_code == 200
    d = r.get_json()
    for key in ("started_at", "uptime_seconds", "errors_last_hour",
                "warnings_last_hour", "active_schedules", "registered_projects",
                "log_sizes_kb", "recent_audit", "auth_enabled", "python"):
        assert key in d, f"missing health key: {key}"
    assert d["uptime_seconds"] >= 0
    assert isinstance(d["log_sizes_kb"], dict)
    for k in ("hub_log", "audit_jsonl", "schedule_log"):
        assert k in d["log_sizes_kb"]
    assert isinstance(d["recent_audit"], list)


def test_hub_health_recent_audit_capped_at_5(client):
    d = client.get("/api/hub/health").get_json()
    assert len(d["recent_audit"]) <= 5


# ── Per-schedule notify_on (Session B 2.2) ───────────────────────────────

def test_schedule_add_rejects_non_list_notify_on(client):
    payload = {
        "project_id":    "_mock-full",
        "action":        "tests",
        "schedule_type": "daily",
        "time":          "09:00",
        "notify_on":     "all",  # wrong type — must be list
    }
    r = client.post("/api/schedules/add", json=payload)
    assert r.status_code == 400


def test_schedule_add_accepts_notify_on_list_and_round_trips(client):
    """notify_on field on a schedule should persist and come back via /api/schedules."""
    payload = {
        "project_id":    "_mock-full",
        "action":        "tests",
        "tag":           "@smoke",
        "env":           "uat",
        "schedule_type": "daily",
        "time":          "09:00",
        "notify_on":     ["error"],
    }
    sid = None
    try:
        r = client.post("/api/schedules/add", json=payload)
        assert r.status_code == 200
        sid = r.get_json()["id"]
        # Read back via /api/schedules
        all_scheds = client.get("/api/schedules").get_json()
        match = next((s for s in all_scheds if s["id"] == sid), None)
        assert match is not None
        assert match.get("notify_on") == ["error"]
    finally:
        if sid:
            client.post("/api/schedules/delete", json={"id": sid})


# ── Notification settings endpoints (Session A 1.1) ───────────────────────

def test_notifications_get_returns_default_shape(client):
    r = client.get("/api/config/notifications")
    assert r.status_code == 200
    d = r.get_json()
    for key in ("slack_webhook", "teams_webhook", "discord_webhook", "notify_on"):
        assert key in d
    assert isinstance(d["notify_on"], list)


def test_notifications_save_round_trips(client):
    payload = {
        "slack_webhook":   "https://hooks.slack.com/services/T/B/X",
        "teams_webhook":   "",
        "discord_webhook": "",
        "notify_on":       ["fail", "error"],
    }
    try:
        r = client.post("/api/config/notifications/save", json=payload)
        assert r.status_code == 200 and r.get_json()["ok"] is True
        # Read back
        d = client.get("/api/config/notifications").get_json()
        assert d["slack_webhook"] == payload["slack_webhook"]
        assert d["notify_on"] == ["fail", "error"]
    finally:
        # Reset to empty so test pollution doesn't break local config
        client.post("/api/config/notifications/save", json={
            "slack_webhook": "", "teams_webhook": "", "discord_webhook": "",
            "notify_on": ["fail", "error"],
        })


def test_notifications_save_rejects_non_list_notify_on(client):
    r = client.post("/api/config/notifications/save", json={"notify_on": "all"})
    assert r.status_code == 400


# ── Audit endpoint (Session A 1.2) ────────────────────────────────────────

def test_audit_endpoint_returns_entries_shape(client):
    r = client.get("/api/audit?limit=10")
    assert r.status_code == 200
    d = r.get_json()
    assert "entries" in d and isinstance(d["entries"], list)
    assert "count" in d
    assert d["count"] == len(d["entries"])
    assert len(d["entries"]) <= 10


def test_audit_endpoint_filter_by_action_prefix(client):
    """Filter narrows the result to matching action prefixes."""
    r = client.get("/api/audit?action=project.&limit=50")
    assert r.status_code == 200
    d = r.get_json()
    for e in d["entries"]:
        assert e["action"].startswith("project."), f"non-matching action leaked: {e['action']}"


def test_audit_endpoint_clamps_limit(client):
    """Out-of-range limits are clamped, not rejected."""
    r = client.get("/api/audit?limit=999999")
    assert r.status_code == 200
    assert len(r.get_json()["entries"]) <= 1000


# ── BasicAuth gate (opt-in via HUB_PASSWORD env var) ───────────────────────

def test_auth_disabled_by_default_when_no_env_var(client, hub, monkeypatch):
    """Without HUB_PASSWORD set (the session default), requests go through
    unauthenticated — matches pre-auth behaviour."""
    monkeypatch.setattr(hub, "HUB_PASSWORD", "")
    r = client.get("/api/projects")
    assert r.status_code == 200


def test_auth_required_when_hub_password_set(client, hub, monkeypatch):
    """With HUB_PASSWORD set, unauthenticated requests get 401 + WWW-Authenticate."""
    monkeypatch.setattr(hub, "HUB_PASSWORD", "s3cret")
    r = client.get("/api/projects")
    assert r.status_code == 401
    assert "Basic" in r.headers.get("WWW-Authenticate", "")


def test_auth_accepts_correct_basic_header(client, hub, monkeypatch):
    """Correct Basic auth header lets the request through."""
    import base64
    monkeypatch.setattr(hub, "HUB_PASSWORD", "s3cret")
    monkeypatch.setattr(hub, "HUB_USERNAME", "hub")
    cred = base64.b64encode(b"hub:s3cret").decode()
    r = client.get("/api/projects", headers={"Authorization": f"Basic {cred}"})
    assert r.status_code == 200


def test_auth_rejects_wrong_password(client, hub, monkeypatch):
    import base64
    monkeypatch.setattr(hub, "HUB_PASSWORD", "s3cret")
    cred = base64.b64encode(b"hub:WRONG").decode()
    r = client.get("/api/projects", headers={"Authorization": f"Basic {cred}"})
    assert r.status_code == 401


def test_static_assets_bypass_auth(client, hub, monkeypatch):
    """Static files must stay fetchable even with auth on, otherwise the
    dashboard can't bootstrap."""
    monkeypatch.setattr(hub, "HUB_PASSWORD", "s3cret")
    r = client.get("/static/app.css")
    assert r.status_code == 200


# ── API-wide error shape contract ──────────────────────────────────────────

def test_api_404_returns_structured_json(client):
    """Any /api/* path that doesn't resolve should return {error, detail}, not HTML."""
    r = client.get("/api/definitely-not-a-route")
    assert r.status_code == 404
    assert r.is_json
    d = r.get_json()
    assert d["error"] == "not found"
    assert "/api/definitely-not-a-route" in d["detail"]


def test_api_405_returns_structured_json(client):
    """Wrong method on a known endpoint returns structured error."""
    r = client.get("/api/run/log")  # POST-only
    assert r.status_code == 405
    assert r.is_json
    d = r.get_json()
    assert d["error"] == "method not allowed"
    assert "GET" in d["detail"]


def test_non_api_404_still_returns_html(client):
    """Browser users on bogus paths still get the friendly HTML 404."""
    r = client.get("/not-a-page")
    assert r.status_code == 404
    # Not JSON — Flask's default HTML page
    assert not r.is_json or r.get_json().get("error") != "not found"


def test_release_gate_response_is_ci_parseable(client):
    """CI pipelines will parse this — shape must stay stable."""
    r = client.get("/api/release-gate?p=_mock-full")
    assert r.status_code == 200
    d = r.get_json()

    # Top-level contract
    for key in ("project_id", "project_type", "phase", "verdict", "go", "criteria", "summary", "thresholds"):
        assert key in d, f"missing top-level key: {key}"

    # Summary counts are coherent — every criterion falls into exactly one bucket
    s = d["summary"]
    assert s["total"] == len(d["criteria"])
    assert s["total"] == s["pass"] + s["warn"] + s["hard_fail"]

    # go and hard_fail agree
    assert d["go"] == (s["hard_fail"] == 0)
