"""
generate_tcm.py — Data-driven TCM Excel generator.

รับ BA Agent output (JSON) แล้ว fill templates/Test_Case_Template.xlsx
ให้เป็น input/{ProjectName}_TestCase.xlsx ที่ column layout ตรง template,
preserve merged cells, และคง SIT EXIT CRITERIA section ไว้

Usage:
  python scripts/generate_tcm.py                          # auto: latest logs/ba_output_*.json
  python scripts/generate_tcm.py --ba-input path.json
  python scripts/generate_tcm.py --ba-input path.json --output input/X.xlsx

Stable — orchestrator เรียกตรงโดยไม่ต้อง regenerate จาก TC Agent.
"""

from __future__ import annotations
import argparse
import json
import re
import shutil
import sys
from copy import copy
from datetime import datetime
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.formatting.formatting import ConditionalFormattingList
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries


PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "Test_Case_Template.xlsx"
INPUT_DIR = PROJECT_ROOT / "input"
LOGS_DIR = PROJECT_ROOT / "logs"
CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"


# ── TCM column layout (fixed, ต้องตรง template) ──────────────────
TCM_COLS = {
    "TSID": 1, "Test Scenario Description": 2, "TCID": 3,
    "Pre-condition": 4, "Test Data": 5, "Test Case Description": 6,
    "Test Steps": 7, "Expected Result": 8, "P/N": 9, "Status": 10,
}
TCM_TSID_COL = "A"
TCM_STATUS_COL = "J"


# ── Helpers ──────────────────────────────────────────────────────

def normalize_header(v) -> str:
    """Collapse whitespace/newlines inside cell text — handles `Test Scenario\\nDescription`."""
    if v is None or not isinstance(v, str):
        return ""
    return " ".join(v.split()).strip().lower()


def safe_unmerge(ws, min_row: int):
    saved = []
    for mr in list(ws.merged_cells.ranges):
        if mr.max_row >= min_row:
            saved.append(str(mr))
            ws.unmerge_cells(str(mr))
    return saved


def restore_merges(ws, saved):
    for r in saved:
        try:
            ws.merge_cells(r)
        except Exception:
            pass


def write_cell(ws, row, col, value):
    ws.cell(row=row, column=col).value = value


# ── CLAUDE.md parser ─────────────────────────────────────────────

def parse_claude_md() -> dict:
    """Extract App name / URL from CLAUDE.md for Customer + project derivation."""
    info = {"app_name": "", "url": "", "project_name": ""}
    if not CLAUDE_MD.exists():
        return info
    text = CLAUDE_MD.read_text(encoding="utf-8")
    for pat, key in [
        (r"\*\*App name\*\*[:：]\s*(.+?)\n", "app_name"),
        (r"\*\*Base URL\*\*[:：]\s*`?([^\s`]+)`?", "url"),
    ]:
        m = re.search(pat, text)
        if m:
            info[key] = m.group(1).strip().rstrip("`")
    if info["app_name"]:
        # "BAY — VoCSurvey" → customer=BAY, project=VoCSurvey
        parts = re.split(r"\s*[—\-–]\s*", info["app_name"], maxsplit=1)
        info["customer"] = parts[0].strip() if parts else info["app_name"]
        info["project_name"] = parts[1].strip() if len(parts) > 1 else info["app_name"]
    else:
        info["customer"] = ""
    return info


# ── TSID description derivation ──────────────────────────────────

def derive_tsid_descriptions(ba: dict) -> dict:
    """
    Priority:
      1. ba.meta.tsid_descriptions (if BA Agent provides it)
      2. Fallback: derive from first scenario_name per TSID (strip detail suffix)
    """
    explicit = (ba.get("meta") or {}).get("tsid_descriptions") or {}
    if explicit:
        return explicit

    result = {}
    for ac in ba.get("acceptance_criteria", []):
        tsid = ac.get("tsid")
        if not tsid or tsid in result:
            continue
        name = ac.get("scenario_name", "") or tsid
        # Trim detail suffix after " - " or " — " — keeps the group label
        base = re.split(r"\s+[-—–]\s+", name, maxsplit=1)[0].strip()
        result[tsid] = base or tsid
    return result


# ── Sheet fillers ────────────────────────────────────────────────

def _snapshot_row_style(ws, row_num, max_col):
    """Capture cell styles from one row for later propagation to overflow rows."""
    snap = []
    for c in range(1, max_col + 1):
        cell = ws.cell(row=row_num, column=c)
        snap.append({
            "fill":          copy(cell.fill),
            "font":          copy(cell.font),
            "border":        copy(cell.border),
            "alignment":     copy(cell.alignment),
            "number_format": cell.number_format,
        })
    return snap


