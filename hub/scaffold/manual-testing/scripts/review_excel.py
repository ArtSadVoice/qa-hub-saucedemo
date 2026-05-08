"""
review_excel.py
───────────────
Excel Review Agent: อ่าน TCM Excel → rule-based checks (ไม่ต้อง API key)
                    + AI quality review (ถ้ามี ANTHROPIC_API_KEY)

Usage:
    python -X utf8 scripts/review_excel.py
    python -X utf8 scripts/review_excel.py --xlsx input/MyProject_TestCase.xlsx
    python -X utf8 scripts/review_excel.py --req requirements/requirement.md
"""

import sys, os, re, argparse, subprocess, tempfile
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR   = PROJECT_ROOT / "agents"
LOG_DIR      = PROJECT_ROOT / "logs"
INPUT_DIR    = PROJECT_ROOT / "input"
REQ_DIR      = PROJECT_ROOT / "requirements"

REQUIRED_PROJECT_FIELDS = [
    "Project Code", "Project Name", "Topic",
    "Customer", "Prepared By", "Prepared Date", "Sprint / Version",
]
VALID_STATUSES  = {"pass", "fail", "in-progress", "block", "cancel", "not start"}
VALID_PN        = {"P", "N"}
MIN_EXPECTED_LEN = 15


# ── Excel reader ──────────────────────────────────────────────────────────────

def read_tcm(xlsx_path: Path) -> dict:
    """Extract all data from TCM Excel into a structured dict."""
    try:
        import openpyxl
    except ImportError:
        print("ERROR: openpyxl not installed — run: pip install openpyxl", flush=True)
        sys.exit(1)

    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    except Exception as e:
        print(f"ERROR: Cannot open Excel: {e}", flush=True)
        sys.exit(1)

    result = {"filename": xlsx_path.name, "project_info": {}, "summary": [], "tcm": []}

    # PROJECT_INFO
    if "PROJECT_INFO" in wb.sheetnames:
        for row in wb["PROJECT_INFO"].iter_rows(values_only=True):
            col_b = row[1] if len(row) > 1 else None
            col_c = row[2] if len(row) > 2 else None
            if col_b and str(col_b).strip().startswith("*"):
                key = str(col_b).strip().lstrip("*").strip()
                result["project_info"][key] = str(col_c).strip() if col_c is not None else ""

    # SUMMARY
    if "SUMMARY" in wb.sheetnames:
        header_found = False
        for row in wb["SUMMARY"].iter_rows(values_only=True):
            if not any(c is not None for c in row):
                continue
            if str(row[1] or "").strip() == "TSID":
                header_found = True
                continue
            if header_found and row[1] and re.match(r"^TS_\d+", str(row[1])):
                result["summary"].append({
                    "tsid":    str(row[1]).strip(),
                    "desc":    str(row[2] or "").strip(),
                    "no_tc":   row[3],
                    "pass":    row[4],
                    "fail":    row[5],
                    "in_prog": row[6],
                    "block":   row[7],
                    "cancel":  row[8],
                })

    # TCM
    if "TCM" in wb.sheetnames:
        cur_tsid = None
        for row in wb["TCM"].iter_rows(values_only=True):
            if not any(c is not None for c in row):
                continue
            if row[0] == "TSID":
                continue
            if row[0] in ("STATUS LEGEND", "Pass"):
                break
            if row[0] and re.match(r"^TS_\d+$", str(row[0])):
                cur_tsid = str(row[0]).strip()
            tcid = str(row[2]).strip() if len(row) > 2 and row[2] else None
            if cur_tsid and tcid and re.match(r"^TS_\d+_\d+", tcid):
                result["tcm"].append({
                    "tsid":      cur_tsid,
                    "scenario":  str(row[1] or "").strip(),
                    "tcid":      tcid,
                    "pre_cond":  str(row[3] or "").strip(),
                    "test_data": str(row[4] or "").strip(),
                    "desc":      str(row[5] or "").strip(),
                    "steps":     str(row[6] or "").strip(),
                    "expected":  str(row[7] or "").strip(),
                    "p_n":       str(row[8] or "").strip(),
                    "status":    str(row[9] or "").strip(),
                    "exec_date": str(row[10] or "").strip(),
                })

    wb.close()
    return result


# ── Rule-based checks ─────────────────────────────────────────────────────────

