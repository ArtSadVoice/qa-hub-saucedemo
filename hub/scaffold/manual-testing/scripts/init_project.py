"""
init_project.py — Initialize a new project from this template
==============================================================

Usage:
    python scripts/init_project.py --name NewProject --url https://your-app.com/path
    python scripts/init_project.py --name NewProject --url https://... --dest C:/Projects/

สิ่งที่ทำอัตโนมัติ:
  1. Copy project folder ไปยัง destination
  2. ล้างข้อมูลเก่า (screenshots, output, logs, archive)
  3. อัปเดต BASE_URL ใน SurveyPage.ts
  4. อัปเดต App name + Base URL ใน CLAUDE.md
  5. ลบ input/*.xlsx เก่า (เพื่อให้ใส่ไฟล์ใหม่)
  6. แสดงขั้นตอนถัดไปที่ต้องทำ
"""
import argparse, shutil, re, sys
from pathlib import Path


def clear_dir(d: Path):
    """ลบไฟล์ทั้งหมดในโฟลเดอร์ แต่เก็บโฟลเดอร์ไว้"""
    if d.exists():
        for f in d.iterdir():
            if f.is_file():
                f.unlink()
            elif f.is_dir():
                shutil.rmtree(f)
    d.mkdir(parents=True, exist_ok=True)


def update_survey_page(dest: Path, url: str):
    ts_file = dest / "tests" / "e2e" / "pages" / "SurveyPage.ts"
    if not ts_file.exists():
        print(f"  ⚠️  ไม่พบ {ts_file.name} — ข้าม")
        return
    content = ts_file.read_text(encoding="utf-8")
    updated = re.sub(
        r"(const BASE_URL\s*=\s*process\.env\.BASE_URL\s*\|\|\s*')[^']*(')",
        rf"\g<1>{url}\g<2>",
        content,
    )
    if updated == content:
        print(f"  ⚠️  ไม่พบ BASE_URL pattern ใน SurveyPage.ts — แก้เองด้วยนะ")
    else:
        ts_file.write_text(updated, encoding="utf-8")
        print(f"  ✓  SurveyPage.ts → BASE_URL = {url}")


def update_claude_md(dest: Path, name: str, url: str):
    md_file = dest / "CLAUDE.md"
    if not md_file.exists():
        print(f"  ⚠️  ไม่พบ CLAUDE.md — ข้าม")
        return
    content = md_file.read_text(encoding="utf-8")
    # Update App name
    content = re.sub(r"(\*\*App name\*\*:).*", rf"\1 {name}", content)
    # Update Base URL
    content = re.sub(r"(\*\*Base URL\*\*:).*", rf"\1 `{url}`", content)
    md_file.write_text(content, encoding="utf-8")
    print(f"  ✓  CLAUDE.md → App name = {name}, Base URL = {url}")


def main():
    ap = argparse.ArgumentParser(description="Initialize a new project from template")
    ap.add_argument("--name", required=True, help="ชื่อ project ใหม่ (e.g. MyNewProject)")
    ap.add_argument("--url",  required=True, help="Base URL ของ app ที่จะ test")
    ap.add_argument("--dest", default=None,  help="ที่จะ copy ไป (default: ../[name])")
    args = ap.parse_args()

    src  = Path(__file__).parent.parent
    dest = Path(args.dest) if args.dest else src.parent / args.name

    print(f"\n{'='*55}")
    print(f"  Init Project: {args.name}")
    print(f"  Source:       {src}")
    print(f"  Destination:  {dest}")
    print(f"  Base URL:     {args.url}")
    print(f"{'='*55}\n")

    # 1. Copy project
    if dest.exists():
        ans = input(f"  ⚠️  {dest} มีอยู่แล้ว — overwrite? (y/N): ").strip().lower()
        if ans != "y":
            print("  ยกเลิก")
            sys.exit(0)
        shutil.rmtree(dest)

    print("  📁 Copying project...")
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", "node_modules", ".git", ".playwright-mcp"
    ))
    print(f"  ✓  Copied → {dest}")

    # 2. Clear old data
    print("\n  🧹 Clearing old data...")
    for folder in ["screenshots", "output", "logs", "archive"]:
        clear_dir(dest / folder)
        print(f"  ✓  {folder}/ cleared")

    # 3. Clear input Excel
    for f in (dest / "input").glob("*.xlsx"):
        f.unlink()
        print(f"  ✓  Removed input/{f.name}")

    # 4. Update BASE_URL
    print("\n  ⚙️  Updating configuration...")
    update_survey_page(dest, args.url)

    # 5. Update CLAUDE.md
    update_claude_md(dest, args.name, args.url)

    # 6. Clear PID file if exists
    pid_file = dest / "web" / ".server.pid"
    if pid_file.exists():
        pid_file.unlink()

    # Done
    print(f"\n{'='*55}")
    print(f"  ✅  Project initialized: {dest.name}")
    print(f"{'='*55}")
    print(f"""
  ขั้นตอนถัดไป:
  1. cd \"{dest}\"
  2. วาง Excel TCM ใน input/  (หรือรัน BA Agent)
  3. ตรวจสอบ tests/e2e/ spec files ให้ตรงกับ UI ใหม่
  4. python scripts/add_excel_charts.py
  5. python web/app.py
""")


if __name__ == "__main__":
    main()
