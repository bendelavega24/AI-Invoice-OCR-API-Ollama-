from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_history_pdf_viewer_exposes_all_pages():
    text = (ROOT / "ui/pages/History.py").read_text(encoding="utf-8")
    assert '"PDF page"' in text
    assert 'list(range(len(pages)))' in text
    assert '_show_image(pages[page_index])' in text
    assert 'The stored source PDF contains all {len(pages)} pages.' in text
    assert '_preferred_pdf_page_index' in text


def test_sidebar_ai_engine_uses_radio_circles_not_dropdown():
    text = (ROOT / "ui/components/nav.py").read_text(encoding="utf-8")
    block = text[text.index("def _render_engine_selector"):text.index("def guard_locked_navigation")]
    assert 'st.radio(' in block
    assert 'st.selectbox(' not in block


def test_ai_search_hides_model_and_provider_name():
    text = (ROOT / "ui/components/ai_search.py").read_text(encoding="utf-8")
    assert 'st.markdown("**🤖 AI Search**")' in text
    assert 'provider_display' not in text
    assert 'AI Search is interpreting your search...' in text
