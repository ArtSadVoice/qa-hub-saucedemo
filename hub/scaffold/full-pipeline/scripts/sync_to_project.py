"""
Sync the gap-closure infrastructure from this canonical project into another
QA-pipeline project. Use this to retrofit existing projects with the
preflight + template-validator + git-hook + design rules from <canonical>.

Usage:
    python scripts/sync_to_project.py /path/to/other/project          # dry run
    python scripts/sync_to_project.py /path/to/other/project --apply  # actually copy
    python scripts/sync_to_project.py /path/to/other/project --apply --include-template
    python scripts/sync_to_project.py /path/to/other/project --apply --include-pipeline-scripts

Sync layers (opt-in via flags):
  ALWAYS (always copied with --apply):
    scripts/_preflight.py        — preflight helpers (pure utility)
    scripts/check_template.py    — standalone template validator CLI
    .githooks/pre-commit         — pre-commit template guard

  --include-pipeline-scripts:
    scripts/generate_report.py   — design rules (12pt body, 14pt heading, all
                                   borders, signoff layout)
    scripts/generate_tcm.py      — preflight-wired TCM writer
    scripts/orchestrator.py      — preflight-wired orchestrator
    scripts/add_excel_charts.py  — preflight-wired chart writer
    scripts/screenshot_injector.py — preflight-wired docx writer
    These have non-trivial project logic. Existing files in target are
    backed up to <name>.docx.bak_<ts>.

  --include-template:
    templates/Test_Result_Template.docx — production template
    Same backup-before-overwrite policy.

NEVER copied (project-specific):
  CLAUDE.md, requirements/, input/, output/, screenshots/, logs/, .env

After --apply, if target has .git, sets `core.hooksPath = .githooks`
unless you pass --no-hooks.
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent

# Layered file lists relative to project root.
ALWAYS = [
    "scripts/_preflight.py",
    "scripts/check_template.py",
    ".githooks/pre-commit",
]

PIPELINE_SCRIPTS = [
    "scripts/generate_report.py",
    "scripts/generate_tcm.py",
    "scripts/generate_chart.py",
    "scripts/orchestrator.py",
    "scripts/add_excel_charts.py",
    "scripts/screenshot_injector.py",
]

TEMPLATE_FILES = [
    "templates/Test_Result_Template.docx",
]


def hash_file(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else "(absent)"


def plan_copy(rel: str, src_root: Path, dst_root: Path) -> dict:
    src = src_root / rel
    dst = dst_root / rel
    if not src.exists():
        return {"rel": rel, "status": "MISSING-SRC", "src": src, "dst": dst,
                "src_hash": "—", "dst_hash": hash_file(dst)}
    src_h = hash_file(src)
    dst_h = hash_file(dst)
    if not dst.exists():
        status = "NEW"
    elif src_h == dst_h:
        status = "SAME"
    else:
        status = "DIFF"
    return {"rel": rel, "status": status, "src": src, "dst": dst,
            "src_hash": src_h, "dst_hash": dst_h}


def apply_copy(plan: dict) -> str:
    src, dst = plan["src"], plan["dst"]
    if plan["status"] == "SAME" or plan["status"] == "MISSING-SRC":
        return "no-op"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if plan["status"] == "DIFF" and dst.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = dst.with_name(dst.name + f".bak_synct_{ts}")
        shutil.copy2(dst, bak)
        result = f"backed up -> {bak.name}; copied"
    else:
        result = "copied"
    shutil.copy2(src, dst)
    # Preserve executable bit for hook
    if rel_is_hook(plan["rel"]):
        try:
            dst.chmod(0o755)
        except Exception:
            pass
    return result


def rel_is_hook(rel: str) -> bool:
    return rel.startswith(".githooks/")


def activate_hooks(target_root: Path) -> str:
    """If target is a git repo, set core.hooksPath = .githooks."""
    if not (target_root / ".git").exists():
        return "skipped (target is not a git repo — run `git init` then re-sync)"
    try:
        r = subprocess.run(
            ["git", "config", "core.hooksPath", ".githooks"],
            cwd=str(target_root), capture_output=True, text=True,
        )
        if r.returncode == 0:
            return "set core.hooksPath = .githooks"
        return f"failed: {r.stderr.strip()}"
    except FileNotFoundError:
        return "skipped (git not on PATH)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target", help="Path to the target project root")
    ap.add_argument("--apply", action="store_true",
                    help="Actually copy. Without this flag, prints the plan only.")
    ap.add_argument("--include-pipeline-scripts", action="store_true",
                    help="Also overwrite generate_*.py / orchestrator.py / writers (with backup)")
    ap.add_argument("--include-template", action="store_true",
                    help="Also overwrite templates/Test_Result_Template.docx (with backup)")
    ap.add_argument("--no-hooks", action="store_true",
                    help="Don't set core.hooksPath in target")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    src_root = SRC_ROOT.resolve()
    if target == src_root:
        print("ERROR: target is the source project itself.")
        return 2
    if not target.exists():
        print(f"ERROR: target does not exist: {target}")
        return 2

    files = list(ALWAYS)
    if args.include_pipeline_scripts:
        files += PIPELINE_SCRIPTS
    if args.include_template:
        files += TEMPLATE_FILES

    print(f"Source: {src_root}")
    print(f"Target: {target}")
    print(f"Mode  : {'APPLY (will copy)' if args.apply else 'DRY RUN (print only)'}")
    print()

    plans = [plan_copy(rel, src_root, target) for rel in files]

    print(f"  {'Status':<10s} {'File':<45s} {'src':<14s} {'dst':<14s}")
    print(f"  {'-'*10:<10s} {'-'*45:<45s} {'-'*14:<14s} {'-'*14:<14s}")
    for p in plans:
        print(f"  {p['status']:<10s} {p['rel']:<45s} {p['src_hash']:<14s} {p['dst_hash']:<14s}")

    counts: dict[str, int] = {}
    for p in plans:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    print()
    print("Summary:", " ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    if not args.apply:
        print("\n(dry run — re-run with --apply to copy)")
        return 0

    print("\nApplying...")
    actioned = 0
    for p in plans:
        result = apply_copy(p)
        if result != "no-op":
            print(f"  {p['rel']:<45s} {result}")
            actioned += 1

    print(f"\nActioned {actioned} file(s).")

    if not args.no_hooks:
        msg = activate_hooks(target)
        print(f"git hooks: {msg}")

    print("\nNext steps for target project:")
    print("  1. Inspect any *.bak_synct_* files to confirm you didn't lose local edits")
    print("  2. cd <target> && python scripts/check_template.py    # verify template still validates")
    print("  3. cd <target> && git diff                              # review the import")
    return 0


if __name__ == "__main__":
    sys.exit(main())
