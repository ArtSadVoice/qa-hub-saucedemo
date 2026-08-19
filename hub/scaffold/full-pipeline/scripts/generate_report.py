"""
Generate TestResult DOCX from Excel template data.
Follows rules defined in CLAUDE.md:
  - ชื่อไฟล์ใช้ underscore, ไม่มี space
  - วันที่ format DD MMM YYYY
  - Backup ก่อนเขียนทับ
  - สีตาม CLAUDE.md spec
Usage: python scripts/generate_report.py
"""
import sys, io, os, re, copy, shutil, zipfile
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import openpyxl
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_DIR    = os.path.join(BASE_DIR, "input")
TMPL_DIR  = os.path.join(BASE_DIR, "templates")
OUT_DIR   = os.path.join(BASE_DIR, "output")
ARCH_DIR  = os.path.join(BASE_DIR, "archive")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(ARCH_DIR, exist_ok=True)

# Auto-detect input Excel from input/ (pick newest .xlsx)
input_files = sorted(
    [f for f in os.listdir(IN_DIR) if f.endswith(".xlsx") and not f.startswith("~$")],
    key=lambda f: os.path.getmtime(os.path.join(IN_DIR, f)),
    reverse=True,
)
if not input_files:
    raise FileNotFoundError(f"ไม่พบ .xlsx ใน {IN_DIR}")
EXCEL_PATH = os.path.join(IN_DIR, input_files[0])
DOCX_TMPL  = os.path.join(TMPL_DIR, "Test_Result_Template.docx")
print(f"Input  : input/{input_files[0]}")
print(f"Template: templates/Test_Result_Template.docx")

# Pre-flight: validate template structure before consuming it. Catches the
# downloaded-template breakage class (duplicate styleIds, missing core styles,
# broken header/footer drawings) that python-docx loads happily but Word
# refuses to open. See scripts/_preflight.py for context.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _preflight import validate_template_structure, PreflightError  # noqa: E402
try:
    validate_template_structure(DOCX_TMPL)
except PreflightError as e:
    print(f"\nERROR: {e}", file=sys.stderr)
    sys.exit(2)

# ── Colors (CLAUDE.md spec) ──────────────────
COLOR = {
    "pass":        "E2EFDA",
    "fail":        "FCE4D6",
    "in-progress": "FFF2CC",
    "block":       "F4B8C1",
    "cancel":      "EDEDED",
    "not start":   "DAEEF3",
    "header":      "2E75B6",
    "header_dark": "1F3864",
    "total_row":   "D9E1F2",
    "white":       "FFFFFF",
    "acc_good":    "E2EFDA",
    "acc_warn":    "FFF2CC",
    "acc_bad":     "FCE4D6",
}

# ─────────────────────────────────────────────
# 1. READ EXCEL DATA
# ─────────────────────────────────────────────

wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)

# --- PROJECT_INFO ---
ws_info = wb["PROJECT_INFO"]
project = {}
sign_off_persons = []
in_signoff = False
header_seen = False

for row in ws_info.iter_rows(values_only=True):
    if not any(c is not None for c in row):
        continue
    col_b = row[1] if len(row) > 1 else None
    col_c = row[2] if len(row) > 2 else None

    if col_b == "SIGN-OFF PERSONS":
        in_signoff = True
        continue
    if col_b == "Role" and col_c == "Name":
        header_seen = True
        continue

    if in_signoff and header_seen and col_b and col_c:
        date_val = row[5]
        date_str = date_val.strftime("%d %b %Y") if isinstance(date_val, datetime) else str(date_val or "")
        sign_off_persons.append({
            "role":     str(row[1] or ""),
            "name":     str(row[2] or ""),
            "position": str(row[3] or ""),
            "company":  str(row[4] or ""),
            "date":     date_str,
        })
    elif not in_signoff and col_b and str(col_b).strip().startswith("*"):
        key = str(col_b).strip().lstrip("* ").strip()
        project[key] = col_c

prep_date = project.get("Prepared Date", "")
if isinstance(prep_date, datetime):
    project["Prepared Date"] = prep_date.strftime("%d %b %Y")
else:
    project["Prepared Date"] = str(prep_date) if prep_date else ""

