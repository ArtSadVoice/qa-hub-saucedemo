r"""Seed universal Claude memory for a project so it applies no matter
which directory Claude Code is invoked from.

Memory in Claude Code is tied to the invocation CWD. The universal
principles (user role, working preferences) are saved at the home dir
slug — invoking Claude from a sub-project directly means none of that
context loads. This script mirrors the two universal memory files into
the target project's memory namespace.

Project-specific memory (e.g. project_f180_hub.md) is NOT copied — each
project should keep its own context where it matters.

Usage:
    python scripts/init_project_memory.py --path C:\Automation\BAY\e2e-surveys-bay
    python scripts/init_project_memory.py --all            # every project in Hub's config.json + Hub itself

Idempotent: re-running overwrites the two universal files with the current
source (scaffold/memory/*.md). It never touches project-specific memory entries.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HUB_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_MEMORY = HUB_ROOT / "scaffold" / "memory"
USER_HOME = Path.home()
CLAUDE_PROJECTS = USER_HOME / ".claude" / "projects"

UNIVERSAL_FILES = ("user_role.md", "feedback_principles.md")


def _slug(abs_path: Path) -> str:
    r"""Produce the Claude Code 'projects' slug from an absolute path.
    Matches the existing convention: each of : \ / ( ) becomes a single '-'."""
    s = str(abs_path)
    for ch in ":\\/()":
        s = s.replace(ch, "-")
    return s


def _ensure_universal_memory(memory_dir: Path, overwrite: bool = True) -> list[str]:
    """Copy universal files from scaffold/memory/ into memory_dir. Returns list of actions taken."""
    memory_dir.mkdir(parents=True, exist_ok=True)
    actions = []
    for fname in UNIVERSAL_FILES:
        src = SCAFFOLD_MEMORY / fname
        if not src.exists():
            actions.append(f"skip {fname} (source missing: {src})")
            continue
        dst = memory_dir / fname
        if dst.exists() and not overwrite:
            actions.append(f"keep {fname}")
            continue
        shutil.copy2(src, dst)
        actions.append(f"copy {fname}")

    # MEMORY.md index: merge, don't clobber project-specific entries
    index = memory_dir / "MEMORY.md"
    existing_lines = []
    if index.exists():
        existing_lines = [
            l for l in index.read_text(encoding="utf-8").splitlines()
            if not any(f"]({u})" in l for u in UNIVERSAL_FILES)
        ]
    header_lines = [
        "- [User Role & Interests](user_role.md) — QA Lead + Automation Engineer; สื่อสารภาษาไทย",
        "- [Core Working Principles](feedback_principles.md) — Think Before Coding · Simplicity First · Goal-Driven Execution",
    ]
    # Universal lines first, then any existing project-specific lines
    all_lines = header_lines + [l for l in existing_lines if l.strip()]
    index.write_text("\n".join(all_lines) + "\n", encoding="utf-8")
    actions.append("write MEMORY.md")
    return actions


def init_for_path(abs_path: Path, overwrite: bool = True) -> Path:
    slug = _slug(abs_path)
    memory_dir = CLAUDE_PROJECTS / slug / "memory"
    _ensure_universal_memory(memory_dir, overwrite=overwrite)
    return memory_dir


def _every_project_path() -> list[Path]:
    """All project paths in config.json, resolved under ROOT_DIR (C:\\Automation\\)."""
    root_dir = HUB_ROOT.parent
    config = json.loads((HUB_ROOT / "config.json").read_text(encoding="utf-8"))
    paths = [HUB_ROOT]  # include Hub itself
    for p in config.get("projects", []):
        rel = p.get("path", "")
        if not rel:
            continue
        abs_p = Path(rel)
        if not abs_p.is_absolute():
            abs_p = (root_dir / rel).resolve()
        paths.append(abs_p)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--path", help="absolute project path to seed memory for")
    group.add_argument("--all", action="store_true", help="seed every project listed in Hub's config.json")
    ap.add_argument("--no-overwrite", action="store_true", help="keep existing universal files instead of replacing them")
    args = ap.parse_args()

    if not SCAFFOLD_MEMORY.is_dir():
        raise SystemExit(f"Source folder not found: {SCAFFOLD_MEMORY}. Create scaffold/memory/ with user_role.md and feedback_principles.md first.")

    overwrite = not args.no_overwrite
    if args.all:
        targets = _every_project_path()
    else:
        targets = [Path(args.path).resolve()]

    print(f"Seeding memory for {len(targets)} project(s) into {CLAUDE_PROJECTS}\n")
    for p in targets:
        mem = init_for_path(p, overwrite=overwrite)
        print(f"✓ {p}")
        print(f"  → {mem}")
    print(f"\nDone. ({len(targets)} projects seeded.)")


if __name__ == "__main__":
    main()
