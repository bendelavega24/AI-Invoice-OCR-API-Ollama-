"""
TC005 — Upload Multi-Page PDF Invoice: "All pages are uploaded and processed successfully."

Observed failure: the invoice was accepted but not all pages were processed correctly. Root causes covered here:

1. A page that failed (OCR/LLM/validation) was dropped silently — nothing told the user which page was lost.
2. Surviving invoices were labelled by their position among the survivors, not their real page number
   ("page 2/2" for what was really page 3), which also skewed the dedup fingerprint.
3. An unexpected error on ONE page aborted the whole file, losing every other page.
4. Page 2+ of a single invoice ("Page 2 of 3") were parsed as separate invoices.
5. A failing save/archive step for one invoice could drop the remaining pages.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from config.settings import settings
from models.invoice import Invoice
from ocr import ocr_engine
from parser import invoice_parser as ip


# --------------------------------------------------------------------------- helpers

def _page(n, total, text, lines=None, **extra):
    page = {
        "page_number": n, "total_pages": total, "text": text, "lines": lines or [],
        "avg_confidence": 0.9, "engine": "paddleocr", "image_path": f"page{n}.png",
    }
    page.update(extra)
    return page


def _fake_ocr(monkeypatch, pages):
    monkeypatch.setattr(ip, "extract_pages_from_file", lambda *a, **k: [dict(p) for p in pages])


def _fake_build(monkeypatch, fail_on=None, boom_on=None):
    """Replace the LLM/vision pipeline; record what it was asked to build."""
    calls = []

    def build(**kw):
        calls.append(kw)
        if fail_on and kw["page_number"] in fail_on:
            raise ip.InvoiceParsingError("LLM returned invalid JSON")
        if boom_on and kw["page_number"] in boom_on:
            raise RuntimeError("Ollama connection reset")
        return Invoice(vendor_name="ACME", invoice_number=f"INV-{kw['page_number']}", source_file=kw["file_path"])

    monkeypatch.setattr(ip, "_build_invoice_from_ocr", build)
    return calls


@pytest.fixture(autouse=True)
def _merge_on(monkeypatch):
    monkeypatch.setattr(settings, "MULTIPAGE_MERGE_CONTINUATIONS", True)


# --------------------------------------------------------------------------- real PDF through the real OCR wrapper

def _make_pdf(path, pages=3):
    import fitz
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Invoice page {i + 1}")
    doc.save(str(path))
    doc.close()
    return str(path)


def test_every_page_of_a_real_pdf_is_ocrd_and_numbered(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(ocr_engine, "extract_from_image",
                        lambda p, **k: {"text": f"text of {Path(p).name}", "lines": [], "avg_confidence": 0.9, "engine": "paddleocr"})
    pages = ocr_engine.extract_pages_from_file(_make_pdf(tmp_path / "inv.pdf", 3))
    assert [p["page_number"] for p in pages] == [1, 2, 3]
    assert all(p["total_pages"] == 3 for p in pages)
    assert len({p["image_path"] for p in pages}) == 3  # one distinct rendered image per page


def test_ocr_crash_on_one_page_does_not_lose_the_others(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path))

    def flaky(path, **k):
        if path.endswith("_page2.png"):
            raise RuntimeError("paddle exploded")
        return {"text": "ok", "lines": [], "avg_confidence": 0.9, "engine": "paddleocr"}

    monkeypatch.setattr(ocr_engine, "extract_from_image", flaky)
    pages = ocr_engine.extract_pages_from_file(_make_pdf(tmp_path / "inv.pdf", 3))
    assert [p["text"] for p in pages] == ["ok", "", "ok"]
    assert "paddle exploded" in pages[1]["ocr_error"]


# --------------------------------------------------------------------------- failure isolation + reporting

def test_failed_page_is_reported_not_silently_dropped(monkeypatch):
    _fake_ocr(monkeypatch, [_page(1, 3, "ACME inv 1"), _page(2, 3, "ACME inv 2"), _page(3, 3, "ACME inv 3")])
    _fake_build(monkeypatch, fail_on={2})
    invoices, skipped = ip.parse_invoice_pages_detailed("x.pdf")
    assert [i.source_pages for i in invoices] == [[1], [3]]  # real page numbers, not 1 and 2
    assert all(i.source_total_pages == 3 for i in invoices)
    assert skipped == [{"pages": [2], "total_pages": 3, "reason": "LLM returned invalid JSON"}]


def test_unexpected_error_on_one_page_does_not_abort_the_file(monkeypatch):
    _fake_ocr(monkeypatch, [_page(1, 3, "a"), _page(2, 3, "b"), _page(3, 3, "c")])
    _fake_build(monkeypatch, boom_on={2})
    invoices, skipped = ip.parse_invoice_pages_detailed("x.pdf")
    assert [i.source_pages for i in invoices] == [[1], [3]]
    assert skipped[0]["pages"] == [2] and "Ollama connection reset" in skipped[0]["reason"]


def test_blank_and_ocr_failed_pages_get_distinct_reasons(monkeypatch):
    _fake_ocr(monkeypatch, [
        _page(1, 3, "real invoice"),
        _page(2, 3, "   "),
        _page(3, 3, "", ocr_error="paddle exploded"),
    ])
    _fake_build(monkeypatch)
    invoices, skipped = ip.parse_invoice_pages_detailed("x.pdf")
    assert len(invoices) == 1
    assert "blank" in skipped[0]["reason"]
    assert skipped[1]["reason"] == "OCR failed: paddle exploded"


def test_unreadable_file_raises_parsing_error_instead_of_crashing(monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("cannot open document")
    monkeypatch.setattr(ip, "extract_pages_from_file", broken)
    with pytest.raises(ip.InvoiceParsingError, match="cannot open document"):
        ip.parse_invoice_pages_detailed("x.pdf")


def test_legacy_wrapper_still_returns_list_and_raises_when_everything_fails(monkeypatch):
    _fake_ocr(monkeypatch, [_page(1, 2, "a"), _page(2, 2, "b")])
    _fake_build(monkeypatch, fail_on={2})
    assert len(ip.parse_invoice_pages("x.pdf")) == 1
    _fake_build(monkeypatch, fail_on={1, 2})
    with pytest.raises(ip.InvoiceParsingError, match="page 1/2.*page 2/2"):
        ip.parse_invoice_pages("x.pdf")


# --------------------------------------------------------------------------- continuation pages

def test_pages_of_one_invoice_are_merged_into_one_invoice(monkeypatch):
    _fake_ocr(monkeypatch, [
        _page(1, 3, "ACME CORP Invoice INV-9 Page 1 of 3",
              lines=[{"text": "ACME", "bbox": [[0, 10], [50, 10], [50, 20], [0, 20]], "confidence": .9}],
              processed_image_path=None),
        _page(2, 3, "Widget 100.00 Page 2 of 3",
              lines=[{"text": "Widget", "bbox": [[0, 5], [50, 5], [50, 15], [0, 15]], "confidence": .9}]),
        _page(3, 3, "TOTAL 500.00 Page 3 of 3"),
    ])
    calls = _fake_build(monkeypatch)
    invoices, skipped = ip.parse_invoice_pages_detailed("x.pdf")
    assert skipped == []
    assert len(invoices) == 1 and len(calls) == 1
    assert invoices[0].source_pages == [1, 2, 3]
    text = calls[0]["ocr_text"]
    assert text.index("INV-9") < text.index("Widget") < text.index("TOTAL 500.00")
    # page-2 boxes sit BELOW page 1's content in the stitched coordinate space, not on top of it
    ys = [min(pt[1] for pt in line["bbox"]) for line in calls[0]["ocr_lines"]]
    assert ys[1] > ys[0] + 10


def test_separate_invoices_without_continuation_markers_stay_separate(monkeypatch):
    _fake_ocr(monkeypatch, [_page(1, 2, "ACME Invoice A"), _page(2, 2, "OTHER CO Invoice B")])
    calls = _fake_build(monkeypatch)
    invoices, _ = ip.parse_invoice_pages_detailed("x.pdf")
    assert [i.source_pages for i in invoices] == [[1], [2]] and len(calls) == 2


def test_each_page_marked_page_1_of_1_stays_separate(monkeypatch):
    _fake_ocr(monkeypatch, [_page(1, 2, "A Page 1 of 1"), _page(2, 2, "B Page 1 of 1")])
    _fake_build(monkeypatch)
    invoices, _ = ip.parse_invoice_pages_detailed("x.pdf")
    assert len(invoices) == 2


def test_two_multi_page_invoices_in_one_pdf_are_grouped_correctly(monkeypatch):
    _fake_ocr(monkeypatch, [
        _page(1, 4, "A Page 1 of 2"), _page(2, 4, "A Page 2 of 2"),
        _page(3, 4, "B Page 1 of 2"), _page(4, 4, "B Page 2 of 2"),
    ])
    _fake_build(monkeypatch)
    invoices, _ = ip.parse_invoice_pages_detailed("x.pdf")
    assert [i.source_pages for i in invoices] == [[1, 2], [3, 4]]


def test_mismatched_total_or_wrong_position_is_not_merged(monkeypatch):
    # page 2 claims "2 of 5" but page 1 said "of 3" -> different documents
    _fake_ocr(monkeypatch, [_page(1, 3, "A Page 1 of 3"), _page(2, 3, "B Page 2 of 5"), _page(3, 3, "C Page 3 of 3")])
    _fake_build(monkeypatch)
    invoices, _ = ip.parse_invoice_pages_detailed("x.pdf")
    assert [i.source_pages for i in invoices] == [[1], [2], [3]]


def test_merge_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "MULTIPAGE_MERGE_CONTINUATIONS", False)
    _fake_ocr(monkeypatch, [_page(1, 2, "A Page 1 of 2"), _page(2, 2, "A Page 2 of 2")])
    _fake_build(monkeypatch)
    invoices, _ = ip.parse_invoice_pages_detailed("x.pdf")
    assert len(invoices) == 2


# --------------------------------------------------------------------------- service layer

@pytest.fixture
def service(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.database import Base
    from services import invoice_service as svc

    engine = create_engine(f"sqlite:///{tmp_path / 'inv.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(svc, "SessionLocal", sessionmaker(bind=engine))
    for name in ("PROCESSED_DIR", "JSON_DIR"):
        (tmp_path / name).mkdir()
        monkeypatch.setattr(settings, name, str(tmp_path / name))
    monkeypatch.setattr(svc, "log_action", lambda *a, **k: None)
    monkeypatch.setattr(svc, "has_transaction_evidence", lambda inv: True)
    src = tmp_path / "upload.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    return svc, str(src)


def _inv(n, total, pages=None, number=None):
    return Invoice(vendor_name="ACME", invoice_number=number or f"INV-{n}", total_amount=100.0,
                   source_pages=pages or [n], source_total_pages=total)


def test_service_labels_use_real_page_numbers_and_report_the_skipped_page(service, monkeypatch):
    svc, path = service
    monkeypatch.setattr(svc, "parse_invoice_pages_detailed", lambda *a, **k: (
        [_inv(1, 3), _inv(3, 3)],
        [{"pages": [2], "total_pages": 3, "reason": "LLM returned invalid JSON"}],
    ))
    results = svc.process_invoice_file(path, original_filename="batch.pdf")
    ok = [r for r in results if r["success"]]
    bad = [r for r in results if not r["success"]]
    assert [r["original_filename"] for r in ok] == ["batch.pdf (page 1/3)", "batch.pdf (page 3/3)"]
    assert len(bad) == 1
    assert bad[0]["file"] == "batch.pdf (page 2/3)"
    assert bad[0]["skipped_pages"] == [2]
    assert "invalid JSON" in bad[0]["error"]


def test_service_merged_invoice_keeps_plain_filename_and_warns(service, monkeypatch):
    svc, path = service
    monkeypatch.setattr(svc, "parse_invoice_pages_detailed",
                        lambda *a, **k: ([_inv(1, 3, pages=[1, 2, 3])], []))
    (result,) = svc.process_invoice_file(path, original_filename="one-invoice.pdf")
    assert result["success"] and result["original_filename"] == "one-invoice.pdf"
    assert any("combined into one invoice" in w for w in result["quality_warnings"])


def test_service_partial_merge_is_labelled_with_its_page_range(service, monkeypatch):
    svc, path = service
    monkeypatch.setattr(svc, "parse_invoice_pages_detailed", lambda *a, **k: (
        [_inv(1, 3, pages=[1, 2])], [{"pages": [3], "total_pages": 3, "reason": "blank"}]))
    results = svc.process_invoice_file(path, original_filename="f.pdf")
    assert results[0]["original_filename"] == "f.pdf (pages 1-2/3)"
    assert results[1]["file"] == "f.pdf (page 3/3)"


def test_service_one_failing_save_does_not_drop_the_remaining_pages(service, monkeypatch):
    svc, path = service
    monkeypatch.setattr(svc, "parse_invoice_pages_detailed",
                        lambda *a, **k: ([_inv(1, 3), _inv(2, 3), _inv(3, 3)], []))
    real_save = svc.InvoiceRepository.save

    def flaky_save(self, invoice):
        if invoice.invoice_number == "INV-2":
            raise RuntimeError("disk I/O error")
        return real_save(self, invoice)

    monkeypatch.setattr(svc.InvoiceRepository, "save", flaky_save)
    results = svc.process_invoice_file(path, original_filename="b.pdf")
    assert [r["success"] for r in results] == [True, False, True]
    assert "disk I/O error" in results[1]["error"]


def test_service_all_pages_failed_returns_one_row_per_page(service, monkeypatch):
    svc, path = service
    monkeypatch.setattr(svc, "parse_invoice_pages_detailed", lambda *a, **k: ([], [
        {"pages": [1], "total_pages": 2, "reason": "x"}, {"pages": [2], "total_pages": 2, "reason": "y"}]))
    results = svc.process_invoice_file(path, original_filename="b.pdf")
    assert [r["file"] for r in results] == ["b.pdf (page 1/2)", "b.pdf (page 2/2)"]
    assert not any(r["success"] for r in results)


def test_service_same_file_pages_get_distinct_fingerprints(service, monkeypatch):
    svc, path = service
    monkeypatch.setattr(svc, "parse_invoice_pages_detailed",
                        lambda *a, **k: ([_inv(1, 3), _inv(3, 3)], []))
    results = svc.process_invoice_file(path, original_filename="b.pdf")
    assert all(r["success"] for r in results)  # page 3 must not collide with page 1's fingerprint
    from database.models import InvoiceORM
    session = svc.SessionLocal()
    try:
        prints = sorted(row.source_fingerprint for row in session.query(InvoiceORM).all())
    finally:
        session.close()
    assert len(prints) == 2
    assert [p.split(":", 1)[1] for p in prints] == ["page:1", "page:3"]