def run_rule_based_checks(data: dict) -> tuple:
    """Run ~20 rule-based checks. Return (markdown_report, warn_count, crit_count)."""
    issues = {"critical": [], "warning": [], "ok": []}

    # ── STRUCTURAL ──────────────────────────────────────────────────────────
    pi = data["project_info"]
    missing_fields = [f for f in REQUIRED_PROJECT_FIELDS if f not in pi or not pi[f]]
    if missing_fields:
        for f in missing_fields:
            issues["critical"].append(f"PROJECT_INFO: ขาด field `* {f}` (ว่างหรือไม่มี)")
    else:
        issues["ok"].append("PROJECT_INFO: ครบทุก 7 required fields")

    summary_tsids = {s["tsid"] for s in data["summary"]}
    tcm_tsids     = {tc["tsid"] for tc in data["tcm"]}

    for t in sorted(tcm_tsids - summary_tsids):
        issues["warning"].append(f"SUMMARY ↔ TCM: `{t}` อยู่ใน TCM แต่ไม่มีใน SUMMARY")
    for t in sorted(summary_tsids - tcm_tsids):
        issues["warning"].append(f"SUMMARY ↔ TCM: `{t}` อยู่ใน SUMMARY แต่ไม่มี TC ใน TCM เลย")
    if not (tcm_tsids - summary_tsids) and not (summary_tsids - tcm_tsids):
        issues["ok"].append("SUMMARY ↔ TCM: TSIDs ตรงกันทั้งสองฝั่ง")

    tcm_count_by_ts: dict = {}
    for tc in data["tcm"]:
        tcm_count_by_ts[tc["tsid"]] = tcm_count_by_ts.get(tc["tsid"], 0) + 1
    for s in data["summary"]:
        try:
            declared = int(s["no_tc"] or 0)
        except (ValueError, TypeError):
            declared = 0
        actual = tcm_count_by_ts.get(s["tsid"], 0)
        if declared != actual:
            issues["warning"].append(
                f"SUMMARY count: `{s['tsid']}` บอก {declared} TC แต่ TCM มีจริง {actual} แถว"
            )

    # ── FORMAT ──────────────────────────────────────────────────────────────
    tsid_re = re.compile(r"^TS_\d{2}$")
    tcid_re = re.compile(r"^TS_\d{2}_\d{2}$")

    bad_tsids = sorted({tc["tsid"] for tc in data["tcm"] if not tsid_re.match(tc["tsid"])})
    for t in bad_tsids:
        issues["warning"].append(f"Format: TSID `{t}` ไม่ตรง pattern TS_XX (ต้องเป็นตัวเลข 2 หลัก)")

    bad_tcids = sorted({tc["tcid"] for tc in data["tcm"] if not tcid_re.match(tc["tcid"])})
    for t in bad_tcids:
        issues["warning"].append(f"Format: TCID `{t}` ไม่ตรง pattern TS_XX_YY (2 หลักทั้งคู่)")

    # TCID sequence continuity per TSID
    tcids_by_ts: dict = defaultdict(list)
    for tc in data["tcm"]:
        tcids_by_ts[tc["tsid"]].append(tc["tcid"])

    for tsid in sorted(tcids_by_ts):
        nums = []
        for t in tcids_by_ts[tsid]:
            m = re.match(r"^TS_\d+_(\d+)$", t)
            if m:
                nums.append(int(m.group(1)))
        nums.sort()
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] > 1:
                issues["warning"].append(
                    f"Sequence: `{tsid}` ขาด TCID ลำดับ _{nums[i]+1:02d} "
                    f"(มี _{nums[i]:02d} → _{nums[i+1]:02d})"
                )

    # Status + P/N values
    for tc in data["tcm"]:
        s = tc["status"].strip()
        if s and s.lower() not in VALID_STATUSES:
            issues["warning"].append(
                f"`{tc['tcid']}`: Status = \"{s}\" ไม่ valid "
                f"(ต้องเป็น Pass/Fail/In-Progress/Block/Cancel/Not Start)"
            )
        pn = tc["p_n"].strip()
        if pn and pn not in VALID_PN:
            issues["warning"].append(f"`{tc['tcid']}`: P/N = \"{pn}\" ต้องเป็น P หรือ N เท่านั้น")

    # ── COMPLETENESS ────────────────────────────────────────────────────────
    for tc in data["tcm"]:
        if not tc["desc"]:
            issues["critical"].append(f"`{tc['tcid']}`: Description (col F) ว่างเปล่า")
        if not tc["expected"]:
            issues["critical"].append(f"`{tc['tcid']}`: Expected Result (col H) ว่างเปล่า")
        elif len(tc["expected"]) < MIN_EXPECTED_LEN:
            issues["warning"].append(
                f"`{tc['tcid']}`: Expected Result สั้นเกิน ({len(tc['expected'])} ตัวอักษร)"
                f" — \"{tc['expected']}\""
            )
        if not tc["p_n"]:
            issues["warning"].append(f"`{tc['tcid']}`: P/N (col I) ว่างเปล่า")

    # ── COVERAGE ────────────────────────────────────────────────────────────
    for tsid in sorted(tcids_by_ts):
        tcs = [tc for tc in data["tcm"] if tc["tsid"] == tsid]
        has_p = any(tc["p_n"] == "P" for tc in tcs)
        has_n = any(tc["p_n"] == "N" for tc in tcs)
        if not has_p:
            issues["warning"].append(
                f"Coverage: `{tsid}` ไม่มี Positive test (P) เลย — ผิดปกติ"
            )
        if not has_n:
            issues["warning"].append(
                f"Coverage: `{tsid}` ไม่มี Negative test (N) เลย "
                f"— แนะนำเพิ่ม unhappy path / validation test"
            )

    # ── Build report ─────────────────────────────────────────────────────────
    total = len(issues["critical"]) + len(issues["warning"])
    if total == 0:
        severity = "✅ OK"
    elif issues["critical"]:
        severity = "🔴 Critical"
    else:
        severity = "⚠️ Warning"

    lines = [
        "# TCM Review Report (Rule-Based)",
        f"**File**: {data['filename']}",
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Total issues**: {total}  |  "
        f"Critical: {len(issues['critical'])}  |  "
        f"Warning: {len(issues['warning'])}  |  "
        f"Severity: {severity}",
        "",
    ]

    if issues["critical"]:
        lines += ["## 🔴 Critical Issues", ""]
        lines += [f"- {i}" for i in issues["critical"]]
        lines.append("")

    if issues["warning"]:
        lines += ["## ⚠️ Warnings", ""]
        lines += [f"- {i}" for i in issues["warning"]]
        lines.append("")

    if issues["ok"]:
        lines += ["## ✅ Passed Checks", ""]
        lines += [f"- {i}" for i in issues["ok"]]
        lines.append("")

    if total == 0:
        lines += ["## ✅ ไม่พบปัญหา — TCM ผ่านทุก rule-based check", ""]

    return "\n".join(lines), len(issues["warning"]), len(issues["critical"])


