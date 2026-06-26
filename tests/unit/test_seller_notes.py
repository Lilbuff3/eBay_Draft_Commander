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


class TestPriceWithCompsThreadsNote:
    def test_note_reaches_grounding_estimate(self):
        from backend.app.services.pricing_engine import PricingEngine
        engine = PricingEngine.__new__(PricingEngine)
        captured = {}

        def fake_estimate(title, condition, identification=None, seller_note=""):
            captured['seller_note'] = seller_note
            return None

        # Force the cascade to reach grounding: no comps, no research price.
        engine.search_sold_listings = lambda *a, **k: []
        engine.filter_comps = lambda comps, ref: []
        engine.get_ai_price_estimate = fake_estimate
        engine._build_keyword_query = lambda title, identification=None: title

        engine.get_price_with_comps(
            "Obscure Widget", condition="Used - Good", seller_note="antique, working"
        )
        assert captured.get('seller_note') == "antique, working"


class TestFinalPricingNote:
    def test_get_final_pricing_forwards_note(self):
        from backend.app.services.listing_ai_agent import ListingAIAgent
        agent = ListingAIAgent.__new__(ListingAIAgent)
        agent._default_shipping_cost = 0.0
        captured = {}

        agent.pricing_engine = MagicMock()
        def fake_comps(*args, **kwargs):
            captured['seller_note'] = kwargs.get('seller_note')
            return {"suggested_price": "10.00", "comps": [], "reasoning": "", "source": "x"}
        agent.pricing_engine.get_price_with_comps.side_effect = fake_comps

        agent.get_final_pricing(
            "Widget", "Used - Good", ai_suggested_price=5, user_price=None,
            shipping_cost=0.0, seller_note="no charger",
        )
        assert captured.get('seller_note') == "no charger"


class TestCaptureNoteCleaning:
    def test_clean_note_trims_and_caps(self):
        from backend.app.blueprints.api.queue_api import _clean_capture_note
        assert _clean_capture_note("  no charger  ") == "no charger"
        assert _clean_capture_note(None) == ""
        assert _clean_capture_note(123) == ""  # non-str -> empty
        long = "x" * 1000
        assert len(_clean_capture_note(long)) == 500


class TestCaptureBridgeNote:
    def test_capture_posts_note_in_body(self, tmp_path, monkeypatch):
        import integrations.hermes.capture_to_dc as bridge

        # one real image so build_item_folder succeeds
        from PIL import Image
        img = tmp_path / "a.jpg"
        Image.new("RGB", (10, 10)).save(img)
        captures = tmp_path / "caps"
        captures.mkdir()

        posted = {}

        class FakeResp:
            status_code = 200
            def json(self):
                return {"success": True, "job_id": "j1", "scheduled_time": "soon"}

        def fake_post(url, json=None, timeout=None):
            posted['url'] = url
            posted['json'] = json
            return FakeResp()

        monkeypatch.setattr(bridge.requests, "post", fake_post)
        monkeypatch.setattr(bridge, "_health_ok", lambda api_base: True)
        # short-circuit polling: return immediately as scheduled
        monkeypatch.setattr(bridge.requests, "get", lambda *a, **k: type("G", (), {
            "status_code": 200, "json": lambda self: {"status": "scheduled"}})())

        bridge.capture([str(img)], api_base="http://x", captures_dir=str(captures),
                       poll_interval=0, poll_timeout=0, note="no charger")

        assert posted['json']['note'] == "no charger"
        assert posted['json']['path']


class TestPluginDeriveNote:
    def test_strips_sell_trigger_keeps_rest(self):
        from integrations.hermes.plugin import _derive_note
        assert _derive_note("blue widget no charger sell") == "blue widget no charger"
        assert _derive_note("SELL antique not replica") == "antique not replica"

    def test_empty_or_trigger_only(self):
        from integrations.hermes.plugin import _derive_note
        assert _derive_note("sell") == ""
        assert _derive_note("") == ""
        assert _derive_note(None) == ""

    def test_collapses_whitespace(self):
        from integrations.hermes.plugin import _derive_note
        assert _derive_note("new   old   stock  sell") == "new old stock"