# --- TCM ---
ws_tcm = wb["TCM"]
ts_groups = {}
ts_order = []
current_tsid = None

for row in ws_tcm.iter_rows(values_only=True):
    if not any(c is not None for c in row):
        continue
    if row[0] == "TSID":
        continue
    if row[0] in ("STATUS LEGEND", "Pass"):
        break

    tsid = row[0]
    if tsid and re.match(r"^TS_\d+$", str(tsid)):
        current_tsid = tsid
        desc = row[1] or ""
        if tsid not in ts_groups:
            ts_groups[tsid] = {"description": str(desc), "tcs": []}
            ts_order.append(tsid)

    tcid = row[2]
    if current_tsid and tcid:
        exec_date = row[10]
        if isinstance(exec_date, datetime):
            exec_date_str = exec_date.strftime("%d %b %Y")
        else:
            exec_date_str = str(exec_date) if exec_date else ""
        ts_groups[current_tsid]["tcs"].append({
            "tcid":            str(row[2] or ""),
            "description":     str(row[5] or ""),
            "expected_result": str(row[7] or ""),
            "pn":              str(row[8] or ""),
            "status":          str(row[9] or ""),
            "executed_date":   exec_date_str,
        })

# Print loaded data summary
print(f"Project  : {project.get('Project Name', '')}")
print(f"Date     : {project.get('Prepared Date', '')}")
print(f"Sign-off : {len(sign_off_persons)} persons")
for tsid in ts_order:
    tcs = ts_groups[tsid]["tcs"]
    p = sum(1 for t in tcs if t["status"].lower() == "pass")
    f = sum(1 for t in tcs if t["status"].lower() == "fail")
    print(f"  {tsid} : {len(tcs)} TCs  Pass={p}  Fail={f}")

# ─────────────────────────────────────────────
# 1b. GENERATE CHART PNG  → screenshots/chart_summary.png
# ─────────────────────────────────────────────

