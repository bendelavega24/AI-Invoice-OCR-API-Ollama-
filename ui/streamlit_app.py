"""Home page — overview of invoice activity and workflow shortcuts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from database.database import init_db
from services.invoice_service import get_dashboard_stats
from ui.components.nav import render_nav, guard_locked_navigation
from ui.components.design_system import page_heading

st.set_page_config(page_title="AI Invoice OCR", page_icon="🧾", layout="wide")
init_db()
render_nav()
guard_locked_navigation()

page_heading(
    "Workspace overview",
    "A clear view of your invoice processing activity.",
    section="AI INVOICE OCR",
)

st.markdown(
    """
    <div class="invoice-home-hero">
      <div class="hero-kicker">DOCUMENT INTELLIGENCE WORKSPACE</div>
      <h2>From invoices to trusted records.</h2>
      <p>Upload, extract, verify, and report in one secure workspace.
      Fields requiring review stay visible so your team can check them
      against the original invoice.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

stats = get_dashboard_stats()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total invoices", stats["total_invoices"])
totals = stats.get("total_by_currency") or {}
total_display = " | ".join(
    f"{currency} {amount:,.2f}"
    for currency, amount in sorted(totals.items())
) or "0.00"
col2.metric("Total amount by currency", total_display)
col3.metric("Vendors", stats["vendor_count"])
col4.metric("Needs review", stats["needs_review"])

st.subheader("Quick access")
st.caption("Continue a workflow without changing the current processing configuration.")
a, b, c = st.columns(3)

with a:
    with st.container(border=True):
        st.markdown('<div class="invoice-quick-title">Upload invoices</div>', unsafe_allow_html=True)
        st.markdown('<div class="invoice-quick-copy">Process a scanned or digital invoice and review its extraction.</div>', unsafe_allow_html=True)
        st.page_link("pages/Upload.py", label="Go to Upload", icon="📤")

with b:
    with st.container(border=True):
        st.markdown('<div class="invoice-quick-title">Invoice history</div>', unsafe_allow_html=True)
        st.markdown('<div class="invoice-quick-copy">Find records, inspect source images, and correct flagged values.</div>', unsafe_allow_html=True)
        st.page_link("pages/History.py", label="Open History", icon="🗂️")

with c:
    with st.container(border=True):
        st.markdown('<div class="invoice-quick-title">Reports & analytics</div>', unsafe_allow_html=True)
        st.markdown('<div class="invoice-quick-copy">Review spending by currency and export filtered invoices.</div>', unsafe_allow_html=True)
        st.page_link("pages/Reports.py", label="Open Reports", icon="📁")

st.markdown(
    '<div class="invoice-help-note">Amounts in different currencies are kept separate. '
    'Verification highlights indicate where manual review is recommended.</div>',
    unsafe_allow_html=True,
)
