# October 16, 2026 modification status

Base: AI-Invoice-OCR-API-Ollama-Dan(1).zip. Supplemental diagnostic sources: storage(1).zip and data(1).zip (not included in deliverable).

## Implemented
- Refuse files containing more than one separately identified invoice **before any database save**. Multiple independent uploads are still allowed. Invoices with genuine continuation pages can be accepted if recognized as one invoice.
- Explain the one-invoice-per-file limitation in Upload UI, scanner flow and documentation.
- Strengthen shared extraction instructions for handwritten customer names/TIN, address ownership, explicit zero line-item prices, document identifiers, dates, Vatable Sales/VAT and withholding tax.
- Correct outdated README and scanner guide; consolidate four technical/QA documents into `docs/technical_reference.md` and remove the redundant manual. Preserve the CSV test-case file.
- Existing tax validation already subtracts withholding tax: `subtotal + tax_amount + zero_rated_sales + vat_exempt_sales - discount - withholding_tax = total_amount`. No conflicting second formula was inserted.
- Remove the original `.env` from the deliverable to avoid packaging a real secret.

## Remaining work / known limits
- Requested named-document field corrections are **not verified or guaranteed**. Prompt refinements alone do not establish accuracy. Reprocess all specified invoices with the same selected API/Ollama model and inspect the OCR and visual traces.
- Failure investigation: supplied traces include HTTP 413 Payload Too Large and repeated HTTP 429 errors from Groq; upload failure may be a provider payload/rate limit, not simply a PDF parser crash. Exact `INV-04.pdf` trace must be mapped and retested with the same provider and configuration.
- The single-invoice policy detects independently parsed invoices across pages, but does **not reliably detect two invoices within one image or page**. Do not interpret this as complete multi-invoice detection.
- Some true multi-page invoices without recognized continuation markings may be rejected as multi-invoice. Split/verify pages manually until grouping improves.
- Existing full test suite has an unrelated OpenRouter retry expectation failure (`tests/test_openrouter_provider.py::test_fallback_after_429_exhausts_retries`), after 218 passed; targeted checks: 5 passed.

## October 19, 2026 review of new data.zip and storage.zip
- Reviewed 52 database invoice records and 54 debug traces. Audit worksheet is supplied separately; the production ZIP contains no private invoice database, original images, or debug payloads.
- **Corrected a validator blind spot:** accounting reconciliation previously permitted deviations of up to **5%** of the target amount. It now uses an absolute PHP 0.05 tolerance; this catches small but significant discrepancies without mixing prior balances into current-period VAT arithmetic.
- Added six regression cases, covering tax-inclusive totals, PHP 1.00 discrepancies, rounding, previous-balance separation, and withholding tax.
- Review examples: INV-39-2: subtotal 26.79 plus VAT 3.21 versus total 26.79; INV-32: sum exceeds total by 1.00; INV-31: negative total and conflicting carried-balance accounting; INV-22: sum differs by 5.00. These are **flags, not proven corrections**; source receipts must determine which field is accurate.
- Some apparent `subtotal != total` differences are legitimate billing statements where current charges and previous balance are separate (e.g. GlobeInvoice1.jpg and INV-07.jpg); no blanket arithmetic rewrite was made.
- Targeted tests: 14 passed. Full suite: 362 passed, 9 failed. Six are existing provider retry/request payload expectations; three are pre-existing test assumptions incompatible with the single-invoice-per-file upload policy. The new changes have not been live-tested against Groq/Ollama APIs.
- Important remaining limits: handwritten names/TINs/line items, visually ambiguous addresses, bill-summary semantics, and uploaded-file multi-invoice detection within a single page still require visual/live inference verification. No hardcoded corrections were inserted.


## October 20, 2026 follow-up: new storage_new.zip / data_new.zip

Base is the **October 19 QA ZIP**; the newly supplied private artifacts were inspected only as references and are **not** packaged. The files contain 24 persisted invoices with new results for INV-30 through INV-43 and 31 saved debug traces. The repairs below were verified against those saved OCR text traces and selected original invoice images; **live LLM/API reprocessing has not been performed**.