def _apply_row_style(ws, row_num, snapshot):
    for c, s in enumerate(snapshot, start=1):
        cell = ws.cell(row=row_num, column=c)
        cell.fill          = s["fill"]
        cell.font          = s["font"]
        cell.border        = s["border"]
        cell.alignment     = s["alignment"]
        cell.number_format = s["number_format"]


def _expand_cf_ranges(ws, start_row: int, end_row: int):
    """For every CF rule whose range starts at start_row, extend its
    end-row to at least end_row so newly-written rows get the same
    conditional formatting (Status colors, etc.)."""
    cf = ws.conditional_formatting
    new_rules = ConditionalFormattingList()
    for cf_range, rules in list(cf._cf_rules.items()):
        sqref_str = str(cf_range.sqref) if hasattr(cf_range, "sqref") else str(cf_range)
        new_parts = []
        for part in sqref_str.split():
            min_c, min_r, max_c, max_r = range_boundaries(part)
            if min_r == start_row and max_r < end_row:
                col_l = get_column_letter(min_c)
                col_r = get_column_letter(max_c)
                new_parts.append(f"{col_l}{min_r}:{col_r}{end_row}")
            else:
                new_parts.append(part)
        new_sqref = " ".join(new_parts)
        for rule in rules:
            new_rules.add(new_sqref, rule)
    ws.conditional_formatting = new_rules


def fill_tcm_sheet(ws, acceptance_criteria, tsid_desc):
    saved = safe_unmerge(ws, min_row=5)
    max_row = ws.max_row
    max_col = ws.max_column

    # Auto-detect column positions (handles line-break headers)
    col_map = dict(TCM_COLS)
    header_row = None
    for r in range(1, 10):
        for c in range(1, max_col + 1):
            vs = normalize_header(ws.cell(row=r, column=c).value)
            if not vs:
                continue
            for key in col_map:
                if vs == key.lower():
                    col_map[key] = c
                    header_row = r
    start_row = (header_row + 1) if header_row else 5

    # Capture style snapshots from first 2 alternating example rows BEFORE wiping
    style_snapshots = [
        _snapshot_row_style(ws, start_row,     max_col),
        _snapshot_row_style(ws, start_row + 1, max_col),
    ]

    # Wipe existing data + ALL styling below header (uniform clean slate)
    end_data_row = start_row + len(acceptance_criteria) - 1
    wipe_end = max(max_row, end_data_row)
    for row in range(start_row, wipe_end + 1):
        for col in range(1, max_col + 1):
            cell = ws.cell(row=row, column=col)
            cell.value = None

    seen = set()
    for idx, ac in enumerate(acceptance_criteria):
        row = start_row + idx
        tsid = ac["tsid"]
        write_cell(ws, row, col_map["TSID"], tsid)
        if tsid not in seen:
            seen.add(tsid)
            write_cell(ws, row, col_map["Test Scenario Description"],
                       tsid_desc.get(tsid, tsid))
        write_cell(ws, row, col_map["TCID"], ac["tcid"])
        given = ac.get("given", "")
        when = ac.get("when", "")
        vtext = ac.get("visible_text") or (ac.get("then", {}) or {}).get("visible_text", [])
        url = ac.get("url") or (ac.get("then", {}) or {}).get("url", "")
        write_cell(ws, row, col_map["Pre-condition"], given)
        write_cell(ws, row, col_map["Test Data"], when)
        write_cell(ws, row, col_map["Test Case Description"], ac.get("scenario_name", ""))
        write_cell(ws, row, col_map["Test Steps"], f"1. Pre-condition: {given}\n2. {when}")
        expected = f"URL: {url}\nVisible text:\n" + "\n".join(f"  - {t}" for t in vtext)
        write_cell(ws, row, col_map["Expected Result"], expected)
        write_cell(ws, row, col_map["P/N"], "P" if ac.get("type") == "happy_path" else "N")
        write_cell(ws, row, col_map["Status"], "Not Start")
        # Apply alternating styling (from captured snapshots) — uniform across overflow
        _apply_row_style(ws, row, style_snapshots[idx % 2])

    # Filter merges that overlap the data rows we just wrote (template footer
    # like A45:L45 / A46:B46 etc. would otherwise hide test case data).
    filtered = []
    for ref in saved:
        min_c, min_r, max_c, max_r = range_boundaries(ref)
        if min_r <= end_data_row and max_r >= start_row:
            continue
        filtered.append(ref)
    restore_merges(ws, filtered)

    # Expand conditional-formatting ranges (e.g. J5:J43 status colors) to
    # cover all data rows we wrote. Template's CF range stops at row 43,
    # so rows 44+ would render the Status text without color highlighting.
    _expand_cf_ranges(ws, start_row, end_data_row)


