"""
watch.py — Daemon: ตรวจ input/*.xlsx อัตโนมัติ re-generate เมื่อมีการเปลี่ยนแปลง

Usage:
    python scripts/watch.py          # Default poll interval: 5s
    python scripts/watch.py 10       # Custom interval: 10s

กด Ctrl+C เพื่อหยุด

Edge cases ที่จัดการ:
- Excel เปิดอยู่ (~$ lock file)  → skip cycle, แสดง "Excel locked, waiting..."
- openpyxl อ่านไม่ได้ (mid-save) → retain last snapshot, แสดง warning
- generate_report.py fail         → แสดง returncode error, ไม่ exit รอ cycle ถัดไป
- ไม่มีไฟล์ใน input/              → แสดง warning, รอ cycle ถัดไป
"""

import sys
import io
import os
import re
import json
import subprocess
import time
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    import openpyxl
except ImportError:
    print("ERROR: openpyxl not installed. Run: pip install openpyxl")
    sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_DIR        = os.path.join(BASE_DIR, "input")
GENERATOR     = os.path.join(BASE_DIR, "scripts", "generate_report.py")
SNAPSHOT_FILE = os.path.join(BASE_DIR, "logs", ".snapshot.json")
ALL_STATUSES  = ["pass", "fail", "not start", "in-progress", "block", "cancel"]

DEFAULT_INTERVAL = 5


# ── Helpers ───────────────────────────────────────────────────────────────────

def ts():
    return datetime.now().strftime("%H:%M:%S")


def find_target_xlsx():
    files = [
        f for f in os.listdir(IN_DIR)
        if f.endswith(".xlsx") and not f.startswith("~$")
    ]
    if not files:
        return None
    files.sort(key=lambda f: os.path.getmtime(os.path.join(IN_DIR, f)), reverse=True)
    return os.path.join(IN_DIR, files[0])


def is_locked(xlsx_path):
    """Check if Excel has a lock file (~$filename)."""
    dirname = os.path.dirname(xlsx_path)
    basename = os.path.basename(xlsx_path)
    lock = os.path.join(dirname, "~$" + basename[2:])
    return os.path.exists(lock)


