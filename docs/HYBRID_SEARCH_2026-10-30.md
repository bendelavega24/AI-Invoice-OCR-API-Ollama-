# Hybrid Search QA change log — 2026-10-30

**Base:** AI-Invoice-OCR-API-Ollama-Dan_QA_HistoryDate_PerformanceAudit_2026-10-29.zip

## Integrated

- `ai/local_search_parser.py`: conservative local-first date, amount, currency, vendor, category, status, lock, presence, and log queries. A meaningful unparsed fragment forces LLM fallback.
- `ai/search_interpreter.py`: `interpret_hybrid_search` validates all plans, invokes model only for requests requiring interpretation, and blocks silent no-op plans. Sends no full vendor list to the remote model.
- `services/search_service.py`: `apply_hybrid_search` pushes supported predicates into read-only, SQLAlchemy parameterized SELECTs, and uses existing exact post-filtering. Existing row retrieval and manual filters are not modified.
- `ui/components/ai_search.py`: model-agnostic AI Search display, interpretation origin and clear behavior; old successful search remains applied until another succeeds or is cleared.
- History, Reports, Log: enabled new search executor and preserved manual filters and export selection. History and Reports pass available currencies to enforce safe amount searches.
- `tests/test_hybrid_search_2026_10_30.py`: local, remote fallback, privacy, SQL and currency regression tests.

## Known limitations

- Uncommon or compound user phrasing still requires the configured Groq/Ollama model, with the existing retry/fallback behavior.
- Arbitrary aggregations such as 'top 5 vendors', and inferred error categories are not guaranteed; unsupported words go to LLM and the allowed filter schema is the only executable output.
- In History, the current-month / previous-month page sections remain distinct; the Search bar scopes to the visible section, not the entire database.
- The pages still load the visible database rows before search filtering. SQL pushdown validates/read-filters supported fields but does not yet change initial list retrieval; very large databases may need further pagination optimization.
- This release was unit-tested, not live-tested with Groq/Ollama or in a Windows Streamlit browser.

## Verification

Run: `python -m pytest -q tests/test_hybrid_search_2026_10_30.py` then `python -m pytest -q tests/`.
Three existing UI tests require Streamlit and one parser test uses an outdated mock function signature; these were already present in the base.
