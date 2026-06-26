"""Seller-note feature: trusted free-text context steering AI + pricing."""
from backend.app.core.prompts import build_seller_note_block, EBAY_LISTING_PROMPT


class TestBuildSellerNoteBlock:
    def test_empty_note_returns_empty_string(self):
        assert build_seller_note_block("") == ""
        assert build_seller_note_block(None) == ""
        assert build_seller_note_block("   ") == ""

    def test_note_is_wrapped_in_trusted_context_block(self):
        block = build_seller_note_block("no charger included")
        assert "no charger included" in block
        assert "SELLER-PROVIDED CONTEXT" in block

    def test_note_is_trimmed(self):
        block = build_seller_note_block("  New Old Stock  ")
        assert "New Old Stock" in block
        assert "  New Old Stock  " not in block


class TestVisionPromptPlaceholder:
    def test_empty_note_prompt_has_no_marker(self):
        rendered = EBAY_LISTING_PROMPT.format(category_suggestions="cats", seller_note="")
        assert "SELLER-PROVIDED CONTEXT" not in rendered
        # JSON structure braces survived .format (no stray KeyError-causing braces)
        assert '"identification"' in rendered

    def test_note_block_appears_when_present(self):
        block = build_seller_note_block("antique, not a replica")
        rendered = EBAY_LISTING_PROMPT.format(category_suggestions="cats", seller_note=block)
        assert "antique, not a replica" in rendered
        assert "SELLER-PROVIDED CONTEXT" in rendered


from unittest.mock import MagicMock, patch


def _make_analyzer():
    """AIAnalyzer with a stubbed client; encode_image short-circuited."""
    from backend.app.services.ai_analyzer import AIAnalyzer
    analyzer = AIAnalyzer.__new__(AIAnalyzer)
    analyzer.client = None  # forces early 'AI Client not initialized' return AFTER prompt build
    return analyzer


class TestAnalyzeItemThreadsNote:
    def test_analyze_item_injects_note_into_prompt(self):
        analyzer = _make_analyzer()
        captured = {}

        def fake_format_capture(*args, **kwargs):
            captured['seller_note'] = kwargs.get('seller_note')
            return "PROMPT"

        with patch("backend.app.services.ai_analyzer.EBAY_LISTING_PROMPT") as mock_prompt, \
             patch.object(analyzer, "encode_image", return_value="ZW5j"):
            mock_prompt.format.side_effect = fake_format_capture
            analyzer.analyze_item(["/fake/img.jpg"], seller_note="no charger")

        block = captured['seller_note']
        assert block is not None and "no charger" in block

    def test_analyze_item_default_note_is_empty_block(self):
        analyzer = _make_analyzer()
        captured = {}
        with patch("backend.app.services.ai_analyzer.EBAY_LISTING_PROMPT") as mock_prompt, \
             patch.object(analyzer, "encode_image", return_value="ZW5j"):
            mock_prompt.format.side_effect = lambda *a, **k: captured.update(k) or "P"
            analyzer.analyze_item(["/fake/img.jpg"])
        assert captured.get('seller_note') == ""
