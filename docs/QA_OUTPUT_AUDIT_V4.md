# QA output audit — revision 4

14 October 2026. Inputs: the supplied `WithAPI_v2.0.3/errors in output/data.zip` and `storage.zip`. Both were present. The previous ZIP was absent from this workspace's outputs directory, but was found in the parent WithAPI_v2.0.3 folder. Its SHA-256 matched the previous delivery manifest: `20e816312e09eb14bb4f2b16d599fa649e4d3ca4a009edac0f767e39b6cbc335`.

## Scope and findings

I audited all **59 current database records**, representing **46 filenames**, using the archived OCR geometry, extraction results and source images. Selected originals were visually checked to confirm the column relationships and financial corrections. This was an audit and deterministic replay of the supplied runs, not a fresh 46-file OCR/model accuracy benchmark.

Confirmed systemic findings:

- **28 records used OCR-only fallback after model extraction failed.** All 59 records contain a warning that vision verification was unavailable. These results must not be treated as independently image-verified.
- **16 records had missing totals converted to 0.00.** Missing currency could similarly become USD. Missing amounts and currency now remain null through the model, database and API. History/Upload display unavailable values explicitly, exports leave the cells blank, and the edit form distinguishes an empty field from an explicitly entered zero. Totals disclose when missing amounts make them incomplete.
- **13 groups of repeated source content contained 14 extra copies.** Changing or missing model-generated vendor/number fields allowed the old identity check to miss these duplicates. An additional exact normalized OCR-content key now prevents repeat saves independently of those fields. Decimal points and signs remain significant. This is not fuzzy image similarity; materially different OCR results still rely on vendor/number identity and review.
- The reviewed Smart identity rule matched a **PLDT advertisement mentioning Smart on another PDF page**. PLDT issuer evidence now excludes that match, and explicit PLDT statement headers take precedence.
- Several totals, current balances, credits, tax rows and party columns were assigned to the wrong fields. The new final reconciliation uses the source labels and columns and rejects ambiguous associations.
- The garbled-text check removed spaces before counting consecutive consonants, incorrectly flagging “Monthly Plan.” It now respects word boundaries.

## Confirmed corrections

| Document | Corrected behavior / values |
|---|---|
| INV-04.pdf | Seller stays **PLDT INC.**, not Smart. The prior complete customer address and multipage preview behavior are retained. |
| INV-39.png | Sales **13.39**, VAT **1.61**, total **15.00 PHP**. The net sales figure is not a current balance. |
| INV-39-2.png | Sales **26.79**, VAT **3.21**, total **30.00 PHP**, not 26.79. The printed Series Number is recovered even after model failure. |
| INV-12.png | Recover Series Number **ISORPF000000318183**, sales **60.71**, VAT **7.29**, total **68.00 PHP**, and the labeled recipient. |
| INV-42.png | Currency **PHP**, VAT **158.76**, total **1,481.76**. Rice line amount **530.00**, consistent with 2 × 265 and the printed subtotal 1,323. The OCR dollar-looking digit is not evidence of USD. |
| Addl Invoice_Page_3.pdf | Separate **Fee: 1 × 10,000** and **Expense: 1 × 500**; sales **10,500**, VAT **1,260**, total **11,760**. Remove the invented 11,260 current balance. Recover Document No. and Issue Date from their labels. |
| Addl Invoice_Page_4.pdf | Preserve sales **85,963.99**, VAT **10,315.68**, withholding **1,719.28**, payable **94,560.39**. Remove gross 96,279.67 from the current-balance field; recover number **3219** and the labeled customer in the fallback run. |
| INV-02.png | **MS. SASA C. ARANETA is the seller** and **MR. IRAWADI JOHN OUD is the recipient**. Keep their separate address columns; recover the 110.00 Philippine-peso amount in the fallback run. |
| INV-07.jpg | Current net service fee **8,000**, VAT **960**, current charges **8,960**, old balance **44,800**, total **53,760**. Rebuild service rows when the previous model rows were invalid. |
| INV-08.jpg | Statement number **0298050594**, sales **1,279.83**, VAT **153.58**, credit **-0.15**, payable **1,433.26**. |
| INV-14.jpg | Sales **2,763.39**, VAT **331.61**, previous credit **-5.70**, payable **3,089.30**, currency **PHP**. The blurred identifier still needs source review when OCR cannot read it. |
| INV-15.jpg | Recover statement number **0434287913**, sales **1,159.82**, VAT **139.18**, current **1,299**, credit **-10**, payable **1,289**. A missing compact date remains reviewable. |
| INV-09.jpg | Source SOA number **1000019396156**, fee **1,248.21**, VAT **149.79**, deduction **99**, current **1,299**, payable **2,595.89**. Credit/payment values no longer replace VAT. |
| INV-37.jpg | Source SOA number **1000044843719**, recurring fee **2,133.76**, deduction **99**, VAT **256.05**, current **2,290.81**. |
| INV-16.png | Printed net subtotal **376.32**, VAT **45.16**, currency **PHP**. The foreign call-rate advertisement does not establish the statement currency. Discount-basis/line-item review remains necessary. |
| INV-25.jpg | Recover seller, sales **4,650**, VAT **558**, total **5,208 PHP**. Do not interpret the “12%” label as 12.00 zero-rated sales. Missing date and unread item details remain reviewable. |
| INV-05 / INV-17 / INV-26 / INV-27 / INV-28 | Recover Meralco identity and available printed statement identifiers/totals, including **5.64 / 9,349.73 / 1,277.60 / 1,502.42 / 17,972.99** respectively. Do not call the buyer the seller. Missing tax-breakdown pages do not establish VATable sales or VAT. |
| INV-29.jpg / INV-40.png | Recover **NOTARIZE185857**, **400.00 USD**, and preserve the zero-value additional seal. The exact source-content check catches these cross-extension copies even after a fallback extraction. |
| INV-38.png | Fallback now recovers total **5,474.56**, allowing the existing printed-subtotal/12%-VAT cross-check to retain VAT **586.56**. Prior hardware row corrections remain covered. |
| INV-33.jpg | Recover total **1,250**, current net **1,116.08**, VAT **133.92**. Source date ambiguity and placeholder account/invoice details still require review. |

