"""
screenshot_injector.py
──────────────────────
Auto-inject Playwright screenshots into the QA Test Result Word report.

สิ่งที่ทำ:
  1. สแกนหา placeholder paragraphs ใน Word document
       "[แนบ Screenshot/Evidence สำหรับ TS_XX]"   → inject screenshots ทุกรูปของ TS นั้น
       "TS_XX_YY  ชื่อ test case"                  → inject screenshot ของ TCID นั้น
       "[แนบ Screenshot/Evidence สำหรับ Test Scenarios]" → inject ทุกรูป
  2. เพิ่ม relationship + image file เข้า docx ZIP
  3. แทน paragraph placeholder ด้วย <w:drawing> inline image + caption

Usage:
  python scripts/screenshot_injector.py
  python scripts/screenshot_injector.py --report output/MyReport.docx --screenshots screenshots/
  python scripts/screenshot_injector.py --dry-run
"""

from __future__ import annotations
import argparse, os, re, shutil, struct, zipfile, zlib
from datetime import datetime
from pathlib import Path

# ── EMU constants (914400 EMU = 1 inch) ──────────────────────────────────────
IMG_MAX_WIDTH_EMU  = 5_740_800   # ~6.27 inches (A4 with 1-inch margins)
IMG_MAX_HEIGHT_EMU = 3_600_000   # ~3.94 inches

# ── Relationship type ─────────────────────────────────────────────────────────
IMG_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

# ── Placeholder patterns (ตาม CLAUDE.md) ─────────────────────────────────────
RE_TS_HEADER  = re.compile(r"\[แนบ Screenshot/Evidence สำหรับ (TS_\d+)\]")
RE_TS_SUMMARY = re.compile(r"\[แนบ Screenshot/Evidence สำหรับ Test Scenarios\]")
RE_TCID_LINE  = re.compile(r"^(TS_\d{2}_\d{2,3})\s+.+")

# ── Status → caption color ────────────────────────────────────────────────────
STATUS_COLORS = {
    "pass":        "1A6B3A",
    "fail":        "7B241C",
    "in-progress": "7D3C00",
    "block":       "4A235A",
    "cancel":      "595959",
    "not start":   "185FA5",
}


# ─────────────────────────────────────────────────────────────────────────────
# PNG / image helpers
# ─────────────────────────────────────────────────────────────────────────────

def png_dimensions(data: bytes) -> tuple[int, int]:
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
    except Exception:
        pass
    return 800, 600


def scale_to_fit(px_w: int, px_h: int, dpi: int = 96) -> tuple[int, int]:
    emu_w = int(px_w * 914_400 / dpi)
    emu_h = int(px_h * 914_400 / dpi)
    if emu_w > IMG_MAX_WIDTH_EMU:
        f = IMG_MAX_WIDTH_EMU / emu_w
        emu_w, emu_h = IMG_MAX_WIDTH_EMU, int(emu_h * f)
    if emu_h > IMG_MAX_HEIGHT_EMU:
        f = IMG_MAX_HEIGHT_EMU / emu_h
        emu_w, emu_h = int(emu_w * f), IMG_MAX_HEIGHT_EMU
    return emu_w, emu_h


# ─────────────────────────────────────────────────────────────────────────────
# XML builders
# ─────────────────────────────────────────────────────────────────────────────

def _drawing_xml(rel_id: str, emu_w: int, emu_h: int, img_id: int, desc: str) -> str:
    d = desc.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    NS_A   = "http://schemas.openxmlformats.org/drawingml/2006/main"
    NS_PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
    NS_R   = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    NS_WP  = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    return (
        f'<w:drawing>'
        f'<wp:inline distT="0" distB="0" distL="0" distR="0" xmlns:wp="{NS_WP}">'
        f'<wp:extent cx="{emu_w}" cy="{emu_h}"/>'
        f'<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{img_id}" name="img{img_id}" descr="{d}"/>'
        f'<wp:cNvGraphicFramePr>'
        f'<a:graphicFrameLocks xmlns:a="{NS_A}" noChangeAspect="1"/>'
        f'</wp:cNvGraphicFramePr>'
        f'<a:graphic xmlns:a="{NS_A}">'
        f'<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic xmlns:pic="{NS_PIC}">'
        f'<pic:nvPicPr>'
        f'<pic:cNvPr id="{img_id}" name="img{img_id}" descr="{d}"/>'
        f'<pic:cNvPicPr><a:picLocks noChangeAspect="1"/></pic:cNvPicPr>'
        f'</pic:nvPicPr>'
        f'<pic:blipFill>'
        f'<a:blip r:embed="{rel_id}" xmlns:r="{NS_R}"/>'
        f'<a:stretch><a:fillRect/></a:stretch>'
        f'</pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        f'<a:ext cx="{emu_w}" cy="{emu_h}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:noFill/></pic:spPr>'
        f'</pic:pic>'
        f'</a:graphicData>'
        f'</a:graphic>'
        f'</wp:inline>'
        f'</w:drawing>'
    )


