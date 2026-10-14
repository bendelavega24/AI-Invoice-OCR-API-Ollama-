"""Meralco "ELECTRIC BILL" extraction rules and deterministic normalization.

The Meralco statement layout is stable enough for a vendor template (same
approach as ``watsons.py``).  Everything here is evidence-gated: a value is only
overwritten when it is read from its own printed label/row, and the financial
block is only applied when it satisfies the accounting identity

    VAT Sales + VAT + VAT Zero Rated + Non-VAT == TOTAL ENERGY AMOUNT

so a mis-read never replaces a good value with a worse one.  The rules run after
the LLM (hosted API *or* local Ollama) and after vision verification, so the
result does not depend on which model produced the first draft.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

MERALCO_TEMPLATE_NAME = "meralco"

# Fields this template pins from printed evidence. Used by the pipeline to drop
# vision "corrections" that this template has proven wrong.
MERALCO_PINNED_FIELDS = (
    "invoice_date", "due_date", "customer_tax_id", "subtotal", "tax_amount",
    "vat_exempt_sales", "zero_rated_sales", "current_charges_total", "vendor_tax_id", "total_amount",
)

MERALCO_PROMPT = """MERALCO ELECTRIC-BILL FORMAT

This document is a Meralco "ELECTRIC BILL". Apply these rules; they take
precedence over generic guesses. Never invent a value that is not printed.

- invoice_number: the value after "EB Invoice No." (13 digits).
- invoice_date: the "Bill Date" in the Billing Info box. NOT the Due Date.
- due_date: the "Due Date" in the Billing Info box.
- vendor_name: MERALCO. vendor_address / vendor_tax_id: the business-center block
  in the page header (address lines, Tel. No., "TIN ...-VAT"), NOT the
  addressee block at the top left.
- customer_name / customer_address: the addressee block at the top left.
- customer_tax_id: only a TIN printed after "CUSTOMER TIN:"; null when that label
  is empty. Never use the meter number, route code, or part of the invoice number.
- line_items: one per row of "BREAKDOWN OF ELECTRICITY CHARGES", amount = the
  SUBTOTAL column (not the PERCENTAGE column, and never the numbers on the
  consumption chart axis). Skip rows that are 0.00.
- subtotal: the Base amount of "VAT Sales" in "Energy Bill Amount" (page 2).
- tax_amount: the VAT amount on that same "VAT Sales" row.
- vat_exempt_sales: "Non-VAT". zero_rated_sales: "VAT Zero Rated".
- current_charges_total: "TOTAL ENERGY AMOUNT" / "TOTAL CURRENT BILL AMOUNT".
- previous_balance: "Balance From Previous Billing".
- total_amount: "TOTAL CURRENT BILL AMOUNT" (the current charges, NOT including the previous balance).
- withholding_tax: null (the CWT remark is conditional, not an applied deduction).
- Line items are VAT-inclusive charge groups, so they sum to current_charges_total,
  NOT to the VAT Sales subtotal. Do not change subtotal to make them match.
