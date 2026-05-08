"""
orchestrator.py
───────────────
Main agentic loop:
  Input (Figma / doc) → BA Agent → Test Case Agent → Playwright Agent → Test Result Agent

Usage:
  python scripts/orchestrator.py --input "requirement.md"
  python scripts/orchestrator.py --figma "https://figma.com/file/xxx" --frame "Login Screen"
  python scripts/orchestrator.py --input "requirement.md" --skip-playwright   # BA + TCM only
"""

import os
import sys
import json
import argparse
import base64
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
CLAUDE_MD    = PROJECT_ROOT / "CLAUDE.md"
AGENTS_DIR   = PROJECT_ROOT / "agents"
OUTPUT_DIR   = PROJECT_ROOT / "output"
INPUT_DIR    = PROJECT_ROOT / "input"
LOG_DIR      = PROJECT_ROOT / "logs"

# ── Helpers ───────────────────────────────────────────────

def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def read_agent_prompt(name: str) -> str:
    return read_file(AGENTS_DIR / f"{name}.md")

def log(stage: str, message: str):
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{stage}] {message}"
    print(line)
    with open(LOG_DIR / f"run_{datetime.now().strftime('%Y%m%d')}.log", "a") as f:
        f.write(line + "\n")

def save_json(data: dict, name: str):
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return path

import subprocess, json, tempfile, os, shutil


def _resolve_claude_exe():
    """หา claude CLI binary
    ลำดับการค้นหา:
      1. CLAUDE_CLI_PATH env var (explicit override)
      2. shutil.which("claude") — PATH lookup
      3. Probe install locations ปกติ (~/.local/bin, %APPDATA%/npm, ...)
      4. Enumerate C:\\Users\\*\\.local\\bin\\claude.* เป็น fallback กว้าง
         (Hub/service launcher บน Windows อาจไม่ inherit USERPROFILE ของ user)
    Returns: (path, candidates_tried) — path คือ None ถ้าไม่เจอ
    """
    candidates = []

    # 1. Explicit override
    override = os.environ.get("CLAUDE_CLI_PATH", "").strip()
    if override:
        candidates.append(("CLAUDE_CLI_PATH", Path(override)))
        if Path(override).exists():
            return str(Path(override)), candidates

    # 2. PATH lookup
    found = shutil.which("claude")
    candidates.append(("shutil.which", found or "(not on PATH)"))
    if found:
        return found, candidates

    # 3. Known install locations
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", ""))
    program_files = Path(os.environ.get("ProgramFiles", ""))
    known = [
        home / ".local" / "bin" / "claude.exe",
        home / ".local" / "bin" / "claude.cmd",
        home / ".local" / "bin" / "claude",
        appdata / "npm" / "claude.cmd",
        appdata / "npm" / "claude.exe",
        program_files / "Claude" / "claude.exe",
    ]
    for p in known:
        candidates.append(("known", p))
        try:
            if p.exists():
                return str(p), candidates
        except OSError:
            continue

    # 4. Enumerate C:\Users\*\.local\bin\claude.*
    users_root = Path("C:/Users")
    if users_root.exists():
        for user_dir in users_root.iterdir():
            for ext in ("exe", "cmd", ""):
                p = user_dir / ".local" / "bin" / (f"claude.{ext}" if ext else "claude")
                candidates.append(("users-scan", p))
                try:
                    if p.exists():
                        return str(p), candidates
                except OSError:
                    continue

    return None, candidates

# ── Agent caller — SDK if API key available, else claude CLI ──────────────────

def _call_via_sdk(system_prompt: str, user_message) -> str:
    """Call Claude via anthropic SDK (requires ANTHROPIC_API_KEY)."""
    import anthropic
    client = anthropic.Anthropic()
    # user_message can be str or list of content blocks (image + text)
    content = user_message if isinstance(user_message, list) else user_message
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8096,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


