"""
generate_chart.py — Standalone Bar+Pie chart generator from input TCM xlsx.

Reads the latest input/*.xlsx → writes screenshots/chart_summary.png.

Usage (CLI):
    python scripts/generate_chart.py
    python scripts/generate_chart.py --input input/Foo.xlsx --output screenshots/x.png

Why a standalone script:
    Both `generate_report.py` (which embeds the chart in the Word report)
    and `screenshot_injector.py` (which injects the chart PNG into the
    docx after generation) need the chart to reflect the *current* xlsx.
    Previously, the chart was generated only as a side-effect of
    `generate_report.py`. If an operator re-edited the xlsx and ran only
    `/inject`, the injected chart was stale (mtime older than xlsx).

    By extracting the generator, `screenshot_injector.py` can subprocess
    this script to refresh the chart before injecting it.

Exit codes:
    0 = ok (or matplotlib missing — printed a warning, not a hard fail)
    1 = could not find input xlsx / could not read TCM sheet
"""
from __future__ import annotations
import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
DEFAULT_OUTPUT = ROOT / "screenshots" / "chart_summary.png"


def _latest_xlsx(input_dir: Path) -> Path | None:
    files = sorted(
        (f for f in input_dir.glob("*.xlsx") if not f.name.startswith("~$")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def _read_ts_data(xlsx_path: Path) -> tuple[list[str], dict[str, dict]]:
    """Return (ts_order, ts_groups) — same shape as generate_report.py."""
    import openpyxl
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    if "TCM" not in wb.sheetnames:
        raise RuntimeError(f"'TCM' sheet missing in {xlsx_path.name}")
    ws = wb["TCM"]

    ts_groups: dict[str, dict] = {}
    ts_order: list[str] = []
    current_tsid: str | None = None

    for row in ws.iter_rows(values_only=True):
        if not any(c is not None for c in row):
            continue
        if row[0] == "TSID":
            continue
        if row[0] in ("STATUS LEGEND", "Pass"):
            break

        tsid = row[0]
        if tsid and re.match(r"^TS_\d+$", str(tsid)):
            current_tsid = str(tsid)
            if current_tsid not in ts_groups:
                ts_groups[current_tsid] = {"description": str(row[1] or ""), "tcs": []}
                ts_order.append(current_tsid)

        tcid = row[2]
        if current_tsid and tcid:
            ts_groups[current_tsid]["tcs"].append({
                "tcid":   str(tcid),
                "status": str(row[9] or ""),
            })

    return ts_order, ts_groups


def generate_chart_png(xlsx_path: Path, out_png: Path) -> bool:
    """Generate the 2-panel chart. Returns True on success, False if matplotlib missing."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  Chart PNG skipped (matplotlib not installed — run: pip install matplotlib)")
        return False

    ts_order, ts_groups = _read_ts_data(xlsx_path)

    no_tcs = [len(ts_groups[t]["tcs"]) for t in ts_order]
    passes = [sum(1 for tc in ts_groups[t]["tcs"] if tc["status"].lower() == "pass") for t in ts_order]
    fails  = [sum(1 for tc in ts_groups[t]["tcs"] if tc["status"].lower() == "fail") for t in ts_order]

    status_totals = {"Pass": 0, "Fail": 0, "In-Progress": 0, "Block": 0, "Cancel": 0, "Not Start": 0}
    for t in ts_order:
        for tc in ts_groups[t]["tcs"]:
            s = tc["status"].strip().lower()
            if   s == "pass":        status_totals["Pass"]        += 1
            elif s == "fail":        status_totals["Fail"]        += 1
            elif s == "in-progress": status_totals["In-Progress"] += 1
            elif s == "block":       status_totals["Block"]       += 1
            elif s == "cancel":      status_totals["Cancel"]      += 1
            elif s == "not start":   status_totals["Not Start"]   += 1

    fig = plt.figure(figsize=(14, 6), facecolor="white")
    ax1 = fig.add_subplot(121)
    ax2 = fig.add_subplot(122)

    # Bar chart
    x  = np.arange(len(ts_order))
    w  = 0.26
    b1 = ax1.bar(x - w, no_tcs, w, label="No. Test Cases", color="#2E75B6", alpha=0.9)
    b2 = ax1.bar(x,     passes,  w, label="Pass",           color="#70AD47", alpha=0.9)
    b3 = ax1.bar(x + w, fails,   w, label="Fail",           color="#FF4B4B", alpha=0.9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(ts_order, fontsize=9, rotation=15, ha="right")
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

    # Pie chart
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

    import matplotlib.pyplot as plt2  # alias to satisfy "tight_layout" lint
    plt2.tight_layout(pad=2.5)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


def regenerate_if_stale(xlsx_path: Path, png_path: Path) -> str:
    """Regenerate chart only if PNG mtime < xlsx mtime (or PNG missing).
    Returns one of: 'wrote', 'fresh', 'no-matplotlib', 'no-input'.
    Used by screenshot_injector for cheap idempotent calls."""
    if not xlsx_path.exists():
        return "no-input"
    needs_rebuild = (
        not png_path.exists()
        or png_path.stat().st_mtime < xlsx_path.stat().st_mtime
    )
    if not needs_rebuild:
        return "fresh"
    ok = generate_chart_png(xlsx_path, png_path)
    return "wrote" if ok else "no-matplotlib"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Bar+Pie chart PNG from TCM xlsx")
    ap.add_argument("--input", help="Input xlsx path (default: latest in input/)")
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT),
                    help=f"Output PNG path (default: {DEFAULT_OUTPUT.relative_to(ROOT)})")
    ap.add_argument("--if-stale", action="store_true",
                    help="Skip regen if PNG already newer than input xlsx")
    args = ap.parse_args()

    if args.input:
        xlsx = Path(args.input)
        if not xlsx.exists():
            print(f"ERROR: input not found: {xlsx}", file=sys.stderr)
            return 1
    else:
        xlsx = _latest_xlsx(INPUT_DIR)
        if not xlsx:
            print(f"ERROR: no .xlsx in {INPUT_DIR}", file=sys.stderr)
            return 1

    out = Path(args.output)
    print(f"Input : {xlsx}")
    print(f"Output: {out}")

    if args.if_stale:
        result = regenerate_if_stale(xlsx, out)
        print(f"  result: {result}")
        return 0
    ok = generate_chart_png(xlsx, out)
    if ok:
        print(f"  Wrote {out.relative_to(ROOT) if out.is_absolute() else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
