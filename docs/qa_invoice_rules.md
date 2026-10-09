# QA Invoice Handling Rules

This document records the acceptance, payment-status, validation, and duplicate rules added after the QA dataset review.

## 1. Processing status vs. payment status

These are independent fields.

- **Processing status** describes OCR/extraction quality and workflow state (for example, processed or needs review).
- **Payment status** describes the commercial state: `paid`, `unpaid`, or `unknown`.

`unknown` is intentional. The system must not invent a paid/unpaid state when the document does not provide enough evidence.

## 2. When an uploaded document is accepted

A document may be saved when there is meaningful transaction evidence even if one or more common invoice fields are absent.

- Missing invoice number: accept and flag for review.
- Missing invoice date: accept and flag for review.
- Missing total amount: accept and flag for review when other transaction evidence exists.
- Explicit zero total (for example, a zero-charge billing invoice): accept; zero is a real value, not a missing value.
- Blank/unused invoice or receipt form with no actual transaction evidence: reject and explain that no transaction was detected.

This distinction prevents the application from fabricating values while still allowing users to archive and review incomplete or supplementary commercial documents.

## 3. QA examples

- **INV-20**: a delivery receipt with handwritten items but blank invoice number/date. It is accepted as a real transaction document with review warnings.
- **INV-34**: the Smart billing invoice explicitly states `Total Current Bill Charges 0.00`; it is accepted as a zero-charge invoice rather than treated as an invoice with a missing amount.
- **INV-36**: a blank/unused printed receipt form. It is rejected because printed boilerplate/serial numbers alone are not sufficient transaction evidence.
- **INV-38 / INV-38-2**: the same invoice number can be accepted for different vendors.
- **INV-29 / INV-40**: the same logical Proof/Notarize invoice in different image formats is treated as a duplicate.

## 4. Duplicate policy

Invoice number is no longer globally unique. Duplicate checks use a composite identity.

1. An exact source/page fingerprint already stored is a duplicate.
2. Candidate comparison is scoped to the normalized vendor, so the same invoice number from different vendors is allowed.
3. For the same vendor and invoice number, matching line-item signatures plus matching date or total indicate the same logical invoice.
4. If the same vendor reuses an invoice number but the purchased items differ, both records are allowed.
5. If invoice numbers are missing, the system uses vendor + date + total + line items more conservatively.
6. A paid and an unpaid version of the same business invoice may coexist as lifecycle records.
7. File format or file-byte differences alone do not make a document unique.

## 5. Payment-status inference

The system is conservative.

- Explicit outstanding/due balances or a positive **current** amount due -> `unpaid`; this takes precedence over prior-period wording such as “Payments Received” or instructions saying charges “must be fully paid”.
- Explicit paid-in-full evidence, or a zero amount due with evidence of payment applied -> `paid`.
- Ambiguous documents -> `unknown`.
- A generic phrase such as “Thank you for your payment” does not by itself mark a current bill paid, because it can refer to the previous billing period.

Users can correct the payment status in History.

## 6. Philippine document-compliance note

Under current Philippine invoicing rules, principal invoices are expected to carry required transaction details such as the transaction date and total amount. Delivery receipts and billing statements can be supplementary documents rather than the principal invoice. The application therefore distinguishes **successful ingestion** from **document completeness/compliance**: incomplete real documents can be stored with warnings and review status instead of being silently treated as fully compliant invoices.

References (checked October 2026):

- Republic Act No. 11976 (Ease of Paying Taxes Act): https://lawphil.net/statutes/repacts/ra2024/ra_11976_2024.html
- BIR Revenue Regulations No. 7-2024: https://bir-cdn.bir.gov.ph/BIR/pdf/RR%20No.%207-%202024.pdf

## 7. Multi-page PDF history preview

The original uploaded PDF is archived intact in `data/processed`; it is not reduced to its first page. History now exposes a page selector for PDF-backed records so users can inspect every stored page. If a multi-invoice PDF produced page-specific records, History initially selects the page associated with that record while still allowing access to the rest of the source PDF.

## 7. QA test case register

Manual QA results are tracked in [`qa_test_cases.csv`](qa_test_cases.csv) (Test Case ID, workflow stage, steps, expected/actual result, Pass/Fail, remarks). TC001 (PDF upload) and TC002 (PNG upload) are currently recorded as **Fail**: the invoice is accepted, but major fields were not extracted correctly. Re-run them against the rules above and update the Status/Actual Result columns.