"""

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_DMY = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})")
_MONEY = re.compile(r"^\s*(?:₱|PHP|P)?\s*(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})\s*$", re.I)
_CARRIED = {"remaining balance", "previous balance", "carried balance", "balance forward"}


# ----------------------------------------------------------------- helpers
def _rect(line: dict):
    try:
        pts = line.get("bbox") or []
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def _money(text: str):
    m = _MONEY.match(str(text or ""))
    if not m:
        return None
    return round(float(m.group(1).replace(",", "") + "." + m.group(2)), 2)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _letters(text: str) -> int:
    return len(re.findall(r"[A-Za-z]", text or ""))


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _geo(lines):
    out = []
    for ln in lines or []:
        r = _rect(ln)
        if r and _clean(ln.get("text")):
            out.append((ln, r, _clean(ln.get("text"))))
    return out


def _find(geo, pattern):
    rx = re.compile(pattern, re.I)
    return next((g for g in geo if rx.match(g[2])), None)


def _row_cells(geo, label, min_gap=0.0):
    """Money cells on the same row, to the right of ``label``, ordered by x."""
    _, (x1, y1, x2, y2), _ = label
    cy, band = (y1 + y2) / 2, max(0.6 * (y2 - y1), 10.0)
    cells = []
    for ln, (cx1, cy1, cx2, cy2), txt in geo:
        if cx1 <= x2 + min_gap or abs((cy1 + cy2) / 2 - cy) > band:
            continue
        v = _money(txt)
        if v is not None:
            cells.append((cx1, v))
    return [v for _, v in sorted(cells)]


def _parse_dmy(text: str):
    m = _DMY.search(text or "")
    if not m:
        return None
    mon = _MONTHS.get(m.group(2)[:3].lower())
    if not mon:
        return None
    return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(1)):02d}"


def _labelled_date(ocr_text: str, label: str):
    """Date printed as ``<label>`` followed (same or next line) by ``D Mon YYYY``."""
    lines = [_clean(x) for x in str(ocr_text or "").splitlines()]
    rx = re.compile(rf"(?i)^{label}\s*:?\s*(.*)$")
    for i, line in enumerate(lines):
        m = rx.match(line)
        if not m:
            continue
        for cand in [m.group(1)] + lines[i + 1:i + 3]:
            d = _parse_dmy(cand)
            if d:
                return d
            if cand and not cand.startswith(":") and _letters(cand) > 3:
                break
    return None


# --------------------------------------------------------------- extractors
def _energy_bill_amounts(geo, ocr_text: str) -> dict:
    """VAT Sales (base, VAT), VAT Zero Rated, Non-VAT and TOTAL ENERGY AMOUNT."""
    res: dict[str, Any] = {}
    if geo:
        spec = {
            "vat_sales": r"^VAT\s*Sales$",
            "zero": r"^VAT\s*Zero[\s-]*Rated$",
            "non_vat": r"^Non[\s-]*VAT$",
            "total": r"^TOTAL\s+ENERGY\s+AMOUNT$",
        }
        for key, rx in spec.items():
            label = _find(geo, rx)
            if label:
                cells = _row_cells(geo, label)
                if cells:
                    res[key] = cells
    if "vat_sales" not in res:  # flattened-text fallback
        text = str(ocr_text or "")
        num = r"([\d,]+\.\d{2})"
        m = re.search(rf"(?im)^\s*VAT\s*Sales\s*\n\s*{num}\s*\n\s*{num}", text)
        if m:
            res["vat_sales"] = [float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))]
        for key, label in (("zero", r"VAT\s*Zero[\s-]*Rated"), ("non_vat", r"Non[\s-]*VAT"),
                           ("total", r"TOTAL\s+ENERGY\s+AMOUNT")):
            m = re.search(rf"(?im)^\s*{label}\s*\n\s*{num}", text)
            if m:
                res[key] = [float(m.group(1).replace(",", ""))]
    return res


def _breakdown_items(geo) -> list[dict]:
    """Rows of 'BREAKDOWN OF ELECTRICITY CHARGES' using the SUBTOTAL column."""
    head = _find(geo, r"^BILL\s*SUBGROUP$")
    sub_h = _find(geo, r"^SUBTOTAL$")
    if not head or not sub_h:
        return []
    pct_h = _find(geo, r"^PERCENTAGE$")
    top = head[1][3]
    stop = _find(geo, r"^(?:Please be informed|For authorized collecting agents)")
    bottom = stop[1][1] if stop and stop[1][1] > top else top + 900
    sub_x1 = sub_h[1][0]
    right_limit = pct_h[1][0] if pct_h else sub_x1 + 450
    items = []
    for ln, (x1, y1, x2, y2), txt in geo:
        cy = (y1 + y2) / 2
        if not (top < cy < bottom) or x2 > sub_x1 + 60 or _letters(txt) < 3:
            continue
        if _money(txt) is not None or "%" in txt:
            continue
        band = max(0.7 * (y2 - y1), 12.0)
        amounts = [
            _money(t) for l2, (a1, b1, a2, b2), t in geo
            if a1 > x2 and a2 < right_limit and abs((b1 + b2) / 2 - cy) <= band and _money(t) is not None
        ]
        if amounts and amounts[0] > 0:
            items.append((cy, txt, amounts[0]))
    items.sort()
    return [{"description": d, "quantity": 1.0, "unit_price": a, "amount": a} for _, d, a in items]


def _seller_and_buyer_blocks(geo, customer_name: str):
    """Split the page header into the seller (business-center) block and the
    addressee block using column alignment. Returns (seller_lines, buyer_lines,
    seller_x1) as lists of (text, rect)."""
    bar = _find(geo, r"^ELECTRIC\s*BILL$")
    tel = next((g for g in geo if re.match(r"(?i)^Tel\.?\s*No", g[2])
                and (not bar or g[1][3] < bar[1][1])), None)
    name_key = _norm(customer_name)
    name = next((g for g in geo if name_key and _norm(g[2]) == name_key
                 and (not bar or g[1][3] < bar[1][1])), None)
    if not bar or not tel or not name:
        return [], [], None
    col_x = tel[1][0]
    tol = max(20.0, 0.012 * max(g[1][2] for g in geo))
    seller = [(t, r) for _, r, t in geo
              if abs(r[0] - col_x) <= tol and r[3] <= tel[1][1] + 2 and r[1] >= name[1][1] - 5
              and _letters(t) >= 3 and not re.search(r"(?i)\b(?:tin|tel)\b", t)]
    buyer = [(t, r) for _, r, t in geo
             if abs(r[0] - name[1][0]) <= 60 and r[1] >= name[1][1] - 5 and r[1] < bar[1][1] - 2
             and _norm(t) != name_key and _letters(t) >= 4]
    seller.sort(key=lambda x: x[1][1])
    buyer.sort(key=lambda x: x[1][1])
    return seller, buyer, col_x


def _strip_overlap(text: str, seller_segments: list[str]) -> str:
    """OCR sometimes fuses the end of a seller line into a neighbouring buyer line
    ("...AYALA-ALABANG" + "PRIME ST." -> "...AYALA-ALABANGRIME ST."). Remove a
    trailing run that is the (possibly first-letter-clipped) tail of a seller line."""
    for seg in seller_segments:
        s = _clean(seg)
        for k in (0, 1):
            tail = s[k:]
            if len(_norm(tail)) >= 5 and _clean(text).lower().endswith(tail.lower()) and len(text) > len(tail) + 5:
                return _clean(text)[: len(_clean(text)) - len(tail)].rstrip(" ,;")
    return text


def _snap_spelling(text: str, reference_words: list[str]) -> str:
    """Replace a near-miss word (OCR typo) with the same word read cleanly elsewhere
    in the header of the same bill (e.g. MONTINLOPA -> MUNTINLUPA)."""
    words = text.split(" ")
    for i, w in enumerate(words):
        core = re.sub(r"[^A-Za-z]", "", w)
        if len(core) < 8:
            continue
        for ref in reference_words:
            rc = re.sub(r"[^A-Za-z]", "", ref)
            if rc.lower() != core.lower() and len(rc) == len(core) \
                    and SequenceMatcher(None, core.lower(), rc.lower()).ratio() >= 0.8:
                words[i] = w.replace(core, rc.upper() if core.isupper() else rc)
                break
    return " ".join(words)


# ---------------------------------------------------------------- the rule
def normalize_meralco_extraction(
    data: dict, ocr_text: str, ocr_lines: list[dict] | None = None, hints: dict | None = None,
) -> tuple[dict, list[str]]:
    out = dict(data)
    notes: list[str] = []
    geo = _geo(ocr_lines)
    hints = hints or {}

    def setf(field, value, why):
        old = out.get(field)
        same = (abs(float(old) - float(value)) < 0.005) if isinstance(value, float) and old is not None \
            and not isinstance(old, str) else old == value
        if not same:
            out[field] = value
            notes.append(f"Meralco template: {field} {old!r} -> {value!r} ({why}).")

    text = str(ocr_text or "")

    m = re.search(r"(?i)EB\s*Invoice\s*(?:No\.?|Number)\s*:?\s*(\d{10,})", text)
    if m:
        setf("invoice_number", m.group(1), "printed EB Invoice No.")

    bill = _labelled_date(text, r"Bill\s*Date")
    if bill:
        setf("invoice_date", bill, "printed Bill Date, not the Due Date")
    due = _labelled_date(text, r"Due\s*Date")
    if due:
        setf("due_date", due, "printed Due Date")

    # ---- financial block (identity-gated)
    amt = _energy_bill_amounts(geo, text)
    vs = amt.get("vat_sales") or []
    if len(vs) >= 2 and amt.get("total"):
        base, vat = vs[0], vs[1]
        zero = (amt.get("zero") or [0.0])[0]
        non_vat = (amt.get("non_vat") or [0.0])[0]
        total = amt["total"][-1]
        if abs(base + vat + zero + non_vat - total) <= 0.05:
            setf("subtotal", float(base), "VAT Sales base")
            setf("tax_amount", float(vat), "VAT on VAT Sales")
            setf("zero_rated_sales", float(zero), "VAT Zero Rated")
            setf("vat_exempt_sales", float(non_vat), "Non-VAT")
            setf("current_charges_total", float(total), "TOTAL ENERGY AMOUNT")
            # QA ground truth: Total_Amount is the current bill (TOTAL CURRENT BILL AMOUNT).
            # The carried balance stays in previous_balance and is not a line item.
            setf("total_amount", float(total), "current bill amount; carried balance kept in previous_balance")
            kept = [li for li in out.get("line_items") or []
                    if _clean((li or {}).get("description")).lower() not in _CARRIED]
            if len(kept) != len(out.get("line_items") or []):
                out["line_items"] = kept
                notes.append("Meralco template: carried-balance display row removed from line items (kept in previous_balance).")
        else:
            notes.append("Meralco template: Energy Bill Amount block did not reconcile to TOTAL ENERGY AMOUNT; financial fields left unchanged.")

    # ---- line items from the charges table (must reconcile to current charges)
    cct = out.get("current_charges_total")
    rows = _breakdown_items(geo)
    if rows and cct is not None and abs(sum(r["amount"] for r in rows) - float(cct)) <= 0.05:
        current = [li for li in out.get("line_items") or []
                   if _clean((li or {}).get("description")).lower() not in _CARRIED]
        carried = [li for li in out.get("line_items") or []
                   if _clean((li or {}).get("description")).lower() in _CARRIED]
        key = lambda items: sorted((_norm(i.get("description")), round(float(i.get("amount") or 0), 2)) for i in items)
        if key(current) != key(rows):
            out["line_items"] = rows + carried
            notes.append("Meralco template: line items rebuilt from the SUBTOTAL column of the charges table (sum equals current charges).")

    # ---- customer TIN: only what is printed after the label
    if _find(geo, r"^CUSTOMER\s*TIN\s*:?$") or re.search(r"(?i)CUSTOMER\s*TIN", text):
        label = _find(geo, r"^CUSTOMER\s*TIN\s*:?$")
        tin = None
        tin_rx = re.compile(r"\b\d{3}[- ]?\d{3}[- ]?\d{3}(?:[- ]?\d{3,5})?\b")
        if label:
            _, (x1, y1, x2, y2), _t = label
            cy, band = (y1 + y2) / 2, max(0.6 * (y2 - y1), 10.0)
            for _l, (a1, b1, a2, b2), t in sorted(geo, key=lambda g: g[1][0]):
                if a1 > x2 and abs((b1 + b2) / 2 - cy) <= band and a1 < x2 + 500 and tin_rx.fullmatch(t.strip()):
                    tin = t.strip()
                    break
        else:
            mm = re.search(r"(?i)CUSTOMER\s*TIN\s*:?[ \t]*(\d{3}[- ]?\d{3}[- ]?\d{3}(?:[- ]?\d{3,5})?)", text)
            tin = mm.group(1) if mm else None
        if tin is None and out.get("customer_tax_id"):
            setf("customer_tax_id", None, "CUSTOMER TIN label is empty on the bill")
        elif tin and not out.get("customer_tax_id"):
            setf("customer_tax_id", tin, "TIN printed after CUSTOMER TIN")

    # ---- seller vs addressee blocks
    seller, buyer, col_x = _seller_and_buyer_blocks(geo, out.get("customer_name") or "")
    if seller and buyer:
        vendor_segments = [t for t, _ in seller]
        hint = hints.get("vendor_header_address")
        if hint:
            segs = [s.strip(" ,;") for s in re.split(r"[\r\n]+", str(hint)) if s.strip(" ,;")]
            if segs and not re.search(r"(?i)\b(?:tel|tin)\b", " ".join(segs)):
                vendor_segments = segs if len(segs) > 1 else [str(hint).strip()]
        setf("vendor_address", ", ".join(vendor_segments), "seller business-center block")

        ref_words = [w for t, _ in seller for w in t.split()]
        parts = []
        for t, r in buyer:
            if col_x is not None and r[2] > col_x - 10:  # line fused with the seller column
                t = _strip_overlap(t, vendor_segments)
            parts.append(_snap_spelling(_clean(t), ref_words))
        if len(parts) >= 2:
            setf("customer_address", ", ".join(parts), "addressee block (seller column excluded)")

    return out, notes
