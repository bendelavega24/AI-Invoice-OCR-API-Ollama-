# QA October 29 — MERALCO printed dates, History currency totals and performance

## Source and scope

Base: `AI-Invoice-OCR-API-Ollama-Dan_QA_TeammateMerge_2026-10-29.zip`.
Evidence: `data_latest.zip` and `storage_latest.zip` (examined for this review only; not included in the release).

## Fixed: History currency mixing

`ui/pages/History.py` now calls the existing `services.currency_totals.totals_by_currency` helper for each History result section, so USD and PHP never contribute to the same aggregate. Unknown currencies are shown separately as `UNSPECIFIED`. The row-level values were already currency labeled. This change is display-only and does not rewrite saved invoice totals.

## INV-27.png: the Bill Date is printed, but invalid

The supplied invoice image clearly labels `Bill Date` and prints `31/11/2021`, which cannot be a calendar date (November has 30 days). The `Billing Period` (`32/13/2021 to 00/00/2021`) and `Due Date` (`31/02/2021`) are independently invalid. The absence of a normalized ISO Invoice Date (`-`) is appropriate: filling it with the billing period, due date, or November 30 would invent a corrected value. A new explicit **Invoice Date verification** issue names the source's `31/11/2021` and prohibits borrowing adjacent dates. The History evidence renderer also adds this note to existing saved records whose validation issues captured the bad source date. No database modification or reprocessing of existing records occurs automatically.

A *valid* Bill Date in this MERALCO layout continues to be used as Invoice Date (unchanged). The new rule only concerns invalid printed dates.

## Why some uploads took more than 900 seconds

The saved `pipeline_stages.timing_seconds` show slow local OCR dominating two runs: 783.2 seconds of OCR on the first INV-27 attempt; 896.4 seconds of OCR for INV-26. Both invoked `paddleocr+trocr` although virtually all regions were classified as printed: INV-27 had 146 printed and 2 handwritten; INV-26 had 139 printed and 1 handwritten. OCR engine source files `ocr/ocr_engine.py`, `ocr/preprocessing.py`, `ocr/detail_recovery.py` were identical between the October 28 and October 29 ZIP builds; therefore this timing evidence cannot establish the teammate merge *caused* the slowdown. Four-angle auto-orientation analysis, per-region OCR, optional TrOCR and model startup can be costly. The logs also show Groq 429 backoff/retries, which may add time after OCR.

For a controlled speed comparison, use the *same printed-only invoice* on the *same machine*, with identical `.env`, OCR model cache and image, after warming model loading. Record four test runs (two baseline, two modified) using `OCR_AUTO_ORIENT_ENABLED` unchanged. Compare `ocr_entire_source_file` separately from `pipeline_after_ocr`. To isolate false handwriting detection, use the Upload page's `Manually override handwriting detection` -> **Printed** option on a genuinely printed invoice; do not use this on genuine handwriting. Separately test `OCR_AUTO_ORIENT_ENABLED=false` **only** on known upright scans and compare extraction accuracy before adopting it. Avoid making multiple simultaneous performance changes.

## QA verification

Targeted tests: 20 passed (October 29 patch + previous October 28/29 functionality).
Full suite: 781 passed, 4 existing failures (three Streamlit tests not runnable in this environment; one pre-existing parser mock signature mismatch).
Live Streamlit and Groq processing have **not** been run in this environment. The existing invoice database, uploads, debug data and credentials were not changed.
