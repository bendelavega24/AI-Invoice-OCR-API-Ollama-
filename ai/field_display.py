"""Display evidence-based verification indicators beside extracted values.

Never describe support indicators as statistical probabilities of correctness.
"""
from __future__ import annotations

from ai.field_evidence import build_field_evidence


def evidence_for_invoice(detail: dict) -> tuple[dict[str, dict], bool]:
    """Saved evidence, or an explicitly marked historic OCR-text-only estimate."""
    saved = detail.get("field_evidence") or {}
    if saved:
        return saved, any(meta.get("historic_ocr_only") for meta in saved.values() if isinstance(meta, dict))
    if detail.get("raw_text"):
        return build_field_evidence(detail, detail.get("raw_text") or "", validation_issues=detail.get("validation_issues") or [], ocr_engine=detail.get("ocr_engine_used")), True
    return {}, True


def indicator(meta: dict | None) -> str:
    if not meta or meta.get("status") in {"not_provided", "derived"}:
        return ""
    status = meta.get("status")
    if status == "missing":
        return "⚠️ Missing"
    if status == "manual_edit":
        return "✏️ Manual"
    score = meta.get("score")
    if score is None:
        return "⚠️ Unverified"
    pct = f"{round(100 * score)}% evidence"
    return f"⚠️ {pct}" if meta.get("warning") else f"✓ {pct}"


def field_review_summary(evidence: dict[str, dict], limit: int = 16) -> list[str]:
    problems = []
    for path, meta in evidence.items():
        warning = meta.get("warning") if isinstance(meta, dict) else None
        if warning:
            problems.append(f"{path.replace('_', ' ')}: {warning}")
    return problems[:limit]


