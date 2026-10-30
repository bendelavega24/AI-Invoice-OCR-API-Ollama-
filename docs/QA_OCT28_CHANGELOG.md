# October 28, 2026 QA changes and verification

**Base:** `AI-Invoice-OCR-API-Ollama-Dan_QA_Consolidated_2026-10-26.zip`.
**Reference evidence:** newly supplied `data.zip` and `storage(1).zip`.

## Source-backed findings

- **INV-29.jpg (NOTARIZE, INC. DBA PROOF):** saved Customer was `INVOICE NUMBER`.
  The saved OCR text includes the billed party **ABC Company**, but places the
  headings `Invoice number`, `Date`, and `Payment terms` between the `Bill to`
  label and the customer. A generic, evidence-limited column-heading skip in
  `reconcile_customer_name` recovers the customer. The invoice itself prints USD
  amounts; **USD is valid**, not an invalid ISO currency. It must be reported
  separately from PHP without implicit conversion.
- **INV-28.png (MERALCO):** stored Invoice Date `2026-12-31` is future-dated
  relative to October 28, 2026. Existing validation already reported a future
  date but stored field evidence incorrectly marked it supported. The new code
  flags it in the field-level evidence and also overlays a warning in History
  for previously stored records without modifying those records.
- Missing **Vendor**, **Invoice #**, **Invoice Date**, and **Total Amount Due**
  remain required-field validation errors and now have explicit missing-field
  verification indicators, including older saved evidence where fields are absent.
- Peso notation `PHP`, `₱`, `P` immediately before an amount is normalized to
  PHP. A random `P` inside a name/address is **not** a currency marker. The
  currency fallback in the sample `.env.example` is now PHP, but a source-marked
  USD invoice stays USD.

## Accounting and exports

- Dashboard: show native-currency totals separately and select a single
  currency for Vendor, Category and Month spending charts. The former global
  total that mixed currencies is intentionally not used.
- Reports: show a Total Amount Due metric for each currency; invoice rows
  retain their original currency. Generated CSV, Excel and PDF include one
  **TOTAL** summary row per currency. Optional charts distinguish buckets
  by currency. No exchange-rate lookup or silent conversion is performed.
- The repository's legacy `stats()['total_amount']` returns `None` instead of
  an invalid cross-currency grand total. `total_by_currency` contains the
  currency-specific amounts.

## Default hosted model

- `.env.example` and `config/settings.py` use `LLM_BASE_URL=https://api.groq.com/openai/v1`
  and `LLM_MODEL=qwen/qwen3.8-27b` as hosted API defaults. The existing `.env`
  overrides these values, so update your own local `.env` manually; it is not
  included in this source archive.
- Supported optional Ollama/local model modes remain unchanged.
- Groq API requires a valid key and account access; models, pricing and rate
  limits may change. No live inference calls were performed in this QA run.

## Documentation and dependency audit

- Updated `README.md`, `SCANNER_PRINT_SETUP.md`, `SETUP_SERVER.md`, and
  `docs/user_manual.md` in English to describe the *actual* source's API/Ollama
  options, account controls, approved fields, one-invoice-per-file policy,
  currency handling, and QA review behavior.
- `requirements.txt`: removed overlapping `opencv-python` distribution; the
  already pinned `opencv-contrib-python` provides `cv2`. Other pinned package
  versions are retained; package installation on the user's Windows hardware
  and scanner/printer end-to-end operation were not reproduced in this environment.

## Regression testing

- Added `tests/test_oct28_currency_review_and_docs.py` for customer ownership,
  missing/future review warnings, peso symbols, currency-grouped exports,
  default Groq configuration, and documentation/dependency presence.
- Native-currency CSV, Excel and PDF files generated successfully in the test
  environment, with separate USD and PHP TOTAL rows.
- Full test run results: **754 passed, 4 failed** (see release notes for the
  existing failures: 3 Streamlit UI tests require the missing Streamlit test
  dependency, 1 old parser mock rejects a `seller_header` parameter).
- Source reviewed against current saved invoice rows only. Saved invoice rows
  were *not edited* by this build. Rerun extraction for INV-29 or manually
  edit it after checking the source. For INV-28, History can flag the future
  date immediately via the current UI overlay.

## Installation

Back up `.env`, `data/`, `storage/` and the SQLite file before updating.
Use this source ZIP in a new folder. Do not overwrite your saved invoice database
or credentials with any distribution files. Run your own live Groq/Ollama and
Streamlit QA tests on representative invoices before replacing the production
installation.