def _call_via_cli(system_prompt: str, user_message) -> str:
    """Call Claude via claude -p CLI (no API key needed).
    Streams stdout line-by-line so Hub watchdog does not timeout on silence."""
    text = user_message if isinstance(user_message, str) else user_message[-1]["text"]
    prompt_text = f"{system_prompt}\n\n---\n\n{text}"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt_text)
        tmp_path = f.name

    claude_exe, tried = _resolve_claude_exe()
    if not claude_exe:
        diag = "\n".join(f"  [{src}] {p}" for src, p in tried)
        raise FileNotFoundError(
            "ไม่พบ claude CLI\n"
            f"USERPROFILE = {os.environ.get('USERPROFILE')}\n"
            f"Path.home()  = {Path.home()}\n"
            f"ตำแหน่งที่ลอง:\n{diag}\n"
            "วิธีแก้:\n"
            "  • เซ็ต CLAUDE_CLI_PATH=<full path to claude.exe> ใน environment\n"
            "  • หรือ install ใหม่: npm install -g @anthropic-ai/claude-code\n"
            "  • หรือเซ็ต ANTHROPIC_API_KEY เพื่อใช้ SDK แทน"
        )

    try:
        with open(tmp_path, "r", encoding="utf-8") as f:
            proc = subprocess.Popen(
                [claude_exe, "-p"],
                stdin=f,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
            )
        lines = []
        for line in proc.stdout:
            print(line, end="", flush=True)
            lines.append(line)
        proc.wait()
        output = "".join(lines).strip()

        # Auth check — claude CLI prints "Not logged in" และ exit 0 ถ้ายัง login
        # ไม่ผ่าน ถ้าไม่ detect ตรงนี้ JSON parse จะ fail แทน confusing
        if "Not logged in" in output or "Please run /login" in output:
            raise RuntimeError(
                "claude CLI ยังไม่ได้ login\n"
                "วิธีแก้: เปิด terminal interactive แล้วรัน `claude` หนึ่งครั้ง → ทำตามขั้นตอน /login\n"
                "หรือเซ็ต ANTHROPIC_API_KEY ใน environment เพื่อใช้ SDK แทน CLI"
            )
        return output
    finally:
        os.unlink(tmp_path)


def call_agent(system_prompt, user_message, stage):
    """Call Claude: SDK if ANTHROPIC_API_KEY is set, otherwise fall back to claude CLI."""
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        try:
            return _call_via_sdk(system_prompt, user_message)
        except Exception as e:
            log(stage, f"SDK error ({e}) — falling back to claude CLI")
    return _call_via_cli(system_prompt, user_message)


def preflight_auth_check() -> None:
    """Verify auth is available before starting the pipeline.
    Fails fast with a clear message instead of crashing mid-stage after
    loading requirements and building prompts.
    """
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return  # SDK path — API key present

    # CLI path — need a logged-in claude binary
    claude_exe, tried = _resolve_claude_exe()
    if not claude_exe:
        diag = "\n".join(f"  [{src}] {p}" for src, p in tried)
        raise FileNotFoundError(
            "ไม่พบ claude CLI\n"
            f"USERPROFILE = {os.environ.get('USERPROFILE')}\n"
            f"ตำแหน่งที่ลอง:\n{diag}\n"
            "วิธีแก้: ตั้ง CLAUDE_CLI_PATH หรือ ANTHROPIC_API_KEY"
        )

    # Probe credentials ในหลาย home dir เพราะ launcher (Hub/service) บน Windows
    # อาจไม่ inherit USERPROFILE ของ user → Path.home() ชี้ผิด
    creds_candidates = []

    # a. Path.home() ปกติ
    creds_candidates.append(Path.home() / ".claude" / ".credentials.json")

    # b. ดึง home มาจาก path ของ claude_exe ที่ resolver เจอ
    #    เช่น C:\Users\X\.local\bin\claude.exe → C:\Users\X
    try:
        exe_path = Path(claude_exe).resolve()
        for parent in exe_path.parents:
            creds_candidates.append(parent / ".claude" / ".credentials.json")
    except OSError:
        pass

    # c. Enumerate C:\Users\*\.claude\.credentials.json
    users_root = Path("C:/Users")
    if users_root.exists():
        for user_dir in users_root.iterdir():
            creds_candidates.append(user_dir / ".claude" / ".credentials.json")

    creds_found = None
    for c in creds_candidates:
        try:
            if c.exists() and c.stat().st_size > 0:
                creds_found = c
                break
        except OSError:
            continue

    if not creds_found:
        diag = "\n".join(f"  {c}" for c in creds_candidates)
        raise RuntimeError(
            "claude CLI ยังไม่ได้ login (ไม่พบ .credentials.json)\n"
            f"USERPROFILE = {os.environ.get('USERPROFILE')}\n"
            f"Path.home()  = {Path.home()}\n"
            f"ตำแหน่งที่ลอง:\n{diag}\n"
            "วิธีแก้:\n"
            "  • รัน `claude` ใน terminal interactive แล้วทำตามขั้นตอน /login\n"
            "  • หรือเซ็ต ANTHROPIC_API_KEY ใน environment เพื่อใช้ SDK แทน CLI"
        )


