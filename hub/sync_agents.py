"""
sync_agents.py — QA Hub Demo: Sync scaffold files to registered projects

Usage:
    python sync_agents.py                    # sync ทุก project ที่ active
    python sync_agents.py --project bay-voc  # sync เฉพาะ project นี้
    python sync_agents.py --dry-run          # ดูว่าจะเปลี่ยนอะไร ไม่แตะไฟล์จริง
    python sync_agents.py --force            # overwrite แม้ไฟล์ถูกแก้ใน project
    python sync_agents.py --only agents      # sync เฉพาะ group (agents/commands/scripts)

Syncs (Group A — safe to overwrite):
    scaffold/full-pipeline/agents/           →  <project>/agents/
    scaffold/full-pipeline/.claude/agents/   →  <project>/.claude/agents/
    scaffold/full-pipeline/.claude/commands/ →  <project>/.claude/commands/
    scaffold/full-pipeline/scripts/          →  <project>/scripts/
"""

import sys, json, shutil, hashlib, argparse
from pathlib import Path
from datetime import datetime

HUB_DIR     = Path(__file__).resolve().parent
ROOT_DIR    = HUB_DIR.parent
CONFIG_FILE = HUB_DIR / "config.json"

SCAFFOLDS = {
    "full-pipeline":  HUB_DIR / "scaffold" / "full-pipeline",
    "manual-testing": HUB_DIR / "scaffold" / "manual-testing",
    "playwright-only": HUB_DIR / "scaffold" / "full-pipeline",  # ใช้ full-pipeline scaffold
}
SCAFFOLD = SCAFFOLDS["full-pipeline"]  # default

# (src_dir, glob_pattern, label)
SYNC_GROUPS = {
    "agents": [
        ("agents",          "*.md",  "agents"),
        (".claude/agents",  "*.md",  ".claude/agents"),
    ],
    "commands": [
        (".claude/commands", "*.md", ".claude/commands"),
    ],
    "scripts": [
        ("scripts", "*.py", "scripts"),
    ],
}

# ไฟล์ที่ไม่ sync แม้อยู่ใน scaffold (มี placeholder หรือ project-specific)
EXCLUDE_FILES = {
    "scripts": {"init_project.py"},
}

def load_config():
    if not CONFIG_FILE.exists():
        print("❌ ไม่พบ config.json")
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

def resolve_path(raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else (ROOT_DIR / raw).resolve()

def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()

def sync_dir(src_dir: Path, dst_dir: Path, glob: str, label: str,
             exclude: set, dry_run: bool, force: bool, result: dict):
    if not src_dir.exists():
        return
    if not dry_run:
        dst_dir.mkdir(parents=True, exist_ok=True)

    for src_file in sorted(src_dir.glob(glob)):
        if src_file.name in exclude:
            continue
        dst_file = dst_dir / src_file.name

        if dst_file.exists():
            if file_hash(src_file) == file_hash(dst_file):
                continue
            if not force:
                result["skipped"].append(
                    f"{label}/{src_file.name} — แตกต่างจาก scaffold (ใช้ --force เพื่อ overwrite)"
                )
                continue
            if not dry_run:
                shutil.copy2(src_file, dst_file)
            result["updated"].append(f"{label}/{src_file.name}")
        else:
            if not dry_run:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
            result["new"].append(f"{label}/{src_file.name}")


def sync_project(project: dict, dry_run: bool, force: bool, only: str | None) -> dict:
    name = project["name"]
    phase = project.get("phase", "active")
    proj_type = project.get("type", "full-pipeline")
    proj_path = resolve_path(project["path"])
    scaffold = SCAFFOLDS.get(proj_type, SCAFFOLD)

    result = {"name": name, "skipped": [], "updated": [], "new": [], "errors": []}

    if not proj_path.exists():
        result["errors"].append(f"path ไม่พบ: {proj_path}")
        return result

    if phase != "active":
        result["skipped"].append(f"phase={phase} — ข้าม")
        return result

    groups = {only: SYNC_GROUPS[only]} if only and only in SYNC_GROUPS else SYNC_GROUPS

    for group_name, entries in groups.items():
        exclude = EXCLUDE_FILES.get(group_name, set())
        for src_rel, glob, label in entries:
            sync_dir(
                scaffold / src_rel, proj_path / src_rel,
                glob, label, exclude, dry_run, force, result
            )

    # สร้าง docs/reviews/ ถ้ายังไม่มี
    reviews_dir = proj_path / "docs" / "reviews"
    if not reviews_dir.exists():
        if not dry_run:
            reviews_dir.mkdir(parents=True, exist_ok=True)
            (reviews_dir / ".gitkeep").touch()
        result["new"].append("docs/reviews/")

    # บันทึก .last-sync timestamp
    if not dry_run and (result["new"] or result["updated"]):
        last_sync_file = proj_path / ".claude" / "agents" / ".last-sync"
        last_sync_file.write_text(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            encoding="utf-8"
        )

    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", help="project id ที่ต้องการ sync (ถ้าไม่ระบุ = ทุก active project)")
    parser.add_argument("--dry-run", action="store_true", help="ดูผลลัพธ์โดยไม่แตะไฟล์จริง")
    parser.add_argument("--force", action="store_true", help="overwrite ไฟล์ที่แตกต่างจาก scaffold")
    parser.add_argument("--only", choices=["agents", "commands", "scripts"],
                        help="sync เฉพาะ group นี้เท่านั้น")
    args = parser.parse_args()

    cfg = load_config()
    projects = cfg.get("projects", [])

    if args.project:
        projects = [p for p in projects if p["id"] == args.project]
        if not projects:
            print(f"❌ ไม่พบ project id: {args.project}")
            sys.exit(1)

    if not projects:
        print("❌ ไม่มี project ใน config.json")
        sys.exit(1)

    mode = "[DRY RUN] " if args.dry_run else ""
    scope = f"[{args.only}] " if args.only else ""
    print(f"\n{'═'*55}")
    print(f"  QA Hub Demo — Scaffold Sync  {scope}{mode}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*55}\n")

    total_new = total_updated = total_skipped = total_errors = 0

    for project in projects:
        result = sync_project(project, args.dry_run, args.force, args.only)
        name = result["name"]

        has_changes = result["new"] or result["updated"] or result["errors"]
        status = "✅" if not result["errors"] else "❌"
        print(f"{status} {name}")

        for f in result["new"]:
            print(f"   + {f}")
            total_new += 1
        for f in result["updated"]:
            print(f"   ↑ {f}")
            total_updated += 1
        for f in result["skipped"]:
            print(f"   ~ {f}")
            total_skipped += 1
        for f in result["errors"]:
            print(f"   ✗ {f}")
            total_errors += 1

        if not has_changes and not result["skipped"]:
            # แสดง last-sync date ถ้ามี
            last_sync = resolve_path(project["path"]) / ".claude" / "agents" / ".last-sync"
            if last_sync.exists():
                ts = last_sync.read_text(encoding="utf-8").strip()
                print(f"   (up-to-date — last sync: {ts})")
            else:
                print("   (ไม่มีการเปลี่ยนแปลง — ทุกไฟล์ตรงกับ scaffold แล้ว)")

    print(f"\n{'─'*55}")
    print(f"  + new: {total_new}  ↑ updated: {total_updated}  ~ skipped: {total_skipped}  ✗ errors: {total_errors}")
    if args.dry_run:
        print("  (dry run — ไม่มีไฟล์ถูกแก้ไขจริง)")
    print(f"{'─'*55}\n")

if __name__ == "__main__":
    main()
