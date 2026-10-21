# Technical reference and QA notes

**Policy:** One invoice per file; scan one invoice at a time. An unrelated invoice on another PDF page must be uploaded separately. OCR/model outputs require human verification.

## Architecture

# Architecture

## Pipeline overview

```
Upload (Streamlit / API)
    │
    ▼
services/upload_service.py   — validates & saves file to data/uploads/
    │
    ▼
parser/invoice_parser.py     — orchestrates the pipeline below
    │
    ├─▶ ocr/ocr_engine.py     — PaddleOCR (primary) → Tesseract → EasyOCR fallback
    │        └─ ocr/preprocessing.py (deskew, denoise, threshold)
    │
    ├─▶ ai/extractor.py       — calls local Ollama model (Qwen2.5 / Llama3)
    │        ├─ ai/prompt_builder.py   (schema-constrained prompt)
    │        └─ ai/validator.py        (business-rule checks, triggers retry)
    │
    ├─▶ ai/post_processing.py — normalizes dates, currency, numbers
    ├─▶ ai/confidence.py      — combines OCR + validation into a confidence score
    │
    ▼
models/invoice.py            — Pydantic Invoice model (typed, validated)
    │
    ▼
database/repository.py       — persists to SQLite via SQLAlchemy
    │
    ▼
services/invoice_service.py  — archives JSON, moves file to processed/
```

## Layers

