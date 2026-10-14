"""Calls local Ollama text LLM to turn OCR text into structured invoice JSON.

This version also records a structured trace of every generation/correction
attempt when a mutable ``trace`` dict is supplied by the caller.
"""
from __future__ import annotations

import time
import re
import json
from copy import deepcopy
import requests
from config.settings import settings
from config.logging import get_logger
from ai.prompt_builder import build_extraction_prompt, build_correction_prompt
from ai import llm_client
from ai.validator import validate_extraction
from utils.invoice_template_detector import detect_invoice_template
from utils.helpers import safe_json_loads

logger = get_logger("ai.extractor")


class ExtractionError(Exception):
    pass


def _usage_from_ollama(body: dict) -> dict:
    return {
        "prompt_eval_count": body.get("prompt_eval_count"),
        "eval_count": body.get("eval_count"),
        "total_duration": body.get("total_duration"),
        "load_duration": body.get("load_duration"),
        "prompt_eval_duration": body.get("prompt_eval_duration"),
        "eval_duration": body.get("eval_duration"),
    }


def _call_ollama(prompt: str, trace_attempt: dict | None = None) -> str:
    """Send one extraction/correction prompt to the configured LLM provider.

    Name kept for backward compatibility (tests and callers patch it). With
    LLM_PROVIDER=ollama this is exactly the original local-Ollama call. With
    OpenRouter it tries OpenRouter first (with retries) and, if that fails and
    LLM_FALLBACK_TO_OLLAMA is on, repeats the request on local Ollama.
    """
    if llm_client.pick_provider() != "openrouter":
        return _call_local_ollama(prompt, trace_attempt)
    if not llm_client.fallback_enabled():
        return _call_openrouter(prompt, trace_attempt)
    try:
        return _call_openrouter(prompt, trace_attempt)
    except ExtractionError as first_error:
        llm_client.note_openrouter_failure(first_error)
        logger.warning(f"{llm_client.label()} failed ({first_error}); falling back to local Ollama")
        if trace_attempt is not None:
            trace_attempt.pop("timeout_attempts", None)
            trace_attempt["fallback_from"] = {"provider": "openrouter", "error": str(first_error)[:500]}
        try:
            return _call_local_ollama(prompt, trace_attempt)
        except ExtractionError as second_error:
            raise ExtractionError(
                f"{llm_client.label()} failed ({first_error}) and the local Ollama fallback also failed ({second_error})"
            ) from second_error


def _call_openrouter(prompt: str, trace_attempt: dict | None = None) -> str:
    model = settings.OPENROUTER_MODEL
    payload = llm_client.chat_payload(
        prompt, model=model, temperature=settings.LLM_TEMPERATURE, max_tokens=settings.LLM_MAX_TOKENS
    )
    if trace_attempt is not None:
        trace_attempt.update({
            "endpoint": "/chat/completions", "provider": "openrouter", "model": model,
            "prompt": prompt, "request_format": "json",
        })
    timeout_s = settings.OPENROUTER_TIMEOUT_SECONDS
    start = time.perf_counter()
    try:
        # Initial extraction must be valid JSON (else retry / fail over); a bad
        # *correction* keeps the old behaviour: caller retains the last usable extraction.
        strict = (trace_attempt or {}).get("kind", "initial") == "initial"
        raw, usage, resp = llm_client.request_openrouter(payload, timeout_s, expect_json=True, strict=strict)
    except requests.exceptions.Timeout as e:
        elapsed = time.perf_counter() - start
        if trace_attempt is not None:
            trace_attempt.setdefault("timeout_attempts", []).append({"attempt": 1, "elapsed_seconds": round(elapsed, 3)})
        logger.warning(f"{llm_client.label()} call timed out after {elapsed:.1f}s (limit={timeout_s}s per try)")
        raise ExtractionError(f"{llm_client.label()} request timed out ({timeout_s}s per try, retries exhausted).") from e
    except requests.RequestException as e:
        if trace_attempt is not None:
            trace_attempt["error"] = str(e)
            response = getattr(e, "response", None)
            if response is not None:
                trace_attempt["response_body"] = response.text[:4000]
        raise ExtractionError(f"{llm_client.label()} request failed: {e}") from e
    if trace_attempt is not None:
        trace_attempt["http_status"] = resp.status_code
        trace_attempt["elapsed_seconds"] = round(time.perf_counter() - start, 3)
        trace_attempt["raw_response"] = raw
        trace_attempt["usage"] = usage
    if usage.get("finish_reason") == "length":
        logger.warning(f"{llm_client.label()} hit the max_tokens cap; JSON may be truncated (raise LLM_MAX_TOKENS)")
    return raw


