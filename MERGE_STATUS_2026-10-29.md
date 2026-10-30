# Teammate Source Merge Review — October 29, 2026

## Provenance and priority

- **Base:** `AI-Invoice-OCR-API-Ollama-Dan_QA_CurrencyReview_Groq_2026-10-28.zip`
- **Teammate candidate:** `AI-Invoice-OCR-main_DanNew.zip`
- **User-provided Home fix:** `ui/streamlit_app.py` — copied **exactly** as uploaded (SHA-256: `abad42ad96e66e9877e544d35a7202795445e0d26dc949563864b58cfc6cf100`).
- This is a **selective integration**, not a direct replacement by the teammate branch. The October 28 capabilities take precedence in conflicts.

## Merged changes and reasons

1. **Column-based party ownership** (`ai/party_columns.py`): FROM/SHIP TO layout assigns addresses by OCR boxes rather than interleaved reading order; guarded by two same-row labels. Also fixes a zero-padded invoice number whose first zero was read as a capital `O`, and flags it for human confirmation.
2. **MERALCO layout recovery** (`ai/invoice_templates/meralco.py`): added source-bound handling for *Your electric bill* and *Billing Invoice* layouts, using explicit column labels, dates, TIN, and charge rows. Bad/impossible dates remain missing for review. The new specialist is called only when the relevant page layout is actually detected. Generic MERALCO forcing was intentionally not applied.
3. **Printed retail/utility line-item geometry** (`ai/post_processing.py`): the teammate's improved geometry filter ignores consumption-chart axis ticks, percentages, row quantities, dates, and neighboring line-item prices. Existing subtotal/total logic is not replaced.
4. **SCommerce invoice labels** (`parser/ecommerce_invoice.py`): repairs a constrained `ISS1`/`ISSI` OCR confusion, and clears an invented issue date when the printed Date Issued box is blank.
5. **Seller TIN verification** (`ai/vision_verifier.py`): excludes Customer TIN from vendor-header extraction and handles a clipped `TN` label; preserves the evidence gate.
6. **Party master safety** (`ai/party_master.py`, `config/party_master.json`): adds four new teammate vendor reference entries, preserving all existing October 28 records. Corrects vendor TIN only when a near match is corroborated by vendor-address tokens, avoids overwriting the location of a distinct MERALCO business center, prevents vendor and customer using the same TIN when seller evidence is available, and restores spaces after middle initials.

## Specifically retained from October 28

- Groq default `https://api.groq.com/openai/v1`, `qwen/qwen3.8-27b`, PHP default.
- PHP and USD separated on Dashboard, Reports, and CSV/Excel/PDF export (no currency mixing).
- Conditional local vision and model-availability checks, one-invoice-per-file upload rule, safe multi-page handling, error/report distinctions.
- Field evidence and amber verification highlights; approved History fields and hidden optional fields; Qty compact display.
- October 26/28 source-evidence corrections, validations, migrations, and existing PDF page viewer.

## Intentionally not copied wholesale

The teammate branch's replacement `parser/invoice_parser.py`, `services/invoice_service.py`, `ui/pages/Dashboard.py`, `ui/pages/History.py`, `database/database.py`, `config/settings.py`, `ai/validator.py`, and `ai/post_processing.py` contain incompatible changes. In particular, older multi-invoice PDF processing, PHP/USD aggregation, older Groq defaults, and missing-value behavior could regress. `parser/page_filter.py`, `parser/soa_layout.py`, and `parser/extraction_salvage.py` were not activated: their intended fixes overlap the October 28 source-recovery pipeline and require separate end-to-end review before adoption.

The candidate also contains `.env`, caches and debug files. Those are **not included** in this distribution.

## Testing and release limits

- Tested targeted invoice-fixture recoveries for INV-02, INV-17, INV-19 and INV-25 and retained the earlier full QA suite.
- The full pytest run passed **777 tests** with **4 baseline failures**: three Streamlit UI tests cannot run in this environment (`ModuleNotFoundError: streamlit`), and one old parser mock does not accept the newer `seller_header` keyword argument. The full suite was rerun after the final O/0 verification-warning change and yielded the same **777 passed / 4 baseline failures**.
- **Not a claim that INV-01 through INV-26 are all correct**. Teammate-specific modules, model timing, and live invoice processing still require testing on both PCs.
- Install into a new folder; back up `.env`, `data`, and `storage`. Existing invoices are not automatically reprocessed.
- For repeatable hardware comparisons use identical invoices, model IDs, `.env`, OCR/model versions, prompt settings and image preprocessing. Compare processing logs and per-field results, not just elapsed time. CPU/RAM normally affect speed, memory pressure and timeout/fallback behavior rather than changing the mathematical meaning of a field.
