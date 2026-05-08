r"""Backup Hub state files to a rotating set of timestamped .zip archives.

State files covered (all gitignored, so the repo won't save you):
- config.json
- run_history.json
- run_history_archive/  (monthly JSONL archives, if present)
- schedules.json
- bugs/*.json

Usage:
    python scripts/backup.py                         # defaults below
    python scripts/backup.py --dest D:\Hub-Backups    # send elsewhere
    python scripts/backup.py --keep 14                # keep 14 most recent

Schedule daily (Windows, Task Scheduler):
    schtasks /create /tn "QAHubDemoBackup" /tr "python C:\Automation\qa-hub-saucedemo\scripts\backup.py" /sc daily /st 02:00

Schedule daily (cron, Linux):
    0 2 * * * cd /opt/qa-hub-saucedemo && python scripts/backup.py
"""
import argparse
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

HUB_ROOT = Path(__file__).resolve().parent.parent

# Files/dirs to include, relative to HUB_ROOT. Missing items are silently skipped.
STATE_PATHS = [
    "config.json",
    "run_history.json",
    "schedules.json",
    "run_history_archive",
    "bugs",
]


def _iter_sources(root: Path):
    """Yield (absolute path, archive-name) for every file to include."""
    for rel in STATE_PATHS:
        p = root / rel
        if not p.exists():
            continue
        if p.is_file():
            yield p, rel
        else:
            for f in p.rglob("*"):
                if f.is_file():
                    yield f, str(f.relative_to(root)).replace("\\", "/")


def make_backup(dest_dir: Path) -> Path:
    """Build a zip of Hub state. Returns the final zip path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = dest_dir / f"hub-backup-{stamp}.zip"
    tmp = out.with_suffix(".zip.tmp")

    files = list(_iter_sources(HUB_ROOT))
    if not files:
        raise SystemExit("Nothing to back up — no state files found under " + str(HUB_ROOT))

    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_path, arcname in files:
            zf.write(abs_path, arcname)

    tmp.replace(out)  # atomic on POSIX + Windows
    return out


def prune_old_backups(dest_dir: Path, keep: int) -> int:
    """Remove all but the N most-recent hub-backup-*.zip files. Returns count removed."""
    if keep <= 0:
        return 0
    files = sorted(dest_dir.glob("hub-backup-*.zip"), key=lambda p: p.stat().st_mtime)
    excess = files[:-keep] if len(files) > keep else []
    for f in excess:
        f.unlink(missing_ok=True)
    return len(excess)


def main() -> None:
    p = argparse.ArgumentParser(description="Hub state backup to rotating zip archives")
    p.add_argument("--dest", default=str(HUB_ROOT / "backups"), help="backup directory (default: ./backups)")
    p.add_argument("--keep", type=int, default=30, help="max zips to retain (default: 30)")
    args = p.parse_args()

    dest = Path(args.dest)
    zip_path = make_backup(dest)
    pruned = prune_old_backups(dest, args.keep)

    size_kb = zip_path.stat().st_size / 1024
    msg = f"✓ backed up {len(list(_iter_sources(HUB_ROOT)))} files → {zip_path.name} ({size_kb:,.1f} KB)"
    if pruned:
        msg += f" · pruned {pruned} old backup(s)"
    print(msg)


if __name__ == "__main__":
    main()
