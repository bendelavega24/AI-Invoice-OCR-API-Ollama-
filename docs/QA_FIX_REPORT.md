# AI Invoice OCR System — QA fix report

Prepared 13 October 2026. This archive contains implemented fixes and regression coverage, not a certification that every QA defect is closed.

## Inputs and recovery

The four paths supplied under `C:/Users/Ben/Downloads/` were missing: `AI-Invoice-OCR-API-Ollama-Dan.zip`, `invoices_used_in_QA.7z`, `Buglist.xlsx`, and `Datasets.xlsx`. Matching filenames were found and used in `C:/TGSI/AI/AI Invoice OCR System/QA Results/`. The supplied `Manual-Evaluation.xlsx` existed at its specified nested QA Results path. No required input remained unavailable. Original files were not modified.

Defects were read from **Description of Actual Defect Behavior** and linked using **Related Test Cases** to **Related Test Case**, then **Invoice_File**. Document contents were treated as evidence, not instructions. The archive supplied 46 invoice samples. Existing manual-evaluation results were read as historical evidence; they were not replaced with invented scores.

Dataset filenames `INV-38_2.png` and `INV-39_2.png` correspond to archive names `INV-38-2.png` and `INV-39-2.png`. BUG-024, 026, 027, 028, 029 and 031 have no matching invoice mapping in the supplied dataset. BUG-001 names INV-04.pdf in its defect description. Both INV-25.jpg and INV-25.png exist; the mapped missing-date test uses the PNG.

## Main changes

- Prevent Ollama prompt truncation by explicitly allocating 16,384 context tokens and compacting the extraction prompt. Reject non-invoice JSON and preserve the last valid extraction if a correction fails.
- Read native PDF text and geometry where usable; retain OCR fallback for scanned pages. Join compatible sequential numbered pages and flag incomplete or failed pages. Unnumbered pages remain separate rather than being assumed to belong to one invoice.
- Correct orientation/deskew handling, normalize shadows, and try the original printed image when preprocessing lowered recognition quality. Handwriting-engine failures fall back to printed recognition with a warning.
- Recover statement dates, IDs and totals from explicit printed labels; distinguish current charges, previous balance and total payable. Source-driven rules do not contain hardcoded QA answers.
- Persist and display missing-field, arithmetic and confidence warnings. Preserve explicit zeros and valid identifiers; reject non-finite numbers. Confidence is labelled as a heuristic estimate, not measured accuracy.
- Scope duplicates to normalized vendor plus invoice number; preserve punctuation and leading zeros. Migrate SQLite identity indexes without deleting historical rows. Unknown identities remain reviewable rather than sharing a fake duplicate key.
- Keep a file failure from aborting the whole upload, move blocking API processing to a worker thread, preserve quality data when archiving files, unify keyword searches and include review information in exports.

## Validation performed

**New QA regressions: 62 passed. Full suite: 373 passed, 6 failed (379 tests).** All six failures also occurred on the untouched original archive (baseline: 311 passed, 6 failed). No new failing test was introduced. Tests include validation, zero values, identifiers, multi-page grouping, partial failures, duplicate edits, data round trips, literal search, two SQLite uniqueness layouts, deskew, orientation probes, model deadlines, correction failure recovery, actual statement text fixtures, API upload/export, and a Streamlit quality component test.

The six existing failures are:

1. `test_1_59_retail_layout_reliability.py::test_history_uses_one_table_per_month_and_keeps_category_column`
2. `test_1_64_ui_categories_name_normalization.py::test_history_has_month_separator_and_custom_category_manager`
3. `test_1_64_ui_categories_name_normalization.py::test_reports_uses_single_confirm_download_button`
4. `test_1_65_custom_category_and_bulk_lock.py::test_history_ui_has_add_category_below_others_and_bulk_lock`
5. `test_filtered_logs_print_restart.py::test_token_valid_in_process_but_invalid_after_restart`
6. `test_openrouter_provider.py::test_missing_key_fails_clearly`

The first four assert legacy UI source strings. The fifth launches a subprocess with a replacement PYTHONPATH that cannot see this validation environment's isolated SQLAlchemy installation. The sixth expects the old `OPENROUTER_API_KEY` message while the existing application uses `LLM_API_KEY`. They remain visible in the test suite. Two request-payload/timeout expectations were updated for the intentional Ollama context and timeout changes.

