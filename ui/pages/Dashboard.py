"""Streamlit page: spend analytics dashboard."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st
from services.invoice_service import get_dashboard_stats
from services.report_service import spend_by_vendor, spend_by_month, spend_by_category
from ui.components.nav import render_nav, guard_locked_navigation

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

render_nav()
guard_locked_navigation()

st.title("📊 Dashboard")

stats = get_dashboard_stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Invoices", stats["total_invoices"])
c2.metric("Total Spend", f"{stats['total_amount']:,.2f}")
c3.metric("Vendors", stats["vendor_count"])
c4.metric("Needs Review", stats["needs_review"])

st.divider()

st.subheader("Spend by Vendor")
vendor_totals = spend_by_vendor()
if vendor_totals:
    df = pd.DataFrame(list(vendor_totals.items()), columns=["Vendor", "Total"]).head(15)
    st.bar_chart(df.set_index("Vendor"))
else:
    st.info("No data yet — upload some invoices first.")

st.subheader("Spend by Category")
category_totals = spend_by_category()
if category_totals:
    df = pd.DataFrame(list(category_totals.items()), columns=["Category", "Total"])
    st.bar_chart(df.set_index("Category"))
else:
    st.info("No data yet — upload some invoices first.")

st.subheader("Spend by Month")
month_basis = st.radio(
    "Month is based on", ["Invoice date", "Upload date"],
    index=0, horizontal=True, key="dashboard_month_basis",
)
month_totals = spend_by_month(date_basis="invoice" if month_basis == "Invoice date" else "uploaded")
if month_totals:
    df = pd.DataFrame(list(month_totals.items()), columns=["Month", "Total"])
    # A bar chart is meaningful even when all uploaded records fall in ONE month.
    st.bar_chart(df.set_index("Month"))
    st.caption(f"{len(month_totals)} month(s) with recorded dates. Only invoices with a valid selected date are included.")
else:
    st.info("No invoices with a valid date for the selected month basis.")
