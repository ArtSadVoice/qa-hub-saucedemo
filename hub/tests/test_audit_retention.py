"""Audit log retention — verify archive_old_entries splits the log correctly
and the /api/audit/archive endpoint is wired up.

Each test uses a temp directory + monkeypatches the module-level constants so
the real audit.jsonl is never touched.
"""
import json
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def temp_audit(tmp_path, monkeypatch):
    """Redirect audit module to a fresh temp dir."""
    import audit
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "audit.jsonl"
    archive_dir = log_dir / "audit_archive"
    monkeypatch.setattr(audit, "_LOG_DIR", log_dir)
    monkeypatch.setattr(audit, "_LOG_FILE", log_file)
    monkeypatch.setattr(audit, "_ARCHIVE_DIR", archive_dir)
    return audit, log_file, archive_dir


def _write(log_file, *entries):
    log_file.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )


def test_archive_keeps_recent_archives_old(temp_audit):
    audit, log_file, archive_dir = temp_audit
    now = datetime.now()
    recent = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    old    = (now - timedelta(days=120)).strftime("%Y-%m-%d %H:%M:%S")
    older  = (now - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    _write(log_file,
        {"ts": recent, "user": "u", "action": "a.recent", "details": {}},
        {"ts": old,    "user": "u", "action": "a.old",    "details": {}},
        {"ts": older,  "user": "u", "action": "a.older",  "details": {}},
    )

    result = audit.archive_old_entries(retention_days=90)

    assert result["kept"]     == 1
    assert result["archived"] == 2
    assert not result["skipped"]

    # Live file now contains only the recent entry
    live = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(live) == 1
    assert json.loads(live[0])["action"] == "a.recent"

    # Two distinct months in archive
    archives = sorted(archive_dir.glob("audit_*.jsonl"))
    assert len(archives) == 2
    total_archived = sum(len(p.read_text(encoding="utf-8").strip().splitlines()) for p in archives)
    assert total_archived == 2


def test_archive_keeps_unparseable_lines(temp_audit):
    """Defensive: corrupted / unclassifiable entries must NOT be lost."""
    audit, log_file, _ = temp_audit
    log_file.write_text(
        '{"ts": "BAD-TS", "action": "a.bad"}\n'
        'this is not json at all\n'
        '{"ts": "' + (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S") + '", "action": "a.old"}\n',
        encoding="utf-8",
    )
    result = audit.archive_old_entries(retention_days=90)
    # 2 unparseable kept + 1 old archived
    assert result["kept"]     == 2
    assert result["archived"] == 1


def test_archive_skipped_when_no_old_entries(temp_audit):
    audit, log_file, archive_dir = temp_audit
    recent = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    _write(log_file, {"ts": recent, "user": "u", "action": "a", "details": {}})
    result = audit.archive_old_entries(retention_days=90)
    assert result["archived"] == 0
    assert not archive_dir.exists()  # didn't create the dir for nothing


def test_archive_disabled_when_retention_zero(temp_audit):
    audit, log_file, _ = temp_audit
    old = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    _write(log_file, {"ts": old, "user": "u", "action": "a", "details": {}})
    result = audit.archive_old_entries(retention_days=0)
    assert result["skipped"]
    # File untouched
    assert len(log_file.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_api_audit_archive_endpoint_returns_stats(client, tmp_path, monkeypatch):
    """Smoke test that /api/audit/archive is wired up and returns the
    expected schema. Uses a temp log file so we don't move real entries."""
    import audit
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "audit.jsonl"
    archive_dir = log_dir / "audit_archive"
    monkeypatch.setattr(audit, "_LOG_DIR", log_dir)
    monkeypatch.setattr(audit, "_LOG_FILE", log_file)
    monkeypatch.setattr(audit, "_ARCHIVE_DIR", archive_dir)

    old = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    _write(log_file, {"ts": old, "user": "u", "action": "a.old", "details": {}})

    r = client.post("/api/audit/archive", json={"retention_days": 90})
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert "kept" in d and "archived" in d and "archived_files" in d
    assert d["archived"] == 1
