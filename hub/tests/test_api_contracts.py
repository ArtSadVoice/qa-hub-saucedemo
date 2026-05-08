"""API contract tests — pin the JSON shape of every endpoint the Vue v2
frontend reads. Catches the field-name drift class of bug that broke
Dashboard StatsRow, System Check, Bug Tracker update, and several others
during the v2.0.0 audit.

Each test asserts:
  • Required keys exist (missing → frontend renders dashes / placeholders)
  • Each key's value type is the expected primitive (str / int / bool / list)
  • Nested structures expose their own required keys

Tests do NOT pin exact values — counts / project ids vary in dev. They
pin the **shape** so that renaming a field server-side fails CI.
"""
import pytest


# ── helpers ─────────────────────────────────────────────────────────────

def _has_keys(obj: dict, *keys: str):
    """Assert obj is a dict and contains every key in `keys`. Returns the
    list of missing keys for clearer pytest output."""
    assert isinstance(obj, dict), f"expected dict, got {type(obj).__name__}"
    missing = [k for k in keys if k not in obj]
    assert not missing, f"missing keys: {missing} (got: {sorted(obj.keys())})"


def _types(obj: dict, **expected: type):
    """Assert each key in `expected` has the listed type. Allows None for
    Optional fields by passing (type, type(None)) tuples."""
    for key, want in expected.items():
        if key not in obj:
            continue
        got = obj[key]
        assert isinstance(got, want), (
            f"{key}: expected {want}, got {type(got).__name__} (value={got!r})"
        )


# ── /api/projects ───────────────────────────────────────────────────────

def test_contract_api_projects(client):
    """/api/projects returns enriched project list. Frontend reads:
    id, name, path, type, phase, color, exists, has_xlsx, has_docx,
    screenshot_count, last_run, company, category."""
    r = client.get("/api/projects")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list) and data, "expected non-empty project list"

    for p in data:
        # Required core fields — frontend treats absence as fatal
        _has_keys(p, "id", "name", "path", "type")
        # Enriched fields — frontend renders as "—" or hides if missing
        _has_keys(p, "exists", "has_xlsx", "has_docx", "screenshot_count")

        _types(p,
               id=str, name=str, path=str, type=str,
               exists=bool, has_xlsx=bool, has_docx=bool,
               screenshot_count=int)

        # last_run is "DD MMM YYYY HH:MM" string OR null when no runs yet
        if p.get("last_run") is not None:
            assert isinstance(p["last_run"], str)


# ── /api/info ────────────────────────────────────────────────────────────

def test_contract_api_info_full_pipeline(client):
    """For full-pipeline projects, /api/info returns nested totals and
    accuracy. The Dashboard StatsRow bug was reading info.pass which
    doesn't exist — the field is info.totals.pass."""
    r = client.get("/api/info?p=_mock-full")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "total_tc", "totals", "accuracy", "shot_count", "project_meta")
    _types(d, total_tc=int, accuracy=int, shot_count=int)
    _has_keys(d["totals"], "pass", "fail", "not start", "in-progress", "block", "cancel")
    _types(d["totals"], **{"pass": int, "fail": int})


def test_contract_api_info_playwright_only(client):
    """playwright-only projects use pw_last (not totals) for Pass/Fail.
    pw_last.pct (not pass_pct — that one was the audit bug)."""
    r = client.get("/api/info?p=_mock-playwright")
    if r.status_code == 404:
        pytest.skip("_mock-playwright not registered in this env")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "shot_count")
    if "pw_last" in d and d["pw_last"] is not None:
        _has_keys(d["pw_last"], "pass", "fail", "total", "pct")
        _types(d["pw_last"], **{"pass": int, "fail": int, "total": int, "pct": int})


# ── /api/bugs ────────────────────────────────────────────────────────────

def test_contract_api_bugs_list(client):
    """Each bug must expose id/title/severity/status/created_at, plus
    optional description/assignee that BugEditModal needs."""
    r = client.get("/api/bugs?p=_mock-manual")
    assert r.status_code == 200
    bugs = r.get_json()
    assert isinstance(bugs, list)
    if not bugs:
        pytest.skip("no bugs in mock — need at least one to verify shape")

    for b in bugs:
        _has_keys(b, "id", "title", "severity", "status", "created_at")
        _types(b, id=str, title=str, severity=str, status=str, created_at=str)
        assert b["severity"] in ("Critical", "High", "Medium", "Low")
        assert b["status"] in ("Open", "Fixed", "Closed")


