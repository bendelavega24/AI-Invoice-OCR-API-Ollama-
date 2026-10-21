# AI Invoice OCR — Version 6 operating guide

AI Invoice OCR is a Python/Streamlit desktop-oriented invoice capture, extraction, validation and reporting system using SQLite. Its OCR stack includes PaddleOCR for printed text and optional TrOCR for handwriting. An OpenAI-compatible API such as Groq can run extraction; Ollama provides an optional local model path. External API processing sends invoice content to the selected provider, so use only approved documents and observe your organization's data policies.

## Setup and launch

1. Install Python and the dependencies: `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env`, configure `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL` and `LLM_MODEL` for your API provider. For a local Ollama setup, select the Ollama provider and install/pull the configured local model.
3. Use `python app.py ui` to launch the Streamlit interface. See `SETUP_SERVER.md` for office/LAN deployment and login details. Never distribute the `.env` file or API keys.
4. Keep `data/invoices.db`, processed invoice originals and application storage backed up before replacing a version.

## Uploading and scanning

**Exactly one invoice per file.** Do not upload a PDF or image containing two or more independent invoices. Multi-invoice input is not supported because it increases processing time and reduces accuracy. Split different invoices into separate files first. You may upload several separate files in one batch, provided each contains only one invoice. Multiple pages belonging to a single invoice can be used when page continuation is clearly indicated; check the History preview to ensure every page is present.

For a scanner, **scan one invoice at a time**. Scan subsequent pages only if they are part of that same invoice. Use 300 DPI as a starting point, keep page edges visible, and avoid blur, shadows or unreadable handwriting. See `SCANNER_PRINT_SETUP.md` for device setup and printing.

## Processing and review

The pipeline reads uploaded pages, performs preprocessing and OCR, invokes the configured language model, normalizes extracted fields, validates amounts, and saves accepted invoice records in SQLite. Review invoice number, seller/customer identification, date, tax IDs, addresses, handwritten entries and line items before relying on results. OCR and generative AI can misread faint writing or aligned tables. Rejected or failed documents should be corrected and resubmitted; do not assume partially extracted data is reliable.

Validation uses `Total Amount Due = Vatable Sales + VAT + Zero-Rated Sales + VAT-Exempt Sales − Discount − Withholding Tax`. A printed withholding tax is a deduction separate from discounts. Explicit printed zero line-item prices must not be replaced by guessed prices. The equation only applies when the displayed fields represent the same tax basis and period; a balanced result alone does not prove the extraction is correct.

## Reference documents

- `SCANNER_PRINT_SETUP.md`: scanner and printer setup, hardware caveats.
- `SETUP_SERVER.md`: Windows/network deployment.
- `docs/technical_reference.md`: application architecture, API, troubleshooting and QA limitations.
- `docs/qa_test_cases.csv`: existing QA case reference data.

## Notes

Free provider plans may enforce request-size (HTTP 413) and rate (HTTP 429) limits, and model behavior can differ per call. Reduce image payload resolution or number of pages and retry at a later time where appropriate; verify the provider's current policies. Use local inference if confidential documents must remain on-device.


## October 20, 2026 QA update: results and validation
- For clearly formatted retail tables, post-processing now preserves the item-by-item printed Qty, Unit Price and Total Unit Price, including rows with a printed zero amount.
- On the Dashboard, **Spend by Month** uses invoice dates by default. Select **Upload date** to view upload-based monthly totals. Months represented by only one data point now display as bars.
- Unresolved financial and extraction validation checks display on the **Upload** page and under the selected invoice on **History**. Some legitimate credits and account statements require manual reconciliation; the system does not silently change an inconsistent printed Total Amount Due.
- **Incomplete/blank invoices are warnings**, separate from a processing exception; duplicates are warnings too.
- If upgrading from an earlier version, **back up your `.env`, data folder, and storage folder** before installing. SQLite automatically adds a nullable `validation_issues` field; previous records remain unchanged until reprocessed.
- Never use unverified/unclear invoice information as an authoritative amount to pay. See `MODIFICATION_STATUS.md` for case-by-case QA findings and outstanding limitations.

## Field-level evidence and review (October 21, 2026)

Each newly processed invoice retains **per-field evidence records** (including every extracted line-item description, quantity, unit price and total amount) in SQLite as JSON in `invoices.field_evidence`. The prior single overall invoice confidence remains **internal**. The History screen deliberately hides all confidence percentages: normal fields show only their values, and fields requiring verification receive an amber highlight with a **⚠ Verify** label. The line-item table retains only four useful columns (Item, Qty, Unit Price, Total Unit Price); individual questionable cells are highlighted amber. A collapsed **View verification reasons** section lists details on demand. Upload and Edit continue to surface verification issues.

