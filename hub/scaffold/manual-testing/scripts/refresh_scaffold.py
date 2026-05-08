"""
Refresh the canonical scaffold at _hub/scaffold/ with the latest infrastructure
from THIS project. Run after improvements (preflight, validators, design rules,
template fixes) so future `init_project.py` runs and `_hub/scaffold/` copies
ALL inherit the gap-closure shell.

Usage:
    python scripts/refresh_scaffold.py              # dry run
    python scripts/refresh_scaffold.py --apply
    python scripts/refresh_scaffold.py --apply --target C:/custom/scaffold

Default target: C:/Automation/_hub/scaffold (Windows-friendly, side-by-side
with project folders under C:/Automation).

What gets pushed to scaffold:
  - All files tracked in this project's git EXCEPT:
      * `templates/*.bak_*`, `scripts/*.bak_*` (forensic backups)
      * Files under input/, output/, screenshots/, logs/, archive/ except .gitkeep
  - CLAUDE.md is sanitized: project-specific App name / Base URL / figma_url
    become {{APP_NAME}} / {{BASE_URL}} / {{FIGMA_URL}} placeholders so a
    fresh copy starts neutral. (init_project.py replaces them on scaffold.)

Sync semantics: idempotent. Files identical to scaffold are skipped; changed
files overwrite (no backup — scaffold is canonical, not project work). Files
present in scaffold but not in source are reported as DROP (and removed in
--apply).
"""
from __future__ import annotations
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = Path(r"C:/Automation/_hub/scaffold")


def git_tracked_files(root: Path) -> list[str]:
    r = subprocess.run(
        ["git", "ls-files"], cwd=str(root),
        capture_output=True, text=True, check=True,
    )
    return [line for line in r.stdout.splitlines() if line.strip()]


def is_forensic_backup(rel: str) -> bool:
    return bool(re.search(r"\.bak_[0-9_a-zA-Z]+", rel))


def is_runtime_artifact(rel: str) -> bool:
    head = rel.split("/", 1)[0]
    if head not in {"input", "output", "screenshots", "logs", "archive"}:
        return False
    # Keep .gitkeep so directory structure is preserved
    return not rel.endswith(".gitkeep")


def is_excluded(rel: str) -> bool:
    return is_forensic_backup(rel) or is_runtime_artifact(rel)


CLAUDE_SANITIZE_RULES = (
    (re.compile(r"(\*\*App name\*\*[:：]\s*).*"),    r"\1{{APP_NAME}}"),
    (re.compile(r"(\*\*Base URL\*\*[:：]\s*)`?[^`\n]*`?"), r"\1`{{BASE_URL}}`"),
    (re.compile(r"(\*\*figma_url\*\*[:：]\s*)`?[^`\n]*`?"), r"\1`{{FIGMA_URL}}`"),
)


def sanitize_claude_md(text: str) -> str:
    out = text
    for pat, repl in CLAUDE_SANITIZE_RULES:
        out = pat.sub(repl, out)
    return out


def hash_bytes(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()[:12]


def get_source_bytes(rel: str) -> bytes:
    """Read source file, applying sanitization for CLAUDE.md."""
    src_path = SRC_ROOT / rel
    data = src_path.read_bytes()
    if rel == "CLAUDE.md":
        try:
            text = data.decode("utf-8")
            data = sanitize_claude_md(text).encode("utf-8")
        except UnicodeDecodeError:
            pass
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Push canonical scaffold to _hub/scaffold/")
    ap.add_argument("--target", default=str(DEFAULT_TARGET),
                    help=f"Scaffold dir (default: {DEFAULT_TARGET})")
    ap.add_argument("--apply", action="store_true",
                    help="Actually write. Default: dry run.")
    ap.add_argument("--prune", action="store_true",
                    help="Delete scaffold files no longer in source (only with --apply)")
    args = ap.parse_args()

    target = Path(args.target)
    print(f"Source: {SRC_ROOT}")
    print(f"Target: {target}")
    print(f"Mode  : {'APPLY' if args.apply else 'DRY RUN'}\n")

    tracked = git_tracked_files(SRC_ROOT)
    keep = [r for r in tracked if not is_excluded(r)]
    excluded = [r for r in tracked if is_excluded(r)]

    print(f"  Tracked files in source: {len(tracked)}")
    print(f"  Excluded (forensic + runtime): {len(excluded)}")
    print(f"  Will sync: {len(keep)}\n")

    if excluded:
        print("  Excluded sample:")
        for r in excluded[:6]:
            print(f"    - {r}")
        if len(excluded) > 6:
            print(f"    - ... and {len(excluded) - 6} more")
        print()

    plans: list[dict] = []
    for rel in keep:
        src_data = get_source_bytes(rel)
        src_hash = hash_bytes(src_data)
        dst_path = target / rel
        if dst_path.exists():
            dst_hash = hash_bytes(dst_path.read_bytes())
            status = "SAME" if src_hash == dst_hash else "UPDATE"
        else:
            dst_hash = "(absent)"
            status = "NEW"
        plans.append({"rel": rel, "status": status, "src_hash": src_hash,
                      "dst_hash": dst_hash, "data": src_data, "dst": dst_path})

    # Detect prune candidates
    if target.exists():
        existing = {str(p.relative_to(target)).replace("\\", "/")
                    for p in target.rglob("*") if p.is_file()}
    else:
        existing = set()
    sourced = {p["rel"] for p in plans}
    prune_list = sorted(existing - sourced)

    counts: dict[str, int] = {}
    for p in plans:
        counts[p["status"]] = counts.get(p["status"], 0) + 1

    nonzero = [p for p in plans if p["status"] != "SAME"]
    print(f"  {'Status':<8s} {'File':<55s} {'src':<14s} {'dst':<14s}")
    print(f"  {'-'*8:<8s} {'-'*55:<55s} {'-'*14:<14s} {'-'*14:<14s}")
    for p in nonzero[:60]:
        print(f"  {p['status']:<8s} {p['rel']:<55s} {p['src_hash']:<14s} {p['dst_hash']:<14s}")
    if len(nonzero) > 60:
        print(f"  ... and {len(nonzero) - 60} more")

    if prune_list:
        print(f"\n  Prune candidates ({len(prune_list)} — only deleted with --apply --prune):")
        for r in prune_list[:10]:
            print(f"    - {r}")
        if len(prune_list) > 10:
            print(f"    - ... and {len(prune_list) - 10} more")

    print()
    print("Summary:", " ".join(f"{k}={v}" for k, v in sorted(counts.items())),
          f"PRUNE-CAND={len(prune_list)}")

    if not args.apply:
        print("\n(dry run — re-run with --apply)")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    written = 0
    for p in plans:
        if p["status"] == "SAME":
            continue
        p["dst"].parent.mkdir(parents=True, exist_ok=True)
        p["dst"].write_bytes(p["data"])
        # Preserve hook executable bit
        if p["rel"].startswith(".githooks/"):
            try:
                p["dst"].chmod(0o755)
            except Exception:
                pass
        written += 1
    print(f"\nWrote {written} file(s).")

    if args.prune and prune_list:
        for r in prune_list:
            (target / r).unlink(missing_ok=True)
        print(f"Pruned {len(prune_list)} file(s).")

    print("\nNext steps:")
    print(f"  - Scaffold ready at {target}")
    print( "  - To create a new project from it:")
    print(f"      cp -r {target} /path/to/new-project")
    print( "      cd /path/to/new-project && python scripts/init_project.py --name Foo --url https://...")
    print( "    (or just init_project.py — it auto-detects this scaffold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