# ── AI review (requires ANTHROPIC_API_KEY) ────────────────────────────────────

def format_tcm_for_prompt(data: dict) -> str:
    lines = [
        f"## File: {data['filename']}",
        f"## Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "### PROJECT_INFO sheet",
    ]
    if data["project_info"]:
        for k, v in data["project_info"].items():
            lines.append(f"  * {k}: {v}")
    else:
        lines.append("  (ไม่พบข้อมูล)")
    lines.append("")

    lines.append("### SUMMARY sheet")
    if data["summary"]:
        lines.append("| TSID | Description | No.TC | Pass | Fail | In-Prog | Block | Cancel |")
        lines.append("|------|-------------|-------|------|------|---------|-------|--------|")
        for s in data["summary"]:
            lines.append(
                f"| {s['tsid']} | {s['desc']} | {s['no_tc']} | {s['pass']} | "
                f"{s['fail']} | {s['in_prog']} | {s['block']} | {s['cancel']} |"
            )
    else:
        lines.append("  (ไม่พบข้อมูล SUMMARY)")
    lines.append("")

    lines.append(f"### TCM sheet ({len(data['tcm'])} test cases)")
    for tc in data["tcm"]:
        lines.append(f"- **{tc['tcid']}** [{tc['p_n']}] [{tc['status']}]")
        lines.append(f"  Scenario: {tc['scenario']}")
        lines.append(f"  Description: {tc['desc']}")
        lines.append(f"  Expected: {tc['expected']}")
        if tc["pre_cond"]:
            lines.append(f"  Pre-condition: {tc['pre_cond']}")
        if tc["test_data"]:
            lines.append(f"  Test Data: {tc['test_data']}")

    return "\n".join(lines)


