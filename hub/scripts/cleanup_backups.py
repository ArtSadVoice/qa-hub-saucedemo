"""
cleanup_backups.py — Remove stale `*.bak_*` files across registered projects
and the hub's scaffold/templates dirs.

The sync workflow (`scripts/sync_to_project.py`) backs up every file it
overwrites to `<name>.bak_synct_<YYYYMMDD_HHMMSS>`. Template patches and
hand-edits also drop `*.bak_<...>` files. None of these are ever cleaned
up automatically — disk grows over time.

This script keeps the most-recent N backups per file (default: 3) and
deletes anything older than D days (default: 30). Idempotent; safe to
re-run; supports --dry-run.

Usage:
    python scripts/cleanup_backups.py                    # dry-run, default policy
    python scripts/cleanup_backups.py --apply            # actually delete
    python scripts/cleanup_backups.py --apply --keep 5 --older-than 14
    python scripts/cleanup_backups.py --apply --root C:/Automation/Custom

Default scan roots:
    - C:/Automation/<every project path from hub config.json>
    - C:/Automation/qa-hub-saucedemo/scaffold
    - C:/Automation/qa-hub-saucedemo/templates  (if exists)

Backup file pattern (matched by regex):
    *.bak_<anything>

Examples of files this would touch:
    scripts/_preflight.py.bak_synct_20260504_140110
    templates/Test_Result_Template.docx.bak_addexit_20260504_093530
    scaffold/full-pipeline/templates/Test_Result_Template.docx.bak_v2_1_broken_*

Output: human-readable summary; exit 0 even when no files deleted.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB_CONFIG = ROOT / "config.json"

# Pattern for backup files we manage. Anchored to filename only — does
# NOT match arbitrary `.bak.something.else` paths in the middle of a name.
BACKUP_RE = re.compile(r"\.bak_[^/\\]+$")


def _load_project_paths() -> list[Path]:
    """Read hub config.json and resolve each registered project path
    against C:/Automation/ root. Returns absolute Paths."""
    if not HUB_CONFIG.exists():
        return []
    try:
        cfg = json.loads(HUB_CONFIG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  WARN: could not read {HUB_CONFIG}: {e}")
        return []
    out: list[Path] = []
    automation = Path(r"C:/Automation")
    for proj in cfg.get("projects", []):
        rel = (proj.get("path") or "").strip()
        if not rel:
            continue
        # Already-absolute paths win; otherwise join under C:/Automation/
        p = Path(rel)
        abs_p = p if p.is_absolute() else (automation / rel)
        out.append(abs_p)
    return out


def _find_backups(roots: list[Path]) -> list[Path]:
    """Walk each root, collecting all files matching BACKUP_RE."""
    found: list[Path] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for p in root.rglob("*"):
            try:
                if p.is_file() and BACKUP_RE.search(p.name):
                    found.append(p)
            except (OSError, PermissionError):
                continue
    return found


def _group_by_original(paths: list[Path]) -> dict[Path, list[Path]]:
    """Group backups by the file they originally back up.
    `foo.py.bak_synct_20260504_140110` -> original = `foo.py`."""
    groups: dict[Path, list[Path]] = defaultdict(list)
    for p in paths:
        # Strip ALL trailing `.bak_<token>` segments — handles double-backups
        original_name = p.name
        while True:
            m = BACKUP_RE.search(original_name)
            if not m:
                break
            original_name = original_name[: m.start()]
        original = p.with_name(original_name)
        groups[original].append(p)
    return groups


def main() -> int:
    ap = argparse.ArgumentParser(description="Clean up stale *.bak_* backups")
    ap.add_argument("--apply", action="store_true",
                    help="Actually delete (default: dry-run)")
    ap.add_argument("--keep", type=int, default=3,
                    help="Per file, keep this many MOST RECENT backups (default: 3)")
    ap.add_argument("--older-than", type=int, default=30, dest="older_than",
                    help="Delete backups older than this many days (default: 30)")
    ap.add_argument("--root", action="append", default=None,
                    help="Additional root to scan (repeatable). "
                         "Default: registered projects + scaffold/")
    args = ap.parse_args()

    if args.keep < 0:
        print("ERROR: --keep must be >= 0", file=sys.stderr)
        return 2
    if args.older_than < 0:
        print("ERROR: --older-than must be >= 0", file=sys.stderr)
        return 2

    # Build scan roots
    roots = list(_load_project_paths())
    roots.append(ROOT / "scaffold")
    if (ROOT / "templates").exists():
        roots.append(ROOT / "templates")
    if args.root:
        for r in args.root:
            roots.append(Path(r))

    print(f"Scan roots ({len(roots)}):")
    for r in roots:
        marker = "✓" if r.exists() else "✗"
        print(f"  {marker} {r}")
    print()

    backups = _find_backups(roots)
    if not backups:
        print("No backup files found.")
        return 0

    print(f"Found {len(backups)} backup file(s) across roots.")
    groups = _group_by_original(backups)
    print(f"  Grouped under {len(groups)} original file(s).")
    print()

    cutoff = datetime.now() - timedelta(days=args.older_than)
    print(f"Policy: keep most-recent {args.keep} per group, delete anything older than {cutoff:%Y-%m-%d %H:%M}.")
    print()

    delete_plan: list[Path] = []
    keep_plan: list[Path] = []

    for original, baks in groups.items():
        # Sort by mtime desc — most recent first
        baks_sorted = sorted(baks, key=lambda p: p.stat().st_mtime, reverse=True)
        # First N kept regardless of age
        kept = baks_sorted[: args.keep]
        candidates = baks_sorted[args.keep:]
        # Of the candidates beyond N, drop those older than cutoff;
        # newer-than-cutoff candidates also get kept (so an active project
        # with frequent backups doesn't lose all its safety nets).
        for p in candidates:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            if mtime < cutoff:
                delete_plan.append(p)
            else:
                kept.append(p)
        keep_plan.extend(kept)

    print(f"  KEEP   : {len(keep_plan)} file(s)")
    print(f"  DELETE : {len(delete_plan)} file(s)")
    print()

    if delete_plan:
        print("Files to delete:")
        for p in delete_plan[:20]:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            size_kb = p.stat().st_size / 1024
            print(f"    {mtime:%Y-%m-%d %H:%M}  {size_kb:>6.1f} KB  {p}")
        if len(delete_plan) > 20:
            print(f"    ... and {len(delete_plan) - 20} more")
        total_kb = sum(p.stat().st_size for p in delete_plan) / 1024
        print(f"  Total reclaim: {total_kb:.1f} KB ({total_kb/1024:.2f} MB)")
        print()

    if not args.apply:
        print("(dry-run — re-run with --apply to delete)")
        return 0

    if not delete_plan:
        return 0

    actioned = 0
    for p in delete_plan:
        try:
            p.unlink()
            actioned += 1
        except OSError as e:
            print(f"  WARN: could not delete {p}: {e}", file=sys.stderr)
    print(f"Deleted {actioned}/{len(delete_plan)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
