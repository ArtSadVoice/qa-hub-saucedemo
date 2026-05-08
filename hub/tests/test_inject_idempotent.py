"""Verify screenshot_injector is idempotent across re-runs.

Regression test for the bug where running Stage 6 (Inject Screenshots)
twice would double-embed every image in the Word report.
"""
import importlib.util
import re
import struct
import sys
import zipfile
import zlib
from pathlib import Path

HUB_DIR = Path(__file__).resolve().parent.parent
INJECTOR_PATH = HUB_DIR / "scaffold" / "full-pipeline" / "scripts" / "screenshot_injector.py"


def _load_injector_module():
    spec = importlib.util.spec_from_file_location("screenshot_injector_scaffold", INJECTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["screenshot_injector_scaffold"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_png(path: Path, w: int = 40, h: int = 30) -> None:
    # Minimal valid PNG (IHDR + IDAT + IEND)
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )
    sig  = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    raw  = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    path.write_bytes(sig + ihdr + idat + iend)


def _make_minimal_docx(path: Path, tcids: list[str]) -> None:
    body_paras = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{tcid} {tcid} test case</w:t></w:r></w:p>'
        for tcid in tcids
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body_paras}</w:body>'
        '</w:document>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    doc_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '</Relationships>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)


def _count_sc_media(docx_path: Path) -> int:
    with zipfile.ZipFile(docx_path) as zf:
        return sum(1 for n in zf.namelist() if re.match(r"^word/media/sc_", n))


def _count_sc_rels(docx_path: Path) -> int:
    with zipfile.ZipFile(docx_path) as zf:
        rels = zf.read("word/_rels/document.xml.rels").decode()
    return len(re.findall(r'Target="media/sc_', rels))


def _count_image_paragraphs(docx_path: Path) -> int:
    with zipfile.ZipFile(docx_path) as zf:
        doc = zf.read("word/document.xml").decode()
    return len(re.findall(r"<w:drawing>", doc))


def test_inject_is_idempotent(tmp_path: Path) -> None:
    mod = _load_injector_module()

    shots_dir  = tmp_path / "screenshots"
    output_dir = tmp_path / "output"
    shots_dir.mkdir()
    output_dir.mkdir()

    tcids = ["TS_01_01", "TS_01_02", "TS_02_01"]
    for tc in tcids:
        _make_png(shots_dir / f"{tc}.png")

    report = output_dir / "Report.docx"
    _make_minimal_docx(report, tcids)

    # First injection
    result1 = mod.ScreenshotInjector(report, shots_dir, report).run()
    assert result1["status"] == "ok", result1
    media_1  = _count_sc_media(report)
    rels_1   = _count_sc_rels(report)
    drawings_1 = _count_image_paragraphs(report)
    assert media_1 == len(tcids), f"first run should embed {len(tcids)} images, got {media_1}"
    assert rels_1 == len(tcids)
    assert drawings_1 == len(tcids)

    # Second injection on the already-injected report
    result2 = mod.ScreenshotInjector(report, shots_dir, report).run()
    assert result2["status"] == "ok", result2
    media_2  = _count_sc_media(report)
    rels_2   = _count_sc_rels(report)
    drawings_2 = _count_image_paragraphs(report)

    assert media_2 == media_1, f"media files doubled on re-run: {media_1} → {media_2}"
    assert rels_2  == rels_1,  f"relationships doubled on re-run: {rels_1} → {rels_2}"
    assert drawings_2 == drawings_1, (
        f"inline drawings doubled on re-run: {drawings_1} → {drawings_2}"
    )


def test_inject_is_idempotent_with_chart_summary(tmp_path: Path) -> None:
    """Chart_summary caption ('CHART_SUMMARY') must not accumulate on re-run."""
    mod = _load_injector_module()

    shots_dir  = tmp_path / "screenshots"
    output_dir = tmp_path / "output"
    shots_dir.mkdir()
    output_dir.mkdir()

    _make_png(shots_dir / "TS_01_01.png")
    _make_png(shots_dir / "chart_summary.png")

    # Report contains both a TCID line and the Test Scenarios summary placeholder
    body_paras = (
        '<w:p><w:r><w:t xml:space="preserve">TS_01_01 first test case</w:t></w:r></w:p>'
        '<w:p><w:r><w:t xml:space="preserve">[แนบ Screenshot/Evidence สำหรับ Test Scenarios]</w:t></w:r></w:p>'
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body_paras}</w:body>'
        '</w:document>'
    )
    report = output_dir / "Report.docx"
    with zipfile.ZipFile(report, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>'
        )
        zf.writestr("word/document.xml", document_xml)
        zf.writestr(
            "word/_rels/document.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '</Relationships>'
        )

    def _count_chart_summary_text() -> int:
        with zipfile.ZipFile(report) as zf:
            doc = zf.read("word/document.xml").decode()
        return doc.count(">CHART_SUMMARY<") + len(re.findall(r">CHART_SUMMARY\s", doc))

    # Run inject 3 times — each run should keep exactly one visible CHART_SUMMARY caption
    for i in range(3):
        mod.ScreenshotInjector(report, shots_dir, report).run()

    chart_captions = _count_chart_summary_text()
    assert chart_captions == 1, (
        f"CHART_SUMMARY caption text should appear once, got {chart_captions} after 3 runs"
    )
    assert _count_sc_media(report) == 2   # TS_01_01 + chart_summary
    assert _count_sc_rels(report)  == 2


def test_inject_handles_multi_image_per_tcid(tmp_path: Path) -> None:
    mod = _load_injector_module()

    shots_dir  = tmp_path / "screenshots"
    output_dir = tmp_path / "output"
    shots_dir.mkdir()
    output_dir.mkdir()

    # TS_01_01 has two screenshots (_1 and _2 suffix), TS_01_02 has one
    _make_png(shots_dir / "TS_01_01_1.png")
    _make_png(shots_dir / "TS_01_01_2.png")
    _make_png(shots_dir / "TS_01_02.png")

    report = output_dir / "Report.docx"
    _make_minimal_docx(report, ["TS_01_01", "TS_01_02"])

    mod.ScreenshotInjector(report, shots_dir, report).run()
    m1 = _count_sc_media(report)
    assert m1 == 3

    mod.ScreenshotInjector(report, shots_dir, report).run()
    m2 = _count_sc_media(report)
    assert m2 == 3, f"multi-image TCID should stay at 3 media files, got {m2}"
