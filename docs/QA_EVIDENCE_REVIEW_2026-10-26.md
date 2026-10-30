# v6 document-evidence QA review — 26 October 2026

## Scope and safety

Base: `AI-Invoice-OCR-API-Ollama-Dan-QA-Fixed-v6.zip` (not the October 21/23 builds). Invoice files came from the prior QA images archive and OCR trace fixtures. This is a **development QA build**; source corrections are generic and evidence-driven, not filename/value-specific replacements. The QA replay uses saved OCR and intentionally **does not call Groq, Ollama or a live Streamlit UI**. It does not repair old records in SQLite; upload and process the originals again after backing up application data.

### Completed source-code changes

- New `ai/qa_source_review.py`, connected into `parser/invoice_parser.py`, checks source evidence and OCR geometry before final validation.
- MERALCO: independently match the supplier business-center header vs customer header; recover printed Bill Date from its own geometric column; assemble complete electricity charge rows only if the independently printed current charge agrees with their sum. Do not invent VATable Sales or VAT when no such values are printed. Existing due/previous balance remains separate.
- PLDT: recover printed monthly service fee and VAT from independent labels, preserve CR balances as negative, remove duplicated category total when a labeled plan row already represents that charge, and clean customer addresses of stub/billing-summary amounts. Reject a subscriber address incorrectly copied into vendor address. Warn for ambiguous statement ID.
- Globe: restore an explicitly printed monthly fee even if zero; include a negative Current Bill adjustment only if current-bill arithmetic corroborates it; keep VAT out of the line items; recover the repeated labeled customer mailing address and avoid substituting billing-period dates for invoice dates. The recovered Globe adjustment is **inferred and flagged for review**.
- Sun Cellular: keep common trading brand when expressly printed; independently recover service fee, usage, and printed credit only if they reconcile with printed subtotal and current charges. Reject a billing-period start mislabeled as invoice date and request image verification.
- Converge: flag divergent pre-tax charge candidates as requiring review rather than selecting a supposedly exact value with false certainty. Remove tax summary rows from merchandise/service line items.
- Parser/validator: negative prices for actual credit, adjustment, discount and subsidy rows are permitted; adjustment/current-bill tax arithmetic is checked before issuing a false line-items/subtotal warning.
- For very low-resolution inputs, added offline `tools/enhance_low_resolution_invoice.py` (bicubic enlargement, gentle local contrast and limited sharpening); it cannot restore missing pixels.

### Requested invoice QA disposition