def test_contract_api_bugs_update_persists_description_and_assignee(client):
    """Regression guard for the silent-data-loss bug. /api/bugs/update
    used to drop description and assignee from its whitelist — values
    looked saved (toast OK) but were dropped."""
    # Find any existing bug to update; create one if list is empty
    bugs = client.get("/api/bugs?p=_mock-manual").get_json()
    if not bugs:
        r = client.post(
            "/api/bugs/add",
            json={"project_id": "_mock-manual", "title": "contract test stub", "severity": "Low"},
        )
        assert r.status_code == 200
        bug_id = r.get_json()["bug"]["id"]
    else:
        bug_id = bugs[0]["id"]

    # Save BOTH fields the audit found getting dropped
    r = client.post("/api/bugs/update", json={
        "project_id": "_mock-manual",
        "id": bug_id,
        "description": "CONTRACT-TEST-DESC-marker-9931",
        "assignee":    "contract-test@example.com",
    })
    assert r.status_code == 200, r.get_json()

    # Read back — fields must round-trip
    after = next(b for b in client.get("/api/bugs?p=_mock-manual").get_json() if b["id"] == bug_id)
    assert after.get("description") == "CONTRACT-TEST-DESC-marker-9931", \
        "description was dropped — backend whitelist regression"
    assert after.get("assignee") == "contract-test@example.com", \
        "assignee was dropped — backend whitelist regression"


def test_schema_validation_rejects_unknown_field_on_bugs_update(client):
    """validate_body decorator should 400 on a typo'd field instead of
    silently dropping it (the audit pattern that hid description/assignee
    bugs for who-knows-how-long)."""
    bugs = client.get("/api/bugs?p=_mock-manual").get_json()
    if not bugs:
        pytest.skip("need at least one bug in mock to test the path")
    r = client.post("/api/bugs/update", json={
        "project_id": "_mock-manual",
        "id": bugs[0]["id"],
        "descriptionn": "typo'd field — should 400",   # double-n on purpose
    })
    assert r.status_code == 400
    err = r.get_json()
    assert "unknown field" in err["error"].lower()
    assert "descriptionn" in err["error"]


def test_schema_validation_rejects_unknown_field_on_projects_update(client):
    r = client.post("/api/projects/update", json={
        "id": "_mock-manual",
        "phasee": "active",   # typo
    })
    assert r.status_code == 400
    assert "unknown field" in r.get_json()["error"].lower()


def test_contract_api_bugs_add_respects_status(client):
    """Regression guard: /api/bugs/add used to ignore the status field
    and force everything to 'Open'."""
    r = client.post("/api/bugs/add", json={
        "project_id": "_mock-manual",
        "title": "contract status test",
        "severity": "Low",
        "status": "Closed",
    })
    assert r.status_code == 200
    bug = r.get_json()["bug"]
    assert bug["status"] == "Closed", \
        "POST /api/bugs/add ignored status — regression"
    # cleanup
    client.post("/api/bugs/delete", json={"project_id": "_mock-manual", "id": bug["id"]})


# ── /api/release-gate ────────────────────────────────────────────────────

def test_contract_api_release_gate(client):
    """Release Gate verdict has 5 distinct values. ReleaseReadinessView
    used to collapse them to a bool — now keeps them all."""
    r = client.get("/api/release-gate?p=_mock-full")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "project_id", "project_type", "phase", "verdict", "go",
              "criteria", "summary")
    _types(d, project_id=str, project_type=str, phase=str, verdict=str, go=bool,
           criteria=list, summary=dict)
    assert d["verdict"] in ("GO", "NOGO", "NOT_READY", "SKIP_PLANNING", "SKIP_PAUSED")
    _has_keys(d["summary"], "total", "pass", "warn", "hard_fail")
    _types(d["summary"], total=int, warn=int, hard_fail=int, **{"pass": int})

    for c in d["criteria"]:
        _has_keys(c, "id", "label", "ok", "warn", "detail")
        _types(c, id=str, label=str, ok=bool, warn=bool, detail=str)


# ── /api/flakiness ───────────────────────────────────────────────────────

