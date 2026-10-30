# Batch consistency and field corrections — revision 3

13 October 2026. Based on the supplied WithAPI_2.0.2 `data.zip` and `storage.zip`, both found at the exact paths provided. The prior v2 deliverable and working files were present. Original archives and the supplied deployment database were read without modification.

## Why batch and individual uploads differed

**A confirmed defect in the previous package shared the vision circuit breaker across the upload batch.** The Upload page opened one `vision_batch()` around all files, and the service's nested `vision_scope` reused it. After the first timeout, later files were denied vision calls even when their own upload was otherwise healthy.

The supplied traces explicitly say `Vision skipped for this batch after an earlier failure: vision request timed out`. During the initial sequence, skipped-call counts rise across successive invoices: Globe 8, the next invoice 10, then 14, North Star Page 5 at 18, and later files up to 29. This is direct evidence of state carried between files.

A separate effect is **the per-file 30-second processing budget**, which already starts before OCR. It was not one deadline for the entire batch. On the initial North Star upload, OCR consumed 17.659 seconds and extraction/correction consumed 14.387 seconds; the initial model call timed out and the pipeline used OCR-only fallback. On the initial Globe upload, OCR consumed 26.547 seconds, leaving very little time for the model; its initial extraction likewise timed out. These cases produced partial fallback fields. Re-uploading individually changed the available runtime conditions and created a new vision scope, so some fields improved. Model and crop-OCR variation can also affect repeated reads, but the shared failure state and recorded initial timeouts are confirmed causes here.

**This revision gives every `process_invoice_file` call a fresh vision state.** Retries remain bounded within that file, while its failure cannot suppress checks on the next file. The outer batch wrapper can remain for compatibility. The existing `VISION_BATCH_GUARD_ENABLED` configuration key remains supported; its effective boundary at the service entry point is now one file.

The reported fields also now have deterministic recovery at the final reconciliation step. That recovery uses printed labels, layout and explicitly reviewed party information rather than relying on an LLM retry. A failed initial model call can still produce a `needs_review` result; this change does not promise successful model generation or a strict 30-second end-to-end SLA on every document.

## Field-specific causes and fixes

| Input | Finding | Change verified against both available runs |
|---|---|---|
| Sample Invoice_Page_2.pdf | The number 44072 sits next to a bare `No.` under SERVICE INVOICE. The timeout fallback did not recognize that relationship and saved an UNVERIFIED number. | Recover the number from the SERVICE INVOICE / No. spatial block. Both captured runs produce **44072**. |
| Sample Invoice_Page_2.pdf | Focused OCR placed the first postal line before ADDRESS and read `Unit` as `Unt`. The previous rule required an exact `Unit` spelling, discarded the first line, and retained only `Meraico Ave.Ortigas`. This was also present in the later single-upload database record. | Recover the full postal span despite label order and the observed Unit/Unt spelling. Use the existing reviewed customer-address variant to repair OCR spelling. Result: **Unit 2102, 21st Floor, One Corporate Centre, Dona Julia Vargas Avenue corner Meralco Ave. Ortigas**. |
| Addl Invoice_Page_2.pdf | The batch fallback had no customer fields. In the later run, the TIN was still null before saving. It is explicitly printed below Customer TIN in the right-hand account block, not necessarily next to the customer name. | Read the labeled TIN independently: **007-848-122-00000**. Recover **TSUKIDEN GLOBAL SOLUTIONS INC** and the left-hand postal block, ending **Metro Manila,1605**. Do not include the plan description beneath it. |
| INV-38-2.png | USD was an extraction guess even though the document shows Philippines and no explicit foreign currency. The later saved record was PHP, confirming the run-to-run inconsistency. | Use Philippines/PHP evidence as a currency fallback when no foreign currency is explicitly printed. Result: **PHP**, regardless of a model's unsupported USD guess. |
| Addl Invoice_Page_5.pdf | The VAT row's 296.16 was substituted for the ticket service-fee row. The source table has a foreign unit cost, an exchange rate and a local-currency amount column. | Align the service description with its quantity and local total, and require agreement with the printed subtotal. Result: **quantity 1, unit price 2,468.00, amount 2,468.00**. The table's USD 40.00 × ROE 61.70 is represented in the application's local invoice currency PHP; VAT 296.16 stays separate. |
| INV-34.jpg | The issuer footer is blurred, and the model guessed Smart Constructions Inc and USD. Both captured outputs repeat that error. | Apply the user-confirmed issuer **SMART COMMUNICATIONS INC** and **PHP** only with multiple source cues: Smart, account number, current bill charges and VAT registration context. This is documented reviewed party information in `config/party_master.json`, not a claim that every blurred character was read accurately. |

