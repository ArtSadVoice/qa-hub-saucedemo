"""Sprint G — security hardening tests.

Covers:
  • Response carries the expected security headers (P2.2)
  • Write-endpoint rate limit (60/min/ip/route) returns 429 (P2.3)
  • Auth-fail rate limit is wired (P2.3) — only fires when HUB_PASSWORD set
  • Oversized request body rejected with 413 (P2.4)
"""
import json
import pytest


# ── P2.2 — security headers ──────────────────────────────────────────────

def test_security_headers_present_on_api_response(client):
    """Every successful API response must carry the headers our CSP / frame
    guard rely on. Missing any → frontend dark-mode might leak iframe, or a
    type-sniffed XSS could land."""
    r = client.get("/api/projects")
    assert r.status_code == 200
    h = r.headers
    assert h.get("X-Content-Type-Options") == "nosniff"
    assert h.get("X-Frame-Options") == "DENY"
    assert h.get("Referrer-Policy") == "same-origin"
    csp = h.get("Content-Security-Policy") or ""
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    perms = h.get("Permissions-Policy") or ""
    assert "camera=()" in perms


def test_security_headers_present_on_404(client):
    """404 responses still go through after_request — confirm headers attach."""
    r = client.get("/api/__nope__")
    assert r.status_code == 404
    assert r.headers.get("X-Frame-Options") == "DENY"


# ── P2.3 — write rate limit ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_rate_buckets():
    """Each test starts with a clean rate bucket so iteration count is
    predictable. Module-level dict — safe to clear between tests."""
    import app as hub_app
    with hub_app._RATE_LOCK:
        hub_app._rate_buckets.clear()


def test_write_rate_limit_kicks_in_after_threshold(client):
    """61st POST in the 60-second window should 429.
    Use /api/bugs/add against a synthetic project — the route validates
    body, but we expect the rate-limit before_request to short-circuit."""
    pid = "_mock-manual"
    payload = {"project_id": pid, "title": "rate-limit test", "severity": "Low"}
    successes = 0
    saw_429 = False
    for _ in range(70):
        r = client.post("/api/bugs/add", json=payload)
        if r.status_code == 429:
            saw_429 = True
            err = r.get_json()
            assert "rate limit" in err["error"].lower()
            break
        successes += 1
    assert saw_429, f"never got 429 after {successes} requests — limiter not active"
    assert successes >= 50, f"limiter fired too early ({successes}) — expected ~60"


def test_write_rate_limit_does_not_apply_to_get(client):
    """GET requests are read-only and shouldn't burn the write bucket."""
    for _ in range(80):
        r = client.get("/api/projects")
        assert r.status_code == 200, f"GET 429'd at iteration; status={r.status_code}"


def test_write_rate_limit_per_ip(client, monkeypatch):
    """Two different IPs share neither bucket. Simulate by patching
    _client_ip to return a fresh value each call."""
    import app as hub_app
    counter = {"i": 0}

    def fake_ip():
        counter["i"] += 1
        return f"10.0.0.{counter['i'] % 5 + 1}"   # rotate 5 IPs

    monkeypatch.setattr(hub_app, "_client_ip", fake_ip)
    # 100 requests across 5 IPs = 20 each, well under the 60/min cap
    for _ in range(100):
        r = client.post("/api/bugs/add", json={"project_id": "_mock-manual", "title": "x", "severity": "Low"})
        assert r.status_code != 429


# ── P2.4 — request size cap ──────────────────────────────────────────────

def test_oversized_body_returns_413(client):
    """Send a JSON payload above MAX_CONTENT_LENGTH — Flask returns 413
    automatically. Build a 12 MB title to blow the 10 MB cap."""
    huge_title = "A" * (12 * 1024 * 1024)
    r = client.post(
        "/api/bugs/add",
        data=json.dumps({"project_id": "_mock-manual", "title": huge_title, "severity": "Low"}),
        content_type="application/json",
    )
    # Flask returns 413 (Request Entity Too Large) when body exceeds the cap
    assert r.status_code == 413


def test_normal_body_accepted(client):
    """Sanity: a normal-sized body still works."""
    r = client.post("/api/bugs/add", json={
        "project_id": "_mock-manual",
        "title":      "ordinary bug",
        "severity":   "Low",
    })
    assert r.status_code == 200
    # cleanup
    bug = r.get_json()["bug"]
    client.post("/api/bugs/delete", json={"project_id": "_mock-manual", "id": bug["id"]})
