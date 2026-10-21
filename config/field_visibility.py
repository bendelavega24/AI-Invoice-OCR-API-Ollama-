"""Client-facing invoice field visibility policy.

Optional metadata stays in extraction, SQLite and internal validation, but is
not displayed in client invoice detail or exported invoice reports.
"""
from __future__ import annotations


INTERNAL_ONLY_INVOICE_FIELDS = frozenset({"due_date", "tax_rate", "payment_terms"})

# Additional client-facing fields displayed below the main financial amounts
# on the History detail page. Keep this explicit to avoid leaking future
# internal fields merely because they happen to be present in the database.
HISTORY_SECONDARY_FIELDS = (
    ("Customer Contact", "customer_contact"),
    ("Current Charges", "current_charges_total"),
    ("Previous Balance", "previous_balance"),
    ("Currency", "currency"),
)


def visible_field_evidence(evidence: dict | None) -> dict:
    """Suppress verification notices for metadata that the UI does not show.

    Leave saved evidence untouched: downstream confidence and validation
    still have access to all original data.
    """
    return {
        key: value for key, value in (evidence or {}).items()
        if str(key).split(".", 1)[0] not in INTERNAL_ONLY_INVOICE_FIELDS
    }


def visible_validation_issues(issues: list[str] | None) -> list[str]:
    """Keep internal-only metadata *validation notices* out of the UI.

    Financial and invoice-date discrepancies continue to be displayed. Only
    messages whose subject is exclusively one of the hidden optional fields
    are removed from client-facing summaries. Stored warnings stay intact.
    """
    public = []
    for issue in issues or []:
        value = str(issue)
        words = value.lstrip().split(None, 1)
        subject = words[0].rstrip(":") if words else ""
        if subject not in INTERNAL_ONLY_INVOICE_FIELDS:
            public.append(value)
    return public