The updated currency rule does **not** assume every invoice mentioning Philippines must use PHP. Explicit USD/EUR/GBP invoices keep their stated currency. The North Star exchange-rate table is treated separately because its local totals are explicitly PHP. These cases have negative-control regression tests.

## Database findings

The supplied deployment database has 14 current invoice rows. The current North Star row has number 44072 but the shortened address; the current Globe row has a null customer TIN; current Shopee currency is PHP; current Smart currency is USD. Earlier deleted-upload snapshots remain in the JSON/diagnostic archive, enabling comparison with the current records.

The missing fields were already absent or incorrect in the pipeline's final data, so these observations do not indicate the database discarded a correct TIN/address during persistence. This revision changes extraction and reconciliation. It does not rewrite the supplied database or historical records automatically.

## Validation

- **27 new tests passed**, including all ten captured batch/single results, complete pipeline replay, upload-order independence, explicit foreign-currency controls and negative issuer matching.
- **55 tests passed** when running this revision's tests together with revision 2's 28 targeted regressions.
- Broader runnable suite: **425 passed, 6 pre-existing failures**. Two API TestClient tests and one asynchronous upload test were not rerun in this revision because the prior session's restricted local socket setup stalled those checks. The normal tests remain in the archive for execution on the deployment machine.
- The batch-failure test exercises the actual service boundary with a simulated first-file HTTP timeout. It confirms the next file makes its own request, the two files have different vision states, and the outer batch is not contaminated. A separate test confirms repeated failures are still bounded within one file.
- Field tests replay the supplied OCR geometry, focused OCR regions and model outputs through the updated pipeline. This establishes the reported deterministic corrections. **No fresh live Ollama batch or new OCR accuracy/SLA benchmark was run in this revision.**
- Python compilation, packaged Python syntax, ZIP integrity, duplicate ZIP entry checks and original sample database byte preservation passed.

The six existing failures remain the four legacy UI source-string tests, the subprocess dependency-path test and the old API-key expectation test documented in the earlier reports. None is a newly introduced assertion failure.

## Installation and retest

1. Back up the deployment database and storage. Extract this updated archive to a new application directory and retain the deployment's existing `.env` and database rather than replacing them with the archive's original sample database.
2. Restart the application. No new database columns are introduced in this revision. The existing SQLite migrations remain included.
3. Correct existing rows in History or remove the affected row through the normal application workflow before re-uploading; otherwise duplicate detection will intentionally reject the new copy. Existing rows are not automatically rewritten.
4. Upload the reported invoices together, then in a different order. Confirm all fields in the table above, inspect review warnings and verify that a timeout on one file does not disable subsequent files' verification.
5. Run `python -m pytest tests/test_qa_batch_round3.py tests/test_qa_output_round2.py -q` and the full suite on the deployment machine, including the three socket-dependent tests. Retest cold and warm model latency separately if the 30-second target is required.

The revision retains prior fixes and documentation. Source and regression fixtures are included; runtime dependencies, model caches, debug outputs and the supplied production database are not bundled as new deployment data.
