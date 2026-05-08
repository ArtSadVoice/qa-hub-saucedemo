"""
Shared pre-flight checks for the QA pipeline.

Closes recurring failure modes:

1. Excel-overwrite race
   When the user has an xlsx open in Excel desktop, Excel holds a
   "~$Name.xlsx" lock file and an in-memory snapshot. If a script writes a
   new xlsx while Excel is open, Excel may later save its (now stale)
   snapshot back, silently truncating the script's output.

2. Word-overwrite / lock race
   Same pattern but with .docx files: if a docx is open in Word, the writer
   either fails outright (Permission denied) or, if the writer doesn't
   detect the lock, Word's eventual save can stomp on the new content.

3. Word template structural corruption
   Templates downloaded from external sources can parse as well-formed XML
   and load via python-docx, yet still fail to open in Word. Common
   breakage: duplicate w:styleId, missing core styles (Normal, TableNormal,
   Header, Footer), header drawings with broken rId references.

Public API:
    check_xlsx_not_locked(path, *, action)       -> raises if lock present
    check_docx_not_locked(path, *, action)       -> raises if lock present
    wait_for_xlsx_unlocked(path, timeout, poll)  -> retry-with-progress
    wait_for_docx_unlocked(path, timeout, poll)  -> retry-with-progress
    validate_template_structure(path, strict)    -> structural rules
    smoke_test_template(path)                    -> tool-based open test
"""
from __future__ import annotations
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path


class PreflightError(RuntimeError):
    """Raised when a preflight check would otherwise lead to silent corruption."""


# ────────────────────────────────────────────────────────────────────────────
# Lock-file helpers (Excel + Word both use ~$Name.ext convention)
# ────────────────────────────────────────────────────────────────────────────

def lock_path_for(path: Path | str) -> Path:
    """Office creates ~$Filename beside the file when it's open."""
    p = Path(path)
    return p.with_name("~$" + p.name)


def _check_not_locked(path: Path | str, *, action: str, kind: str) -> None:
    target = Path(path)
    target_lock = lock_path_for(target)
    if target_lock.exists():
        raise PreflightError(
            f"Cannot {action} '{target.name}' — {kind} has it open "
            f"(lock file: {target_lock.name}).\n"
            f"  → Close the file in {kind} desktop, then rerun.\n"
            f"  Background: see scripts/_preflight.py for the overwrite race."
        )

    parent = target.parent if target.parent.exists() else None
    if parent:
        # Same-extension siblings being open is enough to risk a save-time
        # autosave clobber if the user has multiple Office windows open.
        ext = target.suffix.lower()
        siblings = [p for p in parent.glob(f"~$*{ext}") if p != target_lock]
        if siblings:
            names = ", ".join(p.name[2:] for p in siblings)
            raise PreflightError(
                f"Other {ext} in '{parent.name}/' open in {kind}: {names}\n"
                f"  → Close all {kind} windows pointing at {parent.name}/ then rerun."
            )


def check_xlsx_not_locked(xlsx_path: Path | str, *, action: str = "write") -> None:
    """Abort if the target xlsx (or any sibling .xlsx) is open in Excel."""
    _check_not_locked(xlsx_path, action=action, kind="Excel")


def check_docx_not_locked(docx_path: Path | str, *, action: str = "write") -> None:
    """Abort if the target docx (or any sibling .docx) is open in Word."""
    _check_not_locked(docx_path, action=action, kind="Word")


def _wait_for_unlocked(
    path: Path | str,
    *,
    kind: str,
    action: str,
    timeout: float,
    poll: float,
) -> None:
    """Poll until lock file disappears; print progress; raise on timeout."""
    target = Path(path)
    target_lock = lock_path_for(target)
    start = time.monotonic()
    last_msg = 0.0
    first = True

    while True:
        if not target_lock.exists():
            # Also clear sibling-scan
            try:
                _check_not_locked(target, action=action, kind=kind)
            except PreflightError:
                pass  # sibling lock — fall through to wait
            else:
                if not first:
                    print(f"[preflight] {kind} released — proceeding.", flush=True)
                return

        elapsed = time.monotonic() - start
        if elapsed > timeout:
            raise PreflightError(
                f"Timed out after {int(elapsed)}s waiting for '{target.name}' "
                f"in {kind} to close.\n"
                f"  Lock file still present: {target_lock.name}\n"
                f"  → Close {kind} or rerun with longer timeout."
            )

        # Print every ~10s to be useful but not spammy
        if first or (time.monotonic() - last_msg) >= 10.0:
            remaining = int(timeout - elapsed)
            print(
                f"[preflight] Waiting for {kind} to release "
                f"'{target.name}' ({remaining}s before abort)... "
                f"close the file now.",
                flush=True,
            )
            last_msg = time.monotonic()
            first = False

        time.sleep(poll)