def _warn_if_prompt_truncated(body: dict, trace_attempt: dict | None) -> None:
    """Ollama silently truncates a prompt that doesn't fit its context window and reports the window size as the
    number of prompt tokens it evaluated. Make that visible: it is the kind of failure that otherwise only shows up
    as 'the invoice was accepted but fields were extracted wrongly'. (Best-effort: with prompt caching Ollama can
    under-report prompt_eval_count, so a missing warning does not prove nothing was cut.)"""
    used = body.get("prompt_eval_count")
    ctx = settings.OLLAMA_NUM_CTX
    if isinstance(used, int) and ctx and used >= ctx - 8:
        logger.warning(
            f"Ollama evaluated {used} prompt tokens with a {ctx}-token context window: the prompt was almost "
            f"certainly truncated and extraction quality will suffer. Raise OLLAMA_NUM_CTX."
        )
        if trace_attempt is not None:
            trace_attempt["possible_prompt_truncation"] = True


def _call_local_ollama(prompt: str, trace_attempt: dict | None = None) -> str:
    """Original local-Ollama request, unchanged."""
    url = f"{settings.OLLAMA_HOST}/api/generate"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",  # strongly reduces prose/fenced-code invalid-JSON failures
        "keep_alive": settings.OLLAMA_KEEP_ALIVE,
        "options": {"temperature": settings.LLM_TEMPERATURE, "num_ctx": settings.OLLAMA_NUM_CTX,
                    "num_predict": settings.OLLAMA_NUM_PREDICT},
    }

    if trace_attempt is not None:
        trace_attempt.update({
            "endpoint": "/api/generate",
            "num_ctx": settings.OLLAMA_NUM_CTX,
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "request_format": "json",
        })

    attempts = settings.OLLAMA_TIMEOUT_RETRIES + 1
    last_error = None
    for attempt in range(1, attempts + 1):
        start = time.perf_counter()
        try:
            resp = requests.post(url, json=payload, timeout=settings.OLLAMA_TIMEOUT_SECONDS)
            elapsed = time.perf_counter() - start
            if trace_attempt is not None:
                trace_attempt["http_status"] = resp.status_code
                trace_attempt["elapsed_seconds"] = round(elapsed, 3)
            resp.raise_for_status()
            body = resp.json()
            raw = body.get("response", "")
            if trace_attempt is not None:
                trace_attempt["raw_response"] = raw
                trace_attempt["usage"] = _usage_from_ollama(body)
            _warn_if_prompt_truncated(body, trace_attempt)
            return raw
        except requests.exceptions.Timeout as e:
            elapsed = time.perf_counter() - start
            last_error = e
            if trace_attempt is not None:
                trace_attempt.setdefault("timeout_attempts", []).append({"attempt": attempt, "elapsed_seconds": round(elapsed, 3)})
            logger.warning(
                f"Ollama call timed out after {elapsed:.1f}s "
                f"(attempt {attempt}/{attempts}, limit={settings.OLLAMA_TIMEOUT_SECONDS}s)"
            )
            continue
        except requests.RequestException as e:
            if trace_attempt is not None:
                trace_attempt["error"] = str(e)
                response = getattr(e, "response", None)
                if response is not None:
                    trace_attempt["response_body"] = response.text[:4000]
            raise ExtractionError(f"Ollama request failed: {e}") from e

    raise ExtractionError(
        f"Ollama request timed out after {attempts} attempt(s), "
        f"{settings.OLLAMA_TIMEOUT_SECONDS}s each."
    ) from last_error


def _looks_like_meralco(ocr_text: str) -> bool:
    """Backstop when utils.invoice_template_detector does not recognise a Meralco bill."""
    t = str(ocr_text or "")
    return bool(re.search(r"(?i)meralco", t) and re.search(r"(?i)ELECTRIC\s*BILL|EB\s*Invoice", t))


def _apply_meralco_template(parsed: dict, ocr_text: str, ocr_lines, trace: dict) -> dict:
    """Deterministic Meralco rules (bill date, customer TIN, VAT block, addresses,
    carried balance). Runs after the LLM loop so the model cannot undo them."""
    from ai.invoice_templates.meralco import normalize_meralco_extraction
    try:
        fixed, notes = normalize_meralco_extraction(parsed, ocr_text, ocr_lines)
    except Exception as exc:  # never lose a good extraction to a template bug
        logger.warning(f"Meralco template post-processing failed: {exc}")
        trace["meralco_template_error"] = str(exc)
        return parsed
    trace["meralco_template_notes"] = notes
    for n in notes:
        logger.info(n)
    return fixed


