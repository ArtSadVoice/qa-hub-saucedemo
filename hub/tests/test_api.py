"""Integration tests for Flask endpoints. Uses real registered projects (read-only)."""
import json


# ── /api/projects ─────────────────────────────────────────────────────────

def test_projects_list_returns_registered(client):
    r = client.get("/api/projects")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert len(data) >= 2  # at least _mock-full + _mock-manual should be registered
    # Each project has required fields
    for p in data:
        assert "id" in p and "name" in p and "type" in p


def test_projects_includes_mock_projects(client):
    r = client.get("/api/projects")
    ids = {p["id"] for p in r.get_json()}
    assert "_mock-full" in ids
    assert "_mock-manual" in ids


# ── /api/release-gate (Q2 endpoint) ───────────────────────────────────────

def test_release_gate_missing_p_returns_400(client):
    r = client.get("/api/release-gate")
    assert r.status_code == 400
    assert "missing" in r.get_json()["error"].lower()


def test_release_gate_nonexistent_project_returns_404(client):
    r = client.get("/api/release-gate?p=__does_not_exist__")
    assert r.status_code == 404
    assert "not found" in r.get_json()["error"].lower()


def test_release_gate_mock_full_has_9_criteria(client):
    r = client.get("/api/release-gate?p=_mock-full")
    assert r.status_code == 200
    d = r.get_json()
    assert d["project_type"] == "full-pipeline"
    assert d["summary"]["total"] == 9
    assert d["verdict"] in ("GO", "NOGO", "NOT_READY")
    assert isinstance(d["go"], bool)
    assert d["go"] == (d["summary"]["hard_fail"] == 0)


def test_release_gate_mock_manual_has_6_criteria(client):
    r = client.get("/api/release-gate?p=_mock-manual")
    d = r.get_json()
    assert d["project_type"] == "manual-testing"
    assert d["summary"]["total"] == 6


def test_release_gate_criteria_structure(client):
    r = client.get("/api/release-gate?p=_mock-manual")
    d = r.get_json()
    for c in d["criteria"]:
        assert "id" in c and "label" in c and "ok" in c and "warn" in c and "detail" in c
        assert isinstance(c["ok"], bool)
        assert isinstance(c["warn"], bool)
        # warn and ok are mutually exclusive (by design in _gate_item)
        assert not (c["warn"] and c["ok"])


def test_release_gate_default_thresholds_80(client):
    r = client.get("/api/release-gate?p=_mock-manual")
    t = r.get_json()["thresholds"]
    assert t["pass_rate"] == 80
    assert t["tcm_pass_rate"] == 80
    assert t["screenshot_coverage"] == 80


def test_release_gate_respects_gates_override(client, hub, monkeypatch, tmp_path):
    """Per-project gates in config should override defaults."""
    # Temporarily patch load_config to inject gates for _mock-full
    original = hub.load_config
    def patched():
        cfg = original()
        for p in cfg.get("projects", []):
            if p["id"] == "_mock-full":
                p["gates"] = {"pass_rate": 95, "tcm_pass_rate": 90, "screenshot_coverage": 85}
        return cfg
    monkeypatch.setattr(hub, "load_config", patched)
    # Also patch get_project since it's used inside get_paths
    def patched_get_project(pid):
        cfg = patched()
        for p in cfg.get("projects", []):
            if p["id"] == pid:
                abs_path = hub.ROOT_DIR / p["path"]
                return {**p, "abs_path": abs_path}
        return None
    monkeypatch.setattr(hub, "get_project", patched_get_project)

    r = client.get("/api/release-gate?p=_mock-full")
    t = r.get_json()["thresholds"]
    assert t["pass_rate"] == 95
    assert t["tcm_pass_rate"] == 90
    assert t["screenshot_coverage"] == 85


# ── compute_release_gate (direct call, no Flask) ──────────────────────────

def test_compute_release_gate_returns_error_for_unknown(hub):
    result = hub.compute_release_gate("__does_not_exist__")
    assert "error" in result


def test_compute_release_gate_short_circuits_on_planning_phase(hub, monkeypatch):
    def fake_paths(pid):
        return {"proj": {"id": pid, "type": "full-pipeline", "phase": "planning"}}
    monkeypatch.setattr(hub, "get_paths", fake_paths)
    result = hub.compute_release_gate("x")
    assert result["verdict"] == "SKIP_PLANNING"
    assert result["go"] is False
    assert result["criteria"] == []


def test_compute_release_gate_short_circuits_on_paused_phase(hub, monkeypatch):
    def fake_paths(pid):
        return {"proj": {"id": pid, "type": "playwright-only", "phase": "paused"}}
    monkeypatch.setattr(hub, "get_paths", fake_paths)
    result = hub.compute_release_gate("x")
    assert result["verdict"] == "SKIP_PAUSED"
    assert result["go"] is False
