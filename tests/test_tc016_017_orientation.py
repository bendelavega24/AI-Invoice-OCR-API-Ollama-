"""
TC016 / TC017 — rotated (90 deg / 180 deg) invoices must be corrected automatically.

Root causes covered:

1. The orientation probe recognised sample crops with PaddleOCR's 180-degree angle classifier ON. With it on,
   an upside-down crop is flipped upright BEFORE recognition, so a page rotated 180 degrees read as well as an
   upright one: 0 and 180 degrees scored the same and the page was never turned (TC017). For a 90/270-degree
   page the right turn and the right turn + 180 also tied, so the page could be "corrected" to upside down (TC016).
2. After a page WAS rotated, the vision cross-checks still received the original, un-rotated file while the OCR
   boxes they crop with belong to the rotated image.

PaddleOCR itself isn't installed here, so a stand-in engine reproduces the semantics verified in PaddleOCR 2.8.1
(paddleocr.py::ocr): det=False/rec=True/cls=True runs the classifier first, which flips 180-degree crops upright;
cls=False reads the crop as-is; tall (sideways) crops are unreadable.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
import pytest

from config.settings import settings
from ocr import ocr_engine, paddleocr_engine
from ocr.preprocessing import rotate_90

BAR_W, BAR_H, N_BARS = 300, 22, 10


def _upright_page():
    """White page with 10 horizontal 'text lines'. Each line is dark on its LEFT half and mid-gray on its right
    half, so the line has a recognisable up/down + left/right orientation (like real text does)."""
    page = np.full((420, 360, 3), 255, dtype="uint8")
    for i in range(N_BARS):
        y = 20 + i * 38
        page[y:y + BAR_H, 30:30 + BAR_W // 2] = 0
        page[y:y + BAR_H, 30 + BAR_W // 2:30 + BAR_W] = 110
    return page


def _fake_detect_boxes(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    mask = (img < 200).astype("uint8")
    # merge the two halves of a bar into one region
    mask = cv2.dilate(mask, np.ones((3, 3), "uint8"), iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        boxes.append([[x, y], [x + w, y], [x + w, y + h], [x, y + h]])
    return boxes


def _make_fake_recognizer(record=None):
    def fake_recognize_crop(crop, cls=True):
        if record is not None:
            record.append(cls)
        h, w = crop.shape[:2]
        if h > w:                                   # sideways text: unreadable
            return {"text": "", "confidence": 0.05}
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        left_dark = gray[:, : w // 2].mean() < gray[:, w // 2:].mean()
        if not left_dark:                           # upside-down (180 deg) text
            if cls:                                 # the angle classifier flips it upright first
                return {"text": "INVOICE NUMBER 1234", "confidence": 0.95}
            return {"text": "~l", "confidence": 0.1}
        return {"text": "INVOICE NUMBER 1234", "confidence": 0.95}
    return fake_recognize_crop


@pytest.fixture
def fake_paddle(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "OCR_AUTO_ORIENT_ENABLED", True)
    monkeypatch.setattr(paddleocr_engine, "detect_boxes", _fake_detect_boxes)
    monkeypatch.setattr(paddleocr_engine, "recognize_crop", _make_fake_recognizer())


def _save(tmp_path, img, name):
    path = str(tmp_path / name)
    cv2.imwrite(path, img)
    return path


# ------------------------------------------------------------------------ the actual TC016 / TC017 scenarios

@pytest.mark.parametrize("scan_rotation_cw", [90, 180, 270])
def test_rotated_invoice_is_turned_back_upright(tmp_path, fake_paddle, scan_rotation_cw):
    upright = _upright_page()
    scanned = rotate_90(upright, scan_rotation_cw // 90)   # how the invoice came out of the scanner
    path = _save(tmp_path, scanned, f"scan_{scan_rotation_cw}.png")

    out_path, turns = ocr_engine.correct_page_orientation(path, return_turns=True)

    assert out_path != path and turns != 0
    assert np.array_equal(cv2.imread(out_path), upright), \
        f"{scan_rotation_cw} deg page was not restored to upright (applied {turns * 90} deg)"


def test_upright_invoice_is_left_alone(tmp_path, fake_paddle):
    path = _save(tmp_path, _upright_page(), "upright.png")
    out_path, turns = ocr_engine.correct_page_orientation(path, return_turns=True)
    assert (out_path, turns) == (path, 0)


def test_orientation_probe_never_uses_the_angle_classifier(tmp_path, monkeypatch):
    """Regression guard for the root cause: probing with cls=True makes 0 and 180 degrees indistinguishable."""
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(paddleocr_engine, "detect_boxes", _fake_detect_boxes)
    seen = []
    monkeypatch.setattr(paddleocr_engine, "recognize_crop", _make_fake_recognizer(seen))
    ocr_engine._detect_page_orientation(_save(tmp_path, _upright_page(), "p.png"))
    assert seen and set(seen) == {False}


def test_the_stand_in_reproduces_the_old_bug_when_the_classifier_is_on(tmp_path, monkeypatch):
    """Sanity check on the test double itself: forcing cls=True (the old behaviour) leaves a 180-degree page as is."""
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "OCR_AUTO_ORIENT_ENABLED", True)
    monkeypatch.setattr(paddleocr_engine, "detect_boxes", _fake_detect_boxes)
    fake = _make_fake_recognizer()
    monkeypatch.setattr(paddleocr_engine, "recognize_crop", lambda crop, cls=False: fake(crop, cls=True))
    path = _save(tmp_path, rotate_90(_upright_page(), 2), "flipped.png")
    assert ocr_engine._detect_page_orientation(path) == 0   # old behaviour: never corrected


def test_real_recognition_still_uses_the_angle_classifier(monkeypatch):
    """Only the probe turns cls off; normal text reading must keep correcting individually flipped lines."""
    calls = []

    class FakeOCR:
        def ocr(self, img, **kw):
            calls.append(kw)
            return [[("TEXT", 0.9)]]

    monkeypatch.setattr(paddleocr_engine, "_get_paddle_instance", lambda: FakeOCR())
    paddleocr_engine.recognize_crop(np.zeros((10, 40, 3), "uint8"))
    paddleocr_engine.recognize_crop(np.zeros((10, 40, 3), "uint8"), cls=False)
    assert [c["cls"] for c in calls] == [True, False]


# ------------------------------------------------------------------------ vision checks must see the upright image

def test_vision_checks_receive_the_rotated_image_not_the_original(tmp_path, monkeypatch):
    from copy import deepcopy
    from parser import invoice_parser as parser

    original = tmp_path / "scan.png"
    upright = tmp_path / "oriented_scan.png"
    original.write_bytes(b"sideways")
    upright.write_bytes(b"upright")

    data = dict(invoice_number="INV-1", invoice_date="2026-08-06", vendor_name="Example", subtotal=100.,
                tax_amount=12., total_amount=112., currency="PHP",
                line_items=[dict(description="Monthly software subscription", quantity=1, unit_price=100., amount=100.)])
    monkeypatch.setattr(parser, "extract_invoice_data", lambda *a, **k: deepcopy(data))
    monkeypatch.setattr(parser, "save_diagnostic_trace", lambda **kw: None)

    seen = {}

    def spy(name, result):
        def fn(path, *a, **k):
            seen[name] = path
            return result
        return fn

    monkeypatch.setattr(parser, "recover_vendor_header_fields", spy("header", ({}, [], set())))
    monkeypatch.setattr(parser, "verify_against_image", spy("full_page", ({}, [])))
    for name in ["verify_handwritten_invoice_date", "verify_statement_summary_crop", "verify_customer_address_crop",
                 "verify_vendor_address_crop", "verify_plate_number_crop"]:
        monkeypatch.setattr(parser, name, spy(name, (None, [])))

    text = "Example\nInvoice INV-1\nVATable Sales 100.00\nVAT 12.00\nTotal 112.00"
    ocr_result = {"oriented_image_path": str(upright), "orientation_quarter_turns": 3}
    parser._build_invoice_from_ocr(str(original), str(original), text, .99, "paddleocr", ocr_result=ocr_result)

    assert seen, "vision steps did not run"
    assert all(path == str(upright) for path in seen.values()), seen


def test_vision_falls_back_to_the_original_when_there_is_no_rotated_copy(tmp_path, monkeypatch):
    from copy import deepcopy
    from parser import invoice_parser as parser

    original = tmp_path / "scan.png"
    original.write_bytes(b"x")
    data = dict(invoice_number="INV-1", invoice_date="2026-08-06", vendor_name="Example", subtotal=100.,
                tax_amount=12., total_amount=112., currency="PHP",
                line_items=[dict(description="Monthly software subscription", quantity=1, unit_price=100., amount=100.)])
    monkeypatch.setattr(parser, "extract_invoice_data", lambda *a, **k: deepcopy(data))
    monkeypatch.setattr(parser, "save_diagnostic_trace", lambda **kw: None)
    seen = []
    monkeypatch.setattr(parser, "recover_vendor_header_fields", lambda *a, **k: ({}, [], set()))
    monkeypatch.setattr(parser, "verify_against_image", lambda path, *a, **k: (seen.append(path) or ({}, [])))
    for name in ["verify_handwritten_invoice_date", "verify_statement_summary_crop", "verify_customer_address_crop",
                 "verify_vendor_address_crop", "verify_plate_number_crop"]:
        monkeypatch.setattr(parser, name, lambda *a, **k: (None, []))

    text = "Example\nInvoice INV-1\nVATable Sales 100.00\nVAT 12.00\nTotal 112.00"
    # no ocr_result at all, and one pointing at a file that no longer exists
    parser._build_invoice_from_ocr(str(original), str(original), text, .99, "paddleocr")
    parser._build_invoice_from_ocr(str(original), str(original), text, .99, "paddleocr",
                                   ocr_result={"oriented_image_path": str(tmp_path / "gone.png")})
    assert seen == [str(original), str(original)]