def extract_invoice_data(ocr_text: str, template_name: str | None = None, trace: dict | None = None,
                         ocr_lines: list | None = None) -> dict:
    """Run extraction + validation/correction loop.

    ``trace`` is optional and backward-compatible. When provided it is
    populated in-place, including raw LLM responses, parsed JSON, validation
    issues and Ollama token counts for every attempt.
    """
    if trace is None:
        trace = {}
    trace.setdefault("model", llm_client.active_text_model())
    trace.setdefault("attempts", [])

    if not ocr_text or not ocr_text.strip():
        trace["error"] = "Empty OCR text"
        raise ExtractionError("Empty OCR text — nothing to extract.")

    if template_name is None:
        template_name = detect_invoice_template(ocr_text)
    # utils.invoice_template_detector returns "generic" (not None) when it is not confident,
    # so treat both as "no template" before the Meralco backstop.
    if template_name in (None, "", "generic") and _looks_like_meralco(ocr_text):
        template_name = "meralco"
    trace["template_name"] = template_name
    logger.info(f"Invoice template selected: {template_name}")

    prompt = build_extraction_prompt(ocr_text, template_name=template_name)
    initial = {"kind": "initial"}
    trace["attempts"].append(initial)
    raw_response = _call_ollama(prompt, initial)
    parsed = safe_json_loads(raw_response)
    initial["parsed_json"] = parsed

    if parsed is None:
        trace["error"] = "LLM did not return valid JSON"
        raise ExtractionError("LLM did not return valid JSON.")

    # Use existing rules before asking the model to repair already-resolvable noise.
    from ai.post_processing import post_process, clean_line_items
    def prepare(candidate):
        if not getattr(settings, "LLM_EARLY_CLEANUP_ENABLED", True):
            return deepcopy(candidate)
        normalized = post_process(deepcopy(candidate))
        normalized, notes = clean_line_items(normalized)
        trace.setdefault("early_cleanup", []).append({"notes": notes, "normalized_json": deepcopy(normalized)})
        return normalized

    parsed = prepare(parsed)
    previous_issue_fingerprint = None
    seen_results = {json.dumps(parsed, sort_keys=True, default=str)}
    for attempt in range(settings.LLM_MAX_RETRIES):
        issues = validate_extraction(parsed, template_name=template_name, ocr_text=ocr_text)
        issue_fingerprint = tuple(sorted(re.sub(r"\s+", " ", str(x)).strip() for x in issues))
        trace.setdefault("validation_history", []).append({"attempt": attempt, "issues": list(issues)})
        if not issues:
            break
        # 1.70 speed optimization: when a correction produces exactly the
        # same validation problems as the preceding cycle, further retries
        # have plateaued. Keep the latest parsed JSON and let deterministic
        # OCR/geometry reconciliation handle the remaining issues.
        if (
            getattr(settings, "LLM_STOP_ON_STALLED_VALIDATION", True)
            and previous_issue_fingerprint is not None
            and issue_fingerprint == previous_issue_fingerprint
        ):
            trace["stopped_on_stalled_validation"] = {
                "attempt": attempt,
                "issues": list(issues),
                "reason": "validation issue set unchanged after previous correction",
            }
            logger.info("Stopping LLM correction retries: validation issues are unchanged from the previous cycle.")
            break
        previous_issue_fingerprint = issue_fingerprint
        logger.info(f"Validation issues (attempt {attempt+1}): {issues}")
        correction_prompt = build_correction_prompt(ocr_text, parsed, issues, template_name=template_name)
        corr_trace = {"kind": "correction", "correction_number": attempt + 1, "issues_given_to_model": list(issues)}
        trace["attempts"].append(corr_trace)
        raw_response = _call_ollama(correction_prompt, corr_trace)
        corrected = safe_json_loads(raw_response)
        corr_trace["parsed_json"] = corrected
        if isinstance(corrected, dict) and corrected:
            corrected = prepare(corrected)
            fingerprint = json.dumps(corrected, sort_keys=True, default=str)
            if fingerprint in seen_results:
                trace["stopped_on_repeated_result"] = {"attempt": attempt + 1, "reason": "correction repeated a previously seen normalized result"}
                break
            seen_results.add(fingerprint)
            parsed = corrected
        else:
            trace["stopped_on_invalid_correction"] = {"attempt": attempt + 1, "reason": "correction returned no usable object; retained last usable extraction"}
            break

    if template_name == "meralco":
        parsed = _apply_meralco_template(parsed, ocr_text, ocr_lines, trace)
    trace["final_validation_issues"] = validate_extraction(parsed, template_name=template_name, ocr_text=ocr_text)
    trace["final_parsed_json"] = parsed
    return parsed