Python compilation passed. The supplied SQLite database was copied and initialized twice; integrity and foreign-key checks passed and existing row counts were preserved. That database contains zero invoices and zero line items, so populated-database preservation was additionally tested using synthetic fixtures for both legacy unique-index forms. The original database bytes are retained in the delivered ZIP, not the modified test database.

### Live local checks

Final local model runs used Ollama `qwen2.5:7b`, vision verification disabled, native-text PDF extraction, and a 30-second shared model budget. These timings cover parsing/extraction, not upload, database saving, export or network transfer.

| Sample | Final parsing time | Verified values |
|---|---:|---|
| INV-04.pdf (PLDT) | 8.41 s | ID 0434287913; date 2020-03-07; subtotal 1,159.82; tax 139.18; current charges 1,299.00; previous balance -10.00; total payable 1,289.00 |
| INV-01.pdf (Meralco) | 7.22 s | ID 4230011264445; date 2020-01-10; VAT sales 884.27; tax 98.63; non-VAT 51.65; current charges 1,034.55; previous balance 1,508.52; total payable 2,543.07 |

The dataset's Meralco value 1,034.55 is the printed **current bill**, while the printed **total amount due is 2,543.07**. The implementation preserves both fields instead of overwriting the payable total to fit that dataset value. Electricity line items represent the printed charge-category breakdown; they are not a claim that every detailed kWh quantity/rate row is reconstructed.

Actual PaddleOCR printed-image checks covered INV-02.png, INV-07.jpg, INV-08.jpg, INV-09.jpg, INV-10.jpeg, INV-11.jpeg, INV-13.png and INV-22.jpg. The 90-degree sample required three clockwise quarter-turns and the 180-degree sample two, as expected. These runs exercised OCR and preprocessing, not full model extraction or a scored transcription benchmark. Their machine-readable summary is included in `docs/qa_validation_summary.json`.

### Acceptance limits

- **BUG-014 remains acceptance-pending:** >=90% character accuracy has not been demonstrated against independently transcribed ground truth. Model/recognizer confidence must not be used as that score.
- **BUG-031 remains acceptance-pending:** the budget bounds model requests/retries, not native OCR or all I/O. Cold model startup, handwriting, damaged images and large files can exceed 30 seconds. An intermediate PLDT run took 31.64 seconds before the final redundant-correction fix; the latest faster result is not an SLA guarantee.
- The complete 46-file batch and all mapped end-to-end UI workflows were not rerun. Full browser interaction, handwriting accuracy, logo/watermark removal, all item-table details, and arbitrary unnumbered multi-page grouping are not certified.
- Bad source images can still produce incorrect characters. Review status and warnings help expose uncertainty; they do not make uncertain values correct. Review-marked invoices remain saveable/exportable with their warnings.

## Defect traceability

“Implemented; retest” means the associated code path was changed and regression-tested where described, but QA should rerun the original test before closing the defect. “Mitigated; retest” identifies broader OCR/layout behavior whose full acceptance is not established.

