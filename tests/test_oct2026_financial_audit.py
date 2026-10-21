"""Regression checks from the October 2026 QA database audit."""
from ai.validator import validate_extraction

def invoice(**changes):
    record = {"invoice_number":"X1", "vendor_name":"Example", "invoice_date":"2025-01-01", "currency":"PHP", "subtotal":100.0, "tax_amount":12.0, "discount":0.0, "withholding_tax":0.0, "zero_rated_sales":0.0, "vat_exempt_sales":0.0, "total_amount":112.0}
    record.update(changes)
    return record

def test_small_receipt_vat_mismatch_is_not_ignored():
    issues = validate_extraction(invoice(subtotal=26.79, tax_amount=3.21, total_amount=26.79))
    assert any("does not match total_amount" in issue for issue in issues)

def test_one_peso_discrepancy_is_flagged():
    issues = validate_extraction(invoice(subtotal=3934.97, tax_amount=449.97, total_amount=4383.94))
    assert any("does not match total_amount" in issue for issue in issues)

def test_small_rounding_difference_is_allowed():
    issues = validate_extraction(invoice(total_amount=112.02))
    assert not any("does not match total_amount" in issue for issue in issues)

def test_statement_checks_current_charges_separately():
    data = invoice(subtotal=4257.0, tax_amount=None, discount=59.0, current_charges_total=4198.0, previous_balance=1749.51, total_amount=5947.51)
    issues = validate_extraction(data)
    assert not any("does not match" in issue for issue in issues)

def test_statement_carried_balance_small_mismatch_is_flagged():
    data = invoice(subtotal=100.0, tax_amount=0.0, current_charges_total=100.0, previous_balance=10.0, total_amount=110.5)
    issues = validate_extraction(data)
    assert any("does not match total_amount/Amount to Pay" in issue for issue in issues)

def test_withholding_tax_is_subtracted():
    issues = validate_extraction(invoice(subtotal=85963.99, tax_amount=10315.68, withholding_tax=1719.28, total_amount=94560.39))
    assert not any("does not match" in issue for issue in issues)
