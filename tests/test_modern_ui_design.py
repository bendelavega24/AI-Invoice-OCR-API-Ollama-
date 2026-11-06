"""Regression guardrails for the presentation-only Modern UI release."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE_FILES = (
    "ui/streamlit_app.py",
    "ui/pages/Upload.py",
    "ui/pages/Dashboard.py",
    "ui/pages/History.py",
    "ui/pages/Reports.py",
    "ui/pages/Log.py",
    "ui/pages/Users.py",
)

def test_all_modern_pages_remain_valid_python():
    for relative_path in PAGE_FILES:
        path = ROOT / relative_path
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

def test_all_pages_use_shared_nav_and_header():
    for relative_path in PAGE_FILES:
        body = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "render_nav()" in body
        assert "page_heading(" in body
        assert "set_page_config(" in body

def test_brand_theme_does_not_override_service_logic():
    css = (ROOT / "ui/components/design_system.py").read_text(encoding="utf-8")
    assert "[data-testid=\"stSidebar\"]" in css
    assert ".invoice-home-hero" in css
    assert "stMetric" in css
    assert "def apply_modern_theme()" in css
    # The design system must not perform imports from services or database.
    tree = ast.parse(css)
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not any(
        getattr(n, "module", "") and (n.module.startswith("services") or n.module.startswith("database"))
        for n in imports
    )

def test_login_gate_and_upload_lock_remain():
    nav = (ROOT / "ui/components/nav.py").read_text(encoding="utf-8")
    assert "require_login()" in nav
    assert "guard_locked_navigation" in nav
    assert "is_upload_locked()" in nav
    assert "disabled=locked and path != _UPLOAD_PAGE" in nav
    assert "st.page_link" in nav

def test_currency_separation_and_search_preserved():
    home = (ROOT / "ui/streamlit_app.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "ui/pages/Dashboard.py").read_text(encoding="utf-8")
    assert 'stats.get("total_by_currency")' in home
    assert "totals_by_currency(" in dashboard
    assert "spend_by_month(" in dashboard
    for page in ("History.py", "Reports.py", "Log.py"):
        content = (ROOT / "ui/pages" / page).read_text(encoding="utf-8")
        assert "apply_hybrid_search(" in content

def test_theme_works_with_streamlit_138():
    config = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#2563EB"' in config
    assert "[theme.sidebar]" not in config