# ── Stage 1: BA Agent ─────────────────────────────────────

def run_ba_agent(args) -> dict:
    log("BA_AGENT", "Starting requirement analysis")
    system_prompt = read_agent_prompt("ba_agent")
    claude_md     = read_file(CLAUDE_MD)

    # Build content blocks
    content_blocks = []

    # Attach Figma screenshot if provided
    if args.figma_image:
        img_path = Path(args.figma_image)
        img_data = base64.b64encode(img_path.read_bytes()).decode()
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": img_data}
        })
        log("BA_AGENT", f"Attached Figma image: {img_path.name}")

    # Build text prompt — combine all .md files if --input-dir given
    input_text = ""
    if getattr(args, "input_dir", None):
        req_dir = Path(args.input_dir)
        md_files = sorted(
            [f for f in req_dir.glob("*.md") if "_backup_" not in f.name],
            key=lambda f: f.name,
        )
        if md_files:
            parts = [f"### {f.name}\n\n{f.read_text(encoding='utf-8')}" for f in md_files]
            input_text = "\n\n---\n\n".join(parts)
            log("BA_AGENT", f"Loaded {len(md_files)} requirement files: {[f.name for f in md_files]}")
        else:
            log("BA_AGENT", f"WARNING: no .md files found in {req_dir}")
    elif args.input:
        input_text = read_file(Path(args.input))
        log("BA_AGENT", f"Loaded requirement: {args.input}")

    prompt = f"""
CLAUDE.md (project context):
{claude_md}

---
Requirement Input:
{input_text if input_text else "(see attached Figma image above)"}

{"Figma Frame: " + args.frame if args.frame else ""}

วิเคราะห์ requirement นี้ตาม BA Agent protocol และ output JSON schema
"""
    content_blocks.append({"type": "text", "text": prompt})

    raw = call_agent(system_prompt, content_blocks, "BA_AGENT")

    # Parse JSON from response — robust extraction
    import re as _re
    ba_output = None
    candidates = []

    # 1. fenced ```json ... ```
    m = _re.search(r'```json\s*([\s\S]*?)\s*```', raw)
    if m: candidates.append(m.group(1).strip())

    # 2. any fenced block ``` ... ```
    for m in _re.finditer(r'```(?:\w*)\s*([\s\S]*?)\s*```', raw):
        candidates.append(m.group(1).strip())

    # 3. largest {...} block in the raw text
    m = _re.search(r'(\{[\s\S]*\})', raw)
    if m: candidates.append(m.group(1).strip())

    for candidate in candidates:
        try:
            ba_output = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue

    if ba_output is None:
        log("BA_AGENT", "WARNING: Could not parse JSON from any candidate — saving raw output")
        log("BA_AGENT", f"Raw response (first 300 chars): {raw[:300]}")
        ba_output = {"raw": raw, "meta": {"confidence_score": 0, "feature_name": "unknown"}}

    save_json(ba_output, "ba_output")

    # Confidence gate
    confidence = ba_output.get("meta", {}).get("confidence_score", 0)
    log("BA_AGENT", f"Confidence score: {confidence}")

    if confidence < 0.7:
        clarifications = ba_output.get("clarifications_needed", [])
        if clarifications:
            print("\n" + "─"*60)
            print("⚠️  BA Agent confidence ต่ำ — ข้อมูลที่ต้องการเพิ่มเติม:")
            for i, q in enumerate(clarifications, 1):
                print(f"\n{i}. {q.get('question')}")
                print(f"   ตัวอย่างคำตอบ: {q.get('example_answer')}")
                print(f"   กระทบ: {q.get('impact')}")
            print("─"*60)

            if getattr(args, "no_interactive", False):
                # Fix 1: non-interactive mode (Hub SSE) — skip input(), log warning and continue
                log("BA_AGENT", f"WARNING: low confidence ({confidence}) — non-interactive mode, continuing anyway")
                print("⏭  --no-interactive: ข้าม clarification — ดำเนินการต่อด้วย confidence ปัจจุบัน")
                print("   (รันผ่าน CLI โดยไม่ใช้ --no-interactive เพื่อตอบคำถามแบบ interactive)")
            else:
                print("\nกรอกคำตอบแล้วรันใหม่ หรือพิมพ์ 'skip' เพื่อดำเนินการต่อด้วย confidence ปัจจุบัน")
                answer = input("> ").strip()
                if answer.lower() != "skip":
                    ba_output = refine_ba_with_answers(system_prompt, ba_output, answer)

    return ba_output