def _image_para(rel_id: str, emu_w: int, emu_h: int, img_id: int, desc: str) -> str:
    return (
        f'<w:p>'
        f'<w:pPr><w:jc w:val="center"/>'
        f'<w:spacing w:before="80" w:after="80"/></w:pPr>'
        f'<w:r>{_drawing_xml(rel_id, emu_w, emu_h, img_id, desc)}</w:r>'
        f'</w:p>'
    )


def _caption_para(tcid: str, filename: str, status: str = "", idx: int = 0, total: int = 1) -> str:
    color = STATUS_COLORS.get(status.lower(), "595959")
    label = tcid
    if total > 1:
        label += f"  ({idx + 1}/{total})"
    if status:
        label += f"  [{status.upper()}]"
    return (
        f'<w:p>'
        f'<w:pPr><w:jc w:val="center"/>'
        f'<w:spacing w:before="0" w:after="120"/></w:pPr>'
        f'<w:r>'
        f'<w:rPr><w:i/><w:iCs/>'
        f'<w:sz w:val="16"/><w:szCs w:val="16"/>'
        f'<w:color w:val="{color}"/></w:rPr>'
        f'<w:t xml:space="preserve">{label}</w:t>'
        f'</w:r></w:p>'
    )


def _spacer() -> str:
    return '<w:p><w:pPr><w:spacing w:before="120" w:after="0"/></w:pPr></w:p>'


# ─────────────────────────────────────────────────────────────────────────────
# ZIP / relationship helpers
# ─────────────────────────────────────────────────────────────────────────────

def _max_rel_id(rels_xml: str) -> int:
    ids = [int(m) for m in re.findall(r'Id="rId(\d+)"', rels_xml)]
    return max(ids) if ids else 0


def _add_rel(rels_xml: str, rel_id: str, rel_type: str, target: str) -> str:
    entry = f'<Relationship Id="{rel_id}" Type="{rel_type}" Target="{target}"/>'
    return rels_xml.replace("</Relationships>", entry + "\n</Relationships>")


def _add_content_type(ct_xml: str, ext: str, mime: str) -> str:
    if f'Extension="{ext}"' in ct_xml:
        return ct_xml
    entry = f'<Default Extension="{ext}" ContentType="{mime}"/>'
    return ct_xml.replace("</Types>", entry + "\n</Types>")


# ─────────────────────────────────────────────────────────────────────────────
# Paragraph splitting
# ─────────────────────────────────────────────────────────────────────────────

def _para_text(xml: str) -> str:
    return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


