"""Unit tests for ai_provider — covers provider routing + error paths.

These tests do NOT make real CLI subprocesses or API calls; both providers
are patched. The point is to verify the abstraction layer's contract:
- generate() routes to the right provider based on config
- errors are raised as AIProviderError with helpful messages
- prompt builder produces a stable shape
"""
from unittest.mock import patch

import pytest

import ai_provider as A


# ── Routing ────────────────────────────────────────────────────────────────

def test_generate_defaults_to_cli_provider():
    with patch.object(A, "_cli_generate", return_value="cli output") as m:
        result = A.generate("hello")
    m.assert_called_once()
    assert result["provider"] == "cli"
    assert result["output"] == "cli output"


def test_generate_routes_to_api_when_configured():
    with patch.object(A, "_api_generate", return_value="api output") as m:
        result = A.generate("hello", config={"provider": "api", "api_key": "sk-test"})
    m.assert_called_once()
    assert result["provider"] == "api"
    assert result["output"] == "api output"


def test_generate_rejects_unknown_provider():
    with pytest.raises(A.AIProviderError, match="Unknown ai.provider"):
        A.generate("hello", config={"provider": "openai"})


# ── CLI provider ───────────────────────────────────────────────────────────

def test_cli_provider_raises_when_claude_binary_missing():
    with patch.object(A.shutil, "which", return_value=None):
        with pytest.raises(A.AIProviderError, match="Claude CLI not found"):
            A._cli_generate("test prompt")


def test_cli_provider_raises_on_non_zero_exit():
    fake_run = type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()
    with patch.object(A.shutil, "which", return_value="/usr/bin/claude"):
        with patch.object(A.subprocess, "run", return_value=fake_run):
            with pytest.raises(A.AIProviderError, match="returned code 1"):
                A._cli_generate("test")


def test_cli_provider_returns_stripped_stdout_on_success():
    fake_run = type("R", (), {"returncode": 0, "stdout": "  some answer  \n", "stderr": ""})()
    with patch.object(A.shutil, "which", return_value="/usr/bin/claude"):
        with patch.object(A.subprocess, "run", return_value=fake_run):
            assert A._cli_generate("test") == "some answer"


def test_cli_provider_raises_on_empty_output():
    fake_run = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    with patch.object(A.shutil, "which", return_value="/usr/bin/claude"):
        with patch.object(A.subprocess, "run", return_value=fake_run):
            with pytest.raises(A.AIProviderError, match="empty output"):
                A._cli_generate("test")


# ── API provider ───────────────────────────────────────────────────────────

def test_api_provider_raises_without_key():
    with pytest.raises(A.AIProviderError, match="no API key"):
        A._api_generate("test", api_key="")


# ── Prompt builder ─────────────────────────────────────────────────────────

def test_test_plan_prompt_includes_required_pieces():
    p = A.build_test_plan_prompt(
        requirement="As a user I want to log in",
        project_name="My Project",
        project_type="full-pipeline",
    )
    assert "As a user I want to log in" in p
    assert "My Project" in p
    assert "full-pipeline" in p
    assert "TS_001" in p   # template asks for scenario IDs
    assert "Coverage" in p
    assert "Risk" in p


def test_test_plan_prompt_falls_back_when_project_meta_missing():
    p = A.build_test_plan_prompt("REQ", "", "")
    assert "(unnamed)" in p
    assert "full-pipeline" in p   # default project_type fallback


# ── /api/config/ai endpoints ───────────────────────────────────────────────

def test_api_config_ai_get_returns_shape(client):
    r = client.get("/api/config/ai")
    assert r.status_code == 200
    d = r.get_json()
    for key in ("provider", "model", "api_key_set"):
        assert key in d


def test_api_config_ai_save_rejects_unknown_provider(client):
    r = client.post("/api/config/ai/save", json={"provider": "openai"})
    assert r.status_code == 400


def test_api_config_ai_save_round_trips(client):
    payload = {"provider": "cli", "model": "claude-sonnet-4-6"}
    try:
        r = client.post("/api/config/ai/save", json=payload)
        assert r.status_code == 200 and r.get_json()["ok"] is True
        d = client.get("/api/config/ai").get_json()
        assert d["provider"] == "cli"
        assert d["model"] == "claude-sonnet-4-6"
    finally:
        client.post("/api/config/ai/save", json={"provider": "cli", "model": ""})


def test_api_config_ai_save_preserves_existing_api_key_when_omitted(client, hub):
    """Saving without api_key in payload must not erase a previously-stored key.
    This is the most common gotcha — UI re-saves with the password field empty."""
    cfg = hub.load_config()
    cfg["ai"] = {"provider": "api", "api_key": "sk-existing"}
    hub.save_config(cfg)
    try:
        r = client.post("/api/config/ai/save", json={"provider": "api"})
        assert r.status_code == 200
        cfg2 = hub.load_config()
        assert cfg2["ai"].get("api_key") == "sk-existing"
    finally:
        # Restore
        cfg = hub.load_config()
        cfg.pop("ai", None)
        hub.save_config(cfg)


def test_api_generate_test_plan_requires_requirement(client):
    r = client.post("/api/ai/generate-test-plan", json={})
    assert r.status_code == 400
    assert "required" in r.get_json()["error"]


def test_api_generate_test_plan_rejects_oversize_input(client):
    r = client.post("/api/ai/generate-test-plan", json={"requirement": "x" * 60_000})
    assert r.status_code == 400


def test_api_generate_test_plan_returns_502_on_provider_error(client, hub):
    """When the underlying provider raises AIProviderError, the endpoint should
    surface a structured 502 (bad gateway), not crash with 500."""
    from ai_provider import AIProviderError
    with patch("ai_provider.generate", side_effect=AIProviderError("CLI missing")):
        r = client.post("/api/ai/generate-test-plan", json={"requirement": "test req"})
    assert r.status_code == 502
    d = r.get_json()
    assert d["error"] == "AI provider error"
    assert "CLI missing" in d["detail"]