### Evidence-grounded changes
- New `ai/structured_table_recovery.py`: final-pass reconstruction for clearly identified Description/Qty/Unit Price/Amount tables using **complete OCR rows**, not broad nearest-price geometry. Detects missing rows and protects explicit zero-total lines. OCR-damaged amounts are only recomputed when row arithmetic is independently confirmed by the table subtotal or a one-peso OCR error.
  - INV-43: two items (Sneakers 1×1,999.00, Backpack 1×1,499.00).
  - INV-42: Rice 5kg 2×265=530; Toothpaste 2×89=178; other items preserved.
  - INV-41: Foldable Chair 2×895=1,790 and Table Lamp 1×1,295=1,295.
  - INV-40: IHN additional seal 2×0.00 = 0.00, rather than treating quantity 2 as amount.
  - INV-38: Power Drill 1×3,495=3,495, Screwdriver Set 1×695=695, Measuring Tape 2×349=698; VAT corrected to 586.56 only when 12% of 4,888.00 AND total 5,474.56 corroborate it.
- New `ai/statement_qa_recovery.py`: evidence-based cleaning of buyer addresses, explicit SOA / Statement of Account number ownership, service charge rows, and electric bill breakdown rows.
  - INV-39/39-2: exclude buyer names and financial column headers/amounts from postal addresses.
  - INV-37/35: recover SOA numbers 1000044843719 and 1000058304197; keep Monthly Recurring Fee item, negative Adjustments-Current Bill credit, original VAT/current total and correctly labeled Remaining Balance. INV-37 also recovers 3037D.
  - INV-34: remove a stray D logo artifact from Smart; leave unspecified customer address blank.
  - INV-32: recover vendor business-center address and electricity breakdown; prices are taken from each printed labeled row, not consumption-chart ticks.
  - INV-31: recover statement no. 0448162-171, VATable Sales 2,347.23 (= 2,320.53 + 26.70) and the corresponding item values. Strip address billing metadata. The scan visibly prints a negative -1,147.90 payable amount that **cannot be reconciled** with the extracted current charges and previous balance. No fabricated discount is permitted; verification warning is shown. The 4105 postcode is visible in the image but not reliably extracted by the saved OCR; check it manually.
  - INV-30: correct line item 2,999.00; prefer the main customer address starting 1132B over a conflicting payment-stub OCR read starting 1152B. Since the faint vendor address cannot be corroborated from the OCR header, leave it blank and warn, not an invented Mandaluyong office address. The invoice's printed VAT 3,250.00 exceeds the amount due 2,999.00 and remains flagged.
- INV-36: incomplete/blank-form rejections now use a **warning**, as do duplicates, instead of a processing-error banner; genuine processing failures remain errors.
- Dashboard: Spend by Month now defaults to **invoice date** and has an optional upload-date grouping. Uses bars instead of a one-point line chart; a single month is visible. Missing dates are excluded rather than guessed.
- Validation: unresolved extraction errors are stored as JSON in a new nullable `invoices.validation_issues` TEXT column (automatically migrated in SQLite). Show them on Upload. Recheck live stored fields and show warnings in History even for records saved by older builds; this reflects manual edits. Highlight negative Total Amount Due and explicit payable amount arithmetic discrepancies. Legitimately negative adjustment/credit line amounts are allowed when appropriately labeled.

### Test status
- 13 new synthetic/layout regression tests in `tests/test_oct20_incorrect_outputs.py`: all passed.
- Focused invoice/audit/single-invoice test selection: **58 passed**.
- Full suite on this machine: **375 passed, 9 failed**. All nine have the same pre-existing areas as the October 19 build: six outdated OpenRouter/Ollama request/retry expectations and three older multi-invoice PDF tests that contradict the enforced single-invoice-per-file policy. No new failed cases were identified in this run.

