"""Startup-time validators for Hub state files.

Returns a list of human-readable error strings (empty list = clean).
Used by app.py startup to fail loud instead of producing mysterious
errors deep inside request handlers.
"""

import re
import zipfile
from pathlib import Path

VALID_PROJECT_TYPES = {"full-pipeline", "manual-testing", "playwright-only", "pytest-only"}
VALID_PROJECT_PHASES = {"active", "planning", "paused"}
REQUIRED_PROJECT_FIELDS = ("id", "name", "path", "type")

# Minimum styles every Word template must carry for the report generator
# (and Word) to render cleanly. Mirrors scaffold/full-pipeline/scripts/_preflight.py
# REQUIRED_STYLES intentionally — kept in sync, not imported, so Hub's
# startup validator does not depend on scaffold being intact.
REQUIRED_TEMPLATE_STYLES = {
    "Normal", "DefaultParagraphFont", "TableNormal", "TableGrid",
    "Heading1", "Heading2", "Heading3",
    "Header", "Footer", "HeaderChar", "FooterChar",
}


def validate_config(cfg: dict) -> list[str]:
    """Check that config.json has the shape Hub expects.

    Catches issues a human (or a bad edit) can introduce:
    missing required fields, unknown type/phase values, duplicate ids or paths.
    """
    errors: list[str] = []
    if not isinstance(cfg, dict):
        return ["config.json root is not an object"]

    projects = cfg.get("projects", [])
    if not isinstance(projects, list):
        return ["config.json 'projects' must be a list"]

    seen_ids: dict[str, int] = {}
    seen_paths: dict[str, int] = {}

    for i, p in enumerate(projects):
        ctx = f"projects[{i}]"
        if not isinstance(p, dict):
            errors.append(f"{ctx}: not an object")
            continue

        for field in REQUIRED_PROJECT_FIELDS:
            if not p.get(field):
                errors.append(f"{ctx}: missing required field '{field}'")

        t = p.get("type")
        if t and t not in VALID_PROJECT_TYPES:
            errors.append(f"{ctx}.type={t!r} is not one of {sorted(VALID_PROJECT_TYPES)}")

        phase = p.get("phase")
        if phase and phase not in VALID_PROJECT_PHASES:
            errors.append(f"{ctx}.phase={phase!r} is not one of {sorted(VALID_PROJECT_PHASES)}")

        pid = p.get("id")
        if pid:
            if pid in seen_ids:
                errors.append(f"duplicate id {pid!r} at projects[{i}] (also at projects[{seen_ids[pid]}])")
            else:
                seen_ids[pid] = i

        path = p.get("path")
        if path:
            if path in seen_paths:
                errors.append(f"duplicate path {path!r} at projects[{i}] (also at projects[{seen_paths[path]}])")
            else:
                seen_paths[path] = i

    email = cfg.get("email")
    if email is not None:
        if not isinstance(email, dict):
            errors.append("email config must be an object")
        else:
            # If configured at all, require the host/user/port triplet
            if email.get("smtp_host") or email.get("smtp_user"):
                for field in ("smtp_host", "smtp_port", "smtp_user"):
                    if not email.get(field):
                        errors.append(f"email.{field} required when SMTP is partially configured")

    return errors


# ────────────────────────────────────────────────────────────────────────────
# Scaffold integrity — catch broken docx templates before they get copied
# into a fresh project. Past incident: a v2_1 template downloaded from
# elsewhere had duplicate styleIds and was missing core styles. python-docx
# parsed it fine but Word refused to open the resulting reports. Validating
# at hub startup + in CI prevents the broken template from sitting in the
# scaffold for weeks before someone notices.
# ────────────────────────────────────────────────────────────────────────────


def _validate_docx_template(path: Path) -> list[str]:
    """Structural lint of a Word template — duplicate styleIds + core styles."""
    issues: list[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            if "word/styles.xml" not in z.namelist():
                return ["missing word/styles.xml"]
            styles_xml = z.read("word/styles.xml").decode("utf-8")
    except zipfile.BadZipFile:
        return ["not a valid docx (zip is corrupt)"]
    except OSError as e:
        return [f"could not open: {e}"]

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


def validate_scaffolds(scaffold_root: Path) -> list[str]:
    """Validate every scaffold/<flavor>/templates/Test_Result_Template.docx.

    Walks each scaffold flavor directory and runs a structural check on its
    Word template. Returns one error string per issue, prefixed with the
    flavor so the operator can locate the bad file.

    Behavior:
      - Missing scaffold root → empty list (validator stays no-op for repos
        that don't ship a scaffold). Logged as a warning at the call site.
      - Flavor without a templates/Test_Result_Template.docx → silently
        skipped (some flavors may be playwright-only and have no docx).
    """
    errors: list[str] = []
    if not scaffold_root.exists() or not scaffold_root.is_dir():
        return errors

    for flavor in sorted(p for p in scaffold_root.iterdir() if p.is_dir()):
        tpl = flavor / "templates" / "Test_Result_Template.docx"
        if not tpl.exists():
            continue
        for issue in _validate_docx_template(tpl):
            errors.append(f"scaffold/{flavor.name}/templates/Test_Result_Template.docx: {issue}")

    return errors
