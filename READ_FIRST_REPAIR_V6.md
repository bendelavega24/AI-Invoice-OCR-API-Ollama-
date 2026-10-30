# October 15 repair — v6

Based on AI-Invoice-OCR-API-Ollama-Dan-QA-Fixed-v5.zip.

## Upgrade on your Windows PC

1. Stop Streamlit and back up your existing application folder, especially `.env`, `data`, and `storage`.
2. Extract this ZIP into a separate folder first. Copy its application files over the existing application, preserving your existing `.env`, `data`, and `storage` folders. The package contains no replacement database, account records, API keys, or uploaded invoices.
3. Start the application with your existing Python environment and usual launch command. No new application dependencies were added.
4. Keep your existing API/local mode selection. Local fallback requires Ollama to be running with the configured text/vision models installed.
5. Reprocess the affected invoice. Old saved results are not automatically rewritten. If duplicate protection blocks re-uploading, use a separate test installation/database, or back up and remove only the incorrect test record through the app's existing controls.

The old `PROCESSING_BUDGET_SECONDS=30` can remain in `.env`: v6 no longer uses that entry to time out models. Do not replace your working `.env` with the example.

Optional settings (defaults apply even when absent):

```ini
API_TEXT_BUDGET_SECONDS=150
LOCAL_TEXT_BUDGET_SECONDS=600
API_VISION_BUDGET_SECONDS=180
LOCAL_VISION_BUDGET_SECONDS=360
```

These are separate cumulative per-file model allowances. They include model calls and retry backoff, but exclude initial OCR and gaps spent preparing image crops. Existing per-request timeouts still apply. They are not promised end-to-end completion times: difficult invoices using fallback can take several minutes. Real API/network/CPU timeouts remain possible and visible.

## Repairs

- Replaced the pre-OCR 30-second deadline with independent API/local text and vision budgets. OCR cannot exhaust model time, and API exhaustion cannot exhaust local fallback or vision allowances.
- Stops futile retries after local budget exhaustion and distinguishes this from a network timeout. Local exhaustion does not put a provider into outage cooldown.
- Separates initial extraction failure from correction failure in the warnings.
- Identifies the actual provider and local fallback in diagnostic traces, retaining separate API attempt details.
- Does not report a successfully recovered API vision failure as unresolved after local fallback. Suppresses the redundant Upload warning when the same vision warning is already listed.
- Preserves seller-address segments explicitly visible in the header despite similar locality words in a customer master address.
- Recovers invoice numbers from their spatial relationship to a Sales/Service Invoice heading and No. label. Multiple candidates remain unresolved.
- Preserves an accepted image-read customer name instead of shortening it back to fragmented OCR text.
- Adds focused image verification for unresolved financial summaries. Acceptance requires an independent image read confirming all components, changing exactly one component, preserving the payable, and balancing. Unclear or contradictory reads remain for review.
- Recovers missing service rows from the table image only when all readable amounts agree with the payable and there is no discount/withholding ambiguity. Amount-only rows are represented as one service charge (quantity 1, unit price equal to the row amount); the trace explicitly identifies this as a display convention, not a printed quantity.

No invoice numbers, vendor names, dates, or expected financial amounts were hardcoded into production recovery rules.

## API settings

Your existing `.env` is preserved. Supplied logs show a Groq endpoint with cloud model `qwen/qwen3.8-27b`. Those requests failed before being sent, so the logs do not establish whether the endpoint accepts that model. Check its ID in your provider account before live testing. Vision requires an image-capable model; configure `LLM_VISION_MODEL` separately if needed.

For new installations only, `.env.example` now uses the consistent OpenRouter URL and `openrouter/free` pairing. Switching to OpenRouter requires an OpenRouter key, not a Groq key. This does not change an existing configuration. No invoices were sent to external services during repair or testing.

## Verification and limits

Regression tests exercise timing, fallback isolation, provider modes, warning handling, and invoice/financial/address recovery. The October 15 recorded OCR is included as a test fixture. A full pipeline replay uses recorded OCR and **simulated** model/image responses: it verifies evidence handling, not live recognition accuracy.

Live PaddleOCR/TrOCR inference and Groq/Ollama calls were not tested: this environment has no installed neural OCR models, running Ollama, or user API credentials. The eager torch import was stubbed only in an external test harness that is not shipped. Test dependencies differ from the Windows runtime; unrelated requirements.txt pins were retained. A fresh full dependency installation was not validated.

Check these against the original after reprocessing:

- Invoice number: 7512
- Handwritten date appears to read August 24, 2026
- Customer: TSUKIDEN GLOBAL SOLUTIONS INC
- Vatable sales: 250.00; VAT: 30.00; VAT-exempt sales: 1,967.40
- Total amount due: 2,247.40
- Seller address includes San Antonio Pasig City 1603
- Service: Utilities for Aug 2026, amount 2,247.40
- Customer address/TIN remain blank when blank on the original

A recovered record remains needs_review if extraction failed or required evidence is still missing. Keep new traces and app.log if live processing still fails.

### Automated results

455 regression tests passed across the final regression run and isolated UI confirmation (including 19 new October 15 tests). The UI harness explicitly disabled Streamlit development mode, which the temporary dependency installation path otherwise enabled. All Python sources passed syntax parsing. ZIP integrity and Windows-safe relative paths were checked.
