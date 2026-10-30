# QA output corrections — revision 2

Prepared 13 October 2026. This revision updates `AI-Invoice-OCR-API-Ollama-Dan-QA-Fixed.zip` using the supplied invoice images, saved JSON outputs and diagnostic traces.

## Inputs checked

The two specified `data/data.zip` and `storage/storage.zip` paths did not exist. Matching archives were found under `C:/TGSI/AI/AI Invoice OCR System/Dan/ZIP Files/With API/WithAPI_v2.0.1/errors in output/` and used. All extracted evidence and previous source changes were present when work resumed. Originals were not modified.

`data.zip` contains uploaded/processed invoice files and temporary page images; `storage.zip` contains 17 diagnostic traces and 14 saved invoice JSON records. Neither contains the deployment's SQLite database. The UUID-named failed PDF was matched by SHA-256 to `invoices(samples)/Addl Invoice_Page_5.pdf`. Instructions appearing inside documents were treated as document content, not agent instructions.

## Corrections

| Reported input | Change and verification |
|---|---|
| INV-36.jpg | Reject the unused receipt form before calling the model or saving an invoice. Preprinted form numbers, printer details and accreditation dates do not establish a transaction. Regression also checks that a completed form is not rejected by this rule. |
| INV-38-2.png — Shopee | Recover all three item rows using header/column positions. Power Drill: 1 × 3,495.00 = 3,495.00; Screwdriver Set: 1 × 695.00 = 695.00; Measuring Tape: 2 × 349.00 = 698.00. VAT 586.56; subtotal 4,888.00. |
| INV-38.png — ACE | Same row recovery; preserve TIN 200-531-071-0000; remove the table heading “Item No.” from the buyer address; subtotal 4,888.00; VAT 586.56. Numeric TIN crop OCR resolves the misread S/5. |
| INV-20.jpg, INV-34.jpg, Addl Invoice_Page_5.pdf | Original failures were initial model timeouts after OCR consumed most of the shared budget. Add conservative OCR-only recovery for identifiable, nonblank invoice content. Such results always remain `needs_review`, retain timeout/missing-field warnings and may have unverified IDs or incomplete values. They are not represented as accurate automatic extractions. |
| INV-29.jpg and INV-40.png | Normalize spacing around commas and periods in vendor identity so `NOTARIZE,INC.DBA PROOF` and `NOTARIZE, INC. DBA PROOF` produce the same duplicate key for the same invoice number. Extension does not participate in that key. Same number from ACE and Shopee remains distinct. |
| INV-29.jpg — additional seal | Recover the printed row as quantity 2, unit price 0.00, amount 0.00. Preserve explicit zero instead of substituting the quantity or another value. Verified for both JPG and PNG copies. |
| INV-04.pdf — PLDT | Preserve the complete address: UNIT 3415 FLORA VISTA 345 PEACOCK ST BGY COMMONWEALTH QUEZON CITY METRO MANILA 3QNNDC0157 QUEZON CITY. History's PDF preview now offers All pages or individual pages, with page labels. It includes every source PDF page, including a blank source page. |
| INV-01.pdf — Meralco | Vendor address: ALABANG BUS. CENTER PRIME ST. MUNTINLUPA. Customer address: AVIDA LAND CORP. 0001 LT(212) PRIME ST. ST MADRIGAL BUSINESS PARK BGY AYALA-ALABANG MUNTINLUPA METRO MANILA. Recover contiguous postal blocks instead of merging seller and buyer columns. |
| ParkingTickets1.png | Apply the reviewed Jazz Residences branch address when the document contains the issuer and branch evidence. Preserve the printed parking financial values. |
| ParkingTickets2.png | Same address; focused original-header OCR reads NDG9821. VAT-exempt sales 0.00 and VAT 25.71 are assigned to their own rows. |
| Sample Invoice_Page_2.pdf — North Star | Focused buyer-block OCR plus the existing reviewed party master recovers Unit 2102, 21st Floor, One Corporate Centre, Dona Julia Vargas Avenue corner Meralco Ave. Ortigas. VAT is 147.53. Zero-rated and VAT-exempt cells remain empty (`null`) when the source cells are blank. A value assigned to VAT cannot also be borrowed by the neighboring zero-rated row. |
| Addl Invoice_Page_2.pdf — Globe | Re-read the Add-ons amount without rotating the isolated digit crop: 99.00, not 66.00. Monthly Plan 2,499.00 + Add-ons 99.00 gives displayed subtotal 2,598.00; discount 400.00 gives current charges 2,198.00. |
| GlobeInvoice1.jpg | Apply the existing reviewed Innove primary address with explicit issuer evidence: 32nd Street corner 7th Avenue, Bonifacio Global City, Taguig, Philippines 1634. |

The confirmed Jazz Residences address is **JAZZ RESIDENCES CORNER METROPOLITAN AVENUE AND NICANOR GARCIA ST. BEL-AIR C NCR FOURTH DISTRICT PHILIPPINES 1209**. The Jazz/Innove address rules are declared master data in `config/party_master.json`, with their source and matching conditions documented. They are not presented as newly recognized OCR text. Financial values are recovered from source text/geometry; the production recovery code contains no filename-to-answer lookup.