def wait_for_xlsx_unlocked(
    xlsx_path: Path | str,
    *,
    timeout: float = 60.0,
    poll: float = 2.0,
    action: str = "write",
) -> None:
    """Wait up to `timeout` seconds for Excel to release the file."""
    _wait_for_unlocked(xlsx_path, kind="Excel", action=action,
                       timeout=timeout, poll=poll)


def wait_for_docx_unlocked(
    docx_path: Path | str,
    *,
    timeout: float = 60.0,
    poll: float = 2.0,
    action: str = "write",
) -> None:
    """Wait up to `timeout` seconds for Word to release the file."""
    _wait_for_unlocked(docx_path, kind="Word", action=action,
                       timeout=timeout, poll=poll)


# ────────────────────────────────────────────────────────────────────────────
# Template structural validation
# ────────────────────────────────────────────────────────────────────────────

REQUIRED_STYLES = {
    "Normal", "DefaultParagraphFont", "TableNormal", "TableGrid",
    "Heading1", "Heading2", "Heading3",
    "Header", "Footer", "HeaderChar", "FooterChar",
}

REQUIRED_BODY_ANCHORS = (
    "5. Test Result",
    "6. Type of Testing",
    "TS_01:",
)

REQUIRED_PLACEHOLDERS = (
    "{{PROJECT_CODE}}",
    "{{PROJECT_NAME}}",
    "{{PREPARED_DATE}}",
    "{{APPLICATION_OVERVIEW_DESCRIPTION}}",
)

MIN_TABLE_COUNT = 4   # tables[0..3] required by generate_report.py


def validate_template_structure(
    docx_path: Path | str,
    *,
    strict: bool = True,
) -> list[str]:
    """Validate the docx template against generate_report's expectations.

    Returns list of human-readable issues; empty = OK.
    With strict=True (default), raises PreflightError if any issue.

    Designed to catch the failure modes seen with the v2_1 template:
    duplicate styleIds, missing core styles, missing anchors / placeholders.
    """
    p = Path(docx_path)
    if not p.exists():
        msg = f"Template not found: {p}"
        if strict:
            raise PreflightError(msg)
        return [msg]

    issues: list[str] = []

    try:
        with zipfile.ZipFile(p) as z:
            names = set(z.namelist())
            styles_xml = z.read("word/styles.xml").decode("utf-8") if "word/styles.xml" in names else ""
            doc_xml    = z.read("word/document.xml").decode("utf-8") if "word/document.xml" in names else ""
    except zipfile.BadZipFile:
        msg = f"Template is not a valid ZIP/docx: {p.name}"
        if strict:
            raise PreflightError(msg)
        return [msg]

    style_ids = re.findall(r'<w:style[^>]+w:styleId="([^"]+)"', styles_xml)
    seen: dict[str, int] = {}
    for sid in style_ids:
        seen[sid] = seen.get(sid, 0) + 1
    duplicates = [sid for sid, c in seen.items() if c > 1]
    if duplicates:
        issues.append(f"Duplicate w:styleId values: {duplicates}")

    missing_styles = REQUIRED_STYLES - set(style_ids)
    if missing_styles:
        issues.append(f"Missing required styles: {sorted(missing_styles)}")

    body_text = re.sub(r"<[^>]+>", "", doc_xml)
    body_compact = re.sub(r"\s+", " ", body_text)
    for anchor in REQUIRED_BODY_ANCHORS:
        if anchor not in body_compact:
            issues.append(f"Missing body anchor text: {anchor!r}")

    for ph in REQUIRED_PLACEHOLDERS:
        if ph not in body_compact:
            issues.append(f"Missing placeholder: {ph}")

    table_count = doc_xml.count("<w:tbl>") + doc_xml.count("<w:tbl ")
    if table_count < MIN_TABLE_COUNT:
        issues.append(
            f"Template has {table_count} tables, "
            f"need at least {MIN_TABLE_COUNT} "
            f"(0=banner, 1=project info, 2=signoff anchor, 3=summary anchor)"
        )

    if issues and strict:
        msg = (
            f"Template '{p.name}' failed validation ({len(issues)} issues):\n"
            + "\n".join(f"  - {i}" for i in issues)
            + "\n  → Run `python scripts/check_template.py` for diagnostics, "
              "or restore from a .bak_* backup."
        )
        raise PreflightError(msg)

    return issues