| Invoice | Outcome of available evidence checks |
|---|---|
| Addl Invoice_Page_2.pdf | Customer TIN `007-848-122-00000` recovered from labeled line. **Only first of two indicated pages is present** in the saved fixture: review complete PDF. |
| ParkingTickets1.png / ParkingTickets2.png | Existing seller normalization includes the Jazz Residences address and the NCR/fourth district/1209 suffix. Variants in source spelling should be visually reviewed. |
| Sample Invoice_Page_2.pdf | Source VAT `147.53` retained. |
| INV-34.jpg | Zero-priced Monthly Plan remains an explicit line item (zero is not missing). |
| INV-33.jpg | Source contains `1,116.07` AND `1,116.08` as different pre-tax references, with `133.92` VAT and `1,250.00` total; contradiction generates a review warning. |
| INV-28.png | MERALCO branch/customer header restored; charges include Government Taxes, FIT-All, prior balance, and documented total `17,972.99`. VAT and VATable Sales are **not printed**: kept missing internally and flagged, not fabricated. |
| INV-04.pdf | Printed service-plan charge is preserved; duplicate summary row dropped where it would cause double counting. Net `1,159.82` corroborated. |
| INV-05.jpg | MERALCO sender/customer header and electricity line rows recovered; **original Bill Date is 24 September 2022**, not 30 April 2006. |
| INV-07.jpg | OCR source shows **₱8,000.00 monthly service fee and ₱960.00 VAT**. ₱960.00 is not VATable Sales. Subscriber location recoverable from printed stub. |
| INV-08.jpg | Printed total `1,433.26`; credit `0.15 CR` stored as -0.15; customer address separated from billing figures. Unsupported vendor address cleared for verification. |
| INV-09.jpg | VAT `149.79`, MRF and inferred adjustment -99.00 appear as separate rows; VAT excluded from line items. No explicit invoice date was seen. |
| INV-13.png | Tax summary `TAXES` not treated as an item. Full printed customer address needs source/image confirmation. |
| INV-14.jpg | Fee `2,763.39`, VAT `331.61`, payable `3,089.30`; subscriber address separated from summary; vendor address copied from subscriber cleared. The distinct SOA identifier remains **unverified** due to unreadable/corrupt OCR digits. |
| INV-15.jpg | Net `1,159.82`, VAT `139.18`, and SOA identifier recovered; `Value Added Tall` removed as purchased item. |
| INV-16.png | Sun brand, net `376.32`, VAT `45.16`, fee `312.50`, usage `79.84`, printed credit -16.02 reconcile. Statement date and difficult small identifier **require visual checking**, OCR loses some digits. |
| INV-17.jpg | Seller office, Bill Date `22 May 2023`, Generation `5,652.57` and Applied Credits -0.17 recovered via independently reconciling printed charge table. |
| INV-18.jpg | Customer mailing block recovered including Makabuhay / Silang / Cavite / 4118; bill number only `1` in OCR and account-number fallback is **provisional**, not a true confirmed invoice number. No invoice date explicitly printed. One-time charge `891.96`. |
| INV-19.jpg | No customer name/address/invoice date printed; invalid repeated OCR table-price placeholders suppressed. The seller office street is severely blurred; manual verification required. |
| INV-20.jpg | Handwritten vendor address/invoice number apparently absent; don't invent them. No reproducible saved fixture was available for automated full-field verification. |
| INV-21.jpg | Existing source recovery contains `1,000.00` and `1,500.00` in the requested item rows. Other financial discrepancies may require further review. |
| INV-22.jpg | Source-supported cooperative short-name normalization available, address cleared if no explicit office label. No saved OCR fixture to verify all image details. |
| INV-06.jpg / INV-10.jpeg | Original files have only **298×409** and **252×356** pixels, respectively. Enhance for possible better OCR but **do not infer absent characters**. If required invoice identity/details remain illegible, reject or request better source image rather than silently accepting inaccurate extraction. |

### Additional detected problems

- A PLDT plan description can represent the **same** monthly fee as the generic service-charge category total; counting both would double-bill line items.
- A PLDT subscriber address can be mistakenly used as the **vendor address**, and the customer address can contain an entire bill summary. Both are now guarded against where the source evidence supports correction.
- Telecom credits and electricity Applied Credits/Subsidies can legitimately be **negative**; the previous validator incorrectly flagged these credit rows as invalid negative prices.
- Many single-page electricity records state **Page 1 of 2**, and some PLDT statements state **Page 1 of 3/4/7**. When the complete multi-page invoice is required, the missing pages should trigger review. Multi-page *one invoice* is distinct from multiple separate invoices in one file.
- Printed VATable Sales and a category subtotal are not always the same on utility statements. Validation should use individual supported identities instead of forcing all amounts into a single tax formula.

### Verification limits

- Source changes are tested using 18 focused scenarios and a replay of 49 available saved OCR fixtures; there was **no live API/Ollama extraction**, scanner use, or Streamlit browser interaction.
- Low-confidence/handwritten values require a fresh run with the original image or manual review. Visual observations in a particular test fixture do not justify global constants. Document-specific incomplete recognition remains unresolved where source evidence cannot support safe recovery.
- Backup `.env`, `data`, and `storage` before replacing the application. This ZIP does not contain existing invoice records.
