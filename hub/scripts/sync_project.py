"""
sync_project.py — Sync scaffolded files (scripts/templates/agents) จาก
qa-hub-saucedemo/scaffold/ ไปยัง project ปลายทาง

ใช้แก้ปัญหา drift: เมื่อ scaffold ถูก update แต่ project ที่ scaffold ออกไปแล้ว
ไม่ได้ sync — ทำให้ generate_report.py / template เก่าเกินไป

Usage:
    # 1) ตรวจ drift (read-only)
    python scripts/sync_project.py --project C:\\Automation\\KTB\\CR134

    # 2) Sync ทุกไฟล์ที่ drift (auto-backup ของเก่าที่ <file>.bak_<ts>)
    python scripts/sync_project.py --project C:\\Automation\\KTB\\CR134 --apply

    # 3) Sync เฉพาะไฟล์ที่ระบุ
    python scripts/sync_project.py --project C:\\Automation\\KTB\\CR134 --apply \\
        --files generate_report.py Test_Result_Template.docx

    # 4) บังคับใช้ scaffold type ที่กำหนด (default: auto-detect จาก CLAUDE.md)
    python scripts/sync_project.py --project C:\\Automation\\KTB\\CR134 \\
        --scaffold full-pipeline

Project type detection: อ่านบรรทัด `**Type**: <kind>` ใน <project>/CLAUDE.md
ถ้าไม่พบ → ต้องระบุ --scaffold

Files tracked (อยู่ในรายการแล้วเท่านั้นถึงจะ sync):
- scripts/*.py (ตัด __pycache__, *.bak_*, .template)
- templates/Test_Result_Template.docx
- templates/Test_Case_Template.xlsx
- templates/BA_Requirements_Template.xlsx
- agents/*.md
- requirements.txt

ไฟล์ที่ไม่ sync (project data หรือ scaffold-time only):
- CLAUDE.md, input/, output/, screenshots/, logs/, archive/
- requirements/, figma/, *.template, .gitkeep
"""
from __future__ import annotations
import argparse
import hashlib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HUB_DIR     = Path(__file__).resolve().parent.parent
SCAFFOLD_DIR = HUB_DIR / "scaffold"

# Relative paths (จาก project root) ที่จะ track ไว้ — แต่ไฟล์จริงต้องอยู่ใน scaffold ด้วย
TRACKED_PATTERNS = [
    "scripts/*.py",
    "templates/Test_Result_Template.docx",
    "templates/Test_Case_Template.xlsx",
    "templates/BA_Requirements_Template.xlsx",
    "agents/*.md",
    "requirements.txt",
]

# ตัดทิ้งระดับไฟล์ — ไฟล์ที่ match pattern แต่ติด exclude นี้จะข้าม
EXCLUDE_NAMES = {"__pycache__"}

def _is_excluded(path: Path) -> bool:
    if path.name in EXCLUDE_NAMES:
        return True
    if ".bak_" in path.name or ".bak." in path.name:
        return True
    if path.name.endswith(".template"):
        return True
    if path.name == ".gitkeep":
        return True
    return False


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_scaffold_type(project_dir: Path) -> str | None:
    """อ่าน CLAUDE.md หา `**Type**: <kind>`."""
    claude_md = project_dir / "CLAUDE.md"
    if not claude_md.exists():
        return None
    text = claude_md.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"\*\*Type\*\*:\s*([\w-]+)", text)
    if m:
        return m.group(1).strip()
    return None


def collect_scaffold_files(scaffold_dir: Path) -> list[Path]:
    """List ไฟล์ relevant ใน scaffold (ใช้ TRACKED_PATTERNS + exclude rules)."""
    files: list[Path] = []
    for pat in TRACKED_PATTERNS:
        for p in scaffold_dir.glob(pat):
            if p.is_file() and not _is_excluded(p):
                files.append(p)
    return sorted(set(files), key=lambda p: p.relative_to(scaffold_dir).as_posix())