def refine_ba_with_answers(system_prompt: str, ba_output: dict, answers: str) -> dict:
    log("BA_AGENT", "Refining with clarification answers...")
    prompt = f"""
Previous analysis:
{json.dumps(ba_output, ensure_ascii=False, indent=2)}

Clarification answers from stakeholder:
{answers}

อัปเดต JSON output โดยรวมคำตอบเหล่านี้ เพิ่ม confidence_score และเติม clarifications_needed ที่ตอบแล้ว
"""
    raw = call_agent(system_prompt, prompt, "BA_AGENT_REFINE")
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        return json.loads(raw)
    except Exception:
        return ba_output


# ── Stage 2: TCM generation (stable tool, no LLM) ─────────
#
# ใช้ scripts/generate_tcm.py เป็น deterministic tool — ไม่ regenerate
# จาก TC Agent เพื่อหลีกเลี่ยง column-layout bugs ที่เคยเกิดใน LLM output
# (TS_09 desc หาย, SIT EXIT section หาย, col I/J swap ของ P/N vs Status)
# ดู agents/qa_agent.md MODE 1 TCM_GENERATE สำหรับบริบท

def run_qa_agent(ba_output: dict) -> Path:
    log("QA_AGENT", "Generating TCM Excel from BA output (stable tool)")

    # Pre-flight: wait for Excel to release any xlsx in input/ (UX-friendly
    # retry instead of abort). Any open xlsx is a hazard because Excel's
    # in-memory snapshot can overwrite our output.
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    try:
        from _preflight import wait_for_xlsx_unlocked, PreflightError
        sentinel = INPUT_DIR / "_preflight_probe.xlsx"
        wait_for_xlsx_unlocked(sentinel, timeout=60, action="generate TCM in")
    except PreflightError as e:
        log("QA_AGENT", f"PRE-FLIGHT FAILED: {e}")
        raise

    # หา BA output JSON ที่เพิ่ง save โดย save_json() (latest ใน logs/)
    ba_files = sorted(LOG_DIR.glob("ba_output_*.json"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    if not ba_files:
        raise FileNotFoundError("No ba_output_*.json found in logs/ — BA stage ต้องรันก่อน")
    ba_json = ba_files[0]

    script_path = PROJECT_ROOT / "scripts" / "generate_tcm.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Stable tool missing: {script_path}")

    import subprocess
    run_result = subprocess.run(
        [sys.executable, "-X", "utf8", str(script_path), "--ba-input", str(ba_json)],
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, encoding="utf-8",
    )
    if run_result.returncode != 0:
        log("TC_AGENT", f"ERROR: {run_result.stderr}")
        raise RuntimeError(f"generate_tcm.py failed: {run_result.stderr}")

    log("TC_AGENT", f"TCM Excel generated successfully\n{run_result.stdout.strip()}")

    # Find newest xlsx in input/
    xlsx_files = sorted(INPUT_DIR.glob("*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not xlsx_files:
        raise FileNotFoundError("No xlsx found in input/ after generation")
    return xlsx_files[0]


# ── Stage 3: Playwright Agent ─────────────────────────────

def run_playwright_agent(ba_output: dict, tcm_path: Path) -> dict:
    log("PW_AGENT", "Generating and running Playwright tests")
    system_prompt = read_agent_prompt("playwright_agent")
    claude_md     = read_file(CLAUDE_MD)

    prompt = f"""
CLAUDE.md:
{claude_md}

BA Output (acceptance criteria + selectors):
{json.dumps(ba_output, ensure_ascii=False, indent=2)}

TCM File: {tcm_path.name}

ทำตามลำดับ:
1. สร้าง Playwright spec files สำหรับแต่ละ TS ใน ba_output
2. รัน playwright test
3. อ่านผล pass/fail แต่ละ TCID
4. อัปเดต Status และ Executed Date กลับใน {tcm_path.name}
5. บันทึก screenshot ไว้ใน screenshots/[TCID].png
6. Output สรุปเป็น JSON: {{ "results": {{"TCID": "Pass|Fail", ...}}, "screenshots": [...] }}
"""

    result = call_agent(system_prompt, prompt, "PW_AGENT")
    save_json({"raw": result}, "playwright_output")

    # Parse results JSON
    try:
        if "```json" in result:
            result_json = result.split("```json")[1].split("```")[0].strip()
        else:
            result_json = result
        pw_results = json.loads(result_json)
    except Exception:
        pw_results = {"results": {}, "screenshots": [], "raw": result}

    return pw_results


# ── Stage 4: Test Result Agent ────────────────────────────

def run_test_result_agent(pw_results: dict) -> Path:
    log("TR_AGENT", "Generating Word test result report")
    import subprocess

    # Call existing run.py (which calls generate_report.py)
    run_result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "run.py")],
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True
    )
    print(run_result.stdout)
    if run_result.returncode != 0:
        log("TR_AGENT", f"WARNING: run.py error: {run_result.stderr}")

    # Find latest output docx
    output_files = sorted(OUTPUT_DIR.glob("*.docx"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not output_files:
        raise FileNotFoundError("No .docx found in output/ after generation")

    report_path = output_files[0]
    log("TR_AGENT", f"Report saved: {report_path.name}")
    return report_path


# ── Main ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="QA Agentic Loop Orchestrator")
    parser.add_argument("--input",          help="Path to a single requirement doc (.md / .txt / .xlsx)")
    parser.add_argument("--input-dir",      help="Directory — all .md files combined as BA input (survey_map.md + requirement.md etc.)")
    parser.add_argument("--figma-image",    help="Path to exported Figma screenshot (.png)")
    parser.add_argument("--frame",          help="Figma frame name (for context)")
    parser.add_argument("--skip-playwright", action="store_true", help="Stop after TCM generation")
    parser.add_argument("--skip-ba",         help="Path to existing BA JSON output to skip BA stage")
    parser.add_argument("--no-interactive",  action="store_true",
                        help="Non-interactive mode: skip input() prompts (used by Hub/SSE)")
    args = parser.parse_args()

    print("\n" + "═"*60)
    print("  QA Agentic Loop — Starting")
    mode = "SDK (claude-opus-4-6)" if os.environ.get("ANTHROPIC_API_KEY", "").strip() else "claude CLI"
    print(f"  Agent mode: {mode}")
    print("═"*60 + "\n")

    # Pre-flight: verify auth before loading requirements / building prompts
    preflight_auth_check()

    # ── Stage 1: BA Agent ──
    if args.skip_ba:
        log("MAIN", f"Skipping BA Agent — loading: {args.skip_ba}")
        ba_output = json.loads(Path(args.skip_ba).read_text())
    else:
        ba_output = run_ba_agent(args)

    print(f"\n✓ Stage 1 complete — Feature: {ba_output.get('meta', {}).get('feature_name', '?')}")
    print(f"  Scenarios: {len(ba_output.get('acceptance_criteria', []))}")

    # ── Guard: refuse to proceed (and overwrite TCM) if BA failed ──
    ac_count   = len(ba_output.get("acceptance_criteria", []))
    confidence = ba_output.get("meta", {}).get("confidence_score", 0) or 0
    feature    = ba_output.get("meta", {}).get("feature_name", "")
    if ac_count == 0 or confidence == 0 or feature in ("", "unknown"):
        log("MAIN", f"BA Agent did not return a valid analysis "
                    f"(confidence={confidence}, acceptance_criteria={ac_count}, feature='{feature}')")
        log("MAIN", "Aborting before Stage 2 to preserve existing TCM Excel.")
        log("MAIN", "Common cause: Claude CLI returned narrative text instead of JSON. "
                    "Re-run BA Agent or inspect logs/ba_output_*.json")
        print("\n" + "═"*60)
        print("  ❌ Pipeline aborted — BA output invalid (TCM not overwritten)")
        print("═"*60 + "\n")
        sys.exit(2)

    # ── Stage 2: Test Case Agent ──
    tcm_path = run_qa_agent(ba_output)
    print(f"\n✓ Stage 2 complete — TCM: {tcm_path.name}")

    if args.skip_playwright:
        print("\n⏭  --skip-playwright: stopping after TCM generation")
        return

    # ── Stage 3: Playwright Agent ──
    pw_results = run_playwright_agent(ba_output, tcm_path)
    pass_count = sum(1 for v in pw_results.get("results", {}).values() if v == "Pass")
    fail_count = sum(1 for v in pw_results.get("results", {}).values() if v == "Fail")
    print(f"\n✓ Stage 3 complete — Pass: {pass_count} / Fail: {fail_count}")

    # ── Stage 4: Test Result Agent ──
    report_path = run_test_result_agent(pw_results)
    print(f"\n✓ Stage 4 complete — Report: {report_path.name}")

    print("\n" + "═"*60)
    print(f"  Pipeline complete!")
    print(f"  Report: output/{report_path.name}")
    print("═"*60 + "\n")


if __name__ == "__main__":
    main()
