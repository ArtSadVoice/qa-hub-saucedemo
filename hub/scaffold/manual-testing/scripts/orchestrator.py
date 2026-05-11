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


def _resolve_claude_cli() -> str:
    """Resolve absolute path to claude CLI executable.

    On Windows, subprocess.run([...]) without shell=True calls CreateProcess directly,
    which does not search PATHEXT — so "claude" alone fails even when claude.exe is on PATH.
    """
    found = shutil.which("claude")
    if found:
        return found
    raise FileNotFoundError(
        "claude CLI not found on PATH. Install with: npm install -g @anthropic-ai/claude-code"
    )


def _call_via_cli(system_prompt: str, user_message) -> str:
    """Call Claude via claude -p CLI (no API key needed)."""
    text = user_message if isinstance(user_message, str) else user_message[-1]["text"]
    prompt_text = f"{system_prompt}\n\n---\n\n{text}"
    claude_exe = _resolve_claude_cli()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt_text)
        tmp_path = f.name
    try:
        with open(tmp_path, "r", encoding="utf-8") as f:
            result = subprocess.run(
                [claude_exe, "-p"],
                stdin=f,
                capture_output=True, text=True, encoding="utf-8",
            )
        return result.stdout.strip()
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
        md_files = sorted(req_dir.glob("*.md"), key=lambda f: f.name)
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
        ["python", "-X", "utf8", str(script_path), "--ba-input", str(ba_json)],
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
        ["python", str(PROJECT_ROOT / "scripts" / "run.py")],
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