def fill_project_info(ws, ba_meta, claude_info, project_name):
    today = datetime.now().strftime("%d %b %Y")
    info_rows = [
        ("  * Project Code",     ba_meta.get("feature_id", "F-001")),
        ("  * Project Name",     ba_meta.get("feature_name", project_name)),
        ("  * Topic",            f"{ba_meta.get('module', project_name)} UAT"),
        ("  * Customer",         claude_info.get("customer") or "TBD"),
        ("  * Prepared By",      ba_meta.get("prepared_by", "Demo User Phukit")),
        ("  * Prepared Date",    today),
        ("  * Sprint / Version", ba_meta.get("sprint", "Sprint 1")),
        ("  * Document List",    f"{project_name}_TestResult.pdf"),
    ]
    saved = safe_unmerge(ws, min_row=1)
    max_row = ws.max_row
    max_col = ws.max_column

    key_to_row = {}
    for r in range(1, max_row + 1):
        for c in range(1, max_col + 1):
            v = ws.cell(row=r, column=c).value
            if not v or not isinstance(v, str):
                continue
            vs = v.strip()
            for key, _ in info_rows:
                if vs == key or vs.lstrip("* ").strip() == key.lstrip("* ").strip():
                    key_to_row[key] = (r, c)

    for key, val in info_rows:
        if key in key_to_row:
            r, c = key_to_row[key]
            ws.cell(row=r, column=c).value = key
            ws.cell(row=r, column=c + 1).value = val
    restore_merges(ws, saved)


def fill_summary(ws, acceptance_criteria, tsid_desc):
    saved = safe_unmerge(ws, min_row=1)
    tsid_set = sorted({ac["tsid"] for ac in acceptance_criteria})
    max_row = ws.max_row
    max_col = ws.max_column

    # Identify SIT EXIT CRITERIA section (do not wipe)
    sit_exit_row = None
    for r in range(1, max_row + 1):
        v = ws.cell(row=r, column=2).value
        if v and isinstance(v, str) and "SIT EXIT" in v.upper():
            sit_exit_row = r
            break

    # Detect column positions
    cols = {}
    header_row = None
    for r in range(1, min(max_row + 1, 10)):
        for c in range(1, max_col + 1):
            vs = normalize_header(ws.cell(row=r, column=c).value)
            if not vs:
                continue
            mapping = {
                "tsid": ["tsid"],
                "desc": ["test scenario description", "scenario description"],
                "total": ["no. test cases", "total", "total tc", "total cases"],
                "pass": ["pass"], "fail": ["fail"],
                "inprog": ["in-progress", "in progress", "inprogress"],
                "block": ["block"], "cancel": ["cancel"],
                "accuracy": ["accuracy %", "accuracy", "accuracy%"],
            }
            for key, aliases in mapping.items():
                if vs in aliases:
                    cols[key] = c
                    header_row = r

    if header_row is None or "tsid" not in cols:
        header_row = 1
        cols = {"tsid": 1, "total": 2, "pass": 3, "fail": 4}
        ws.cell(row=1, column=1).value = "TSID"
        ws.cell(row=1, column=2).value = "No. Test Cases"
        ws.cell(row=1, column=3).value = "Pass"
        ws.cell(row=1, column=4).value = "Fail"

    start_row = header_row + 1
    wipe_end = (sit_exit_row - 1) if sit_exit_row else (max_row + 5)
    for r in range(start_row, wipe_end + 1):
        for c in range(1, max_col + 1):
            ws.cell(row=r, column=c).value = None

    for idx, tsid in enumerate(tsid_set):
        row = start_row + idx
        ws.cell(row=row, column=cols["tsid"]).value = tsid
        if "desc" in cols:
            ws.cell(row=row, column=cols["desc"]).value = tsid_desc.get(tsid, "")
        if "total" in cols:
            ws.cell(row=row, column=cols["total"]).value = \
                f'=COUNTIF(TCM!{TCM_TSID_COL}:{TCM_TSID_COL},"{tsid}")'
        for key, status in [("pass","Pass"), ("fail","Fail"),
                            ("inprog","In-progress"), ("block","Block"), ("cancel","Cancel")]:
            if key in cols:
                ws.cell(row=row, column=cols[key]).value = (
                    f'=COUNTIFS(TCM!{TCM_TSID_COL}:{TCM_TSID_COL},"{tsid}",'
                    f'TCM!{TCM_STATUS_COL}:{TCM_STATUS_COL},"{status}")'
                )
        if "accuracy" in cols:
            pass_l = get_column_letter(cols["pass"])
            total_l = get_column_letter(cols["total"])
            cancel_l = get_column_letter(cols["cancel"]) if "cancel" in cols else None
            denom = f'{total_l}{row}' + (f'-{cancel_l}{row}' if cancel_l else '')
            ws.cell(row=row, column=cols["accuracy"]).value = \
                f'=IFERROR(({pass_l}{row}/({denom}))*100,"-")'

    total_row = start_row + len(tsid_set)
    ws.cell(row=total_row, column=cols["tsid"]).value = "TOTAL"
    for key in ("total", "pass", "fail", "inprog", "block", "cancel"):
        if key in cols:
            cl = get_column_letter(cols[key])
            ws.cell(row=total_row, column=cols[key]).value = \
                f"=SUM({cl}{start_row}:{cl}{total_row - 1})"
    if "accuracy" in cols and "pass" in cols and "total" in cols:
        p = get_column_letter(cols["pass"])
        t = get_column_letter(cols["total"])
        ws.cell(row=total_row, column=cols["accuracy"]).value = \
            f'=IFERROR(({p}{total_row}/{t}{total_row})*100,"-")'

    # Fallback SIT EXIT CRITERIA if template lost it
    if not sit_exit_row:
        gap = total_row + 2
        ws.cell(row=gap, column=2).value = "SIT EXIT CRITERIA"
        ws.cell(row=gap+1, column=2).value = "• Execution 100% complete"
        ws.cell(row=gap+2, column=2).value = "• SIT pass at 90% of Test Case"
        ws.cell(row=gap+3, column=2).value = "• Critical/High Severity Defect are 0%"

    # Skip merges that now overlap TSID data rows (old TOTAL merge
    # becomes invalid when TSID count shifts TOTAL to a new row)
    data_rows = range(start_row, total_row)
    filtered = []
    for ref in saved:
        min_c, min_r, max_c, max_r = range_boundaries(ref)
        if any(r in data_rows for r in range(min_r, max_r + 1)):
            continue
        filtered.append(ref)
    restore_merges(ws, filtered)
    try:
        ws.merge_cells(start_row=total_row, end_row=total_row,
                       start_column=cols["tsid"],
                       end_column=cols.get("desc", cols["tsid"] + 1))
    except Exception:
        pass