### Deployment / remaining limits
- This ZIP is **source code only**. It intentionally excludes the user's database, uploads, production debug traces, `.env` / API keys, model weights and runtime caches.
- **Back up the existing installation first**, including `.env`, `data/` and `storage/`. Install the revised source code into a clean folder, then separately restore your local configuration and existing data to the matching runtime locations. Do not replace your only database with any distributable database.
- On startup, the SQLite schema migration will add `validation_issues` when necessary. Previously saved invoices are NOT silently rewritten; reprocess their originals to obtain corrected extraction fields. History can nevertheless display current arithmetic checks on old saved fields.
- This is a regression-tested QA candidate, not a guaranteed field-by-field result for future Groq/Ollama requests. API responses, image readability and OCR noise vary. Verify all affected invoices against their images, especially INV-30 (faint seller address), INV-31 (inconsistent printed negative total and postcode), and the electricity bill whose displayed charge breakdown does not add to the payable total.


### October 20 final signed-balance correction
- Independently checked the INV-37 source image: the printed Remaining Balance is parenthesized **(1,499.00)**, i.e. a credit, not +1,499.00. The recovered current charges **2,290.81** minus credit **1,499.00** equals printed payable **791.81**. Added an independent cross-check requiring payable-total arithmetic or printed prior charges minus payments before changing a carried balance to negative.
- For INV-31, the earlier bill shows **1,385.87 - 3,500.00 = -2,114.13**, which independently corroborates the previous-bill credit sign. However **2,628.90 - 2,114.13 = 514.77**, not the printed **-1,147.90**. The new code preserves that inconsistent printed total, with an explicit validation warning; no fabricated discount or silently invented total.
- Added two more regression tests for signed credits. Total new tests: **15**. Full suite: **377 passed, 9 failed**, all in the same historical provider-payload and deliberately unsupported multi-invoice PDF areas.

## October 21, 2026 — per-field and per-line-item confidence review

Base: `AI-Invoice-OCR-API-Ollama-Dan_QA_2026-10-20.zip`. Implemented **evidence support indicators for 24 extracted document fields** and every extracted line-item cell (description, quantity, unit price, amount). Percentages are explainable heuristics based on final OCR text, available line confidence, localized table-row evidence, validation issues, and line-item arithmetic — **not statistical probabilities**. The original overall confidence calculation remains internal and unchanged.

- Store per-field JSON evidence/review reasons in nullable `invoices.field_evidence` without altering existing invoice values; migrate existing SQLite tables on startup (tested on a *copy* of the supplied invoice database).
- History detail shows the field indicator adjacent to the field value and line-item indicators in adjacent columns, plus warnings for ambiguous amounts. The editing form displays relevant field/item warnings. Upload shows an expandable list of values needing review.
- Optional absent fields and derived categories are identified without fake OCR scores. Historic invoices lacking saved confidence show explicitly labeled re-estimates from stored OCR text if present, otherwise no invented confidence. Manual editing invalidates affected field/cell OCR evidence and labels these as `manual_edit`.
- Nine additional targeted regression tests passed; full-suite result **386 passed, 9 failed**, with all nine failures in the same pre-existing provider request/retry expectation tests (6) and legacy multi-invoice PDF tests (3) that contradict the current one-invoice-per-file policy. Full live Groq/Ollama inference was not rerun.
- Important limitation: scores do **not** prove that OCR copied a value from the correct vendor/customer/line-item context, nor can they flag a completely omitted item with no extracted row. A source invoice must still be checked before approving critical amounts.


## October 21, 2026 — compact verification-focused History display

Base: `AI-Invoice-OCR-API-Ollama-Dan_QA_FieldConfidence_2026-10-21.zip`. No new OCR inference logic, score calculation, or database migration.

- Suppress all per-field and per-cell confidence percentages on the History detail page, and keep confidence evidence stored internally.
- Highlight only fields requiring verification with a subtle amber background/left border and `⚠ Verify`; hover for the original warning text. HTML-escape source document content and warnings.
- Replace the nine-column item table (four data columns, four confidence columns, warnings) with a four-column table. Highlight *individual flagged cells*, not entire items/rows. Preserve all numeric values, including zero amounts.
- Provide a collapsed `View verification reasons` section for detailed field/cell issues, and keep existing accounting validation warnings visible. Manual corrections do not remain flagged solely because automatic evidence was invalidated.
- New targeted UI tests: **5 passed**. Together with previous evidence tests: **14 passed**. Full regression suite: **391 passed, 9 failed**, the same six provider-payload expectation mismatches and three deliberately unsupported multi-invoice PDF tests as the prior build. Tests did not include a live Streamlit browser or Groq/Ollama run.