def _split_body(body: str) -> list[str]:
    return re.findall(
        r"(?:<w:p[ >].*?</w:p>|<w:tbl[ >].*?</w:tbl>|<w:sectPr[ >].*?</w:sectPr>)",
        body,
        re.DOTALL,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Core injector class
# ─────────────────────────────────────────────────────────────────────────────

class ScreenshotInjector:
    def __init__(
        self,
        report_path: Path,
        screenshots_dir: Path,
        output_path: Path,
        status_map: dict[str, str] | None = None,
        dry_run: bool = False,
    ):
        self.report_path     = report_path
        self.screenshots_dir = screenshots_dir
        self.output_path     = output_path
        self.status_map      = {k.upper(): v for k, v in (status_map or {}).items()}
        self.dry_run         = dry_run
        self._next_rel       = 1
        self._next_img       = 1
        self._injected: list[dict] = []

    # ── public ───────────────────────────────────────────────────────────────

    def run(self) -> dict:
        self._discover()
        if not self._shots:
            return {"status": "skipped", "reason": "no screenshots found", "injected": []}
        if self.dry_run:
            return self._dry_run_report()
        self._load()
        self._process()
        self._save()
        self._summary()
        return {"status": "ok", "output": str(self.output_path), "injected": self._injected}

    def _refresh_chart_if_stale(self, chart_path: Path) -> None:
        """Regenerate chart_summary.png from the latest input xlsx if its
        mtime is older than the xlsx (or the PNG is missing). Idempotent —
        no-ops when the chart is already up-to-date.

        Imports the standalone generator lazily so an inject run on a
        machine without matplotlib still works (chart simply stays stale
        with a warning printed)."""
        try:
            import sys as _sys
            from pathlib import Path as _P
            _sys.path.insert(0, str(_P(__file__).resolve().parent))
            from generate_chart import _latest_xlsx, regenerate_if_stale
        except Exception as e:
            print(f"  [chart] regenerate skipped — {type(e).__name__}: {e}")
            return
        # Find latest input xlsx beside this project
        input_dir = _P(__file__).resolve().parent.parent / "input"
        xlsx = _latest_xlsx(input_dir)
        if not xlsx:
            return
        result = regenerate_if_stale(xlsx, chart_path)
        if result == "wrote":
            print(f"  [chart] regenerated from {xlsx.name} → {chart_path.name}")
        elif result == "no-matplotlib":
            print(f"  [chart] WARN: matplotlib missing — using stale {chart_path.name}")

    # ── private ──────────────────────────────────────────────────────────────

    def _discover(self):
        self._shots: dict[str, list[Path]] = {}
        if not self.screenshots_dir.exists():
            return
        RE_SHOT = re.compile(r"^(TS_\d{2}_\d{2,3})(?:_\d+)?$", re.IGNORECASE)
        for f in sorted(self.screenshots_dir.iterdir()):
            if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                m = RE_SHOT.match(f.stem)
                if m:
                    key = m.group(1).upper()
                    self._shots.setdefault(key, []).append(f)

    def _load(self):
        self._zip: dict[str, bytes] = {}
        with zipfile.ZipFile(self.report_path) as zf:
            for n in zf.namelist():
                self._zip[n] = zf.read(n)

    def _strip_previous_injection(self, doc: str, rels: str) -> tuple[str, str]:
        # Idempotency: remove blocks added by a prior run of this injector.
        # Marker: relationship targets under media/sc_* (our naming convention).
        sc_rels = re.findall(
            r'<Relationship Id="(rId\d+)"[^>]*?Target="media/sc_[^"]+"\s*/>',
            rels,
        )
        if not sc_rels:
            return doc, rels

        rels = re.sub(
            r'<Relationship Id="rId\d+"[^>]*?Target="media/sc_[^"]+"\s*/>\s*',
            '', rels,
        )
        for name in list(self._zip.keys()):
            if re.match(r'^word/media/sc_[^/]+$', name):
                del self._zip[name]

        body_m = re.search(r"(<w:body>)(.*)(</w:body>)", doc, re.DOTALL)
        if not body_m:
            return doc, rels

        blocks = _split_body(body_m.group(2))
        sc_ref_pat = re.compile(
            '(?:' + '|'.join(f'r:embed="{re.escape(r)}"' for r in sc_rels) + ')'
        )
        # Our captions are italic + 8pt (sz=16 half-points) — matches both
        # TS_XX_YY captions and the CHART_SUMMARY caption.
        caption_pat = re.compile(
            r'<w:r>\s*<w:rPr>\s*<w:i/>\s*<w:iCs/>\s*<w:sz w:val="16"/>',
            re.DOTALL,
        )
        SPACER_XML = '<w:p><w:pPr><w:spacing w:before="120" w:after="0"/></w:pPr></w:p>'

        kept: list[str] = []
        drop_caption = False
        drop_spacer  = False
        for blk in blocks:
            if drop_caption:
                drop_caption = False
                if caption_pat.search(blk):
                    drop_spacer = True
                    continue
            if drop_spacer:
                drop_spacer = False
                if blk == SPACER_XML:
                    continue
            if sc_ref_pat.search(blk):
                if kept and kept[-1] == SPACER_XML:
                    kept.pop()
                drop_caption = True
                continue
            kept.append(blk)

        new_body = body_m.group(1) + "\n".join(kept) + body_m.group(3)
        doc = doc.replace(body_m.group(0), new_body)
        return doc, rels

    def _process(self):
        doc  = self._zip["word/document.xml"].decode()
        rels = self._zip.get("word/_rels/document.xml.rels", b"").decode()
        ct   = self._zip.get("[Content_Types].xml", b"").decode()

        # Ensure rels file exists
        if not rels.strip():
            rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '</Relationships>'
            )

        doc, rels = self._strip_previous_injection(doc, rels)

        self._next_rel = _max_rel_id(rels) + 1

        body_m = re.search(r"(<w:body>)(.*)(</w:body>)", doc, re.DOTALL)
        if not body_m:
            raise ValueError("No <w:body> found")

        blocks    = _split_body(body_m.group(2))
        new_blocks: list[str] = []

        # Track which TCIDs were already injected via TS-header batch
        # so individual TCID lines don't double-inject
        injected_by_header: set[str] = set()

        for blk in blocks:
            if not blk.startswith("<w:p"):
                new_blocks.append(blk)
                continue

            txt = _para_text(blk)

            # Pattern 1: TS section header → drop the placeholder paragraph entirely.
            # generate_report.py inserts "[แนบ Screenshot/Evidence สำหรับ TS_NN]"
            # as a one-off anchor; we don't need it after this stage runs because
            # Pattern 3 injects screenshots individually after each TCID line.
            # Keeping it would (a) leave ugly placeholder text in the final report
            # and (b) break the Hub's s8 status check which scans for any
            # remaining "[แนบ Screenshot/Evidence" string in document.xml.
            if RE_TS_HEADER.search(txt):
                continue

            # Pattern 2: Test Scenarios summary → inject chart_summary.png after placeholder
            #
            # The chart used to go stale here: it was only regenerated as a
            # side-effect of generate_report.py, so running /inject after
            # editing the xlsx without re-running /report left a chart from
            # the previous status snapshot in the docx. Regenerate first if
            # the PNG is older than the latest input xlsx.
            if RE_TS_SUMMARY.search(txt):
                new_blocks.append(blk)
                chart_path = self.screenshots_dir / "chart_summary.png"
                self._refresh_chart_if_stale(chart_path)
                if chart_path.exists():
                    new_blocks.append(_spacer())
                    extra, rels, ct = self._img_blocks(chart_path, "CHART_SUMMARY", rels, ct)
                    new_blocks += extra
                continue

            # Pattern 3: individual TCID line → inject screenshot(s) right after the line
            m2 = RE_TCID_LINE.match(txt.strip())
            if m2:
                tcid = m2.group(1).upper()
                if tcid in injected_by_header:
                    # Already injected (e.g. re-run: caption line also matches regex)
                    new_blocks.append(blk)
                    continue
                if tcid in self._shots:
                    new_blocks.append(blk)
                    new_blocks.append(_spacer())
                    shots_list = self._shots[tcid]
                    total = len(shots_list)
                    for idx, shot_path in enumerate(shots_list):
                        extra, rels, ct = self._img_blocks(shot_path, tcid, rels, ct, idx=idx, total=total)
                        new_blocks += extra
                    injected_by_header.add(tcid)  # track to prevent re-injection on re-run
                    continue

            new_blocks.append(blk)

        new_doc = doc.replace(
            body_m.group(0),
            body_m.group(1) + "\n".join(new_blocks) + body_m.group(3),
        )
        self._zip["word/document.xml"]            = new_doc.encode()
        self._zip["word/_rels/document.xml.rels"] = rels.encode()
        self._zip["[Content_Types].xml"]          = ct.encode()

    def _img_blocks(
        self, path: Path, tcid: str, rels: str, ct: str, idx: int = 0, total: int = 1
    ) -> tuple[list[str], str, str]:
        data    = path.read_bytes()
        ext     = path.suffix.lower().lstrip(".")
        mime    = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        # Use index suffix in filename to avoid collision when multiple images per TCID
        suffix  = f"_{idx + 1}" if total > 1 else ""
        media   = f"word/media/sc_{tcid.lower()}{suffix}.{ext}"
        rel_id  = f"rId{self._next_rel}"
        img_id  = self._next_img

        self._zip[media] = data
        rels = _add_rel(rels, rel_id, IMG_REL_TYPE, f"media/sc_{tcid.lower()}{suffix}.{ext}")
        ct   = _add_content_type(ct, ext, mime)

        self._next_rel += 1
        self._next_img += 1

        px_w, px_h   = png_dimensions(data) if ext == "png" else (800, 600)
        emu_w, emu_h = scale_to_fit(px_w, px_h)
        status       = self.status_map.get(tcid, "")

        self._injected.append({
            "tcid": tcid, "file": path.name,
            "rel_id": rel_id, "emu": f"{emu_w}x{emu_h}", "status": status,
        })
        return (
            [
                _image_para(rel_id, emu_w, emu_h, img_id, tcid),
                _caption_para(tcid, path.name, status, idx=idx, total=total),
                _spacer(),
            ],
            rels,
            ct,
        )

    def _save(self):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        # Pre-flight: wait for Word to release the output docx (if it's open
        # in Word, our save would either fail or get overwritten on Word's
        # next save). UX-friendly retry instead of immediate abort.
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.insert(0, str(_Path(__file__).resolve().parent))
        from _preflight import wait_for_docx_unlocked, PreflightError  # noqa: E402
        try:
            wait_for_docx_unlocked(self.output_path, timeout=60,
                                   action="inject screenshots into")
        except PreflightError as e:
            print(f"\nERROR: {e}", file=_sys.stderr)
            raise
        if self.output_path.exists() and self.output_path.samefile(self.report_path):
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            arch_dir = self.output_path.parent.parent / "archive"
            arch_dir.mkdir(exist_ok=True)
            bak = arch_dir / f"{self.output_path.stem}_backup_{ts}.docx"
            shutil.copy2(self.output_path, bak)
            print(f"  Backup → archive/{bak.name}")
        # Inject `<w:updateFields w:val="true"/>` so Word refreshes the TOC
        # field (and any other fields) on first open. After injection,
        # body headings and pagination shift but TOC entries baked into the
        # docx still reflect the pre-inject state — without this flag, Word
        # shows the stale TOC indefinitely.
        self._ensure_update_fields_on_open()
        with zipfile.ZipFile(self.output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in self._zip.items():
                zf.writestr(name, data)

    def _ensure_update_fields_on_open(self):
        """Two-layer fix to make Word refresh the TOC after injection:

          (1) Set <w:updateFields w:val="true"/> in settings.xml — hint to Word
              that fields in this doc should be updated on open.
          (2) Mark the TOC field's begin <w:fldChar> with w:dirty="true" in
              document.xml — Word's TOC implementation often ignores the
              settings-level hint when it has a cached (pre-inject) result;
              the per-field dirty attribute forces a refresh regardless.

        Both layers are idempotent."""
        # Layer 1: settings.xml
        key = "word/settings.xml"
        raw = self._zip.get(key)
        if raw is None:
            self._zip[key] = (
                b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                b'<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                b'<w:updateFields w:val="true"/>'
                b'</w:settings>'
            )
        else:
            text = raw.decode("utf-8")
            import re as _re
            if "<w:updateFields" in text:
                text = _re.sub(
                    r'<w:updateFields\s+w:val="(?:false|0)"\s*/>',
                    '<w:updateFields w:val="true"/>',
                    text,
                )
            else:
                text = text.replace(
                    "</w:settings>",
                    '<w:updateFields w:val="true"/></w:settings>',
                )
            self._zip[key] = text.encode("utf-8")

        # Layer 2: mark TOC field's begin fldChar dirty in document.xml
        self._mark_toc_field_dirty()

    def _mark_toc_field_dirty(self):
        """Add w:dirty="true" to every <w:fldChar w:fldCharType="begin"...>
        whose corresponding <w:instrText> contains 'TOC'. Idempotent: skips
        elements that already carry w:dirty.

        Also marks PAGEREF field begins as dirty — those are the entries
        inside the TOC; refreshing them is harmless and ensures page
        numbers update if the outer TOC refresh skips them."""
        key = "word/document.xml"
        raw = self._zip.get(key)
        if raw is None:
            return
        text = raw.decode("utf-8")
        import re as _re

        # Match every <w:fldChar ... w:fldCharType="begin" ... /> (self-closing)
        # OR <w:fldChar ... w:fldCharType="begin" ...> (with content). Add
        # w:dirty="true" if not already present.
        pattern = _re.compile(
            r'<w:fldChar([^>]*?)w:fldCharType="begin"([^>]*?)(/?)>'
        )

        def add_dirty(m):
            before, after, slash = m.group(1), m.group(2), m.group(3)
            if 'w:dirty=' in before or 'w:dirty=' in after:
                return m.group(0)  # already dirty
            return f'<w:fldChar{before}w:fldCharType="begin"{after} w:dirty="true"{slash}>'

        new_text = pattern.sub(add_dirty, text)
        if new_text != text:
            self._zip[key] = new_text.encode("utf-8")

    def _summary(self):
        print(f"\n✓ Injected {len(self._injected)} screenshot(s) into {self.output_path.name}")
        for item in self._injected:
            tag = f"  [{item['status']}]" if item["status"] else ""
            print(f"  {item['tcid']:<18} {item['file']}{tag}")

    def _dry_run_report(self) -> dict:
        total_files = sum(len(v) for v in self._shots.values())
        print("\n── Dry Run ──────────────────────────────────────────")
        print(f"  Report:      {self.report_path}")
        print(f"  Screenshots: {self.screenshots_dir}  ({total_files} files, {len(self._shots)} TCIDs)")
        print(f"\n  Would inject:")
        for tcid, paths in sorted(self._shots.items()):
            s = f"  [{self.status_map.get(tcid, '')}]" if self.status_map.get(tcid) else ""
            if len(paths) == 1:
                print(f"    {tcid:<18} ← {paths[0].name}{s}")
            else:
                for i, p in enumerate(paths):
                    print(f"    {tcid:<18} ← {p.name}  ({i + 1}/{len(paths)}){s}")
        print("─────────────────────────────────────────────────────\n")
        return {"status": "dry_run", "would_inject": list(self._shots.keys())}


# ─────────────────────────────────────────────────────────────────────────────
# Status map loader
# ─────────────────────────────────────────────────────────────────────────────

def load_status_map(logs_dir: Path) -> dict[str, str]:
    if not logs_dir.exists():
        return {}
    files = sorted(logs_dir.glob("playwright_output_*.json"), reverse=True)
    if not files:
        return {}
    try:
        import json
        return json.loads(files[0].read_text()).get("results", {})
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Inject screenshots into Word test result")
    ap.add_argument("--report",      default=None)
    ap.add_argument("--screenshots", default="screenshots")
    ap.add_argument("--out",         default=None)
    ap.add_argument("--logs",        default="logs")
    ap.add_argument("--dry-run",     action="store_true")
    args = ap.parse_args()

    root  = Path(__file__).parent.parent
    ss    = root / args.screenshots
    logs  = root / args.logs

    if args.report:
        report = Path(args.report)
    else:
        docs = sorted(
            [d for d in (root / "output").glob("*.docx") if "_backup_" not in d.name],
            key=lambda f: f.stat().st_mtime, reverse=True,
        )
        if not docs:
            print("ERROR: No .docx in output/. Use --report.")
            raise SystemExit(1)
        report = docs[0]

    out = Path(args.out) if args.out else report
    print(f"  Report:      {report}")
    print(f"  Screenshots: {ss}")
    print(f"  Output:      {out}")

    smap = load_status_map(logs)
    if smap:
        print(f"  Status map:  {len(smap)} entries")

    result = ScreenshotInjector(report, ss, out, smap, args.dry_run).run()
    if result["status"] not in ("ok", "dry_run"):
        print(f"  Skipped: {result.get('reason')}")


if __name__ == "__main__":
    main()