# ── Entry point ──────────────────────────────────────────────────

def find_latest_ba_output() -> Path | None:
    if not LOGS_DIR.exists():
        return None
    candidates = sorted(LOGS_DIR.glob("ba_output_*.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def main():
    ap = argparse.ArgumentParser(description="Generate TCM Excel from BA output JSON")
    ap.add_argument("--ba-input", help="Path to BA output JSON (default: latest logs/ba_output_*.json)")
    ap.add_argument("--output",   help="Output xlsx path (default: input/{ProjectName}_TestCase.xlsx)")
    args = ap.parse_args()

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    ba_path = Path(args.ba_input) if args.ba_input else find_latest_ba_output()
    if not ba_path or not ba_path.exists():
        raise FileNotFoundError(
            "No BA output JSON. Pass --ba-input <path> or run BA Agent first."
        )
    ba = json.loads(ba_path.read_text(encoding="utf-8"))

    claude_info = parse_claude_md()
    project_name = (
        (ba.get("meta") or {}).get("feature_name")
        or claude_info.get("project_name")
        or "Project"
    )
    # Safe filename: strip non-filename chars, prefer short token
    short = re.sub(r"[^A-Za-z0-9]", "", claude_info.get("project_name") or project_name)[:32] or "Project"

    output = Path(args.output) if args.output else INPUT_DIR / f"{short}_TestCase.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE_PATH, output)

    wb = load_workbook(output)
    sheet_lookup = {name.lower().replace("_", "").replace(" ", ""): name for name in wb.sheetnames}
    tcm = wb[sheet_lookup["tcm"]] if "tcm" in sheet_lookup else None
    proj = wb[sheet_lookup["projectinfo"]] if "projectinfo" in sheet_lookup else None
    summ = wb[sheet_lookup["summary"]] if "summary" in sheet_lookup else None

    tsid_desc = derive_tsid_descriptions(ba)
    acs = ba.get("acceptance_criteria", [])

    if tcm is not None:
        fill_tcm_sheet(tcm, acs, tsid_desc)
    if proj is not None:
        fill_project_info(proj, ba.get("meta", {}), claude_info, short)
    if summ is not None:
        fill_summary(summ, acs, tsid_desc)

    wb.save(output)
    print(f"Generated: {output}")
    print(f"  BA input: {ba_path}")
    print(f"  Test cases: {len(acs)}")
    print(f"  TSIDs: {sorted({ac['tsid'] for ac in acs})}")


if __name__ == "__main__":
    main()
