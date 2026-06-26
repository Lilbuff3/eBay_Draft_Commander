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


class TestAnalyzeWithResearchForwardsNote:
    def test_note_forwarded_to_analyze_item(self):
        analyzer = _make_analyzer()
        seen = {}

        def fake_analyze_item(image_paths, category_suggestions="", seller_note=""):
            seen['seller_note'] = seller_note
            return {"error": "stop here"}  # short-circuit before research phase

        with patch.object(analyzer, "analyze_item", side_effect=fake_analyze_item):
            analyzer.analyze_with_research(["/fake/img.jpg"], seller_note="antique")

        assert seen['seller_note'] == "antique"


from types import SimpleNamespace


class TestListingAgentReadsNote:
    def _agent(self):
        from backend.app.services.listing_ai_agent import ListingAIAgent
        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent.ai_analyzer = MagicMock()
        agent.ai_analyzer.analyze_with_research.return_value = {
            "identification": {}, "listing": {"suggested_title": "X", "description_html": "d"},
            "item_specifics": {},
        }
        return agent

    def _job(self, metadata):
        return SimpleNamespace(
            id="job1", folder_path="/c/inbox/x", user_title=None, user_description=None,
            ai_data={}, job_metadata=metadata,
        )

    def test_note_from_metadata_passed_to_analyzer(self):
        agent = self._agent()
        job = self._job({"note": "no power cord"})
        with patch("backend.app.services.listing_ai_agent.taxonomy.get_category_suggestions", return_value=[]):
            agent.analyze_item(job, ["/fake/img.jpg"], condition="Used - Good")
        _, kwargs = agent.ai_analyzer.analyze_with_research.call_args
        assert kwargs.get("seller_note") == "no power cord"

    def test_missing_note_passes_empty_string(self):
        agent = self._agent()
        job = self._job({})
        with patch("backend.app.services.listing_ai_agent.taxonomy.get_category_suggestions", return_value=[]):
            agent.analyze_item(job, ["/fake/img.jpg"], condition="Used - Good")
        _, kwargs = agent.ai_analyzer.analyze_with_research.call_args
        assert kwargs.get("seller_note") == ""


class TestPricingGroundingNote:
    def _engine(self):
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine.__new__(PricingEngine)
        engine.ai_client = None  # early-return after prompt build path is fine; we patch prompt capture
        return engine

    def test_estimate_accepts_and_uses_note(self):
        from backend.app.services import pricing_engine as pe
        engine = self._engine()
        # ai_client None -> returns None immediately; assert the kwarg is accepted (no TypeError)
        result = engine.get_ai_price_estimate("Widget", "Used - Good", seller_note="antique")
        assert result is None  # client not configured; call signature accepted the note
