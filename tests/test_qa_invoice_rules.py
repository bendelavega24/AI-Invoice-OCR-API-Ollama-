from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ai.post_processing import infer_payment_status, has_transaction_evidence
from ai.validator import validate_extraction
from database.database import Base
from database.repository import InvoiceRepository, DuplicateInvoiceError
from models.invoice import Invoice, LineItem


def _repo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    return session, InvoiceRepository(session)


def _invoice(vendor="VENDOR A", number="1234567890", *, item="Widget", total=100.0,
             invoice_date="2026-05-13", payment_status="unknown", fingerprint=None):
    return Invoice(
        invoice_number=number,
        invoice_date=invoice_date,
        vendor_name=vendor,
        line_items=[LineItem(description=item, quantity=1, unit_price=total or 0, amount=total or 0)],
        subtotal=total or 0,
        tax_amount=0.0,
        total_amount=total,
        currency="PHP",
        payment_status=payment_status,
        source_fingerprint=fingerprint,
    )


def test_same_invoice_number_different_vendors_is_allowed_qa_inv38():
    session, repo = _repo()
    try:
        a = repo.save(_invoice(vendor="ACE HARDWARE PHILIPPINES INC", number="1234567890", total=5474.56))
        b = repo.save(_invoice(vendor="SHOPEE PHILIPPINES INC", number="1234567890", total=5474.56))
        assert a.id != b.id
        assert session.query(type(a)).filter_by(invoice_number="1234567890").count() == 2
    finally:
        session.close()


def test_same_vendor_and_number_but_different_items_is_allowed():
    session, repo = _repo()
    try:
        repo.save(_invoice(item="RIBTYPE 6.30 MTRS", total=12012.0))
        second = repo.save(_invoice(item="FACIA MOULDING", total=12012.0))
        assert second.id is not None
    finally:
        session.close()


def test_same_logical_invoice_is_rejected_even_if_file_fingerprint_differs():
    session, repo = _repo()
    try:
        repo.save(_invoice(vendor="NOTARIZE INC DBA PROOF", number="NOTARIZE185857",
                           item="PROOF PLATFORM", total=400.0, fingerprint="jpg-hash"))
        with pytest.raises(DuplicateInvoiceError):
            repo.save(_invoice(vendor="NOTARIZE INC DBA PROOF", number="NOTARIZE185857",
                               item="PROOF PLATFORM", total=400.0, fingerprint="png-hash"))
    finally:
        session.close()


def test_paid_and_unpaid_versions_of_same_invoice_are_both_retained():
    session, repo = _repo()
    try:
        unpaid = repo.save(_invoice(payment_status="unpaid"))
        paid = repo.save(_invoice(payment_status="paid"))
        assert unpaid.id != paid.id
    finally:
        session.close()


def test_missing_invoice_number_can_be_saved_and_strong_duplicate_still_detected():
    session, repo = _repo()
    try:
        first = _invoice(number=None, vendor="CHEN HARDWARE", item="RIBTYPE", total=12012.0)
        saved = repo.save(first)
        assert saved.invoice_number is None
        with pytest.raises(DuplicateInvoiceError):
            repo.save(_invoice(number=None, vendor="CHEN HARDWARE", item="RIBTYPE", total=12012.0))
    finally:
        session.close()


def test_zero_charge_invoice_is_valid_not_negative_error():
    data = {
        "invoice_number": "150000H8S7", "invoice_date": "2025-08-31",
        "vendor_name": "SMART COMMUNICATIONS", "total_amount": 0.0,
        "currency": "PHP", "line_items": [],
    }
    issues = validate_extraction(data, ocr_text="Total Current Bill Charges 0.00")
    assert "total_amount must be greater than 0" not in issues
    assert "total_amount cannot be negative" not in issues


def test_explicit_zero_charge_document_has_transaction_evidence_qa_inv34():
    inv = _invoice(vendor="SMART COMMUNICATIONS", number="150000H8S7", total=0.0,
                   item="", invoice_date="2025-08-31")
    inv.line_items = []
    inv.raw_text = "SMART COMMUNICATIONS Billing Invoice Total Current Bill Charges 0.00"
    assert has_transaction_evidence(inv) is True


def test_blank_unused_form_is_not_a_transaction_qa_inv36():
    inv = Invoice(
        invoice_number="22001172351", invoice_date=None, vendor_name="UNKNOWN VENDOR",
        line_items=[], subtotal=0.0, total_amount=None, currency="PHP",
        raw_text="BIR PRINTED RECEIPT No 22001172351 RECEIVED FROM ADDRESS TIN TOTAL DUE",
    )
    assert has_transaction_evidence(inv) is False


def test_payment_inference_does_not_treat_previous_payment_thanks_as_paid_qa_inv37():
    data, _ = infer_payment_status(
        {"payment_status": "unknown"},
        "Thank you for your payment. Previous Balance 0.00 Current Balance 791.81 Total Amount Due 791.81",
    )
    assert data["payment_status"] == "unpaid"


def test_payment_inference_proof_invoice_amount_applied_zero_is_unpaid():
    data, _ = infer_payment_status(
        {"payment_status": "unknown"},
        "Amount Applied USD 0.00 Total Amount Due USD 400.00 Due 03/25/2026",
    )
    assert data["payment_status"] == "unpaid"


def test_exact_same_source_fingerprint_is_always_duplicate():
    session, repo = _repo()
    try:
        repo.save(_invoice(number="A-1", item="One", fingerprint="same:page:1"))
        with pytest.raises(DuplicateInvoiceError, match="source/page fingerprint"):
            repo.save(_invoice(number="A-2", item="Different", total=999.0, fingerprint="same:page:1"))
    finally:
        session.close()