def call_review_agent(system_prompt: str, user_message: str) -> str:
    """Call Claude: SDK if ANTHROPIC_API_KEY is set, otherwise fall back to claude CLI."""
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        try:
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=8096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text
        except Exception as e:
            print(f"⚠️  SDK error ({e}) — falling back to claude CLI", flush=True)

    # Fallback: claude CLI
    full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(full_prompt)
        tmp_path = f.name
    try:
        with open(tmp_path, "r", encoding="utf-8") as f:
            result = subprocess.run(
                ["claude", "-p"],
                stdin=f,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        if result.returncode != 0 and result.stderr:
            return f"ERROR calling Claude: {result.stderr.strip()}"
        return result.stdout.strip()
    finally:
        os.unlink(tmp_path)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Excel Review Agent")
    parser.add_argument("--xlsx", help="Path to TCM Excel (default: latest in input/)")
    parser.add_argument("--req",  help="Path to requirement.md for traceability check")
    args = parser.parse_args()

    # Find Excel
    if args.xlsx:
        xlsx_path = Path(args.xlsx)
    else:
        candidates = sorted(
            [f for f in INPUT_DIR.glob("*.xlsx") if not f.name.startswith("~$")],
            key=lambda f: f.stat().st_mtime, reverse=True,
        )
        if not candidates:
            print("ERROR: ไม่พบไฟล์ .xlsx ใน input/ — ใช้ --xlsx เพื่อระบุไฟล์", flush=True)
            sys.exit(1)
        xlsx_path = candidates[0]

    if not xlsx_path.exists():
        print(f"ERROR: ไม่พบไฟล์: {xlsx_path}", flush=True)
        sys.exit(1)

    print(f"▶ Reading Excel: {xlsx_path.name}", flush=True)
    data = read_tcm(xlsx_path)
    print(f"  Found: {len(data['summary'])} TS, {len(data['tcm'])} TC", flush=True)

    # Find requirement doc
    req_text = ""
    req_path = None
    if args.req:
        req_path = Path(args.req)
    else:
        req_candidates = (
            sorted(REQ_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
            if REQ_DIR.exists() else []
        )
        if req_candidates:
            req_path = req_candidates[0]

    if req_path and req_path.exists():
        req_text = req_path.read_text(encoding="utf-8")
        print(f"  Requirement: {req_path.name}", flush=True)
    else:
        print("  (ไม่มี requirement.md — ข้าม traceability check)", flush=True)

    # ── Rule-based checks (always runs) ──────────────────────────────────────
    print("▶ Running rule-based checks...", flush=True)
    rb_report, warn_count, crit_count = run_rule_based_checks(data)
    print("\n" + rb_report, flush=True)

    final_report = rb_report

    # ── AI quality review (only if ANTHROPIC_API_KEY is set) ─────────────────
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    if has_api_key:
        print("▶ ANTHROPIC_API_KEY found — running AI quality review...", flush=True)
        agent_prompt = AGENTS_DIR / "excel_review_agent.md"
        if not agent_prompt.exists():
            print("⚠️  agents/excel_review_agent.md not found — ข้าม AI review", flush=True)
        else:
            system_prompt = agent_prompt.read_text(encoding="utf-8")
            tcm_text      = format_tcm_for_prompt(data)
            user_message  = (
                f"กรุณา review TCM Excel ต่อไปนี้ตาม Excel Review Agent protocol:\n\n"
                f"{tcm_text}\n"
            )
            if req_text:
                user_message += (
                    f"\n---\n\n## Requirement Document ({req_path.name})\n\n{req_text}\n"
                )
            else:
                user_message += "\n---\n\nไม่มี requirement document — ข้าม traceability check\n"

            ai_review = call_review_agent(system_prompt, user_message)
            if ai_review and not ai_review.startswith("ERROR"):
                final_report += "\n\n---\n\n## 🤖 AI Quality Review\n\n" + ai_review
                print("\n" + ai_review, flush=True)
            else:
                print(f"⚠️  AI review failed: {ai_review}", flush=True)
    else:
        print(
            "\n(ANTHROPIC_API_KEY ไม่ได้ตั้งค่า — ข้าม AI quality review)\n"
            "  ถ้ามี API key: set ANTHROPIC_API_KEY=sk-ant-xxx → รันใหม่เพื่อรับ AI review\n"
            "  ถ้าไม่มี: /ba-agent ใน Claude Code chat ใช้ได้เหมือนกัน (ไม่ต้อง API key)",
            flush=True,
        )

    # ── Save report ───────────────────────────────────────────────────────────
    LOG_DIR.mkdir(exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = LOG_DIR / f"review_excel_{ts}.md"
    out_path.write_text(final_report, encoding="utf-8")
    print(f"\n✓ Report saved: {out_path.name}", flush=True)

    if crit_count > 0:
        sys.exit(1)  # non-zero exit ถ้ามี Critical → Hub แสดง error toast


if __name__ == "__main__":
    main()
