# AI-Invoice-OCR

Local, privacy-friendly invoice extraction: OCR (PaddleOCR/Tesseract/EasyOCR)
+ a local LLM (Qwen 2.5 / Llama 3 via Ollama) turn scanned invoices and PDFs
into structured, validated, searchable data — no cloud calls required.

## Features

- Multi-engine OCR with automatic fallback and image preprocessing (deskew,
  denoise, adaptive threshold)
- Schema-constrained LLM extraction with automatic self-correction retries
- Business-rule validation (totals reconciliation, required fields, currency
  format) and a per-invoice confidence score
- SQLite storage via SQLAlchemy, with vendor deduplication
- Streamlit UI: Upload, Dashboard (spend analytics), History, Reports
  (Excel/CSV/PDF export), and Activity Log
- Local Qwen2.5:7b natural-language search on History, Reports, and Log; the
  model translates plain-English requests into validated filters and never
  executes raw SQL
- Optional FastAPI REST API for integrations
- Fully local — invoice data never leaves your machine


## Using any hosted LLM (Groq, OpenRouter, Together, Cerebras, ...)

Any site with an OpenAI-compatible `/chat/completions` API works. Only three values change in **.env**
(never commit it):

```
LLM_PROVIDER=api
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=qwen/qwen3.8-27b
```

Switching site = new key + new base URL + new model id. Restart the app. `LLM_PROVIDER=ollama` goes back to local.
The retry/fallback notes below apply to every hosted provider.

## Using OpenRouter instead of local Ollama

1. Create a key at https://openrouter.ai/keys and put it in your **.env** (never commit it):

   ```
   LLM_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-...
   OPENROUTER_MODEL=openrouter/free
   ```

2. Restart the app. Text extraction, AI Search and (if enabled) vision verification all go through OpenRouter.
   Set `LLM_PROVIDER=ollama` to switch back to the local models.

With `LLM_PROVIDER=ollama` the local-model path is exactly the original: same requests, same options, same timeouts.

Retries: transient OpenRouter failures (HTTP 408/425/429/5xx, connection errors, an empty answer, or an answer that is
not valid JSON) are retried up to `OPENROUTER_MAX_RETRIES` times with exponential backoff (`Retry-After` is honoured),
within `OPENROUTER_RETRY_BUDGET_SECONDS`. Timeouts get `OPENROUTER_TIMEOUT_RETRIES` extra tries. Permanent errors
(400/401/402/403/404) are not retried. Each retry is recorded in the diagnostic trace (`usage.retries`).

Automatic fallback: with `LLM_FALLBACK_TO_OLLAMA=true` (default), a failed OpenRouter request (invalid key, no credits,
rate limit, timeout, 5xx) is repeated on local Ollama, and OpenRouter is skipped for `OPENROUTER_COOLDOWN_SECONDS`
(600s for 401/402/403) or `OPENROUTER_SHORT_COOLDOWN_SECONDS` (60s otherwise). Ollama must be running with the
model pulled for the fallback to work. Failover details are stored in the diagnostic trace (`fallback_from`).

Notes: `openrouter/free` picks a random free model per request, so results can vary between calls and free models
are rate limited. Invoice text/images are sent to third-party providers - do not use free models for sensitive documents
unless you have checked their data policies. Pin a specific model id in `OPENROUTER_MODEL` for repeatable results.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen2.5:7b
python app.py ui
```

See `docs/user_manual.md` for full setup instructions, `docs/architecture.md`
for how the pipeline fits together, and `docs/api.md` for the REST API.

## Tech stack

| Category | Tool |
|---|---|
| Language | Python 3.11+ |
| UI | Streamlit |
| OCR | PaddleOCR (primary), Tesseract, EasyOCR |
| AI | Ollama (Qwen 2.5 / Llama 3) |
| Image processing | OpenCV, Pillow |
| PDF processing | PyMuPDF |
| Database | SQLite + SQLAlchemy |
| Validation | Pydantic |
| Data / export | pandas, openpyxl, reportlab |
| API | FastAPI + uvicorn |
| Testing | pytest |

## Project structure

See `docs/architecture.md` for a full breakdown of each folder's role.

## Running tests

```bash
pytest tests/ -v
```


## Login & user accounts (offline)

The UI requires a sign-in. Accounts live in the local `users` table (passwords stored as salted PBKDF2-SHA256 hashes — no external service).
Every logged action (upload, edit, lock, delete, export…) is recorded in the **Log** page under the signed-in username.

* **First run:** an admin account is created automatically — username `admin`, password `admin1234`
  (override with `DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD` in `.env` *before* first start). You are forced to choose a new password at first login.
* **Admins** get a **Users** page to create accounts, deactivate/reactivate, change roles and reset passwords. New/reset accounts must set their own password at next login.
* Login is restored from a local browser cookie after refresh or reconnect while the same Streamlit server process is running. Stopping/restarting Streamlit or shutting down the PC requires a new sign-in. Use **Sign out** to end it. Clearing browser cookies, disabling an account, or resetting its password also invalidates access.
* Each new sign-in opens **Home**. Signing out clears temporary Upload results and page selections; saved invoices remain in History.
* The REST API (`api/`) is not covered by this login; changes made through it are logged under the PC's OS username.

**Multi-PC use:** see `SETUP_SERVER.md` (one Host PC runs `start_server.bat`; other PCs just open its address in a browser).

## Scanner, log downloads, and printing

Upload now supports direct flatbed scanning through free NAPS2 on Windows. Log downloads all filtered/searched records as Excel, CSV, or PDF and supports printing. Reports prints the same A3 PDF layout used by Generate Export, with browser printer selection. See [SCANNER_PRINT_SETUP.md](SCANNER_PRINT_SETUP.md) for installation and use.

## CPU speed and verification reliability

See [CPU_SPEED_UPDATE.md](CPU_SPEED_UPDATE.md) for the batch vision-timeout guard, earlier cleanup before text correction, review warnings, and new timing fields. Both improvements are enabled by default without changing your existing .env.

## QA invoice handling and duplicate policy

This build accepts real transaction documents even when some invoice fields are missing, but saves them for review rather than inventing values. Missing invoice number, invoice date, or total amount can therefore be stored as blank when other transaction evidence exists. An explicit zero-charge invoice is also valid input; a blank/unused invoice or receipt form with no transaction evidence is rejected.

Payment state is stored separately from processing state as **Paid**, **Unpaid**, or **Unknown**. Duplicate detection no longer treats the invoice number as globally unique. It considers vendor identity, invoice number when present, date/amount, line-item signature, source/page fingerprint, and payment state. This allows the same invoice number from different vendors and reused handwritten numbers with different purchased items, while still blocking the same logical invoice uploaded again in another image format. Paid and unpaid lifecycle copies may coexist.

See `docs/qa_invoice_rules.md` for the detailed rules and QA examples.
