"""Hub-side scaffold drift detection + per-project preflight.

Two operations exposed to app.py route handlers:

  preflight_project(project_path) -> dict
    Run the same checks the project's own scripts run (Excel locks in
    input/, structural validation of templates/Test_Result_Template.docx)
    BEFORE the user kicks off a pipeline. Cheap (~50ms), idempotent,
    no side-effects.

  audit_project_drift(project_path, scaffold_root, project_type) -> dict
    Compare the project's copy of canonical infrastructure files against
    `scaffold/<project_type>/...` and report which are missing / drifted.
    Helps surface "this project hasn't been re-synced since the gap-closure
    work landed in scaffold/" without the operator having to diff by hand.

Both functions return JSON-serializable dicts so app.py can `jsonify(...)`
directly. Errors are reported as fields, not raised — the dashboard should
not 500 just because a project's input/ folder is missing.

Drift results are cached in-process for DRIFT_TTL_SECONDS (default 30s)
to keep dashboard polls cheap. Caches are invalidated automatically when
a sync runs (call `invalidate_drift_cache(project_path)` from
api_scaffold_sync) so the operator sees the badge flip immediately
after Sync now / bulk-sync.
"""
from __future__ import annotations
import hashlib
import re
import time
import zipfile
from pathlib import Path
from typing import Any

# How long a drift report stays cached. Dashboard polls /api/scaffold/drift
# on a 60s timer (see DashboardView refreshTick); 30s gives one fresh
# report per refresh cycle while still amortising the FS hits when many
# tabs/components ask in quick succession.
DRIFT_TTL_SECONDS = 30.0
_drift_cache: dict[str, tuple[float, dict]] = {}


def _cache_key(project_path: str | Path, scaffold_root: str | Path,
               project_type: str) -> str:
    """Normalised key — resolves both paths so str-vs-Path / abs-vs-rel
    callers produce the same cache slot."""
    try:
        proj = str(Path(project_path).resolve())
    except OSError:
        proj = str(project_path)
    try:
        scaff = str(Path(scaffold_root).resolve())
    except OSError:
        scaff = str(scaffold_root)
    return f"{proj}|{scaff}|{project_type}"


def invalidate_drift_cache(project_path: str | Path | None = None) -> None:
    """Drop one entry (when a sync touched it) or the whole cache (None).
    Cheap; called from api_scaffold_sync after a successful sync so the
    next dashboard poll sees the fresh state instead of the pre-sync one.

    In-place mutation so callers that imported `_drift_cache` by name see
    the change too (avoids the dict-rebinding pitfall when this module is
    re-imported across handlers)."""
    if project_path is None:
        _drift_cache.clear()
        return
    try:
        prefix = str(Path(project_path).resolve()) + "|"
    except OSError:
        prefix = f"{project_path}|"
    for k in [k for k in _drift_cache if k.startswith(prefix)]:
        del _drift_cache[k]

# Files that should be carried by every full-pipeline project, with the
# canonical version sourced from scaffold/full-pipeline/. Add more as the
# scaffold accretes new infrastructure.
DRIFT_TRACKED_FILES = (
    "scripts/_preflight.py",
    "scripts/check_template.py",
    "scripts/sync_to_project.py",
    "scripts/refresh_scaffold.py",
    ".githooks/pre-commit",
    "templates/Test_Result_Template.docx",
)

# Mirror of REQUIRED_TEMPLATE_STYLES in validators.py — kept in sync
# deliberately so this module does not import from validators (and vice
# versa). Both must update together if the rule changes.
REQUIRED_TEMPLATE_STYLES = {
    "Normal", "DefaultParagraphFont", "TableNormal", "TableGrid",
    "Heading1", "Heading2", "Heading3",
    "Header", "Footer", "HeaderChar", "FooterChar",
}


def _hash_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else ""


def _validate_template_structure(path: Path) -> list[str]:
    """Same shape as validators._validate_docx_template — duplicated to
    keep this module self-contained for the drift-API caller path."""
    issues: list[str] = []
    if not path.exists():
        return ["template file missing"]
    try:
        with zipfile.ZipFile(path) as z:
            if "word/styles.xml" not in z.namelist():
                return ["missing word/styles.xml inside docx"]
            styles_xml = z.read("word/styles.xml").decode("utf-8")
    except zipfile.BadZipFile:
        return ["template is not a valid docx (bad zip)"]
    except OSError as e:
        return [f"could not open template: {e}"]

    style_ids = re.findall(r'<w:style[^>]+w:styleId="([^"]+)"', styles_xml)
    seen: dict[str, int] = {}
    for sid in style_ids:
        seen[sid] = seen.get(sid, 0) + 1
    duplicates = sorted(sid for sid, c in seen.items() if c > 1)
    if duplicates:
        issues.append(f"duplicate w:styleId: {duplicates}")

    missing = REQUIRED_TEMPLATE_STYLES - set(style_ids)
    if missing:
        issues.append(f"missing required styles: {sorted(missing)}")

    return issues