The underlying scores are **heuristic evidence-support scores, not calibrated probabilities that a field is correct**; they are stored but are no longer shown as percentages in History. They use exact/partial OCR matches, available OCR line confidence, proximity of numbers to their line-item description, arithmetic checks and unresolved validation issues. A numerical value merely appearing somewhere on a receipt does not establish the correct owner. If a value is unsupported or conflicts with arithmetic, the interface asks for manual verification. Optional fields not present on the document are marked *not provided*, not automatically treated as errors; app-derived fields such as Category do not receive fake OCR scores.

Existing invoice records lacking saved scores can show clearly labeled **historic estimates based on their saved OCR text**. They are not identical to extraction-time scores; if no OCR text was saved, no score is fabricated. When someone manually changes a field or line-item cell, the previous automatic score is invalidated and marked *manual edit* rather than silently reused. This feature never changes financial values to force an equation to reconcile and does not make an additional cloud request. Back up your database first; startup automatically adds the nullable `field_evidence` column to an older SQLite database.

## October 21 — simplified verification display

Confidence remains saved per field and line-item cell, but percentages are hidden on the History detail screen. Only values with actionable extraction warnings are highlighted in amber; hover over a highlighted header field for its warning or expand **View verification reasons** to read all flagged fields and cells. Manually corrected fields are not marked as unverified merely because the previous automatic OCR confidence was invalidated. Arithmetic/validation warnings remain visible. This is a UI-only change: invoice data, extraction logic, and confidence scoring have not changed.

## October 21 — financial detail display and optional fields

The History details panel now displays `0.00` for **unextracted** values in Vatable Sales, VAT-Exempt Sales, Zero-Rated Sales, VAT, Withholding Tax, and Total Amount Due. This is a **display placeholder**, not an actual extracted zero: missing amounts remain `NULL` in SQLite so validation, search, and review can distinguish them from explicitly recorded zeros. A single small explanatory note appears when any of those values was unextracted, and missing Total Amount Due continues to raise a review warning. Opening an invoice in Edit and saving without changing an optional zero does not replace a missing value with a stored zero.

Due Date, Tax Rate, and Payment Terms are optional document fields. Due Date supports payment scheduling, Tax Rate can aid tax review where applicable, and Payment Terms records conditions such as Cash/Net 30. They are retained internally and are not required for invoice acceptance. They are not displayed in client invoice details or reports.

### Client-facing invoice fields

Due Date, Tax Rate and Payment Terms are **not displayed** in the History
invoice detail (or its edit form), nor included in generated invoice CSV,
Excel or PDF reports and print previews. These optional values remain in the
internal database/extraction/validation pipeline for backward compatibility.
Do not interpret this visibility change as deletion of existing stored data.

## October 21, 2026 — approved History detail fields

The **History invoice detail heading uses the uploaded filename** (for example,
`INV-39.png`), with invoice number or internal record ID used only as a fallback
when the filename is unavailable. The filename is no longer repeated among the
detail fields. **Invoice #** remains in the approved details exactly once. The
edit-screen heading follows the same filename-first convention.

Only these client-approved fields are shown in the History detail panel:

- **Document details:** Vendor, Vendor Address, Vendor TIN, Customer,
  Customer Address, Customer TIN, Plate # (when present), Invoice #,
  Invoice Date, Date Uploaded, Category.
- **Financial and state details:** Vatable Sales, VAT-Exempt Sales,
  Zero-Rated Sales, VAT, Withholding Tax, Total Amount Due, Currency,
  Status, Locked.

**Customer Contact, Current Charges and Previous Balance are hidden as
standalone summary fields**, as are Due Date, Tax Rate and Payment Terms.
These values remain stored internally and available to the validation
pipeline. They are omitted from CSV, Excel, PDF and print-report export
columns. Existing *genuine extracted line items* named Current Charges or
Previous Balance still appear in the line-item table, but the system does not
add synthetic line items from the summary fields (which could double-count
statement totals). Confidence review highlights and financial validation
warnings remain available for the approved fields.

Reports still include the existing technical **ID** and **Filename** columns
for record traceability; this History-only heading change does not alter those
identifiers in report exports. The History page never repeats Filename as a
detail field.

**Line-item quantity display:** In History, whole quantities are shown without trailing decimal places; fractional quantities are preserved when present (for example, 1 and 0.75). This is display-only and does not modify quantities stored or used in calculations.