def compare_files(scaffold_dir: Path, project_dir: Path) -> list[dict]:
    """Return list of {rel, status, scaffold_md5, project_md5, scaffold_mtime, project_mtime}.

    status: 'ok' | 'drift' | 'missing'
    """
    rows: list[dict] = []
    for s in collect_scaffold_files(scaffold_dir):
        rel = s.relative_to(scaffold_dir)
        target = project_dir / rel
        s_md5  = md5_of(s)
        s_mt   = datetime.fromtimestamp(s.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        if not target.exists():
            rows.append({
                "rel": rel.as_posix(), "status": "missing",
                "scaffold_md5": s_md5, "project_md5": "—",
                "scaffold_mtime": s_mt, "project_mtime": "—",
            })
            continue
        t_md5 = md5_of(target)
        t_mt  = datetime.fromtimestamp(target.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        rows.append({
            "rel": rel.as_posix(),
            "status": "ok" if s_md5 == t_md5 else "drift",
            "scaffold_md5": s_md5,  "project_md5": t_md5,
            "scaffold_mtime": s_mt, "project_mtime": t_mt,
        })
    return rows


def print_report(rows: list[dict], project_dir: Path, scaffold_type: str) -> None:
    print(f"  Project       : {project_dir}")
    print(f"  Scaffold type : {scaffold_type}")
    print(f"  Files tracked : {len(rows)}")
    print()
    statuses = {"ok": 0, "drift": 0, "missing": 0}
    for r in rows:
        statuses[r["status"]] += 1

    print(f"  ✓ OK      : {statuses['ok']}")
    print(f"  ⚠ Drift   : {statuses['drift']}")
    print(f"  ✗ Missing : {statuses['missing']}")
    print()

    drift_rows = [r for r in rows if r["status"] != "ok"]
    if not drift_rows:
        print("  All tracked files are in sync with scaffold.")
        return

    print("  Files needing attention:")
    print("  " + "─" * 78)
    print(f"  {'Status':<8} {'File':<48} {'Scaffold':<12} {'Project':<12}")
    print("  " + "─" * 78)
    for r in drift_rows:
        icon = "⚠" if r["status"] == "drift" else "✗"
        print(f"  {icon} {r['status']:<6} {r['rel']:<48} {r['scaffold_mtime']:<12} {r['project_mtime']:<12}")


def apply_sync(rows: list[dict], scaffold_dir: Path, project_dir: Path,
               filter_files: list[str] | None = None) -> int:
    """Backup existing → copy scaffold → return count of synced files."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    synced = 0
    for r in rows:
        if r["status"] == "ok":
            continue
        rel = Path(r["rel"])
        if filter_files and rel.name not in filter_files:
            continue

        src = scaffold_dir / rel
        dst = project_dir  / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Backup existing target (if present) using same .bak_<ts> convention as the scripts
        if dst.exists():
            bak = dst.with_name(dst.name + f".bak_{ts}")
            try:
                shutil.copy2(dst, bak)
                print(f"  ✓ backup → {bak.relative_to(project_dir)}")
            except Exception as e:
                print(f"  ⚠ backup failed for {dst.name}: {e}")
                continue
        shutil.copy2(src, dst)
        print(f"  ✓ synced → {rel.as_posix()}")
        synced += 1
    return synced


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync scaffolded files from qa-hub-saucedemo to a project")
    ap.add_argument("--project",  required=True, help="Path to target project root")
    ap.add_argument("--scaffold", choices=["manual-testing", "full-pipeline"],
                    help="Override scaffold type (default: auto-detect from CLAUDE.md)")
    ap.add_argument("--apply",    action="store_true", help="Apply sync (default: check only)")
    ap.add_argument("--files",    nargs="*", default=None,
                    help="Limit sync to specific basenames (only with --apply)")
    args = ap.parse_args()

    project_dir = Path(args.project).resolve()
    if not project_dir.is_dir():
        print(f"ERROR: Project not found: {project_dir}", file=sys.stderr)
        return 2

    # Determine scaffold type
    scaffold_type = args.scaffold or detect_scaffold_type(project_dir)
    if not scaffold_type:
        print("ERROR: Cannot determine scaffold type. Either:", file=sys.stderr)
        print("  - Add `**Type**: manual-testing` (or full-pipeline) to project CLAUDE.md", file=sys.stderr)
        print("  - Or pass --scaffold manual-testing|full-pipeline", file=sys.stderr)
        return 2

    scaffold_dir = SCAFFOLD_DIR / scaffold_type
    if not scaffold_dir.is_dir():
        print(f"ERROR: Scaffold not found: {scaffold_dir}", file=sys.stderr)
        return 2

    print(f"\n  qa-hub-saucedemo scaffold sync")
    print( "  ─────────────────────────────")
    rows = compare_files(scaffold_dir, project_dir)
    print_report(rows, project_dir, scaffold_type)

    if not args.apply:
        print()
        print("  (read-only) Run again with --apply to sync drifted files.")
        return 0

    print()
    print("  Applying sync ...")
    synced = apply_sync(rows, scaffold_dir, project_dir, filter_files=args.files)
    print()
    print(f"  Synced {synced} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