def test_contract_api_flakiness(client):
    """Flakiness output drives the Hub Overview health matrix. UI reads
    verdict, fail_rate_pct, pass_rate_tests, runs_in_window."""
    r = client.get("/api/flakiness?p=_mock-full&window=20")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "verdict", "fail_rate_pct", "runs_in_window")
    _types(d, verdict=str, runs_in_window=int)
    assert d["verdict"] in ("stable", "warn", "flaky", "broken", "unknown")
    # fail_rate_pct may be int OR float; pass_rate_tests may be None
    assert isinstance(d["fail_rate_pct"], (int, float))
    if d.get("pass_rate_tests") is not None:
        assert isinstance(d["pass_rate_tests"], (int, float))


# ── /api/status ──────────────────────────────────────────────────────────

def test_contract_api_status(client):
    """Pipeline view reads s1..s9 stage status. Each stage may have
    {ok, count, file, files, stale} — keys vary by stage type."""
    r = client.get("/api/status?p=_mock-full")
    assert r.status_code == 200
    d = r.get_json()
    # At least s1 (input) should be present for any project
    assert any(k.startswith("s") and k[1:].isdigit() for k in d.keys()), \
        f"no stage keys in /api/status response: {sorted(d.keys())}"
    for k, stage in d.items():
        if not (k.startswith("s") and k[1:].isdigit()):
            continue
        if not isinstance(stage, dict):
            continue
        # ok is the only universally-required field
        if "ok" in stage:
            assert isinstance(stage["ok"], bool)
        if "files" in stage:
            assert isinstance(stage["files"], list)


# ── /api/audit ───────────────────────────────────────────────────────────

def test_contract_api_audit(client):
    """Activity Feed reads {entries[], count}. Each entry has ts/user/
    action/details. The Object-rendered-as-[object Object] bug was
    fixed in the UI but the contract still requires details to be a
    dict (not a stringified blob)."""
    r = client.get("/api/audit?limit=5")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "entries", "count")
    _types(d, entries=list, count=int)
    for e in d["entries"]:
        _has_keys(e, "ts", "action")
        _types(e, ts=str, action=str)
        # details should be a dict (frontend renders k=v pills); object/list inside is fine
        if "details" in e:
            assert isinstance(e["details"], dict)


# ── /api/schedules ───────────────────────────────────────────────────────

def test_contract_api_schedules(client):
    """Schedule list returns enriched entries with project_name."""
    r = client.get("/api/schedules")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    for s in data:
        # env may be missing on legacy entries — frontend treats absent as 'uat'
        _has_keys(s, "id", "project_id", "action", "tag",
                  "schedule_type", "enabled", "created_at")
        _types(s, id=str, project_id=str, action=str, tag=str,
               schedule_type=str, enabled=bool, created_at=str)
        if "env" in s:
            assert s["env"] in ("uat", "prod")
        assert s["schedule_type"] in ("daily", "weekly", "cron")


# ── /api/config/email ────────────────────────────────────────────────────

def test_contract_api_config_email(client):
    """EmailSettingsCard reads provider/smtp_*/resend_*/sender_name/
    subject_template/to[]/cc[]."""
    r = client.get("/api/config/email")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "provider", "smtp_host", "smtp_port", "to", "cc")
    _types(d, provider=str, smtp_host=str, smtp_port=int, to=list, cc=list)
    for r_ in d["to"] + d["cc"]:
        _has_keys(r_, "email")
        _types(r_, email=str)


# ── /api/config/notifications ────────────────────────────────────────────

def test_contract_api_config_notifications(client):
    """NotificationsCard reads slack_webhook/teams_webhook/discord_webhook
    + notify_on list."""
    r = client.get("/api/config/notifications")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "slack_webhook", "teams_webhook", "discord_webhook", "notify_on")
    _types(d, slack_webhook=str, teams_webhook=str, discord_webhook=str, notify_on=list)


# ── /api/config/branding ─────────────────────────────────────────────────

def test_contract_api_config_branding(client):
    """BrandingCard reads app_name / subtitle / logo / primary_color / etc."""
    r = client.get("/api/config/branding")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "app_name", "subtitle", "logo", "primary_color")
    _types(d, app_name=str, subtitle=str, logo=str, primary_color=str)


