"""Detect stable vendor-specific invoice layouts from OCR text."""
from __future__ import annotations


def detect_invoice_template(ocr_text: str) -> str:
    """Return a vendor template name, or ``generic`` when none is confident.

    Watsons is intentionally detected using more than one signal so that a
    product description containing the word "watsons" cannot accidentally
    select the template.
    """
    text = (ocr_text or "").upper()
    watsons_signals = 0
    if "WATSONS" in text:
        watsons_signals += 2
    if "WATSONS PERSONAL CARE STORES" in text:
        watsons_signals += 2
    if "SALES INVOICE NO" in text or "SALES INVOICE NO." in text:
        watsons_signals += 1
    if "VAT REG TIN" in text:
        watsons_signals += 1
    if "TOTAL DISCOUNTS" in text:
        watsons_signals += 1
    if "AMOUNT TO PAY" in text:
        watsons_signals += 1

    if watsons_signals >= 3:
        return "watsons"

    # Meralco "ELECTRIC BILL": several independent layout markers are required,
    # so an address such as "Meralco Ave" on another vendor's invoice can never
    # select this template.
    if "MERALCO" in text:
        meralco_signals = sum(
            marker in text
            for marker in ("ELECTRIC BILL", "EB INVOICE", "BREAKDOWN OF ELECTRICITY CHARGES", "ENERGY BILL AMOUNT")
        )
        if meralco_signals >= 3:
            return "meralco"

    return "generic"
