"""Shared sidebar navigation.

Streamlit's built-in multipage nav (auto-generated from ui/pages/) can't be
disabled programmatically, so we hide it via CSS and render our own
st.page_link-based nav instead. That lets us grey out / disable every page
except Upload while an upload batch is being processed, so the user can't
click away from "Upload" mid-run.

Every page in the app should call `render_nav()` near the top (right after
`st.set_page_config`). Every page *except* Upload should also call
`guard_locked_navigation()` right after that — it's a defense-in-depth check
for direct URL navigation / browser back-button, which `disabled=True` on a
page_link can't prevent by itself.
"""
import streamlit as st
from config.constants import APP_NAME, APP_VERSION, COMPANY_NAME, COPYRIGHT_YEAR
from ai import llm_client
from config.settings import settings
from ui.components.auth import require_login, render_account_box, is_admin
from ui.components.design_system import apply_modern_theme

# (path relative to the main script ui/streamlit_app.py, label, icon)
_PAGES = [
    ("streamlit_app.py", "Home", "🧾"),
    ("pages/Upload.py", "Upload", "📤"),
    ("pages/Dashboard.py", "Dashboard", "📊"),
    ("pages/History.py", "History", "🗂️"),
    ("pages/Reports.py", "Reports", "📁"),
    ("pages/Log.py", "Log", "📋"),
]
# Only shown to (and allowed for) admin accounts.
_ADMIN_PAGES = [
    ("pages/Users.py", "Users", "👥"),
]

_UPLOAD_PAGE = "pages/Upload.py"


def is_upload_locked() -> bool:
    return bool(st.session_state.get("upload_in_progress", False))


def render_nav() -> None:
    """Render the sidebar: title, nav links (disabled but Upload while an
    upload is in progress), and a footer pinned to the bottom."""
    apply_modern_theme()
    require_login()  # shows the sign-in form and halts the page if nobody is logged in
    locked = is_upload_locked()

    with st.sidebar:
        st.markdown(
            '<div class="invoice-brand">'
            '<div class="invoice-brand-mark">AI</div>'
            '<div><div class="invoice-brand-name">Invoice OCR</div>'
            '<div class="invoice-brand-sub">DOCUMENT INTELLIGENCE</div></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="invoice-sidebar-label">Workspace</div>', unsafe_allow_html=True)
        if locked:
            st.warning("⏳ Upload in progress — other tabs are locked until it finishes.")
        for path, label, icon in _PAGES + (_ADMIN_PAGES if is_admin() else []):
            st.page_link(path, label=label, icon=icon, disabled=locked and path != _UPLOAD_PAGE)

        st.divider()
        st.markdown('<div class="invoice-sidebar-label">Processing mode</div>', unsafe_allow_html=True)
        _render_engine_selector(locked)
        st.divider()
        render_account_box(locked=locked)

        st.markdown(
            f"""
            <div class="tsukiden-sidebar-footer">
            © {COPYRIGHT_YEAR} {COMPANY_NAME}<br>
            {APP_NAME} System • Version {APP_VERSION}
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_engine_selector(locked: bool) -> None:
    """Sidebar choice: API only / Ollama only / Both. Applies to the whole app."""
    llm_client.load_saved_mode()
    current = llm_client.get_mode()
    labels = [llm_client.MODE_LABELS[m] for m in llm_client.MODES]
    picked_label = st.radio(
        "🤖 AI engine",
        labels,
        index=llm_client.MODES.index(current),
        disabled=locked,
        key="llm_mode_radio",
        help=(
            "API only: hosted model from LLM_BASE_URL / LLM_MODEL.\n\n"
            "Ollama only: local model, nothing is sent online.\n\n"
            "Both: API first, automatically falls back to local Ollama if the API fails."
        ),
    )
    picked = llm_client.MODES[labels.index(picked_label)]
    if picked != current:
        llm_client.set_mode(picked)
        current = picked
    if current == "ollama_only":
        st.caption(f"Local: `{settings.OLLAMA_MODEL}`")
    else:
        st.caption(f"API: `{settings.OPENROUTER_MODEL}`")
        if not llm_client.api_configured():
            st.warning("No LLM_API_KEY set in .env — API calls will fail.")
        if current == "both":
            st.caption(f"Fallback: `{settings.OLLAMA_MODEL}`")


def guard_locked_navigation() -> None:
    """Call at the top of every non-Upload page, right after render_nav().

    If an upload is in progress, stop the page from rendering any further
    and point the user back to Upload — this covers direct URL navigation
    or the browser back/forward buttons, which a disabled sidebar link
    alone doesn't prevent.
    """
    if is_upload_locked():
        st.warning(
            "An upload is currently being processed. This page is locked until "
            "it finishes — please wait on the Upload tab."
        )
        st.page_link(_UPLOAD_PAGE, label="Go to Upload", icon="📤")
        st.stop()
