"""
TC001 / TC002 — a valid PDF / PNG invoice is accepted but major fields are extracted wrongly.

Cause covered here: the local-Ollama extraction request set no num_ctx, so Ollama used its default context window
(2,048-4,096 tokens). The extraction prompt is ~4,500 tokens before any OCR text is added, so EVERY invoice
overflowed it and Ollama silently dropped tokens from the front of the prompt (instructions, schema, top of the
invoice text — where the vendor and invoice number are).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging

import requests

from ai import extractor
from ai.prompt_builder import build_extraction_prompt
from config.settings import settings


class _Resp:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def test_extraction_request_sets_a_context_window(monkeypatch):
    seen = {}
    monkeypatch.setattr(requests, "post", lambda url, json=None, **kw: (seen.update(payload=json) or _Resp({"response": "{}"})))
    trace = {}
    extractor._call_local_ollama("PROMPT", trace)
    assert seen["payload"]["options"]["num_ctx"] == settings.OLLAMA_NUM_CTX
    assert trace["num_ctx"] == settings.OLLAMA_NUM_CTX


def test_default_context_fits_a_realistic_prompt_plus_response():
    ocr_text = "INVOICE LINE 12345.67 ACME CORPORATION\n" * 150          # ~6,000 chars of OCR text
    prompt = build_extraction_prompt(ocr_text)
    estimated_tokens = len(prompt) / 3.0                                  # deliberately pessimistic
    assert estimated_tokens > 4096, "prompt is unexpectedly small; this guard is no longer meaningful"
    assert settings.OLLAMA_NUM_CTX >= estimated_tokens + settings.LLM_MAX_TOKENS


def test_truncated_prompt_is_flagged(monkeypatch, caplog):
    monkeypatch.setattr(settings, "OLLAMA_NUM_CTX", 4096)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp({"response": "{}", "prompt_eval_count": 4096}))
    trace = {}
    with caplog.at_level(logging.WARNING):
        extractor._call_local_ollama("PROMPT", trace)
    assert trace["possible_prompt_truncation"] is True
    assert any("truncated" in r.getMessage() for r in caplog.records)


def test_normal_prompt_is_not_flagged(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp({"response": "{}", "prompt_eval_count": 5400}))
    trace = {}
    extractor._call_local_ollama("PROMPT", trace)
    assert "possible_prompt_truncation" not in trace
