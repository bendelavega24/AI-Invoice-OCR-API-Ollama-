# Consolidated Build — Regression Test Report (26 October 2026)

**Selected base:** October 26 Fixed-v6 EvidenceCorrections.

**Selective feature donor:** October 23 ConditionalVision.

## Results in the available Python environment

- Full `python -m pytest -q --disable-warnings`: **745 passed, 4 failed** (26 warnings).
- Source-focused tests for conditional vision, review UI, and October 26 invoice evidence pass.
- Migration exercised on a temporary pre-existing SQLite database with its `field_evidence` column intentionally absent: migration restored the column and retained invoice ID 41.
- Archive integrity tested after packaging.

### Four remaining failures

1. `tests/test_2_0_dan_merge.py::test_parser_calls_master_before_boundary_and_validates_final_data` — an existing mock replaces `apply_final_master_pass` with a function that lacks the modern `seller_header` parameter. Production implementation supports it. This failure also existed on the selected October 26 base.
2. `tests/test_qa_audit_round4.py::test_actual_edit_form_keeps_blank_distinct_from_entered_zero` — `streamlit.testing` not installed in the test environment.
3. `tests/test_qa_oct2026.py::test_quality_component_displays_saved_warnings` — `streamlit.testing` not installed in the test environment.
4. `tests/test_qa_output_round2.py::test_pdf_all_pages_and_selection` — `streamlit.testing` not installed in the test environment.

These test failures should not be mistaken for verified production success; run Streamlit tests on a computer with all dependencies installed.

### Not verified here

- A live Ollama `qwen2.5:7b` or `qwen2.5vl:7b` extraction, API-rate-limited Groq fallback, actual OCR GPU/CPU performance, scanning hardware, or a browser-based Streamlit session.
- The outputs of all the QA invoices **after a fresh re-upload**. Source-only tests cannot establish that remote/local LLM inference always extracts the exact same values.

### Deployment advice

Copy the updated source files over a backed-up installation. Keep the existing user-owned `.env`, SQLite database, uploaded scans, and storage JSON. The distributable ZIP intentionally excludes those runtime files. `init_db()` adds the nullable `field_evidence` column to existing SQLite databases on startup. Never overwrite an existing user database with an empty one.