def _scan_excel_locks(input_dir: Path) -> list[str]:
    """Return names of locked xlsx (Excel desktop ~$ file present)."""
    if not input_dir.exists():
        return []
    locks = []
    for lockfile in input_dir.glob("~$*.xlsx"):
        # Strip "~$" prefix to report the actual file name
        locks.append(lockfile.name[2:])
    return sorted(locks)


# ─────────────────────────────────────────────────────────────────────────────
# D — Preflight one project
# ─────────────────────────────────────────────────────────────────────────────


def preflight_project(project_path: str | Path) -> dict[str, Any]:
    """Run the cheap-to-run preflight gates against one project's working
    state. Designed to be hit before "Run Pipeline" so the user sees
    actionable issues early instead of after the pipeline crashes mid-run.

    Result shape:
        {
          "project_path": "...",
          "project_exists": bool,
          "ok": bool,                 # True iff no issues found
          "excel_locks": [str, ...],   # xlsx names currently open in Excel
          "template": {
            "path": "...",
            "exists": bool,
            "issues": [str, ...]      # empty = template structurally OK
          },
          "summary": "ok" | "human-readable issue summary"
        }
    """
    base = Path(project_path)
    out: dict[str, Any] = {
        "project_path": str(base),
        "project_exists": base.exists(),
        "ok": False,
        "excel_locks": [],
        "template": {"path": "", "exists": False, "issues": []},
        "summary": "",
    }

    if not base.exists():
        out["summary"] = "project path does not exist"
        return out

    out["excel_locks"] = _scan_excel_locks(base / "input")

    tpl = base / "templates" / "Test_Result_Template.docx"
    out["template"]["path"] = str(tpl)
    out["template"]["exists"] = tpl.exists()
    if tpl.exists():
        out["template"]["issues"] = _validate_template_structure(tpl)

    issues = []
    if out["excel_locks"]:
        issues.append(f"{len(out['excel_locks'])} xlsx open in Excel")
    if not out["template"]["exists"]:
        issues.append("template missing")
    elif out["template"]["issues"]:
        issues.append(f"template has {len(out['template']['issues'])} structural issue(s)")

    out["ok"] = not issues
    out["summary"] = "ok" if not issues else "; ".join(issues)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# C — Drift audit (one project vs canonical scaffold)
# ─────────────────────────────────────────────────────────────────────────────


def audit_project_drift(
    project_path: str | Path,
    scaffold_root: str | Path,
    project_type: str = "full-pipeline",
) -> dict[str, Any]:
    """Hash-compare project's tracked infrastructure files against the
    canonical scaffold flavor for that project type.

    Cached for DRIFT_TTL_SECONDS. Pass `invalidate_drift_cache(path)`
    after a sync to drop the entry so the next call returns fresh data.

    Result shape:
        {
          "project_path": "...",
          "scaffold_path": "...",
          "project_type": "full-pipeline",
          "files": [
             {"rel": "scripts/_preflight.py",
              "status": "current" | "drifted" | "missing-in-project" |
                        "missing-in-scaffold",
              "project_hash": "...", "scaffold_hash": "..."}
          ],
          "summary": {"current": N, "drifted": N, "missing_in_project": N,
                      "missing_in_scaffold": N},
          "ok": bool   # True iff every file is "current"
        }
    """
    key = _cache_key(project_path, scaffold_root, project_type)
    now = time.monotonic()
    cached = _drift_cache.get(key)
    if cached and (now - cached[0]) < DRIFT_TTL_SECONDS:
        return cached[1]

    base = Path(project_path)
    scaffold = Path(scaffold_root) / project_type

    files_out: list[dict[str, str]] = []
    summary = {"current": 0, "drifted": 0,
               "missing_in_project": 0, "missing_in_scaffold": 0}

    for rel in DRIFT_TRACKED_FILES:
        p_path = base / rel
        s_path = scaffold / rel
        p_hash = _hash_file(p_path)
        s_hash = _hash_file(s_path)

        if not s_path.exists():
            status = "missing-in-scaffold"
        elif not p_path.exists():
            status = "missing-in-project"
        elif p_hash == s_hash:
            status = "current"
        else:
            status = "drifted"

        summary[status.replace("-", "_")] += 1
        files_out.append({
            "rel": rel,
            "status": status,
            "project_hash": p_hash or "(absent)",
            "scaffold_hash": s_hash or "(absent)",
        })

    result = {
        "project_path": str(base),
        "scaffold_path": str(scaffold),
        "project_type": project_type,
        "files": files_out,
        "summary": summary,
        "ok": summary["drifted"] == 0 and summary["missing_in_project"] == 0,
    }
    _drift_cache[key] = (now, result)
    return result