- **config/** — environment-driven settings, logging, constants/schema.
- **ocr/** — pluggable OCR backends behind a single `extract_from_file()` interface.
- **ai/** — LLM prompt construction, extraction call, validation, confidence scoring.
- **parser/** — normalization helpers (currency, dates, tax, table heuristics) and the
  top-level `parse_invoice()` orchestrator.
- **models/** — Pydantic schemas (API/business layer), separate from...
- **database/** — SQLAlchemy ORM models + repository pattern for persistence.
- **services/** — use-case layer that ties parser + database + exports together;
  this is what both the Streamlit UI and the FastAPI routes call into.
- **exports/** — format-specific writers (xlsx/csv/pdf).
- **api/** — thin FastAPI routers, useful for integrating with other systems.
- **ui/** — Streamlit multi-page app (Upload, Dashboard, History, Reports).

## Confidence & review workflow

Every processed invoice gets an `overall_confidence` score (0–1) combining:
1. Average OCR confidence across recognized text lines.
2. A penalty for each business-rule validation issue (missing fields, totals
   mismatch, invalid currency, etc).

If confidence falls below `CONFIDENCE_THRESHOLD` (default 0.75) or any
validation issue remains after retries, the invoice status is set to
`needs_review` instead of `processed`, and it's surfaced in the UI/dashboard
for manual correction.

## Why local LLM (Ollama)?

Invoices often contain sensitive financial data. Using a local model (Qwen 2.5
or Llama 3 via Ollama) keeps all document content on-premises — no data leaves
the machine running the pipeline.


## Vendor-specific invoice templates

The extraction pipeline supports vendor-specific templates in `ai/invoice_templates/`.
The current template is `watsons`, selected by `utils/invoice_template_detector.py` when
multiple Watsons-specific OCR signals are present. The selected template is injected into
`ai/prompt_builder.py` for both the initial Qwen2.5:7b extraction and validation-correction
prompts. A conservative deterministic post-processing step then applies high-confidence
Watsons rules such as vendor normalization, labeled financial fields, category assignment,
and the known `185TH POUCH BAG WITH SHOPPING BAG` line-item correction.

When vision verification is enabled, `ai/vision_verifier.py` also passes the Watsons-specific
visual rules to Qwen2.5-VL:7b and checks additional Watsons fields. Generic invoices continue
to use the existing generic prompt and verification fields.

## Plate number
The invoice model optionally stores `plate_number` for parking tickets and other vehicle-related documents. Extraction requires an explicit plate label (for example `Plate #`) to avoid confusing ticket or transaction IDs with the vehicle plate. The field is shown in History and included in all generated export formats.


---

## Api

# API Reference

Base URL: `http://localhost:8000`

Start with: `python app.py api`

## Health

`GET /health` → `{"status": "ok"}`

## Upload

`POST /api/upload/`
Multipart form-data with a `file` field (image or PDF).

Response:
```json
{
  "success": true,
  "invoice_id": 1,
  "invoice_number": "INV-2024-001",
  "vendor_name": "Acme Corp",
  "total_amount": 1234.56,
  "currency": "USD",
  "confidence_score": 0.91,
  "status": "processed",
  "processed_file": "data/processed/....png"
}
```

## Invoices

- `GET /api/invoices/?limit=100&status=processed` — list invoices
- `GET /api/invoices/{id}` — get one invoice with line items
- `GET /api/invoices/search?q=acme` — search by invoice #/vendor/customer
- `GET /api/invoices/stats` — dashboard aggregate stats
- `GET /api/invoices/export/{fmt}` — export all (or filtered) invoices;
  `fmt` is one of `xlsx`, `csv`, `pdf`

## Error format

Non-2xx responses return:
```json
{"detail": "human readable message"}
```


---

## Qa Invoice Rules

# QA Invoice Handling Rules

This document records the acceptance, validation, and duplicate rules added after the QA dataset review.

## 1. When an uploaded document is accepted

A document may be saved when there is meaningful transaction evidence even if one or more common invoice fields are absent.

- Missing invoice number: accept and flag for review.
- Missing invoice date: accept and flag for review.
- Missing total amount: accept and flag for review when other transaction evidence exists.
- Explicit zero total (for example, a zero-charge billing invoice): accept; zero is a real value, not a missing value.
- Blank/unused invoice or receipt form with no actual transaction evidence: reject and explain that no transaction was detected.

This distinction prevents the application from fabricating values while still allowing users to archive and review incomplete or supplementary commercial documents.

## 2. QA examples

- **INV-20**: a delivery receipt with handwritten items but blank invoice number/date. It is accepted as a real transaction document with review warnings.
- **INV-34**: the Smart billing invoice explicitly states `Total Current Bill Charges 0.00`; it is accepted as a zero-charge invoice rather than treated as an invoice with a missing amount.
- **INV-36**: a blank/unused printed receipt form. It is rejected because printed boilerplate/serial numbers alone are not sufficient transaction evidence.
- **INV-38 / INV-38-2**: the same invoice number can be accepted for different vendors.
- **INV-29 / INV-40**: the same logical Proof/Notarize invoice in different image formats is treated as a duplicate.

## 3. Duplicate policy

Invoice number is no longer globally unique. Duplicate checks use a composite identity.

1. An exact source/page fingerprint already stored is a duplicate.
2. Candidate comparison is scoped to the normalized vendor, so the same invoice number from different vendors is allowed.
3. For the same vendor and invoice number, matching line-item signatures plus matching date or total indicate the same logical invoice.
4. If the same vendor reuses an invoice number but the purchased items differ, both records are allowed.
5. If invoice numbers are missing, the system uses vendor + date + total + line items more conservatively.
6. A paid and an unpaid version of the same business invoice may coexist as lifecycle records.
7. File format or file-byte differences alone do not make a document unique.

## 4. Philippine document-compliance note

Under current Philippine invoicing rules, principal invoices are expected to carry required transaction details such as the transaction date and total amount. Delivery receipts and billing statements can be supplementary documents rather than the principal invoice. The application therefore distinguishes **successful ingestion** from **document completeness/compliance**: incomplete real documents can be stored with warnings and review status instead of being silently treated as fully compliant invoices.

References (checked October 2026):

- Republic Act No. 11976 (Ease of Paying Taxes Act): https://lawphil.net/statutes/repacts/ra2024/ra_11976_2024.html
- BIR Revenue Regulations No. 7-2024: https://bir-cdn.bir.gov.ph/BIR/pdf/RR%20No.%207-%202024.pdf

## 5. Multi-page PDF history preview

The original uploaded PDF is archived intact in `data/processed`; it is not reduced to its first page. History now exposes a page selector for PDF-backed records so users can inspect every stored page. If a multi-invoice PDF produced page-specific records, History initially selects the page associated with that record while still allowing access to the rest of the source PDF.

## 6. QA test case register

Manual QA results are tracked in [`qa_test_cases.csv`](qa_test_cases.csv) (Test Case ID, workflow stage, steps, expected/actual result, Pass/Fail, remarks). TC001 (PDF upload) and TC002 (PNG upload) are currently recorded as **Fail**: the invoice is accepted, but major fields were not extracted correctly. Re-run them against the rules above and update the Status/Actual Result columns.


---

## Release Notes Login Reset Parking

# Login, upload reset, and receipt corrections

Base: AI-Invoice-OCR_merged1.70_modByDan_fixes.zip.

## Changes

- Refresh/reconnect restores the authenticated account using a random browser token. Only its hash is stored in the new browser_login_sessions database table, created automatically on startup. Sign out revokes it and removes the cookie. Password resets and account deactivation invalidate existing tokens too.
- Explicit sign-in always opens Home. Refreshing a signed-in page keeps access to that page.
- Sign out clears temporary Upload results, pending files, and page selections. New sign-ins do not load the old shared last_upload_results.json. Saved invoice records and local invoice files are retained.
- Globe vendor address keeps the first complete printed location (Taguig) and omits the separate Cebu office. Focused extraction prompts request the first location.
- Blank customer Name/TIN labels with writing lines become null (displayed as a dash where applicable).
- Parking VAT parsing separates the printed percentage from the amount. The correction requires a printed amount corroborated by the VAT-inclusive total; it does not substitute a hardcoded receipt amount.

## Applying the update

Stop the running app before replacing application code. Keep a backup of your existing installation. Preserve your current .env, database, storage, and data folders; do not overwrite your live invoice database with a sample database from this ZIP. Start the app with its usual launcher. No additional Python dependency is required by this change. Browser cookies must be allowed for the local app. Use the same local URL consistently (localhost and 127.0.0.1 are separate cookie hosts).

These extraction changes apply when processing invoices. Existing saved invoices are not rewritten; edit their fields or reprocess them using your normal duplicate-handling workflow.

## Verification

- 60 targeted and existing regression tests passed (5 new tests plus 55 existing field/ownership/reliability tests).
- Streamlit AppTest checked sign-in, logout token revocation, Home routing, cleared Upload results, and restoring an account in a new Streamlit session. The cookie component was simulated in this test.
- The JavaScript cookie bridge passed separate write/read/clear acknowledgement checks with a simulated document.
- Replayed saved ParkingTickets1 OCR with the reported wrong fields: VAT corrected to 23.57, name and TIN cleared. ParkingTickets2 retained 25.71. The saved Globe PDF address was reduced to the first Taguig location.
- A real browser run could not be completed because this environment had no browser and the browser download failed. Full OCR/vision models were not run here. On your PC, verify sign-in as user/admin, refresh on Upload, sign out, sign in again, confirm Home, and confirm Upload has no previous result cards.

## October 21, 2026 — field evidence architecture

- `ai/field_evidence.py`: scores supported final extracted invoice fields and **each line-item cell** using stored OCR text, optional OCR line confidence, row-localized text/number matching, and targeted validation issues. Scores describe **evidence support, not calibrated accuracy**. Missing optional values have no numeric score. Derived Category has no document-source score. No new LLM calls are required.
- `ai/confidence.py`: retains the prior overall invoice score internally, attaches the per-field map to `Prediction`. `parser/invoice_parser.py` saves this map to `Invoice.field_evidence`.
- `database/models.py`, `database/database.py`, `database/repository.py`: nullable `invoices.field_evidence` JSON TEXT with automatic SQLite migration, stored independently from the existing overall `confidence_score`. Manual edits invalidate the changed values' scores; affected line-item cells are marked *manual_edit*.
- `ai/field_display.py` and `ui/components/field_evidence.py`: render scores and **inline warnings** beside invoice fields on History and near edit controls. Per-cell columns appear beside extracted line-item values; Upload displays a compact verification list. Older invoices fall back to clearly labeled, OCR-text-only estimates when raw OCR text exists; no score is invented otherwise.
- Interpretation: OCR recognition does **not** prove correct field ownership. An OCR-match score can be high for a wrongly associated customer, vendor, date or monetary field. Humans must review warnings and spot-check important fields. Line items absent from the extraction have no cell to score; completeness is not guaranteed. Cloud model/image reprocessing was **not** performed to validate these scores in production.