| Defect | Related cases | Mapped invoice(s) | Change/evidence | Status |
|---|---|---|---|---|
| BUG-001 | Batch Ingestion Loops | INV-04.pdf | Per-file recovery, shared model deadline, PDF native-text path, and API worker-thread dispatch. Live PLDT PDF completed without abort. | Implemented; retest |
| BUG-002 | TC001, TC002 | INV-01.pdf, INV-02.png | Increased Ollama context to 16,384 tokens; compact structured extraction prompt and schema checks. Live PDF fields and printed PNG OCR checked. | Mitigated; retest |
| BUG-003 | TC005 | INV-04.pdf | Explicit numbered continuation pages grouped into one invoice; all page text reaches extraction; blank PDF page skipped only with evidence. | Implemented; retest |
| BUG-004 | TC016, TC017 | INV-07.jpg, INV-08.jpg | Orientation probes disable automatic crop flipping. Actual 90-degree and 180-degree samples corrected. | Implemented; retest |
| BUG-005 | TC018 | INV-09.jpg | Corrected OpenCV coordinate/angle handling; regression tests cover positive and negative skew; actual sample OCR checked. | Implemented; retest |
| BUG-006 | TC019, TC020 | INV-10.jpeg, INV-11.jpeg | Preprocessing and fallback to original image when printed OCR is stronger. Damaged-image correctness remains an acceptance item. | Mitigated; retest |
| BUG-007 | TC022 | INV-13.png | Added background/shadow normalization; actual shadow sample OCR checked. | Implemented; retest |
| BUG-008 | TC023, TC024, TC025 | INV-14.jpg, INV-15.jpg, INV-16.png | Common preprocessing and quality warnings cover color/grayscale inputs; these three specific samples still need end-to-end retest. | Mitigated; retest |
| BUG-009 | TC026, TC027, TC028, TC029 | INV-04.pdf, INV-17.jpg, INV-18.jpg, INV-19.jpg | Missing fields and incomplete numbered documents now warn. No general logo/watermark removal guarantee; mapped samples need retest. | Mitigated; retest |
| BUG-010 | TC033 | INV-01.pdf | Bill/statement date labels override ambiguous due-date mapping; verified on actual Meralco PDF. | Implemented; retest |
| BUG-011 | TC035, TC042 | INV-01.pdf | Preserve identifiers and unsupported currencies for review rather than silently replacing with USD; symbol extraction still depends on OCR. | Mitigated; retest |
| BUG-012 | TC036, TC037, TC039 | INV-01.pdf | Label-bound statement amount reconciliation; Meralco subtotal, tax, current charges and total payable verified. | Implemented; retest |
| BUG-013 | TC040 | INV-01.pdf, INV-22.jpg | All continuation text retained and actual dense invoice OCR checked; electricity summary rows recovered. Detailed quantity/rate table acceptance remains. | Mitigated; retest |
| BUG-014 | TC041 | INV-01.pdf | Accuracy improvements implemented, but no character-level ground-truth benchmark established. Required >=90% accuracy is NOT certified. | Acceptance pending |
| BUG-015 | TC044, TC045 | INV-01.pdf, INV-04.pdf | Identifiers no longer unconditionally substitute OCR letters; numbered secondary pages retained. | Mitigated; retest |
| BUG-016 | TC046, TC048, TC050 | INV-01.pdf | Compact full-context prompt and label-bound dates/amounts; real Meralco mapping checked. | Mitigated; retest |
| BUG-017 | TC051, TC052, TC053, TC055 | INV-01.pdf | Finite numeric checks, negative-value review, tax/total validation, explicit-zero preservation and persistence regressions. | Implemented; retest |
| BUG-018 | TC056, TC057, TC059 | INV-01.pdf, INV-04.pdf, INV-22.jpg | Continuation text included in extraction; structured row validation and statement rows. Full mapped multi-row acceptance remains. | Mitigated; retest |
| BUG-019 | TC060 | INV-01.pdf, INV-43.png | Persist field confidence and render it with saved warnings in Upload and History. UI component test passed; scores are heuristic. | Implemented; retest |
| BUG-020 | TC061, TC062, TC063, TC064 | INV-23.png, INV-24.png, INV-25.png, INV-26.jpg | Placeholder-aware required-field checks survive normalization and saving; missing fields mark needs_review. | Implemented; retest |
| BUG-021 | TC065, TC066, TC067 | INV-27.png, INV-28.png, INV-29.jpg | Invalid/future invoice dates and unsupported currencies produce review warnings; malformed original evidence retained. | Implemented; retest |
| BUG-022 | TC068, TC069, TC072, TC074 | INV-30.jpg, INV-31.png, INV-34.jpg, INV-36.jpg | Finite/nonnegative numeric checks, tax exceeding total, empty records and row checks; invalid values do not silently pass. | Implemented; retest |
| BUG-023 | TC070, TC071 | INV-32.jpg, INV-33.jpg | Row quantity/price/amount and subtotal/tax/total validation with two-cent tolerance; utility inclusive-charge basis supported. | Implemented; retest |
| BUG-024 | TC075 | No dataset match | Saved warnings shown in Upload/History and exports. Streamlit AppTest confirms warning and field table display. | Implemented; retest |
| BUG-025 | TC079, TC081 | INV-38.png, INV-38_2.png, INV-40.png | Vendor-plus-invoice-number duplicate identity, edit checks and SQLite migration. Case/spacing normalized; punctuation and leading zeros preserved. | Implemented; retest |
| BUG-026 | TC084, TC085 | No dataset match | Round-trip persistence tests for values, items and quality metadata; archived source path updates retain confidence and warnings. | Implemented; retest |
| BUG-027 | TC089, TC090 | No dataset match | Literal keyword lookup across invoice/vendor/customer/filename; stripped input and escaped SQL wildcard characters. | Implemented; retest |
| BUG-028 | TC092 | No dataset match | Shared literal filtering and consistent unlimited record retrieval across History/Reports; stable database ordering. | Implemented; retest |
| BUG-029 | TC102, TC103, TC106 | No dataset match | Preserve valid identifier characters/leading zeros and retain malformed-date evidence instead of silently dropping it. | Implemented; retest |
| BUG-030 | TC113, TC114, TC116 | INV-04.pdf, INV-19.jpg, INV-22.jpg, INV-42.png | Continuation-page grouping, partial-page failure warnings and persisted missing-field/confidence information. | Mitigated; retest |
| BUG-031 | TC099, TC124 | No dataset match | Native PDF path, compact prompt, larger model context and shared retry budget reduce latency. Strict 30-second end-to-end SLA is NOT certified. | Acceptance pending |
| BUG-032 | TC118, TC122 | INV-01.pdf | Persist validation warnings/review status and include them in exports; API export now supplies one file path. Review-marked data remains exportable. | Implemented; retest |
| BUG-033 | TC119, TC120, TC125 | INV-04.pdf, INV-43.png | Continuation pages retained; hyphen placeholders counted as missing; saved warnings and field confidence exposed. | Mitigated; retest |