## October 21, 2026 — financial placeholders and optional metadata

Base: `AI-Invoice-OCR-API-Ollama-Dan_QA_ReviewHighlights_2026-10-21.zip`.

- History now shows `0.00` instead of `— (not extracted)` for absent Vatable Sales, VAT-Exempt Sales, Zero-Rated Sales, VAT, Withholding Tax and Total Amount Due. Original populated values are unaffected.
- UI-only formatting: an absent value remains `None` / SQL `NULL`; no database migration, extraction rules, confidence, line-item logic or validation arithmetic were changed. Displaying a placeholder does **not** certify that the invoice reported zero.
- When any of these six values is absent, a single unobtrusive caption clarifies the placeholder, rather than repeating a caveat on every row. Existing missing-total warnings remain.
- Optional Due Date, Tax Rate and Payment Terms are retained for payment and tax reference; no new mandatory field was introduced.
- New regression tests cover all six labels, missing vs explicit zero vs nonzero/negative values, unchanged source records and existing edit-form blank preservation.

## October 21, 2026 — hide unrequested optional metadata from client outputs

- Due Date, Tax Rate and Payment Terms are internal-only optional metadata.
  Suppress them from the History detail page and associated verification notices,
  and from post-upload field verification notices. Warnings exclusively about
  these hidden metadata fields are suppressed in the client UI, not in stored
  validation records. They were already absent
  from the History edit form.
- Drop the remaining Due Date column from the shared Reports export schema.
  CSV, Excel, PDF and PDF-based print previews now omit all three fields.
- Preserve SQLite schema and stored values, extraction and validation logic,
  and any historical invoice records. Do not silently overwrite existing data.
- Add regression checks for UI visibility policy and each invoice export format.

## October 21, 2026 — client-approved History fields and filename heading

Base: `AI-Invoice-OCR-API-Ollama-Dan_QA_HideOptionalFields_2026-10-21.zip`.

- The History title is now the source **Filename**; Invoice # appears only in
  the details, not twice as both a title and a field. A filename-free record
  falls back to Invoice # or internal record ID. The Edit form also titles
  itself by filename, without repeating the filename in its caption.
- The History left column contains exactly the approved document labels:
  Vendor, Vendor Address, Vendor TIN, Customer, Customer Address,
  Customer TIN, Plate #, Invoice #, Invoice Date, Date Uploaded, Category.
  Optional customer/plate fields can remain hidden when not supplied.
- The right column contains Vatable Sales, VAT-Exempt Sales, Zero-Rated Sales,
  VAT, Withholding Tax, Total Amount Due, Currency, Status and Locked.
  These remain as before, with 0.00 placeholders and actionable amber review
  highlights; confidence scores remain internal.
- Customer Contact, Current Charges and Previous Balance join Due Date,
  Tax Rate and Payment Terms as internal-only standalone metadata. They are
  removed from client-facing History summaries, associated field-evidence
  highlights and CSV/Excel/PDF/print exports, but retained unchanged in SQLite
  and reconciliation/validation logic. Genuine extracted line items named
  Current Charges or Previous Balance remain in the Items purchased table.
  Do not synthesize duplicate line items from existing summary amounts.
- Source records, line-item values, account balances, extraction prompts,
  OCR behavior, and confidence calculations are unchanged.
- Report export retains existing technical ID/Filename reference columns.
- **Testing:** 8 new regression cases passed; focused verification 19 passed.
  Full test suite: **410 passed, 9 failed**. The nine failures are unchanged
  known discrepancies involving provider request/retry payload expectations
  (six) and legacy multi-invoice PDF import behavior (three), which conflicts
  with the current one-invoice-per-file policy. No live browser/API test was
  performed.

## October 21, 2026 — clean Qty display in line items

- The History line-items Qty column now shows whole amounts without trailing decimal digits (e.g., `1` instead of `1.000000`). Genuine fractional quantities such as `0.5` and `1.25` remain visible and are not rounded.
- The editable quantity column also uses variable precision rather than forcing two decimals. Stored quantities, calculations, OCR, evidence and exports are unchanged.
- New regression tests cover whole/fractional/missing quantities and keep verification-cell highlighting.