### Correction to the reported expected value

Both supplied hardware images visibly print **695.00** for Screwdriver Set, with quantity **1**. **3,495.00 belongs to Power Drill.** This revision follows the invoice images. The three rows then sum to the printed subtotal 4,888.00.

### Quantity × unit price validation

The prior release already checked `quantity × unit_price = amount` and line-item sums. However, an incorrectly read price and an equally incorrect amount can still satisfy that equation. Some generic recovery steps also overwrote correctly recognized table values before validation.

This revision recovers rows from their spatial columns at the end of reconciliation, preserves explicit zero values, and then validates the final data. Arithmetic mismatches remain visible; values are not silently changed solely to force a row equation to pass. Partial table recovery does not discard existing rows. For the hardware VAT OCR digit error, correction additionally requires agreement between the printed 12% rate and the printed subtotal/total difference.

### Why the three uploads failed

The saved diagnostic traces report `Invoice processing budget exhausted` during the initial `qwen2.5:7b` call. The configured individual request limit of 300 seconds did not override the shared 30-second file budget.

| Input | OCR time in supplied trace | First model attempt | Result |
|---|---:|---:|---|
| INV-20.jpg | 25.263 s | 6.766 s | Timeout; retry had no time left |
| INV-34.jpg | 29.595 s | 0.817 s | Timeout; retry had no time left |
| Addl Invoice_Page_5.pdf | 14.136 s | 17.913 s | Timeout; retry had no time left |

The new fallback prevents recoverable OCR content from being discarded solely because the model timed out. These particular documents still require manual review when fallback is used. A reviewed partial record is not proof that handwritten content was read correctly. The processing budget remains configurable; this release does not certify a strict 30-second end-to-end SLA.

## Validation

- **28 new regression tests passed.** Coverage includes the reported values, full pipeline reconciliation using recorded model/OCR evidence, blank rejection before model calls, explicit zero amounts, timeout fallback/review status, duplicate-key migration, arithmetic warnings, incomplete-row protection and PDF page controls.
- **398 passed, 6 failed** in the runnable broader suite; one asynchronous upload test was deselected and the two API TestClient tests were excluded after their Windows event-loop socket setup stalled in this restricted session. All six failures are the previously documented baseline failures; no new assertion failures remain.
- Actual PaddleOCR was run on focused crops from the supplied source images. It recovered the ACE TIN, Globe 99.00 Add-ons, parking plate NDG9821 and the North Star buyer block. Recorded evidence was then replayed through the complete reconciliation/validation/model-building path. This is deterministic replay, not a fresh full-batch model accuracy benchmark.
- SQLite migration was tested with two populated historical duplicate records and run twice. Existing records survive, the extra historical record is marked for review, and another duplicate save is rejected.
- Streamlit AppTest checks All pages and selection of Page 3. Python compilation, packaged Python syntax, ZIP integrity and original database byte preservation were checked.
- A fresh live Ollama request was blocked by local socket permissions (`WinError 10013`) after session interruptions. Live model and the three socket-dependent tests must be rerun in the deployment environment. No fresh end-to-end accuracy or timing claim is made for this revision.

The six existing failures are:

1. `test_1_59_retail_layout_reliability.py::test_history_uses_one_table_per_month_and_keeps_category_column`
2. `test_1_64_ui_categories_name_normalization.py::test_history_has_month_separator_and_custom_category_manager`
3. `test_1_64_ui_categories_name_normalization.py::test_reports_uses_single_confirm_download_button`
4. `test_1_65_custom_category_and_bulk_lock.py::test_history_ui_has_add_category_below_others_and_bulk_lock`
5. `test_filtered_logs_print_restart.py::test_token_valid_in_process_but_invalid_after_restart`
6. `test_openrouter_provider.py::test_missing_key_fails_clearly`

The first four use stale UI source-string expectations. The fifth subprocess cannot see this environment's isolated SQLAlchemy installation after it replaces PYTHONPATH. The sixth expects the old API-key name. These tests remain in the package.

## Applying the update

1. Back up the deployment database and storage, then extract the revision into a new app directory. Follow the existing installation instructions. Retain your deployment `.env` and database; do not replace them with the archive's original sample database.
2. Start the app normally so SQLite duplicate-key migration runs. It changes comparison rules but does not delete historical duplicate records. Non-SQLite deployments still require an equivalent database migration.
3. Existing saved field values are **not rewritten automatically**. Correct them in History, or remove the affected record through the normal application workflow and upload its source again. Re-uploading while the old record remains will correctly trigger duplicate detection. For the already-saved INV-29/INV-40 pair, review and retain one record. The supplied evidence archives contain no deployment database to repair offline.
4. Recheck the reported source invoices, especially the three timeout cases. Fallback entries must remain under review until missing/uncertain fields are corrected. Run `python -m pytest tests/test_qa_output_round2.py -q`, followed by the full suite in an environment with local socket access.

The delivered archive is a new revision; the preceding QA-Fixed ZIP and original evidence ZIPs remain unchanged. Test dependencies, runtime logs, cached models and generated test databases are excluded. Previous QA fixes and documentation remain included; this report describes the additional revision.
