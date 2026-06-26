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