def test_legacy_sqlite_invoice_number_unique_not_null_migrates(tmp_path, monkeypatch):
    import sqlite3
    import database.database as db

    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE vendors (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, normalized_name VARCHAR, address VARCHAR, tax_id VARCHAR);
        CREATE TABLE invoices (
            id INTEGER PRIMARY KEY,
            invoice_number VARCHAR NOT NULL UNIQUE,
            invoice_date DATE, date_uploaded DATE, due_date DATE,
            vendor_id INTEGER, vendor_name VARCHAR NOT NULL,
            vendor_address VARCHAR, vendor_tax_id VARCHAR,
            customer_name VARCHAR, customer_contact VARCHAR, customer_address VARCHAR, customer_tax_id VARCHAR,
            plate_number VARCHAR, subtotal FLOAT, tax_amount FLOAT, tax_rate FLOAT, discount FLOAT,
            withholding_tax FLOAT, zero_rated_sales FLOAT, vat_exempt_sales FLOAT, total_amount FLOAT,
            current_charges_total FLOAT, previous_balance FLOAT, currency VARCHAR,
            payment_terms VARCHAR, category VARCHAR, source_file VARCHAR, enhanced_image_path VARCHAR, original_filename VARCHAR,
            ocr_engine_used VARCHAR, confidence_score FLOAT, status VARCHAR, raw_text TEXT, vision_notes TEXT,
            locked BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME
        );
        CREATE TABLE line_items (id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id), description VARCHAR NOT NULL, quantity FLOAT, unit_price FLOAT, amount FLOAT);
        INSERT INTO vendors(id,name,normalized_name) VALUES(1,'VENDOR A','vendor a');
        INSERT INTO invoices(id,invoice_number,vendor_id,vendor_name,total_amount,currency,status,locked) VALUES(1,'LEG-1',1,'VENDOR A',100,'PHP','processed',0);
        INSERT INTO line_items(id,invoice_id,description,quantity,unit_price,amount) VALUES(1,1,'Widget',1,100,100);
    """)
    con.commit(); con.close()

    test_engine = create_engine(f"sqlite:///{path}")
    monkeypatch.setattr(db, "engine", test_engine)
    monkeypatch.setattr(db.settings, "DATABASE_URL", f"sqlite:///{path}")
    db._relax_invoice_number_constraint_if_needed()

    con = sqlite3.connect(path)
    try:
        info = {r[1]: r for r in con.execute("PRAGMA table_info(invoices)")}
        assert info["invoice_number"][3] == 0  # nullable now
        assert not any(bool(r[2]) for r in con.execute("PRAGMA index_list(invoices)"))
        assert con.execute("SELECT invoice_number FROM invoices WHERE id=1").fetchone()[0] == "LEG-1"
        assert con.execute("SELECT description FROM line_items WHERE invoice_id=1").fetchone()[0] == "Widget"
    finally:
        con.close()

def test_malformed_and_future_invoice_dates_force_review_without_being_fatal():
    from ai.post_processing import sanitize_for_model
    bad = {
        "invoice_number": "X", "invoice_date": "2021-11-31", "vendor_name": "Vendor",
        "total_amount": 100.0, "subtotal": 100.0, "currency": "PHP", "line_items": [],
    }
    issues = validate_extraction(bad)
    assert any("not a valid calendar date" in x for x in issues)
    assert sanitize_for_model(bad)["invoice_date"] is None

    future = dict(bad, invoice_date="2999-01-01")
    issues = validate_extraction(future)
    assert any("is in the future" in x for x in issues)


def test_negative_line_price_and_tax_above_total_are_flagged():
    data = {
        "invoice_number": "X", "invoice_date": "2026-01-01", "vendor_name": "Vendor",
        "total_amount": 50.0, "subtotal": 40.0, "tax_amount": 60.0, "currency": "PHP",
        "line_items": [{"description": "Bad row", "quantity": 1, "unit_price": -10, "amount": -10}],
    }
    issues = validate_extraction(data)
    assert any("cannot exceed total_amount" in x for x in issues)
    assert any("negative unit_price" in x for x in issues)
    assert any("negative amount" in x for x in issues)


def test_blank_unused_form_rejected_even_if_ocr_hallucinates_identity_qa_inv36():
    inv = Invoice(
        invoice_number="2704",
        invoice_date="2018-07-27",  # printer/footer date, not a transaction date
        vendor_name="FILIPINAS PRINTING PRESS",
        customer_name="BUREAU OF INTERNAL REVENUE",
        line_items=[],
        subtotal=0.0,
        total_amount=None,
        currency="PHP",
        raw_text=(
            "BIR PRINTED RECEIPT NON-VAT OFFICIAL RECEIPT No 22001172351 "
            "RECEIVED FROM DATE TIN OF BUYER ADDRESS OF BUYER BUSINESS NAME STYLE "
            "IN PAYMENT FOR THE FOLLOWING SERVICES TRANSACTIONS QTY UNIT UNIT PRICE AMOUNT "
            "TOTAL RECEIPTS TOTAL DUE TOTAL AMOUNT DUE Date Issued 07-27-2018"
        ),
    )
    assert has_transaction_evidence(inv) is False


def test_positive_current_amount_due_beats_prior_payment_wording_qa_inv04():
    data, _ = infer_payment_status(
        {"payment_status": "paid"},
        (
            "Less: Payments Received - Thank You! (1,200.00) "
            "Previous Charges must be fully paid immediately. "
            "Total Current Charges 1,299.00 TOTAL AMOUNT DUE 1,289.00"
        ),
    )
    assert data["payment_status"] == "unpaid"