## Deployment and QA retest

1. Extract the updated ZIP to a new application directory. Use the existing README and requirements for installation; runtime libraries and downloaded model weights from this validation environment are not bundled.
2. Before upgrading an existing deployment, stop the app and back up its database and storage. Keep your existing `.env` and data; do not overwrite production data with the ZIP's sample database.
3. Review `.env.example`: use `LLM_CONTEXT_TOKENS=16384`, `PROCESSING_BUDGET_SECONDS=30`, and `OCR_PREPROCESS_ENABLED=true`. An existing environment override takes precedence, so explicitly update old values. Confirm your local Ollama model is installed and running. A larger context requires additional memory.
4. Start the app normally. SQLite migration adds quality fields and replaces invoice-number-only uniqueness with vendor-plus-number identity. Non-SQLite deployments require an equivalent migration using their database migration tooling before starting the updated application.
5. Run `python -m pytest tests/test_qa_oct2026.py -q`, then `python -m pytest tests -q` in the installed application environment. Review the six baseline failures above rather than treating the entire suite as green.
6. Rerun all mapped QA invoices; verify source fields and line items manually, then score character/field accuracy against approved ground truth and measure cold/warm end-to-end latency on deployment hardware. Check duplicate vendors, edited invoices, missing fields, partial documents, searches and exports.

## Package contents and audit

The ZIP preserves all original entries, including the original database, and replaces only changed source/configuration files. It adds the QA regression suite, two PDF-text fixtures, seven supporting Python modules, this report, defect mapping and a validation summary. Runtime caches, logs, installed libraries and newly generated database contents are excluded. Original bundled data remains as supplied.

Changed existing files:

- `.env.example`
- `ai/confidence.py`
- `ai/extractor.py`
- `ai/llm_client.py`
- `ai/post_processing.py`
- `ai/prompt_builder.py`
- `ai/validator.py`
- `ai/vision_budget.py`
- `api/invoices.py`
- `api/upload.py`
- `config/settings.py`
- `database/database.py`
- `database/models.py`
- `database/repository.py`
- `exports/common.py`
- `models/invoice.py`
- `ocr/ocr_engine.py`
- `ocr/paddleocr_engine.py`
- `ocr/preprocessing.py`
- `parser/currency_parser.py`
- `parser/invoice_parser.py`
- `services/invoice_service.py`
- `services/search_service.py`
- `tests/test_openrouter_provider.py`
- `ui/pages/History.py`
- `ui/pages/Reports.py`
- `ui/pages/Upload.py`
- `utils/pdf_utils.py`

Added Python files:

- `ai/processing_budget.py`
- `ai/statement_evidence.py`
- `database/qa_migration.py`
- `parser/page_groups.py`
- `tests/test_qa_oct2026.py`
- `utils/data_quality.py`
- `ui/components/quality_details.py`
