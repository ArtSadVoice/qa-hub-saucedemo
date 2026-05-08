"""Unit tests for pure helpers: atomic writes, email_secret, history archive."""
import json
import os
import threading
from pathlib import Path

import pytest


# ── _atomic_write_text / _atomic_write_json ────────────────────────────────

def test_atomic_write_text_creates_file(hub, tmp_path: Path):
    p = tmp_path / "out.txt"
    hub._atomic_write_text(p, "hello ไทย\n")
    assert p.read_text(encoding="utf-8") == "hello ไทย\n"


def test_atomic_write_text_leaves_no_tmp(hub, tmp_path: Path):
    p = tmp_path / "out.txt"
    hub._atomic_write_text(p, "x")
    tmp_files = list(tmp_path.glob("*.tmp.*"))
    assert tmp_files == [], f"stray tmp files: {tmp_files}"


def test_atomic_write_text_overwrites(hub, tmp_path: Path):
    p = tmp_path / "out.txt"
    p.write_text("old content", encoding="utf-8")
    hub._atomic_write_text(p, "new content")
    assert p.read_text(encoding="utf-8") == "new content"


def test_atomic_write_json_valid_json(hub, tmp_path: Path):
    p = tmp_path / "data.json"
    hub._atomic_write_json(p, {"a": 1, "thai": "ทดสอบ"})
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded == {"a": 1, "thai": "ทดสอบ"}


def test_atomic_write_survives_concurrent(hub, tmp_path: Path):
    """Parallel writers: file must always be valid JSON (no partial corruption).
    In real Hub usage writes are serialized via _hist_lock etc., but this stress-tests the helper.
    On Windows, os.replace may raise PermissionError under extreme contention — acceptable as long
    as surviving writers produce a well-formed file."""
    p = tmp_path / "race.json"
    errors = []

    def writer(i):
        try:
            hub._atomic_write_json(p, {"writer": i, "data": list(range(100))})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    # Core guarantee: no corruption — file parses as valid JSON with expected shape
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert "writer" in loaded and "data" in loaded
    assert len(loaded["data"]) == 100
    # No tmp files left over (each writer cleans its own tmp on failure)
    assert list(tmp_path.glob("*.tmp.*")) == []
    # At least one writer succeeded (n_failures < n_writers)
    assert len(errors) < 10


# ── _email_secret ───────────────────────────────────────────────────────────

def test_email_secret_env_takes_precedence(hub, monkeypatch):
    monkeypatch.setenv("HUB_SMTP_PASS", "from-env")
    assert hub._email_secret("HUB_SMTP_PASS", "from-config") == "from-env"


def test_email_secret_falls_back_to_config(hub, monkeypatch):
    monkeypatch.delenv("HUB_SMTP_PASS", raising=False)
    assert hub._email_secret("HUB_SMTP_PASS", "from-config") == "from-config"


def test_email_secret_empty_env_uses_config(hub, monkeypatch):
    monkeypatch.setenv("HUB_SMTP_PASS", "")
    assert hub._email_secret("HUB_SMTP_PASS", "from-config") == "from-config"


def test_email_secret_both_empty_returns_empty(hub, monkeypatch):
    monkeypatch.delenv("HUB_SMTP_PASS", raising=False)
    assert hub._email_secret("HUB_SMTP_PASS", "") == ""


# ── _archive_history_overflow ───────────────────────────────────────────────

def test_archive_groups_by_month(hub, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hub, "RUN_HISTORY_ARCHIVE_DIR", tmp_path)
    overflow = [
        {"project_id": "x", "ts": "2026-03-15 10:00:00", "pass": 1, "fail": 0},
        {"project_id": "x", "ts": "2026-03-20 11:00:00", "pass": 2, "fail": 0},
        {"project_id": "x", "ts": "2026-04-02 09:00:00", "pass": 3, "fail": 0},
    ]
    hub._archive_history_overflow(overflow)
    # Expect 2 archive files (202603, 202604)
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["run_history_202603.jsonl", "run_history_202604.jsonl"]
    # March file has 2 entries
    mar = (tmp_path / "run_history_202603.jsonl").read_text().splitlines()
    assert len(mar) == 2
    assert all(json.loads(line)["ts"].startswith("2026-03") for line in mar)


def test_archive_appends_existing_file(hub, tmp_path: Path, monkeypatch):
    """Calling archive twice should append, not overwrite."""
    monkeypatch.setattr(hub, "RUN_HISTORY_ARCHIVE_DIR", tmp_path)
    e1 = [{"project_id": "x", "ts": "2026-03-01 10:00:00", "pass": 1, "fail": 0}]
    e2 = [{"project_id": "x", "ts": "2026-03-02 10:00:00", "pass": 2, "fail": 0}]
    hub._archive_history_overflow(e1)
    hub._archive_history_overflow(e2)
    lines = (tmp_path / "run_history_202603.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_archive_empty_is_noop(hub, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hub, "RUN_HISTORY_ARCHIVE_DIR", tmp_path)
    hub._archive_history_overflow([])
    assert list(tmp_path.iterdir()) == []


def test_archive_missing_ts_falls_back_to_current_month(hub, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hub, "RUN_HISTORY_ARCHIVE_DIR", tmp_path)
    hub._archive_history_overflow([{"project_id": "x", "pass": 1, "fail": 0}])
    # Exactly one archive file created (with current month)
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].name.startswith("run_history_") and files[0].name.endswith(".jsonl")