def generate_chart_png():
    """Generate a 2-panel chart PNG (bar + pie) from loaded TS data."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  Chart PNG skipped (matplotlib not installed — run: pip install matplotlib)")
        return

    ts_ids = list(ts_order)
    no_tcs = [len(ts_groups[t]["tcs"]) for t in ts_ids]
    passes = [sum(1 for tc in ts_groups[t]["tcs"] if tc["status"].lower() == "pass") for t in ts_ids]
    fails  = [sum(1 for tc in ts_groups[t]["tcs"] if tc["status"].lower() == "fail") for t in ts_ids]

    status_totals = {"Pass": 0, "Fail": 0, "In-Progress": 0, "Block": 0, "Cancel": 0, "Not Start": 0}
    for t in ts_ids:
        for tc in ts_groups[t]["tcs"]:
            s = tc["status"].strip().lower()
            if s == "pass":         status_totals["Pass"]        += 1
            elif s == "fail":       status_totals["Fail"]        += 1
            elif s == "in-progress":status_totals["In-Progress"] += 1
            elif s == "block":      status_totals["Block"]       += 1
            elif s == "cancel":     status_totals["Cancel"]      += 1
            elif s == "not start":  status_totals["Not Start"]   += 1

    fig = plt.figure(figsize=(14, 6), facecolor="white")
    ax1 = fig.add_subplot(121)
    ax2 = fig.add_subplot(122)

    # ── Bar chart ────────────────────────────────────────────────────────────
    x  = np.arange(len(ts_ids))
    w  = 0.26
    b1 = ax1.bar(x - w, no_tcs, w, label="No. Test Cases", color="#2E75B6", alpha=0.9)
    b2 = ax1.bar(x,     passes,  w, label="Pass",           color="#70AD47", alpha=0.9)
    b3 = ax1.bar(x + w, fails,   w, label="Fail",           color="#FF4B4B", alpha=0.9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(ts_ids, fontsize=9, rotation=15, ha="right")
    ax1.set_title("Test Cases by Test Scenario", fontsize=11, fontweight="bold", pad=12)
    ax1.legend(fontsize=9, loc="upper right")
    ax1.set_ylabel("Count", fontsize=9)
    ax1.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    for bars in [b1, b2, b3]:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax1.annotate(str(int(h)),
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)

    # ── Pie chart ─────────────────────────────────────────────────────────────
    colors_map = {
        "Pass": "#70AD47", "Fail": "#FF4B4B", "In-Progress": "#FFC000",
        "Block": "#F4B8C1", "Cancel": "#BFBFBF", "Not Start": "#9DC3E6",
    }
    pie_items = [(k, v) for k, v in status_totals.items() if v > 0]
    if pie_items:
        labels_pie = [k for k, _ in pie_items]
        values_pie = [v for _, v in pie_items]
        pie_colors = [colors_map.get(l, "#CCCCCC") for l in labels_pie]
        wedges, texts, autotexts = ax2.pie(
            values_pie, labels=labels_pie, colors=pie_colors,
            autopct="%1.0f%%", startangle=90, pctdistance=0.75,
            textprops={"fontsize": 9},
        )
        for at in autotexts:
            at.set_fontsize(8)
            at.set_fontweight("bold")
    ax2.set_title("Test Result Overview", fontsize=11, fontweight="bold", pad=12)

    plt.tight_layout(pad=2.5)
    out_png = os.path.join(BASE_DIR, "screenshots", "chart_summary.png")
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  Chart PNG: screenshots/chart_summary.png")

generate_chart_png()

# ─────────────────────────────────────────────
# 2. PLACEHOLDER MAP
# ─────────────────────────────────────────────

ph = {
    "{{PROJECT_CODE}}":   str(project.get("Project Code", "")),
    "{{PROJECT_NAME}}":   str(project.get("Project Name", "")),
    "{{TOPIC}}":          str(project.get("Topic", "")),
    "{{CUSTOMER}}":       str(project.get("Customer", "")),
    "{{PREPARED_BY}}":    str(project.get("Prepared By", "")),
    "{{PREPARED_DATE}}":  str(project.get("Prepared Date", "")),
    "{{SPRINT_VERSION}}": str(project.get("Sprint / Version", "")),
    "{{DOCUMENT_LIST}}":  str(project.get("Document List", "")),
    "{{VENDOR_COMPANY}}": "QA Hub Demo Company Limited",
    "{{CUSTOMER_COMPANY}}": str(project.get("Customer", "")),
    "{{APPLICATION_OVERVIEW_DESCRIPTION}}":
        f"This document covers UAT test results for {project.get('Project Name', '')} "
        f"({project.get('Topic', '')}).",
}

# ─────────────────────────────────────────────
# 3. HELPERS
# ─────────────────────────────────────────────

def replace_in_paragraph(para, replacements):
    full_text = "".join(run.text for run in para.runs)
    changed = False
    for key, val in replacements.items():
        if key in full_text:
            full_text = full_text.replace(key, val)
            changed = True
    if changed:
        for i, run in enumerate(para.runs):
            run.text = "" if i > 0 else full_text
    return changed


def replace_all_text(doc, replacements):
    for para in doc.paragraphs:
        replace_in_paragraph(para, replacements)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    replace_in_paragraph(para, replacements)


def copy_table_props(src_tbl, dst_tbl):
    src_tblPr = src_tbl._tbl.find(qn("w:tblPr"))
    dst_tblPr = dst_tbl._tbl.find(qn("w:tblPr"))
    if src_tblPr is not None:
        if dst_tblPr is not None:
            dst_tbl._tbl.remove(dst_tblPr)
        dst_tbl._tbl.insert(0, copy.deepcopy(src_tblPr))


def set_cell_bg(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    existing = tcPr.find(qn("w:shd"))
    if existing is not None:
        tcPr.remove(existing)
    tcPr.append(shd)


def add_all_borders(table):
    """Apply all-borders (top/bottom/left/right/insideH/insideV) to a table."""
    tblPr = table._tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        table._tbl.insert(0, tblPr)
    existing = tblPr.find(qn("w:tblBorders"))
    if existing is not None:
        tblPr.remove(existing)
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), "auto")
        borders.append(b)
    tblPr.append(borders)


def set_cell_text(cell, text, bold=False, size=12, color=None,
                  align=WD_ALIGN_PARAGRAPH.LEFT, italic=False):
    for p in cell.paragraphs:
        p.clear()
    para = cell.paragraphs[0]
    para.alignment = align
    run = para.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def status_bg(status):
    return COLOR.get(status.lower(), COLOR["white"])


def find_body_elem_by_text(body, snippet):
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    for elem in body:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "p":
            text = "".join(n.text or "" for n in elem.iter() if n.tag.endswith("}t"))
            if snippet in text:
                return elem
    return None


def insert_before(body, anchor, new_elem):
    idx = list(body).index(anchor)
    body.insert(idx, new_elem)


def make_blank_para(doc):
    p = doc.add_paragraph("")
    doc.element.body.remove(p._p)
    return p._p


def make_heading2(h2_template_p, text):
    """Clone existing Heading 2 XML and replace text."""
    new_p = copy.deepcopy(h2_template_p)
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    runs = new_p.findall(f".//{{{ns}}}r")
    for i, r in enumerate(runs):
        t = r.find(f"{{{ns}}}t")
        if t is not None:
            t.text = text if i == 0 else ""
    return new_p


def build_tc_table(doc, tcs):
    """Build test-case result table, return XML element."""
    headers = ["TCID", "Test Case Description", "Expected Result", "P/N", "Status", "Executed Date"]
    col_w   = [Cm(2.5), Cm(4.8), Cm(5.2), Cm(1.0), Cm(2.2), Cm(2.5)]

    table = doc.add_table(rows=1 + len(tcs), cols=len(headers))
    add_all_borders(table)

    # Header row
    for ci, hdr in enumerate(headers):
        cell = table.rows[0].cells[ci]
        cell.width = col_w[ci]
        set_cell_bg(cell, COLOR["header"])
        set_cell_text(cell, hdr, bold=True, color="FFFFFF",
                      align=WD_ALIGN_PARAGRAPH.CENTER)

    # Data rows
    for ri, tc in enumerate(tcs):
        row = table.rows[ri + 1]
        values = [tc["tcid"], tc["description"], tc["expected_result"],
                  tc["pn"], tc["status"], tc["executed_date"]]
        for ci, val in enumerate(values):
            cell = row.cells[ci]
            cell.width = col_w[ci]
            bg = status_bg(tc["status"]) if ci == 4 else COLOR["white"]
            set_cell_bg(cell, bg)
            align = WD_ALIGN_PARAGRAPH.CENTER if ci in (3, 4, 5) else WD_ALIGN_PARAGRAPH.LEFT
            set_cell_text(cell, val, align=align)

    doc.element.body.remove(table._tbl)
    return table._tbl


def build_summary_table(doc, ts_groups, ts_order):
    """Build summary table, return XML element."""
    headers = ["TSID", "Test Scenario", "No. TC",
               "Pass", "Fail", "Not Start", "In-Prog", "Block", "Cancel", "Accuracy %"]
    col_w   = [Cm(1.8), Cm(5.5), Cm(1.5),
               Cm(1.3), Cm(1.3), Cm(1.5), Cm(1.5), Cm(1.5), Cm(1.5), Cm(2.0)]

    rows_data = []
    total = {"tc": 0, "pass": 0, "fail": 0, "ns": 0, "ip": 0, "bl": 0, "ca": 0}

    for tsid in ts_order:
        tcs = ts_groups[tsid]["tcs"]
        p  = sum(1 for t in tcs if t["status"].lower() == "pass")
        f  = sum(1 for t in tcs if t["status"].lower() == "fail")
        ns = sum(1 for t in tcs if t["status"].lower() == "not start")
        ip = sum(1 for t in tcs if t["status"].lower() == "in-progress")
        bl = sum(1 for t in tcs if t["status"].lower() == "block")
        ca = sum(1 for t in tcs if t["status"].lower() == "cancel")
        cnt = len(tcs)
        acc = f"{round(p/cnt*100)}%" if cnt > 0 else "N/A"
        rows_data.append([tsid, ts_groups[tsid]["description"],
                          str(cnt), str(p), str(f), str(ns), str(ip), str(bl), str(ca), acc])
        total["tc"] += cnt; total["pass"] += p; total["fail"] += f
        total["ns"] += ns; total["ip"] += ip; total["bl"] += bl; total["ca"] += ca

    t_acc = f"{round(total['pass']/total['tc']*100)}%" if total["tc"] > 0 else "N/A"
    rows_data.append(["Total", "", str(total["tc"]), str(total["pass"]), str(total["fail"]),
                      str(total["ns"]), str(total["ip"]), str(total["bl"]), str(total["ca"]), t_acc])

    table = doc.add_table(rows=1 + len(rows_data), cols=len(headers))
    add_all_borders(table)

    # Header
    for ci, hdr in enumerate(headers):
        cell = table.rows[0].cells[ci]
        cell.width = col_w[ci]
        set_cell_bg(cell, COLOR["header_dark"])
        set_cell_text(cell, hdr, bold=True, color="FFFFFF",
                      align=WD_ALIGN_PARAGRAPH.CENTER)

    for ri, vals in enumerate(rows_data):
        row = table.rows[ri + 1]
        is_total = vals[0] == "Total"
        for ci, val in enumerate(vals):
            cell = row.cells[ci]
            cell.width = col_w[ci]
            if is_total:
                set_cell_bg(cell, COLOR["total_row"])
                set_cell_text(cell, val, bold=True,
                              align=WD_ALIGN_PARAGRAPH.CENTER)
            else:
                if ci == 9 and val != "N/A":
                    pct = int(val.rstrip("%"))
                    bg = COLOR["acc_good"] if pct >= 90 else (COLOR["acc_warn"] if pct >= 70 else COLOR["acc_bad"])
                else:
                    bg = COLOR["white"]
                set_cell_bg(cell, bg)
                align = WD_ALIGN_PARAGRAPH.LEFT if ci == 1 else WD_ALIGN_PARAGRAPH.CENTER
                set_cell_text(cell, val, align=align)

    doc.element.body.remove(table._tbl)
    return table._tbl


def rebuild_signoff_table(doc, persons, orig_table):
    """Rebuild sign-off table.
    Layout:
      - Left column  = customer (any non-QA Hub Demo company)
      - Right column = QA Hub Demo Company Limited
      - Row 0        = company-name header
    """
    F180 = "QA Hub Demo Company Limited"
    customer_persons = [p for p in persons if p.get("company", "") != F180]
    f180_persons     = [p for p in persons if p.get("company", "") == F180]

    customer_company = customer_persons[0]["company"] if customer_persons else "Customer"

    n_data = max(len(customer_persons), len(f180_persons))
    table = doc.add_table(rows=1 + n_data, cols=2)
    copy_table_props(orig_table, table)
    add_all_borders(table)

    # Header row — company names
    for ci, name in enumerate([customer_company, F180]):
        cell = table.rows[0].cells[ci]
        cell.width = Cm(9)
        set_cell_bg(cell, COLOR["header"])
        set_cell_text(cell, name, bold=True, color="FFFFFF",
                      align=WD_ALIGN_PARAGRAPH.CENTER, size=12)

    def fill_person_cell(cell, person):
        """Fill cell with role + 2 blank lines (for signature image) + dotted + name/position/date."""
        # Clear existing content (paragraphs and runs)
        for p in list(cell.paragraphs):
            for r in list(p._p):
                p._p.remove(r)
        # Lines (blank ones leave room for an inserted signature image)
        lines = [
            f"{person['role']}:",
            "",
            "",
            "......................................",
            f"Name: {person['name']}",
            f"Position: {person['position']}",
            f"Date: {person['date']}",
        ]
        first_para = cell.paragraphs[0]
        run = first_para.add_run(lines[0])
        run.font.size = Pt(12)
        for line in lines[1:]:
            p = cell.add_paragraph()
            run = p.add_run(line)
            run.font.size = Pt(12)

    # Data rows
    for i in range(n_data):
        row = table.rows[i + 1]
        left_cell = row.cells[0]
        left_cell.width = Cm(9)
        if i < len(customer_persons):
            fill_person_cell(left_cell, customer_persons[i])
        else:
            for p in left_cell.paragraphs:
                p.clear()
        right_cell = row.cells[1]
        right_cell.width = Cm(9)
        if i < len(f180_persons):
            fill_person_cell(right_cell, f180_persons[i])
        else:
            for p in right_cell.paragraphs:
                p.clear()

    doc.element.body.remove(table._tbl)
    return table._tbl


# ─────────────────────────────────────────────
# 4. LOAD & MODIFY DOCUMENT
# ─────────────────────────────────────────────

doc = Document(DOCX_TMPL)
body = doc.element.body

# Replace all {{placeholder}}
replace_all_text(doc, ph)

# Rebuild sign-off table (Table index 2)
orig_signoff = doc.tables[2]
new_signoff = rebuild_signoff_table(doc, sign_off_persons, orig_signoff)
orig_signoff._tbl.getparent().replace(orig_signoff._tbl, new_signoff)

# Rebuild Summary table (Table index 3)
orig_summary = doc.tables[3]
new_summary = build_summary_table(doc, ts_groups, ts_order)
orig_summary._tbl.getparent().replace(orig_summary._tbl, new_summary)

# ─────────────────────────────────────────────
# 5. REBUILD SECTION 5 (Test Result)
# ─────────────────────────────────────────────

# Save H2 template before removing TS_01/TS_02 sections
h2_template = copy.deepcopy(find_body_elem_by_text(body, "TS_01:"))

result_h1    = find_body_elem_by_text(body, "5. Test Result")
next_section = find_body_elem_by_text(body, "6. Type of Testing")

if result_h1 is None or next_section is None:
    raise RuntimeError("Cannot find section anchors in template.")

# Remove elements between "5. Test Result" and "6. Type of Testing"
body_list = list(body)
start_idx = body_list.index(result_h1) + 1
end_idx   = body_list.index(next_section)
for elem in body_list[start_idx:end_idx]:
    body.remove(elem)

# Insert new TS sections
insert_before(body, next_section, make_blank_para(doc))

for tsid in ts_order:
    ts   = ts_groups[tsid]
    tcs  = ts["tcs"]

    # Heading 2
    hdg = make_heading2(h2_template, f"{tsid}: {ts['description']}")
    insert_before(body, next_section, hdg)

    # TC table
    insert_before(body, next_section, build_tc_table(doc, tcs))

    # Evidence header paragraph
    note_p = doc.add_paragraph(f"[แนบ Screenshot/Evidence สำหรับ {tsid}]")
    body.remove(note_p._p)
    for run in note_p.runs:
        run.font.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    insert_before(body, next_section, note_p._p)

    # One paragraph per TC: "TS_XX_YY  Description"
    for tc in tcs:
        tc_p = doc.add_paragraph()
        body.remove(tc_p._p)
        run1 = tc_p.add_run(tc["tcid"])
        run1.font.italic = True
        run1.font.size = Pt(9)
        run1.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
        run2 = tc_p.add_run("  " + tc["description"])
        run2.font.italic = True
        run2.font.size = Pt(9)
        run2.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
        insert_before(body, next_section, tc_p._p)

    insert_before(body, next_section, make_blank_para(doc))

# ─────────────────────────────────────────────
# 6. FIX TABLE OF CONTENTS
# ─────────────────────────────────────────────

def fix_toc(path):
    """
    Rebuild TOC entries in the saved docx to match actual headings.
    Fixes: (1) duplicate bookmark IDs on cloned headings,
           (2) stale TOC entry text from the base template,
           (3) adds w:updateFields so Word refreshes page numbers on open.

    Root causes addressed:
    - toc_entries uses 'PAGEREF' (not 'fldChar') to exclude the TOC field-header
      paragraph (which contains instrText "TOC \\o..."). Including it caused Word
      to show both the raw field code AND the rendered result simultaneously.
    - PAGEREF regex uses r'\\h' (one backslash) to match the literal '\\h' in XML.
    """
    # ── Read docx as zip ──────────────────────────────────────────────────────
    files = {}
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            files[name] = zf.read(name)

    doc_xml      = files["word/document.xml"].decode("utf-8")
    settings_xml = files.get("word/settings.xml", b"").decode("utf-8")

    paras = re.findall(r"<w:p[ >].*?</w:p>", doc_xml, re.DOTALL)

    # ── Step 1: Collect Heading paragraphs + fix duplicate bookmarks ──────────
    toc_nums    = [int(m) for m in re.findall(r"_Toc(\d+)", doc_xml)]
    next_toc_id = max(toc_nums) + 1 if toc_nums else 100000001

    headings    = []   # [{level, text, bookmark}]
    seen_bm     = set()
    new_doc_xml = doc_xml

    for p in paras:
        style_m = re.search(r'<w:pStyle w:val="(Heading(\d+))"', p)
        if not style_m:
            continue
        level = int(style_m.group(2))
        txt   = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)).strip()

        if not txt or txt.lower() in ("contents", "สารบัญ"):
            continue

        bm_names = re.findall(r'<w:bookmarkStart[^>]*w:name="([^"]+)"', p)
        bookmark = bm_names[0] if bm_names else None

        # Duplicate or missing bookmark → assign fresh unique ID
        if bookmark is None or bookmark in seen_bm:
            new_bm = f"_Toc{next_toc_id}"
            next_toc_id += 1
            if bookmark:
                new_p = re.sub(
                    r'(<w:bookmarkStart\b[^>]*\b)w:name="' + re.escape(bookmark) + r'"',
                    r'\g<1>w:name="' + new_bm + '"',
                    p, count=1,
                )
                new_doc_xml = new_doc_xml.replace(p, new_p, 1)
            bookmark = new_bm

        seen_bm.add(bookmark)
        headings.append({"level": level, "text": txt, "bookmark": bookmark})

    # ── Step 2: Find TOC *entry* paragraphs (PAGEREF, NOT instrText "TOC \o") ─
    # The first TOC paragraph in the template is the outer field-header: it has
    # BOTH " TOC \o ..." instrText (the outer field begin/instrText/separate)
    # AND a PAGEREF for its own entry text ("Contents").  Using that para as a
    # template copies the outer field header into EVERY entry, causing Word to
    # treat each entry as a new TOC field and display raw codes on update.
    # Fix: exclude paragraphs that contain the outer TOC instruction.
    toc_entries = [(i, p) for i, p in enumerate(paras)
                   if re.search(r'<w:pStyle w:val="TOC[12]"', p)
                   and "PAGEREF" in p
                   and r" TOC \o " not in p]   # ← exclude outer field-header para

    if not toc_entries:
        files["word/document.xml"] = new_doc_xml.encode("utf-8")
        _save_zip(path, files)
        return

    tpl_toc1 = next((p for _, p in toc_entries if "TOC1" in p), toc_entries[0][1])
    tpl_toc2 = next((p for _, p in toc_entries if "TOC2" in p), tpl_toc1)

    # ── Step 3: Build new TOC entry XML for each heading ─────────────────────
    def _esc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))

    def _make_entry(level, text, bookmark):
        tpl = tpl_toc1 if level == 1 else tpl_toc2
        # Update hyperlink anchor
        entry = re.sub(r'(<w:hyperlink\b[^>]*\b)w:anchor="[^"]*"',
                       r'\g<1>w:anchor="' + bookmark + '"', tpl)
        # Update PAGEREF target — r'\\h' matches literal \h in the XML instrText
        entry = re.sub(
            r'( PAGEREF )_Toc\d+( \\h )',
            r"\g<1>" + bookmark + r"\g<2>",
            entry,
        )
        # Update display text — first <w:t> inside hyperlink before <w:webHidden>
        entry = re.sub(
            r'(<w:hyperlink\b.*?<w:r\b[^>]*>(?:(?!<w:webHidden).)*?<w:t[^>]*>)[^<]*(</w:t>)',
            r"\g<1>" + _esc(text) + r"\g<2>",
            entry, count=1, flags=re.DOTALL,
        )
        return entry

    new_entries = [_make_entry(h["level"], h["text"], h["bookmark"]) for h in headings]

    # ── Step 4: Replace only the TOC entry paragraphs (not the field header) ──
    first_entry = toc_entries[0][1]
    last_entry  = toc_entries[-1][1]

    start_idx = new_doc_xml.find(first_entry)
    end_idx   = new_doc_xml.find(last_entry)
    if start_idx >= 0 and end_idx >= start_idx:
        end_idx += len(last_entry)
        new_doc_xml = (
            new_doc_xml[:start_idx]
            + "\n".join(new_entries)
            + new_doc_xml[end_idx:]
        )

    # ── Step 5: Add w:updateFields so Word updates page numbers on open ───────
    if "<w:updateFields" not in settings_xml:
        settings_xml = settings_xml.replace(
            "</w:settings>",
            '  <w:updateFields w:val="true"/>\n</w:settings>',
        )

    # ── Step 6: Mark every field's begin <w:fldChar> as w:dirty="true" so
    # Word definitely refreshes the TOC on open. settings-level updateFields
    # is sometimes ignored by Word for TOC fields with cached results; the
    # per-field dirty attribute forces a refresh regardless of Word's
    # "update fields on open" preference.
    def _add_dirty(m):
        before, after, slash = m.group(1), m.group(2), m.group(3)
        if 'w:dirty=' in before or 'w:dirty=' in after:
            return m.group(0)
        return f'<w:fldChar{before}w:fldCharType="begin"{after} w:dirty="true"{slash}>'
    new_doc_xml = re.sub(
        r'<w:fldChar([^>]*?)w:fldCharType="begin"([^>]*?)(/?)>',
        _add_dirty,
        new_doc_xml,
    )

    # ── Save ──────────────────────────────────────────────────────────────────
    files["word/document.xml"] = new_doc_xml.encode("utf-8")
    files["word/settings.xml"] = settings_xml.encode("utf-8")
    _save_zip(path, files)
    print(f"  TOC updated: {len(headings)} entries "
          f"({sum(1 for h in headings if h['level']==2)} TS sub-headings)")


def _save_zip(path, files):
    """Re-pack all files back into the docx ZIP."""
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    shutil.move(tmp, path)


# ─────────────────────────────────────────────
# 7. OUTPUT FILENAME  (ชื่อไม่มี space, ใช้ underscore)
# ─────────────────────────────────────────────

proj_code = project.get("Project Code", "Project")
proj_code_safe = re.sub(r"[^\w]", "_", proj_code)   # "Swag Labs (Checkout)" → "Swag_Labs__Checkout_"
proj_code_safe = re.sub(r"_+", "_", proj_code_safe).strip("_")  # collapse underscores

prep_date_str = project.get("Prepared Date", "")
try:
    dt = datetime.strptime(prep_date_str, "%d %b %Y")
    date_str = dt.strftime("%Y%m%d")
except Exception:
    date_str = datetime.today().strftime("%Y%m%d")

base_filename = f"{proj_code_safe}_TestResult_{date_str}.docx"
out_path = os.path.join(OUT_DIR, base_filename)

# Check if file is currently open (Word lock file)
lock_file = os.path.join(OUT_DIR, "~$" + base_filename[2:])
if os.path.exists(out_path) and os.path.exists(lock_file):
    # File is open in Word — save with timestamp suffix instead
    ts_suffix = datetime.now().strftime("%H%M%S")
    out_filename = base_filename.replace(".docx", f"_{ts_suffix}.docx")
    out_path = os.path.join(OUT_DIR, out_filename)
    print("(ไฟล์เดิมถูกเปิดอยู่ใน Word — บันทึกเป็นชื่อใหม่)")
elif os.path.exists(out_path):
    # Backup old file to archive before overwriting
    ts_backup = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_name = base_filename.replace(".docx", f"_bak_{ts_backup}.docx")
    shutil.copy2(out_path, os.path.join(ARCH_DIR, bak_name))
    print(f"Backup → archive/{bak_name}")
    out_filename = base_filename
else:
    out_filename = base_filename

doc.save(out_path)
fix_toc(out_path)
total_tcs = sum(len(ts_groups[t]["tcs"]) for t in ts_order)
total_pass = sum(sum(1 for tc in ts_groups[t]["tcs"] if tc["status"].lower() == "pass") for t in ts_order)
total_fail = sum(sum(1 for tc in ts_groups[t]["tcs"] if tc["status"].lower() == "fail") for t in ts_order)
print(f"\n✓ Saved: output/{out_filename}")
print(f"  Total TCs : {total_tcs}")
print(f"  Pass      : {total_pass}  ({round(total_pass/total_tcs*100) if total_tcs else 0}%)")
print(f"  Fail      : {total_fail}")