# ── /api/config/ai ───────────────────────────────────────────────────────

def test_contract_api_config_ai(client):
    """AISettingsCard reads provider / model / api_key_set."""
    r = client.get("/api/config/ai")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "provider", "model", "api_key_set")
    _types(d, provider=str, model=str, api_key_set=bool)
    assert d["provider"] in ("cli", "api")


# ── /api/metrics ─────────────────────────────────────────────────────────

def test_contract_api_metrics_history(client, tmp_path, monkeypatch):
    """Historical metrics endpoint returns expected envelope, even with an
    empty ring buffer (test process doesn't run the flush worker)."""
    import app as hub_app
    db = tmp_path / "metrics.db"
    monkeypatch.setattr(hub_app, "METRICS_DB", db)
    r = client.get("/api/metrics/history?hours=1")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "entries", "hours", "keep_hours", "rows")
    _types(d, entries=list, hours=int, keep_hours=int, rows=int)
    assert d["hours"] == 1


def test_contract_api_metrics(client):
    """Per-route request metrics endpoint. Pings a few endpoints first so
    the metrics window has data to summarise."""
    # Generate some traffic
    client.get("/api/projects")
    client.get("/api/bugs?p=_mock-manual")
    client.get("/api/release-gate?p=_mock-full")

    r = client.get("/api/metrics")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "started_at", "uptime_seconds", "total_requests",
              "total_errors", "error_rate_pct", "rps_lifetime",
              "routes", "tracked_routes")
    _types(d, started_at=str, uptime_seconds=int, total_requests=int,
           total_errors=int, routes=list, tracked_routes=int)
    assert isinstance(d["error_rate_pct"], (int, float))
    assert isinstance(d["rps_lifetime"], (int, float))

    # routes sorted by p95 desc
    if len(d["routes"]) >= 2:
        assert d["routes"][0]["p95_ms"] >= d["routes"][-1]["p95_ms"]

    for row in d["routes"]:
        _has_keys(row, "route", "count", "errors",
                  "p50_ms", "p95_ms", "p99_ms", "max_ms", "samples")
        _types(row, route=str, count=int, errors=int, samples=int)
        for k in ("p50_ms", "p95_ms", "p99_ms", "max_ms"):
            assert isinstance(row[k], (int, float))


# ── /api/config/backup ───────────────────────────────────────────────────

def test_contract_api_config_backup_list(client):
    """Backup list endpoint returns expected envelope shape."""
    r = client.get("/api/config/backup/list")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "backups", "keep_days")
    _types(d, backups=list, keep_days=int)
    for b in d["backups"]:
        _has_keys(b, "name", "size_kb", "modified")
        _types(b, name=str, modified=str)
        assert isinstance(b["size_kb"], (int, float))


def test_config_backup_run_creates_snapshot(client, tmp_path, monkeypatch):
    """POST /api/config/backup/run should create today's snapshot file."""
    import app as hub_app
    monkeypatch.setattr(hub_app, "CONFIG_BACKUP_DIR", tmp_path)
    r = client.post("/api/config/backup/run")
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["ok"] is True
    assert d["name"].startswith("config_")
    assert (tmp_path / d["name"]).exists()


def test_config_backup_restore_rejects_path_traversal(client):
    """Path-traversal attempt should be rejected with 400."""
    r = client.post("/api/config/backup/restore", json={"name": "../config.json"})
    assert r.status_code == 400
    assert "invalid" in r.get_json()["error"].lower()


def test_config_backup_restore_404_when_missing(client):
    r = client.post("/api/config/backup/restore", json={"name": "config_19000101.json"})
    assert r.status_code == 404


# ── /api/validate/excel ──────────────────────────────────────────────────

def test_contract_api_validate_excel(client):
    """Pipeline Tools' Excel TCM validation panel reads:
    total / filled / not_started / counts / missing_shots / shot_coverage."""
    r = client.get("/api/validate/excel?p=_mock-full")
    if r.status_code == 404:
        pytest.skip("no input excel in _mock-full")
    assert r.status_code == 200
    d = r.get_json()
    _has_keys(d, "total", "filled", "not_started", "counts",
              "missing_shots", "shot_coverage")
    _types(d, total=int, filled=int, not_started=int,
           counts=dict, missing_shots=list, shot_coverage=int)