def read_snapshot(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["TCM"]

    snapshot = {}
    ts_order = []
    current_tsid = None

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
            if current_tsid not in snapshot:
                snapshot[current_tsid] = {
                    "tcs": [],
                    "status_counts": {s: 0 for s in ALL_STATUSES},
                }
                ts_order.append(current_tsid)

        tcid = row[2]
        if current_tsid and tcid:
            tcid_str = str(tcid)
            status_raw = str(row[9] or "").strip().lower()
            snapshot[current_tsid]["tcs"].append(tcid_str)
            if status_raw in snapshot[current_tsid]["status_counts"]:
                snapshot[current_tsid]["status_counts"][status_raw] += 1

    wb.close()

    total_tcs = []
    total_counts = {s: 0 for s in ALL_STATUSES}
    for tsid in ts_order:
        total_tcs.extend(snapshot[tsid]["tcs"])
        for s in ALL_STATUSES:
            total_counts[s] += snapshot[tsid]["status_counts"][s]

    snapshot["__total__"] = {"tcs": total_tcs, "status_counts": total_counts}
    return snapshot


def load_saved_snapshot():
    if not os.path.exists(SNAPSHOT_FILE):
        return None
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_snapshot(snapshot):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def format_status_diff(old_counts, new_counts):
    parts = []
    labels = {
        "pass":        "Pass",
        "fail":        "Fail",
        "not start":   "Not Start",
        "in-progress": "In-Progress",
        "block":       "Block",
        "cancel":      "Cancel",
    }
    for s in ALL_STATUSES:
        o = old_counts.get(s, 0)
        n = new_counts.get(s, 0)
        if o != n:
            parts.append(f"{labels[s]} {o}→{n}")
    return parts


def diff_snapshots(old, new):
    lines = []
    all_tsids = sorted(
        [k for k in set(list(old.keys()) + list(new.keys())) if k != "__total__"]
    )

    for tsid in all_tsids:
        if tsid not in old:
            lines.append(f"  {tsid}: [NEW] {len(new[tsid]['tcs'])} TCs added")
            continue
        if tsid not in new:
            lines.append(f"  {tsid}: [REMOVED]")
            continue

        old_d = old[tsid]
        new_d = new[tsid]

        old_tcs = set(old_d["tcs"])
        new_tcs = set(new_d["tcs"])
        status_parts = format_status_diff(old_d["status_counts"], new_d["status_counts"])

        tc_part = []
        if len(old_tcs) != len(new_tcs):
            added   = new_tcs - old_tcs
            removed = old_tcs - new_tcs
            tc_part.append(f"TCs {len(old_tcs)}→{len(new_tcs)}")
            if added:
                tc_part.append(f"added: {', '.join(sorted(added))}")
            if removed:
                tc_part.append(f"removed: {', '.join(sorted(removed))}")

        all_parts = tc_part + status_parts
        if all_parts:
            lines.append(f"  {tsid}: " + "  ".join(all_parts))

    if "__total__" in old and "__total__" in new:
        total_parts = format_status_diff(
            old["__total__"]["status_counts"],
            new["__total__"]["status_counts"],
        )
        old_tc = len(old["__total__"]["tcs"])
        new_tc = len(new["__total__"]["tcs"])
        if old_tc != new_tc:
            total_parts = [f"TCs {old_tc}→{new_tc}"] + total_parts
        if total_parts:
            lines.append(f"  Total: " + "  ".join(total_parts))

    return lines


def run_generator():
    result = subprocess.run([sys.executable, GENERATOR], cwd=BASE_DIR)
    return result.returncode


# ── Main watch loop ────────────────────────────────────────────────────────────

def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INTERVAL

    last_mtime   = None
    last_snapshot = load_saved_snapshot()

    # Initial file detection
    xlsx_path = find_target_xlsx()
    if xlsx_path:
        fname = os.path.basename(xlsx_path)
        print(f"[{ts()}] Watching input/{fname} (poll: {interval}s)")
        last_mtime = os.path.getmtime(xlsx_path)
    else:
        print(f"[{ts()}] No .xlsx in input/ — waiting... (poll: {interval}s)")

    try:
        while True:
            time.sleep(interval)

            # Re-detect file (may appear/change)
            xlsx_path = find_target_xlsx()

            if xlsx_path is None:
                print(f"[{ts()}] WARNING: No .xlsx in input/ — waiting...")
                last_mtime = None
                continue

            fname = os.path.basename(xlsx_path)

            # Check lock
            if is_locked(xlsx_path):
                print(f"[{ts()}] Excel locked, waiting...")
                continue

            # Check mtime
            try:
                current_mtime = os.path.getmtime(xlsx_path)
            except OSError:
                continue

            if current_mtime == last_mtime:
                continue

            # File changed — read snapshot
            try:
                current = read_snapshot(xlsx_path)
            except Exception as e:
                print(f"[{ts()}] WARNING: Could not read file ({e}) — retaining last snapshot")
                last_mtime = current_mtime
                continue

            # Diff
            if last_snapshot is None:
                print(f"[{ts()}] Change detected! (first snapshot)")
            else:
                diff_lines = diff_snapshots(last_snapshot, current)
                if diff_lines:
                    print(f"[{ts()}] Change detected!")
                    for line in diff_lines:
                        print(line)
                else:
                    # mtime changed but no meaningful diff (e.g. save without data change)
                    last_mtime = current_mtime
                    continue

            # Generate report
            print("Regenerating...")
            rc = run_generator()
            if rc != 0:
                print(f"[{ts()}] ERROR: generate_report.py exited with code {rc}")
            else:
                save_snapshot(current)
                last_snapshot = current
                print(f"[{ts()}] Done.")

            last_mtime = current_mtime
            print(f"[{ts()}] Watching input/{fname} (poll: {interval}s)")

    except KeyboardInterrupt:
        print(f"\n[{ts()}] Stopped.")


if __name__ == "__main__":
    main()