Service-summary rows reconstructed from a printed fee use one charge as quantity 1; that is a normalized billing representation, not a claim that every statement prints a quantity column. No invoice filename, expected invoice number or expected financial amount was hardcoded into recovery rules.

## Records that still need review

This package does **not** certify every field on every source document as correct. The detailed JSON audit lists replayed fields, changes and remaining warnings for each of the 59 saved records. It is a review aid, not an automatic database patch or a complete ground-truth dataset.

- **INV-27** contains invalid printed calendar dates. The system must not invent a valid invoice date.
- **INV-30** explicitly prints VAT 3,250 against a total of 2,999. **INV-31** prints a negative payable amount that does not reconcile with its current charges and prior credit. Preserve the printed values and flag the contradictions; do not change them just to pass arithmetic validation.
- **INV-43** remains a blurred, inconsistent retail read. Its invoice number, subtotal and item digits require a clearer source or manual verification. Other small OCR character errors, such as identifiers on INV-02/INV-41 and the “5kg” description on INV-42, also need checking against the originals.
- **INV-06/INV-10**, the cropped **INV-23/INV-24/INV-32**, and missing-page utility bills cannot support a complete verified extraction. The new null behavior prevents unavailable values from looking like real zeros. Invoice dates/identifiers that remain unreadable are explicitly reviewable.
- Some line-item descriptions, quantities, addresses, discount bases and tax breakdowns remain unresolved. In particular, the gross service amount on TRI-Q and the net-after-discount subtotal on the Sun statement do not share the same accounting basis as a standard retail table. Remaining reconciliation warnings are retained.
- The supplied model/vision timeouts are not fixed by asserting that OCR fallback is accurate. The existing 30-second per-file processing budget starts before OCR. Slow OCR can exhaust the model's time allowance. Model availability, cold-start performance and deployment budget settings still need a live retest. No new live provider request or SLA benchmark was run here.

## Validation

- **101 new tests passed**, including all 59 captured records, full-parser replay for the confirmed corrections, source contradictions, foreign-currency controls, exact duplicate detection, null persistence/export, and an AppTest of the actual History edit form.
- Broader runnable suite: **526 passed, 6 pre-existing failures**. The failures are the four old UI source-string assertions, the subprocess dependency-path test, and the older OpenRouter API-key-name expectation. They were also present in the previous revision.
- Two API TestClient tests and one asynchronous upload test were excluded because the restricted local socket environment stalled those tests in the previous runs. They remain included for deployment-machine execution.
- Database migration was run twice against a **copy of the supplied database**: all **59 rows retained**, **14 extra copies flagged**, SQLite integrity **ok**, and original non-review fields unchanged. No supplied production file was modified.
- ZIP integrity, duplicate archive-entry checks, Python syntax checks and original packaged database preservation are verified by the accompanying manifest.

## Installation and reprocessing

1. Back up the current database and storage. Extract revision 4 to a new directory. Retain the deployment's existing `.env`, database and storage; do not replace them with the ZIP's original sample database.
2. Restart the application. Startup adds and backfills `content_key`; existing duplicate rows are retained and flagged for review, not deleted.
3. Existing extracted values are **not automatically rewritten**. Use History to correct them, or remove the affected record through the normal workflow before re-uploading. Content duplicate detection will otherwise intentionally reject the copy.
4. Keep review warnings visible. Supply missing pages or clearer originals for unresolved fields. Retest the batch in different orders and confirm that one failed file does not suppress the next file's verification.
5. API consumers must allow **null subtotal, total_amount and currency** for unverified outputs. An explicit numeric zero remains zero.
6. Run the complete suite, including the three socket-dependent tests, and a live OCR/provider batch on the deployment machine before treating the outputs as approved accounting records.
