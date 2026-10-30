# Consolidated AI Invoice OCR v6 — 26 October 2026

## Base and donor

- **Base:** `AI-Invoice-OCR-API-Ollama-Dan-QA-Fixed-v6_EvidenceCorrections_2026-10-26.zip`.
- **Selective donor:** `AI-Invoice-OCR-API-Ollama-Dan_QA_ConditionalVision_2026-10-23.zip`.
- Neither source archive was modified.

## Integrated behavior

1. **Source evidence and invoice QA:** All October 26 document, ownership, billing, geometry, targeted-review, and line-item fixes remain in place. These have priority over older general-purpose recovery heuristics.
2. **Selective vision verification:** `ai/vision_decision.py` checks OCR quality, missing critical fields, handwriting, evidence support and financial/line-item arithmetic before invoking expensive **whole-image** verification. Existing independently triggered focused/cropped checks remain intact.
3. **Local Ollama model preflight:** Before processing a batch (including direct-service uploads), use `/api/tags` to check for the configured `VISION_MODEL` (normally `qwen2.5vl:7b`). Check is cached for the batch, including nested per-file request scopes. A missing model does not prevent OCR or text-model extraction. Skipped visual checks can generate review warnings. Cloud/API-only mode does not require the local check.
4. **Persistent evidence support:** Adds nullable `invoices.field_evidence` TEXT (JSON) with a lightweight SQLite migration. Existing `field_confidences` and `confidence_score` remain for compatibility, without exposing the overall confidence score. New invoices retain evidence for document fields and line-item cells; manual changes invalidate old automatic evidence on changed values.
5. **Approved History details:** File name as heading; Invoice # appears once. Client-approved fields, including Plate #, remain. Only questionable fields/line-item cells are highlighted in amber, with reasons on demand. Integer quantities display without decimal tails; fractional quantities remain precise.
6. **Hidden metadata:** Due Date, Tax Rate, Payment Terms, Customer Contact, Current Charges Total and Previous Balance remain internal and are excluded from invoice details/standard exports. Actual current-charge and previous-balance *line items* remain visible when present. Financial fields missing from OCR display `0.00` **only in History** while remaining NULL in SQLite.
7. **Exports and dashboard:** CSV/Excel/PDF share the client-approved export schema. Spend by Month defaults to invoice date, with an upload-date option, and uses bars for single-month datasets.
8. **Upload policy:** Rejects documents where multiple separate invoices are detected before saving any invoice. Several pages of the same invoice remain allowed when grouped successfully.
9. **Unreconciled negative totals:** Emit an explicit calculation-review warning rather than silently replacing the document value.

### Older donor recovery modules

`ai/structured_table_recovery.py` runs only for explicit printed Description/Qty/Unit Price/Amount tables, and its results remain subject to October 26's later source-evidence checks. `ai/statement_qa_recovery.py` is included as a reference but **not invoked**: the base already has newer overlapping statement logic (`ai/statement_evidence.py`, `ai/qa_source_review.py`). Running both would risk conflicting updates or double-counting.

### Verification status

- Run `python -m pytest -q` for the consolidated regression suite.
- A handful of older tests may need the Streamlit runtime or updated mocks; detailed test results are reported separately.
- No live Ollama/Groq inference or end-to-end browser session was executed in this environment.
- Previously saved invoice rows are not automatically reprocessed or corrected. Archived invoices without evidence JSON display OCR-text-only estimates when source text is available.

### Installation and privacy

Back up `.env`, `data/` and `storage/` before updating. The distributable archive excludes live databases, runtime logs, generated images, user uploads, JSON results and API credentials. Retain your existing `.env` and SQLite file; the new nullable evidence column is created on startup. **Do not** replace the database with an empty copy. Review invoices individually before locking and exporting.

**Client display safeguard:** Removed the legacy `quality_details` confidence-percentage expander, including its overall invoice score, from the visible UI. Validation warnings remain available; the History panel highlights only cells/fields requiring verification. Negative credit/adjustment prices remain editable as signed numbers.