# ────────────────────────────────────────────────────────────────────────────
# Smoke test — proxy "Word can open this" using external tools if available
# ────────────────────────────────────────────────────────────────────────────

LIBREOFFICE_PATHS = (
    "soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)


def _find_soffice() -> str | None:
    for cand in LIBREOFFICE_PATHS:
        try:
            if Path(cand).is_file():
                return cand
            located = shutil.which(cand)
            if located:
                return located
        except Exception:
            continue
    return None


def _find_word_com() -> bool:
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False


def smoke_test_template(docx_path: Path | str) -> dict[str, str]:
    """Try to open the template with available tools as a Word-rejection proxy.

    Returns dict mapping tool name → status. Status is one of:
      "ok"       — tool opened/converted the file successfully
      "fail: …"  — tool reported failure (template likely broken)
      "skip: …"  — tool not available

    Tools tried, in order:
      1. python-docx round-trip (always available — quick sanity)
      2. LibreOffice headless convert-to PDF (best Word-proxy)
      3. Word COM via pywin32 (Windows only, requires Office + pywin32)
    """
    p = Path(docx_path)
    results: dict[str, str] = {}

    # 1. python-docx round-trip
    try:
        from docx import Document
        d = Document(p)
        out = p.with_suffix(".smoke_rt.docx")
        d.save(out)
        out.unlink(missing_ok=True)
        results["python-docx"] = "ok"
    except Exception as e:
        results["python-docx"] = f"fail: {type(e).__name__}: {e}"

    # 2. LibreOffice convert-to PDF
    so = _find_soffice()
    if so:
        out_dir = p.parent / "_smoke_lo"
        out_dir.mkdir(exist_ok=True)
        try:
            r = subprocess.run(
                [so, "--headless", "--convert-to", "pdf",
                 "--outdir", str(out_dir), str(p)],
                capture_output=True, text=True, timeout=90,
            )
            pdf = out_dir / (p.stem + ".pdf")
            if r.returncode == 0 and pdf.exists():
                results["libreoffice"] = "ok"
            else:
                err = (r.stderr or r.stdout or "").strip().splitlines()
                results["libreoffice"] = f"fail: {(err[-1] if err else 'no pdf produced')}"
        except subprocess.TimeoutExpired:
            results["libreoffice"] = "fail: timeout (>90s)"
        except Exception as e:
            results["libreoffice"] = f"fail: {type(e).__name__}: {e}"
        finally:
            try:
                shutil.rmtree(out_dir)
            except Exception:
                pass
    else:
        results["libreoffice"] = "skip: soffice not found in PATH or default install dirs"

    # 3. Word COM (Windows + Office + pywin32)
    if sys.platform == "win32" and _find_word_com():
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            try:
                doc = word.Documents.Open(str(p), ReadOnly=True, AddToRecentFiles=False)
                doc.Close(SaveChanges=0)
                results["word-com"] = "ok"
            finally:
                word.Quit()
        except Exception as e:
            results["word-com"] = f"fail: {type(e).__name__}: {e}"
    else:
        if sys.platform != "win32":
            results["word-com"] = "skip: not Windows"
        else:
            results["word-com"] = "skip: pywin32 not installed (pip install pywin32)"

    return results
