"""Release Gate computation — pure domain logic, no Flask dependency.

Helpers are imported from app.py lazily inside compute_release_gate() to
avoid a circular import at module load (app.py also imports from here).
"""
from datetime import datetime


def _gate_item(id_: str, label: str, ok: bool, detail: str, warn: bool = False) -> dict:
    """Build a single gate criterion record."""
    return {"id": id_, "label": label, "ok": bool(ok), "warn": bool(warn) and not bool(ok), "detail": detail}


def compute_release_gate(pid: str) -> dict:
    """Compute Release Gate for a project. Context-free (no Flask request needed).
    Returns {project_id, project_type, phase, verdict, go, criteria[], summary, thresholds}."""
    from app import get_paths, load_bugs, _load_history, latest_xlsx, latest_docx, _excel_tc_stats

    paths = get_paths(pid)
    if not paths:
        return {"error": f"project not found: {pid}"}

    proj      = paths["proj"]
    proj_type = proj.get("type", "full-pipeline")
    phase     = proj.get("phase", "active")

    # Non-active phases short-circuit
    if phase != "active":
        return {
            "project_id":   pid,
            "project_type": proj_type,
            "phase":        phase,
            "verdict":      "SKIP_PLANNING" if phase == "planning" else "SKIP_PAUSED",
            "go":           False,
            "reason":       f"Project is in {phase} phase — gate not evaluated",
            "criteria":     [],
            "summary":      {"total": 0, "pass": 0, "warn": 0, "hard_fail": 0},
        }

    # Per-project gate thresholds
    gates          = proj.get("gates") or {}
    gate_pass_rate = int(gates.get("pass_rate", 80))
    gate_tcm_pass  = int(gates.get("tcm_pass_rate", 80))
    gate_shot_cov  = int(gates.get("screenshot_coverage", 80))
    _wb = lambda g: max(g - 20, 0)  # warn band lower bound

    # ── data ─────────────────────────────────────────────────────────
    bugs = load_bugs(pid)
    open_crit = sum(1 for b in bugs if b.get("severity") == "Critical" and b.get("status") == "Open")
    open_high = sum(1 for b in bugs if b.get("severity") == "High"     and b.get("status") == "Open")

    hist_all   = [e for e in _load_history() if e.get("project_id") == pid and e.get("step") == "tests"]
    valid_hist = [e for e in hist_all if (e.get("pass", 0) > 0 or e.get("fail", 0) > 0)]
    last_test  = valid_hist[-1] if valid_hist else None
    pass_rate  = None
    if last_test:
        tot = last_test.get("pass", 0) + last_test.get("fail", 0)
        if tot > 0:
            pass_rate = round(last_test["pass"] / tot * 100)

    TAG_WEIGHT = {"": 3, "regression": 3, "e2e": 2, "visual": 2, "smoke": 1}
    tag        = (last_test or {}).get("tag", "") if last_test else ""
    tag_weight = TAG_WEIGHT.get(tag, 2)
    tag_label  = f"@{tag}" if tag else "All tests"

    xlsx = latest_xlsx(paths["input"])  if paths["input"].exists()  else None
    docx = latest_docx(paths["output"]) if paths["output"].exists() else None
    spec_files = sorted(paths["tests"].glob("TS_*.spec.ts")) if paths["tests"].exists() else []
    xlsx_mtime = xlsx.stat().st_mtime if xlsx else 0
    spec_stale = bool(xlsx_mtime and spec_files and any(f.stat().st_mtime < xlsx_mtime for f in spec_files))
    shot_count = len(list(paths["screenshots"].glob("TS_*.png"))) if paths["screenshots"].exists() else 0
    pw_idx     = paths["base"] / "playwright-report" / "index.html"
    pw_ok      = pw_idx.exists()
    pw_ts      = datetime.fromtimestamp(pw_idx.stat().st_mtime).strftime("%d %b %Y %H:%M") if pw_ok else None

    tc = _excel_tc_stats(paths) if proj_type in ("full-pipeline", "manual-testing") else {}

    # ── build criteria per project type ───────────────────────────────
    C = []

    def _scope_detail():
        if not last_test: return "ยังไม่มี run history"
        if tag_weight >= 3: return f"✓ {tag_label} · {last_test['ts']}"
        if tag_weight == 2: return f"⚠ {tag_label} — พอสำหรับ minor release, ควรรัน All ก่อน major"
        return f"✗ {tag_label} เท่านั้น — ไม่เพียงพอสำหรับ release"

    def _crit_bug_detail():
        if open_crit == 0:
            return "ไม่มี Critical open bug" + (f" (High: {open_high} — ควรแก้ก่อน)" if open_high else "")
        return f"มี {open_crit} Critical bug ที่ยัง Open"

    def _high_bug_detail():
        return "ไม่มี High open bug" if open_high == 0 else f"มี {open_high} High bug ที่ยัง Open"

    def _pass_rate_detail():
        if pass_rate is None: return "ยังไม่มี run history"
        return f"{pass_rate}% ({last_test['pass']} pass / {last_test['fail']} fail) · {last_test['ts']}"

    def _tcm_pass_detail():
        if not tc or tc.get("total", 0) == 0: return "ไม่พบ TCM"
        return f"{tc['pass_pct']}% ({tc['pass']}/{tc['total']} TCs marked Pass)"

    def _not_start_detail():
        if not tc or tc.get("total", 0) == 0: return "ไม่พบ TCM"
        return (f"ทุก TC มีสถานะแล้ว ({tc['total']} TCs)" if tc["not_started"] == 0
                else f"ยังไม่ได้ทดสอบ {tc['not_started']}/{tc['total']} TCs")

    if proj_type == "playwright-only":
        C.append(_gate_item("run_scope", "Run Scope — ต้องรันอย่างน้อย @e2e หรือ All",
            last_test is not None and tag_weight >= 2, _scope_detail(),
            warn=last_test is not None and tag_weight == 2))
        C.append(_gate_item("pass_rate", f"Pass Rate ≥ {gate_pass_rate}%",
            pass_rate is not None and pass_rate >= gate_pass_rate, _pass_rate_detail(),
            warn=pass_rate is not None and _wb(gate_pass_rate) <= pass_rate < gate_pass_rate))
        C.append(_gate_item("no_critical_bug", "ไม่มี Critical Bug ที่ยัง Open",
            open_crit == 0, _crit_bug_detail()))
        C.append(_gate_item("no_high_bug", "ไม่มี High Bug ที่ยัง Open",
            open_high == 0, _high_bug_detail(), warn=0 < open_high <= 2))
        C.append(_gate_item("has_screenshots", "มี Screenshots จากการรัน",
            shot_count > 0,
            f"{shot_count} screenshot(s) พร้อมแล้ว" if shot_count else "ยังไม่มี screenshot — รัน tests ก่อน"))
        C.append(_gate_item("pw_report_ready", "Playwright HTML Report พร้อม",
            pw_ok,
            f"playwright-report/index.html พร้อม · {pw_ts}" if pw_ok else "รัน tests ก่อนเพื่อ generate playwright-report/",
            warn=(not pw_ok) and pass_rate is not None))

    elif proj_type == "pytest-only":
        C.append(_gate_item("test_executed", "มี Test Run อย่างน้อย 1 ครั้ง",
            last_test is not None,
            f"Last run: {last_test['ts']}" if last_test else "ยังไม่มี run history — รัน tests ก่อน"))
        C.append(_gate_item("run_scope", "Run Scope — ต้องรันอย่างน้อย @e2e หรือ All",
            last_test is not None and tag_weight >= 2, _scope_detail(),
            warn=last_test is not None and tag_weight == 2))
        C.append(_gate_item("pass_rate", f"Pass Rate ≥ {gate_pass_rate}%",
            pass_rate is not None and pass_rate >= gate_pass_rate, _pass_rate_detail(),
            warn=pass_rate is not None and _wb(gate_pass_rate) <= pass_rate < gate_pass_rate))
        C.append(_gate_item("no_critical_bug", "ไม่มี Critical Bug ที่ยัง Open",
            open_crit == 0, _crit_bug_detail()))
        C.append(_gate_item("no_high_bug", "ไม่มี High Bug ที่ยัง Open",
            open_high == 0, _high_bug_detail(), warn=0 < open_high <= 2))
        # pytest-only counts screenshots from screenshots/ + test-results/ (any .png),
        # populated by the @pytest.mark.tcid screenshot hook in apps/.../conftest.py
        _shot_dir1 = paths["base"] / "screenshots"
        _shot_dir2 = paths["base"] / "test-results"
        _shot_n = ((len(list(_shot_dir1.rglob("*.png"))) if _shot_dir1.exists() else 0)
                 + (len(list(_shot_dir2.rglob("*.png"))) if _shot_dir2.exists() else 0))
        C.append(_gate_item("has_screenshots", "มี Screenshots จากการรัน",
            _shot_n > 0,
            f"{_shot_n} screenshot(s) (screenshots/ + test-results/)" if _shot_n
              else "ยังไม่มี screenshot — เพิ่ม @pytest.mark.tcid + screenshot fixture"))

    elif proj_type == "manual-testing":
        C.append(_gate_item("tcm_uploaded", "TCM Excel อัปโหลดแล้ว",
            bool(xlsx), xlsx.name if xlsx else "ยังไม่มีไฟล์ใน input/"))
        C.append(_gate_item("no_not_start", "Test Cases ไม่มี Not Start (ทดสอบครบแล้ว)",
            tc.get("total", 0) > 0 and tc.get("not_started", 0) == 0, _not_start_detail(),
            warn=tc.get("total", 0) > 0 and 0 < tc.get("not_started", 0) < tc.get("total", 0) * 0.2))
        C.append(_gate_item("tcm_pass_rate", f"TCM Pass Rate ≥ {gate_tcm_pass}%",
            tc.get("pass_pct") is not None and tc["pass_pct"] >= gate_tcm_pass, _tcm_pass_detail(),
            warn=tc.get("pass_pct") is not None and _wb(gate_tcm_pass) <= tc["pass_pct"] < gate_tcm_pass))
        C.append(_gate_item("no_critical_bug", "ไม่มี Critical Bug ที่ยัง Open",
            open_crit == 0, _crit_bug_detail()))
        C.append(_gate_item("no_high_bug", "ไม่มี High Bug ที่ยัง Open",
            open_high == 0, _high_bug_detail(), warn=0 < open_high <= 2))
        C.append(_gate_item("word_report_ready", "Word Report พร้อม",
            bool(docx), docx.name if docx else "ยังไม่มี report — รัน Stage 7 ก่อน"))

    else:  # full-pipeline
        C.append(_gate_item("tcm_uploaded", "TCM Excel อัปโหลดแล้ว",
            bool(xlsx), xlsx.name if xlsx else "ยังไม่มีไฟล์ใน input/"))
        C.append(_gate_item("spec_complete", "Test Spec ครบ (Stage 4)",
            bool(spec_files) and not spec_stale,
            (f"⚠ {len(spec_files)} spec — เก่ากว่า Excel" if spec_stale else f"{len(spec_files)} spec file(s)")
              if spec_files else "ยังไม่มี spec — รัน Stage 2 ก่อน",
            warn=bool(spec_files) and spec_stale))
        C.append(_gate_item("no_not_start", "Test Cases ไม่มี Not Start",
            tc.get("total", 0) > 0 and tc.get("not_started", 0) == 0, _not_start_detail(),
            warn=tc.get("total", 0) > 0 and 0 < tc.get("not_started", 0) < tc.get("total", 0) * 0.2))
        C.append(_gate_item("run_scope", "Run Scope — ต้องรันอย่างน้อย @e2e หรือ All",
            last_test is not None and tag_weight >= 2, _scope_detail(),
            warn=last_test is not None and tag_weight == 2))
        C.append(_gate_item("pass_rate", f"Pass Rate ≥ {gate_pass_rate}%",
            pass_rate is not None and pass_rate >= gate_pass_rate, _pass_rate_detail(),
            warn=pass_rate is not None and _wb(gate_pass_rate) <= pass_rate < gate_pass_rate))
        C.append(_gate_item("tcm_pass_rate", f"TCM Pass Rate ≥ {gate_tcm_pass}%",
            tc.get("pass_pct") is not None and tc["pass_pct"] >= gate_tcm_pass, _tcm_pass_detail(),
            warn=tc.get("pass_pct") is not None and _wb(gate_tcm_pass) <= tc["pass_pct"] < gate_tcm_pass))
        C.append(_gate_item("no_critical_bug", "ไม่มี Critical Bug ที่ยัง Open",
            open_crit == 0, _crit_bug_detail()))
        C.append(_gate_item("shot_coverage", f"Screenshot Coverage ≥ {gate_shot_cov}%",
            tc.get("shot_coverage_pct") is not None and tc["shot_coverage_pct"] >= gate_shot_cov,
            "ไม่พบ TCM" if not tc or not tc.get("total")
              else f"{tc['shot_coverage_pct']}% ({tc['shot_coverage_n']}/{tc['total']} TCs มี screenshot)",
            warn=tc.get("shot_coverage_pct") is not None and _wb(gate_shot_cov) <= tc["shot_coverage_pct"] < gate_shot_cov))
        C.append(_gate_item("word_report_ready", "Word Report พร้อม",
            bool(docx), docx.name if docx else "ยังไม่มี report — รัน Stage 7 ก่อน"))

    hard_fail = sum(1 for c in C if not c["ok"] and not c["warn"])
    warn_ct   = sum(1 for c in C if c["warn"])
    pass_ct   = sum(1 for c in C if c["ok"])
    verdict   = "GO" if hard_fail == 0 else ("NOT_READY" if not last_test and proj_type != "manual-testing" else "NOGO")

    return {
        "project_id":   pid,
        "project_type": proj_type,
        "phase":        phase,
        "verdict":      verdict,
        "go":           hard_fail == 0,
        "criteria":     C,
        "summary":      {"total": len(C), "pass": pass_ct, "warn": warn_ct, "hard_fail": hard_fail},
        "thresholds":   {"pass_rate": gate_pass_rate, "tcm_pass_rate": gate_tcm_pass, "screenshot_coverage": gate_shot_cov},
    }
