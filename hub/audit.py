"""Append-only audit log for mutating Hub actions.

Writes to logs/audit.jsonl — one JSON line per event. JSONL is easy to grep,
tail, ship to external tools, and survives partial-write crashes (last line
may be truncated but earlier lines are intact).

Scope: mutations only (add/update/delete/save). Reads aren't logged — they'd
dwarf the signal. If you ever need "who viewed X" support, reverse-proxy
access logs are a better place for that.

Usage:
    from audit import audit
    audit("project.add", id=pid, name=name)
    audit("bug.delete", id=bug_id, project_id=proj_id)

Format:
    {"ts": "2026-04-24 09:12:34", "user": "hub", "action": "project.add",
     "ip": "127.0.0.1", "details": {...}}
"""
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOG_DIR / "audit.jsonl"
_ARCHIVE_DIR = _LOG_DIR / "audit_archive"   # per-month YYYYMM JSONL archives
_lock = threading.Lock()

# Default retention: 90 days. Override with HUB_AUDIT_RETENTION_DAYS env var.
# Set to 0 to disable archiving entirely (audit.jsonl grows unbounded).
try:
    RETENTION_DAYS = max(0, int(os.environ.get("HUB_AUDIT_RETENTION_DAYS", "90")))
except ValueError:
    RETENTION_DAYS = 90

_logger = logging.getLogger("hub.audit")


def _current_user() -> str:
    """Return the authenticated username if BasicAuth is on, else 'anonymous'."""
    try:
        from flask import request
        h = request.headers.get("Authorization", "")
        if h.startswith("Basic "):
            import base64
            decoded = base64.b64decode(h[6:]).decode("utf-8", errors="ignore")
            return decoded.split(":", 1)[0] or "anonymous"
    except Exception:
        pass
    # Fall back to env var identity if request isn't available (e.g. scheduler thread)
    return os.environ.get("HUB_USERNAME", "hub") if os.environ.get("HUB_PASSWORD") else "anonymous"


def _current_ip() -> str:
    try:
        from flask import request
        return request.headers.get("X-Forwarded-For", request.remote_addr or "-").split(",")[0].strip()
    except Exception:
        return "-"


def audit(action: str, **details) -> None:
    """Record a mutation. Never raises — an audit failure must not block the action."""
    entry = {
        "ts":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user":    _current_user(),
        "ip":      _current_ip(),
        "action":  action,
        "details": details,
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    try:
        with _lock:
            with _LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(line)
    except Exception as e:
        # Last-ditch: write to the general logger so we notice, but never
        # propagate — audit must be invisible to callers.
        _logger.warning("audit write failed: %s (entry=%s)", e, entry)


def tail(n: int = 100) -> list[dict]:
    """Return the last n audit entries as parsed dicts (newest last).
    Used by the future /api/audit endpoint."""
    if not _LOG_FILE.exists():
        return []
    with _LOG_FILE.open(encoding="utf-8") as f:
        lines = f.readlines()[-n:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip a corrupted line without failing the whole read
    return out


def archive_old_entries(retention_days: int | None = None) -> dict:
    """Archive entries older than `retention_days` into per-month JSONL files.

    Splits audit.jsonl into:
      • kept: entries within the retention window (rewritten in-place)
      • archived: per-month buckets appended to audit_archive_YYYYMM.jsonl

    Entries with unparseable / missing ts are kept (defensive — never lose data
    we can't classify). Holds the write lock for the duration so concurrent
    `audit()` calls block until the swap completes.

    Returns: {"kept": N, "archived": N, "archived_files": [...], "skipped": 0}
    """
    days = RETENTION_DAYS if retention_days is None else retention_days
    if days <= 0 or not _LOG_FILE.exists():
        return {"kept": 0, "archived": 0, "archived_files": [], "skipped": True}

    cutoff = datetime.now() - timedelta(days=days)

    with _lock:
        # Read all entries
        all_lines: list[str] = []
        with _LOG_FILE.open(encoding="utf-8") as f:
            all_lines = f.readlines()

        if not all_lines:
            return {"kept": 0, "archived": 0, "archived_files": [], "skipped": False}

        kept: list[str] = []
        archived_by_month: dict[str, list[str]] = {}

        for raw in all_lines:
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                # Corrupted line — keep it so a human can inspect later
                kept.append(raw)
                continue
            ts_str = obj.get("ts", "")
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                # Defensive: keep entries we can't classify rather than lose them
                kept.append(raw)
                continue
            if ts >= cutoff:
                kept.append(raw)
            else:
                ym = ts.strftime("%Y%m")
                archived_by_month.setdefault(ym, []).append(raw)

        # Nothing to archive — short-circuit so we don't rewrite the file unnecessarily
        if not archived_by_month:
            return {"kept": len(kept), "archived": 0, "archived_files": [], "skipped": False}

        # Append to per-month archive files
        _ARCHIVE_DIR.mkdir(exist_ok=True)
        archived_files: list[str] = []
        archived_count = 0
        for ym, lines in archived_by_month.items():
            archive_path = _ARCHIVE_DIR / f"audit_{ym}.jsonl"
            with archive_path.open("a", encoding="utf-8") as f:
                for line in lines:
                    f.write(line)
            archived_files.append(archive_path.name)
            archived_count += len(lines)

        # Atomic rewrite of audit.jsonl with kept entries only
        tmp_path = _LOG_FILE.with_suffix(".jsonl.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            for line in kept:
                f.write(line)
        tmp_path.replace(_LOG_FILE)

        _logger.info(
            "audit retention: archived %d entries → %s, kept %d",
            archived_count, archived_files, len(kept),
        )
        return {
            "kept": len(kept),
            "archived": archived_count,
            "archived_files": archived_files,
            "skipped": False,
        }
