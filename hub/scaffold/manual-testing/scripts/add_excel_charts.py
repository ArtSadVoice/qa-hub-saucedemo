"""
add_excel_charts.py — เพิ่ม Bar Chart และ Pie Chart เข้า tab SUMMARY ของ input Excel

Usage:
    python scripts/add_excel_charts.py

อ้างอิงโครงสร้างจาก templates/Test_Result_Template.xlsx:
  - Bar chart (clustered col): No. Test Cases / Pass / Fail per TS scenario
  - Pie chart: สัดส่วน No. Test Cases แต่ละ TS scenario

หมายเหตุ: รันครั้งเดียวก็พอ — chart จะถูก embed ใน Excel ไว้แล้ว
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import re
import openpyxl
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_DIR     = os.path.join(BASE_DIR, "input")

# ── Auto-detect input Excel ────────────────────────────────────────────────
files = sorted(
    [f for f in os.listdir(IN_DIR) if f.endswith(".xlsx") and not f.startswith("~$")],
    key=lambda f: os.path.getmtime(os.path.join(IN_DIR, f)),
    reverse=True,
)
if not files:
    raise FileNotFoundError(f"ไม่พบ .xlsx ใน {IN_DIR}")
EXCEL_PATH = os.path.join(IN_DIR, files[0])
print(f"Input : input/{files[0]}")

wb = openpyxl.load_workbook(EXCEL_PATH)
ws = wb["SUMMARY"]

# ── Find actual data rows ──────────────────────────────────────────────────
# Row 4 = headers, Row 5+ = TS rows, last TS row before TOTAL
ts_rows = []
total_row = None
for i, row in enumerate(ws.iter_rows(min_row=5, values_only=True), start=5):
    b = row[1] if len(row) > 1 else None  # col B (index 1 in 0-based row tuple)
    if b is None:
        break
    if str(b).startswith("TS_"):
        ts_rows.append(i)
    elif str(b).upper() == "TOTAL":
        total_row = i
        break

if not ts_rows:
    raise ValueError("ไม่พบ TS rows ใน SUMMARY sheet (ต้องมี TSID ขึ้นต้นด้วย TS_)")

first_ts = ts_rows[0]
last_ts  = ts_rows[-1]
last_data = total_row if total_row else last_ts

print(f"  TS rows  : {first_ts}–{last_ts}  (Total row: {total_row})")

# ── Remove existing charts (avoid duplication on re-run) ───────────────────
ws._charts.clear()

# ═══════════════════════════════════════════════════════════════════════════
# CHART 1: Bar Chart — No.TC / Pass / Fail per TS (including TOTAL row)
# ═══════════════════════════════════════════════════════════════════════════
bar = BarChart()
bar.type      = "col"
bar.grouping  = "clustered"
bar.varyColors = False
bar.style     = 2
bar.y_axis.title = "Count"
bar.x_axis.numFmt = "General"
bar.x_axis.majorTickMark = "none"
bar.y_axis.majorTickMark = "none"

# Data: D4:F<last_data> — columns D=No.TC, E=Pass, F=Fail (row 4 = header)
data = Reference(ws, min_col=4, max_col=6, min_row=4, max_row=last_data)
bar.add_data(data, titles_from_data=True)

# Categories: B<first_ts>:B<last_data>  (TSID labels)
cats = Reference(ws, min_col=2, min_row=first_ts, max_row=last_data)
bar.set_categories(cats)

# Data labels — show values on bars
bar.dLbls = DataLabelList()
bar.dLbls.showVal  = True
bar.dLbls.showLegendKey = False
bar.dLbls.showCatName   = False
bar.dLbls.showSerName   = False

bar.width  = 18   # cm
bar.height = 12   # cm
ws.add_chart(bar, "B20")
print("  Bar chart added  → B20")

# ═══════════════════════════════════════════════════════════════════════════
# CHART 2: Pie Chart — No. Test Cases distribution per TS (TS rows only)
# ═══════════════════════════════════════════════════════════════════════════
pie = PieChart()
pie.style  = 2

# Data: D<first_ts>:D<last_ts>  (No. TC column, TS rows only — exclude TOTAL)
data_pie = Reference(ws, min_col=4, min_row=first_ts, max_row=last_ts)
pie.add_data(data_pie)

# Labels: B<first_ts>:B<last_ts>
labels = Reference(ws, min_col=2, min_row=first_ts, max_row=last_ts)
pie.set_categories(labels)

# Data labels — show percentage + category
pie.dLbls = DataLabelList()
pie.dLbls.showPercent  = True
pie.dLbls.showCatName  = True
pie.dLbls.showVal      = False
pie.dLbls.showLegendKey = False
pie.dLbls.showSerName  = False

pie.width  = 12   # cm
pie.height = 12   # cm
ws.add_chart(pie, "L20")
print("  Pie chart added  → L20")

# ── Save ───────────────────────────────────────────────────────────────────
wb.save(EXCEL_PATH)
print(f"\n✓ Saved: input/{files[0]}")
