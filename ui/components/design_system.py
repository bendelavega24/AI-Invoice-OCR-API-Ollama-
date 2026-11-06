"""Shared presentation-only design system for the Streamlit 1.38 interface.

No OCR, LLM, database, validation, or navigation behavior belongs here.
The CSS is intentionally scoped to Streamlit's stable test IDs and project
classes; if Streamlit changes its DOM, controls remain natively functional.
"""
from html import escape
import streamlit as st

MODERN_UI_CSS = r"""
<style>
:root {
  --invoice-navy: #15243c;
  --invoice-navy-2: #1c3150;
  --invoice-blue: #2563eb;
  --invoice-bg: #f5f7fb;
  --invoice-surface: #ffffff;
  --invoice-text: #17243b;
  --invoice-muted: #66758c;
  --invoice-border: #e4eaf2;
  --invoice-radius: 14px;
}
html { font-size: 16px; }
/* Unified canvas and type. Keep the native Streamlit focus/disabled states. */
[data-testid="stAppViewContainer"] {
  background: var(--invoice-bg);
  color: var(--invoice-text);
  font-family: "Segoe UI", "Inter", "Aptos", Arial, sans-serif;
}
[data-testid="stHeader"] { background: rgba(245,247,251,.91); }
[data-testid="block-container"] {
  max-width: 1480px;
  padding-top: 2.05rem;
  padding-bottom: 3.5rem;
  padding-left: 2.1rem;
  padding-right: 2.1rem;
}
[data-testid="stAppViewContainer"] h1 {
  font-size: clamp(1.7rem, 2.5vw, 2.4rem) !important;
  font-weight: 760 !important;
  letter-spacing: -.035em;
  line-height: 1.15 !important;
  color: #17243b;
  padding-bottom: .15rem;
}
[data-testid="stAppViewContainer"] h2 {
  font-size: 1.33rem !important;
  font-weight: 700;
  letter-spacing: -.022em;
  color: #1b2c46;
}
[data-testid="stAppViewContainer"] h3 {
  font-size: 1.07rem !important;
  font-weight: 690;
  color: #1b2c46;
}
[data-testid="stCaptionContainer"], [data-testid="stAppViewContainer"] small {
  color: #64748b;
}
.invoice-eyebrow {
  display: block;
  text-transform: uppercase;
  color: #4772bd;
  font-size: .72rem;
  font-weight: 760;
  letter-spacing: .115em;
  margin-bottom: .42rem;
}
.invoice-page-description {
  color: #64748b;
  margin: -.3rem 0 1.15rem;
  font-size: .94rem;
}
.invoice-section-lead {
  font-size: .75rem;
  color: #64748b;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .08em;
  margin: .7rem 0 .3rem;
}
.invoice-help-note {
  border: 1px solid #d7e5fb;
  border-left: 3px solid #2563eb;
  background: #eff6ff;
  color: #254870;
  border-radius: 12px;
  padding: .8rem 1rem;
  font-size: .86rem;
  margin: .3rem 0 .9rem;
}
.invoice-brand {
  display: flex; align-items: center; gap: 11px;
  padding: 4px 3px 18px;
  margin-bottom: 10px;
}
.invoice-brand-mark {
  display: flex; align-items: center; justify-content: center;
  flex: 0 0 39px; width: 39px; height: 39px;
  border-radius: 12px;
  background: linear-gradient(140deg,#5486f5,#2454bb);
  box-shadow: 0 7px 15px rgba(19,60,140,.28);
  color: white; font-size: 16px; font-weight: 850;
}
.invoice-brand-name { color:#ffffff; font-size:1.04rem; font-weight:750; line-height:1.15; letter-spacing:-.03em; }
.invoice-brand-sub { color:#98acc6; font-size:.72rem; margin-top:3px; letter-spacing:.015em; }
.invoice-sidebar-label {
  margin-top: .55rem; margin-bottom: .42rem;
  font-size: .67rem; font-weight: 760; letter-spacing: .13em;
  color: #9db1cf; text-transform: uppercase;
}
.invoice-home-hero {
  background: linear-gradient(115deg,#172b4a 0%, #254b83 72%, #3469b1 100%);
  color: white;
  border-radius: 18px; padding: 1.45rem 1.65rem;
  box-shadow: 0 12px 28px rgba(23,45,80,.12);
  margin-top: .25rem; margin-bottom: 1.2rem;
}
.invoice-home-hero h2 { color:#ffffff !important; font-size:1.26rem !important; margin:.05rem 0 .45rem; }
.invoice-home-hero p { margin:0; color:#d5e5fb; font-size:.91rem; line-height:1.55; }
.invoice-home-hero .hero-kicker { color:#9fc4fe; text-transform:uppercase; font-size:.7rem; font-weight:760; letter-spacing:.12em; }
.invoice-quick-title { font-weight:710; margin-bottom:.2rem; color:#20304c; }
.invoice-quick-copy { color:#64748b; font-size:.86rem; margin-bottom:.5rem; }
/* Native cards and metric tiles. */
[data-testid="stMetric"] {
  background: #ffffff;
  border: 1px solid var(--invoice-border);
  border-radius: 14px;
  box-shadow: 0 3px 14px rgba(22,40,66,.035);
  padding: 1.05rem 1.15rem;
  min-height: 115px;
}
[data-testid="stMetricLabel"] { color:#64748b; font-size:.81rem !important; font-weight:640; }
[data-testid="stMetricValue"] {
  color: #17243b; font-weight:760;
  font-size: clamp(1.28rem, 2vw, 1.85rem) !important;
  letter-spacing: -.04em;
  overflow-wrap: anywhere;
}
[data-testid="stVerticalBlockBorderWrapper"] > div,
[data-testid="stForm"],
[data-testid="stExpander"] {
  border-color:var(--invoice-border) !important;
  border-radius:var(--invoice-radius) !important;
}
[data-testid="stForm"], [data-testid="stExpander"] {
  background:#ffffff;
  box-shadow:0 2px 8px rgba(20,40,72,.025);
}
[data-testid="stFileUploaderDropzone"] {
  border:1.5px dashed #99b5de;
  border-radius: 15px;
  background: #f4f8ff;
  padding: 1rem;
}
[data-testid="stDataFrame"], [data-testid="stTable"] {
  background:#ffffff;
  border-radius:12px;
  overflow:hidden;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [data-baseweb="select"] {
  border-radius:10px !important;
  border-color:#dbe4ef !important;
  background:#ffffff;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: var(--invoice-blue) !important;
}
.stButton button, .stDownloadButton button, .stFormSubmitButton button {
  border-radius:10px !important;
  font-weight:650 !important;
  min-height:2.42rem;
  transition: background-color .15s ease, box-shadow .15s ease;
}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"],
.stFormSubmitButton button[kind="primary"] {
  background:#2563eb !important;
  color:#ffffff !important;
  border-color:#2563eb !important;
}
.stButton button[kind="primary"]:hover, .stFormSubmitButton button[kind="primary"]:hover {
  background:#1d4ed8 !important; border-color:#1d4ed8 !important;
}
[data-testid="stAlert"] { border-radius:11px; }
hr { border-color: #e8edf4 !important; }
/* Navigation: dark professional rail with high contrast controls. */
[data-testid="stSidebarNav"] { display:none; }
[data-testid="stSidebar"], [data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {
  background:#15243c !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span { color: #e5edf7; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:#aebed4; }
[data-testid="stSidebarUserContent"] {
  display:flex; flex-direction:column; min-height: calc(100vh - 3rem);
}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
  border-radius: 10px;
  padding: .53rem .65rem;
  margin: .12rem 0;
  transition: background-color .15s;
}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {
  background:#243d61;
}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"],
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:has([aria-current="page"]) {
  background:#294975;
  box-shadow:inset 3px 0 0 #72a0ff;
}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p { font-size:.87rem; font-weight:600; color:#e5edf7; }
[data-testid="stSidebar"] [data-testid="stRadio"] label { font-size:.84rem; }
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] { gap:.22rem; }
[data-testid="stSidebar"] hr { border-color:#354964 !important; }
[data-testid="stSidebar"] .stButton button {
  background:#203854; color:#e5edf7; border:1px solid #435877;
}
[data-testid="stSidebar"] .stButton button:hover {
  background:#2f5078; color:#fff; border-color:#6482ad;
}
.tsukiden-sidebar-footer {
  margin-top:auto; padding:1rem .3rem .4rem;
  border-top:1px solid #3b506c;
  font-size:.68rem; line-height:1.6; color:#a4b5cb;
}
/* Modernize legacy HTML tables without touching their contents or export logic. */
.tsukiden-report-table-wrap,.audit-log-wrap {
  border:1px solid var(--invoice-border) !important;
  border-radius:12px !important;
  background:#ffffff;
}
.tsukiden-report-table th, table.audit-log th {
  background:#eaf1fb !important;
  color:#23406b !important;
  font-size:.77rem !important;
  letter-spacing:.015em;
  text-transform:none;
  font-weight:720 !important;
  border-bottom:1px solid #dbe5f1 !important;
}
.tsukiden-report-table td, table.audit-log td {
  color:#243651;
  border-bottom:1px solid #e7edf4 !important;
}
.tsukiden-report-table tbody tr:hover, table.audit-log tbody tr:hover {
  background:#f5f9ff !important;
}
@media (max-width: 900px) {
  html {font-size:15px;}
  [data-testid="block-container"] {padding:1.2rem .85rem 2rem;}
  .invoice-home-hero {padding:1.1rem;}
  [data-testid="stMetric"] { min-height:90px; padding:.75rem;}
}
</style>
"""


def apply_modern_theme() -> None:
    """Inject stylesheet once per rendered page, including the login gate."""
    st.markdown(MODERN_UI_CSS, unsafe_allow_html=True)


def page_heading(title: str, description: str, section: str = "WORKSPACE") -> None:
    """Consistent accessible page title; values always HTML-escaped."""
    st.markdown(f'<div class="invoice-eyebrow">{escape(section)}</div>', unsafe_allow_html=True)
    st.title(title)
    if description:
        st.markdown(
            f'<div class="invoice-page-description">{escape(description)}</div>',
            unsafe_allow_html=True,
        )


def help_note(message: str) -> None:
    st.markdown(f'<div class="invoice-help-note">{escape(message)}</div>', unsafe_allow_html=True)
