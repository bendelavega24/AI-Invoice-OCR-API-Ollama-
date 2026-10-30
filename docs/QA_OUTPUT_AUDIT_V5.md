# Invoice OCR QA update v5 — 15 October 2026

## Scope and findings

Audited the supplied v2.0.4 data/storage archives: 45 saved JSON records and 71 diagnostic traces. Both supplied archives and the v4 application ZIP were present. The new evidence archives contain no invoices.db, so this review uses exported JSON and traces, not a live database snapshot. All 45 saved records report incomplete vision verification; 17 report OCR-only recovery. These provider timeouts and the shared per-file processing deadline are material limits on extraction quality. This update does not claim to resolve provider capacity/timeouts.

## Changes

- After source validation and confidence scoring, unavailable Vatable Sales, VAT-Exempt Sales, Zero-Rated Sales, VAT, and Withholding Tax are saved as numeric zero, displayed as 0.00. Known amounts and printed zeroes are retained. Unknown total payable and currency remain unavailable. A default zero is not evidence of a printed zero; source warnings/confidence are retained.
- Remaining Balance rows are synchronized after final source corrections, which previously could replace the rows or change their amounts after the balance row was added. Positive debt and negative credit balances get one row, quantity 1. Zero/absent balances remove stale carried-balance rows. These rows are excluded from current-sales and aggregate-row checks and do not increase header totals a second time.
- INV-16: recover positive previous balance 862.50 when its printed value plus current charges agrees with total due. Previously saved as -862.50.
- INV-21: recover subtotal 5,800.00, VAT 570.00 from the two printed VAT summary rows, total 6,370.00, and four line amounts 2,500 / 1,000 / 1,500 / 800. Recover seller and buyer addresses from their separate FROM/TO columns. The rules use source geometry and arithmetic, not filename-specific answers.
- Recover an explicitly labeled Seller Address, preventing the seller-name label from becoming the address (INV-25 replay).

## Remaining review

This is not a declaration that every invoice is correct. Blurred characters, cropped/missing pages, invalid dates and contradictory printed amounts cannot safely be repaired by arithmetic alone. The accompanying per-record JSON preserves original warnings and lists proposed field changes, original values, line items and targeted review notes. In particular, inspect INV-16's small invoice-number header; INV-41's S/5 identifier; INV-43's blurred amounts; INV-30/31's contradictory totals; INV-33's date/identifier; and the remaining OCR-garbled descriptions. INV-34 is page 3 of 4 and prints zero current charges; upload the complete bill before treating that as the final payable.

## Verification

All 45 saved records were replayed through the full parser using their captured OCR/model responses, with live vision/header recovery disabled. No fresh OCR or live LLM quality benchmark was performed. New tests cover all 45 records at both evidence and full-parser boundaries, missing/known amounts, balance signs, deduplication, stale rows and contradictory VAT summaries. Exact test totals and environment limitations are recorded in Package-Verification-v5.json. ZIP CRC, duplicate entries, Python syntax and preservation of the original packaged database are checked during packaging.

## Applying the update

Back up your deployment, including .env, data, storage and database. Extract this version into a separate application folder and retain your deployment configuration and live data when switching versions. Do not replace the live database with the sample database included in the application archive. Restart the application. The changes apply to newly processed invoices; existing saved history is not rewritten automatically. Reprocess affected invoices after reviewing/removing the old record as appropriate, because duplicate detection intentionally prevents saving a second copy. Review the resulting records against the original invoices before confirming them.
