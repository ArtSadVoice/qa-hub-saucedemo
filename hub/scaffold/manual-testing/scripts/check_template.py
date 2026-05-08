"""
Standalone CLI: validate a Word template before swapping it into the project.

Usage:
    python scripts/check_template.py                     # check current template, structural only
    python scripts/check_template.py path/to/Other.docx  # check arbitrary file
    python scripts/check_template.py --smoke             # also run external-tool smoke test
    python scripts/check_template.py path --smoke        # both

Exit codes:
    0 — template valid
    1 — template has issues (structural or smoke-test fail)

Run this BEFORE replacing templates/Test_Result_Template.docx with a downloaded
template. Catches the breakage seen with v2_1 (duplicate styleIds, missing
core styles) that python-docx accepts but Word rejects.

The optional --smoke flag exercises the file via external tools as a proxy
for Word: python-docx round-trip, LibreOffice headless convert (if installed),
and Word COM (if Office + pywin32 are installed).
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = ROOT / "templates" / "Test_Result_Template.docx"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _preflight import (  # noqa: E402
    validate_template_structure,
    smoke_test_template,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a Word template")
    ap.add_argument("path", nargs="?", default=str(DEFAULT_TEMPLATE),
                    help="Path to template (default: templates/Test_Result_Template.docx)")
    ap.add_argument("--smoke", action="store_true",
                    help="Also run external-tool smoke test (LibreOffice / Word COM)")
    args = ap.parse_args()

    target = Path(args.path)
    print(f"Checking: {target}")
    rc = 0

    # 1. Structural
    issues = validate_template_structure(target, strict=False)
    if not issues:
        print("  [structural] OK — passes all required structural checks.")
    else:
        print(f"  [structural] FAIL — {len(issues)} issue(s):")
        for i in issues:
            print(f"    - {i}")
        rc = 1

    # 2. Smoke (optional)
    if args.smoke:
        print("\nSmoke test (best-effort, requires external tools):")
        results = smoke_test_template(target)
        any_fail = False
        any_ok = False
        for tool, status in results.items():
            label = "ok " if status == "ok" else ("skip" if status.startswith("skip") else "FAIL")
            print(f"  [{label}] {tool:14s} {status}")
            if status == "ok":
                any_ok = True
            elif not status.startswith("skip"):
                any_fail = True
        if any_fail:
            rc = 1
        elif not any_ok:
            print("\n  Note: no smoke-test tool was available. Install one for stronger coverage:")
            print("    - LibreOffice  (https://www.libreoffice.org) → soffice on PATH")
            print("    - pywin32      (pip install pywin32)        → Word COM (Windows + Office)")

    return rc


if __name__ == "__main__":
    sys.exit(main())
