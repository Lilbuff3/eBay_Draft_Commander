"""
Contract test for the pricing projection seam.

ListingAIAgent.get_final_pricing does NOT pass the pricing engine's result
through -- it hand-copies a fixed set of keys into a new dict literal. Anything
the engine returns that isn't named there dies at the seam, silently, and no
amount of testing inside PricingEngine catches it. CLAUDE.md warns about this
in prose; this file makes it fail a test run instead.

`projected_profit` is the cautionary tale: the engine computes it on four of
its return paths and nothing downstream has ever seen it.

The engine's key set is derived from the SOURCE by AST, not hand-maintained.
That matters: a hand-written list only catches a dropped field if the author
remembers to add the new key to it -- which is exactly the step they already
forgot when they failed to thread it. Parsing the real return statements means
adding a field to the engine fails this test until someone either threads it or
records it below as an intentional drop.
"""
import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.app.services import pricing_engine as pricing_engine_module
from backend.app.services.listing_ai_agent import ListingAIAgent


# The engine names the price 'suggested_price'; the projection emits 'price'.
# Pinned here so the rename is documented behavior rather than folklore.
RENAMED = {'suggested_price': 'price'}

# Keys the projection deliberately does not carry. Add to this only with a
# reason -- an entry here is a decision, not a shrug.
INTENTIONALLY_DROPPED = {
    # Returned only by the Strategy-5 total-failure path alongside a null
    # price. The pipeline's own price-floor guard catches that case and routes
    # to review, so the string is redundant today. Threading it would be a
    # behavior change, not a bug fix.
    'error',
}


def _engine_return_keys() -> set:
    """Every literal key in every dict `get_price_with_comps` returns."""
    src = Path(inspect.getfile(pricing_engine_module)).read_text(encoding='utf-8')
    fn = next(
        node for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.FunctionDef) and node.name == 'get_price_with_comps'
    )
    keys = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            keys |= {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    return keys


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setattr(
        'backend.app.services.listing_ai_agent.AIAnalyzer', lambda: MagicMock()
    )
    monkeypatch.setattr(
        'backend.app.services.listing_ai_agent.PricingEngine', lambda: MagicMock()
    )
    return ListingAIAgent()


def test_ast_scan_actually_finds_the_engine_keys():
    """Guard the guard: if the AST scan silently returned nothing (function
    renamed, returns refactored into a helper), every other test in this file
    would vacuously pass forever."""
    keys = _engine_return_keys()
    assert len(keys) >= 8, f"AST scan found suspiciously few engine keys: {keys}"
    assert 'suggested_price' in keys
    assert 'projected_profit' in keys


def test_every_engine_field_is_threaded_or_explicitly_dropped(agent):
    """The seam contract. Add a field to get_price_with_comps and this fails
    until you thread it through get_final_pricing or record it as an
    intentional drop above."""
    engine_keys = _engine_return_keys()
    agent.pricing_engine.get_price_with_comps.return_value = {
        k: f'<{k}>' for k in engine_keys
    }

    result = agent.get_final_pricing(
        title='Widget', condition='USED_EXCELLENT',
        ai_suggested_price=10.0, user_price=None,
    )

    expected = {RENAMED.get(k, k) for k in engine_keys - INTENTIONALLY_DROPPED}
    missing = expected - set(result)
    assert not missing, (
        f"get_final_pricing drops engine field(s) {sorted(missing)}. Thread them "
        f"into the returned dict in listing_ai_agent.get_final_pricing, or add "
        f"them to INTENTIONALLY_DROPPED here with a reason."
    )


def test_engine_price_is_renamed_to_price(agent):
    """Pin the suggested_price -> price rename the projection performs."""
    agent.pricing_engine.get_price_with_comps.return_value = {
        'suggested_price': 42.5, 'comps': [], 'reasoning': '', 'source': 'market_data_isbn',
        'confidence': 'high', 'confidence_reason': 'exact ISBN match',
    }

    result = agent.get_final_pricing(
        title='Widget', condition='USED_EXCELLENT',
        ai_suggested_price=10.0, user_price=None,
    )

    assert result['price'] == '42.5'
    assert 'suggested_price' not in result


def test_projected_profit_reaches_the_caller(agent):
    """The regression that motivated this file: the only profitability number
    the engine computes must survive the seam."""
    agent.pricing_engine.get_price_with_comps.return_value = {
        'suggested_price': 42.5, 'comps': [], 'reasoning': '', 'source': 'market_data_isbn',
        'confidence': 'high', 'confidence_reason': '', 'projected_profit': 18.25,
    }

    result = agent.get_final_pricing(
        title='Widget', condition='USED_EXCELLENT',
        ai_suggested_price=10.0, user_price=None,
    )

    assert result['projected_profit'] == 18.25


class TestSynthesizedPaths:
    """The other two projections never call the engine, so they legitimately
    carry no engine fields. Pinned so the omission reads as a decision."""

    def test_user_override_path_shape(self, agent):
        result = agent.get_final_pricing(
            title='Widget', condition='USED_EXCELLENT',
            ai_suggested_price=10.0, user_price=99.99,
        )

        assert result['price'] == '99.99'
        assert result['source'] == 'user_override'
        assert result['confidence'] == 'user'
        agent.pricing_engine.get_price_with_comps.assert_not_called()
        # No engine ran, so there is nothing to report on these.
        for absent in ('comp_price', 'ai_price', 'projected_profit'):
            assert absent not in result

    def test_engine_failure_path_shape(self, agent):
        agent.pricing_engine.get_price_with_comps.side_effect = RuntimeError('boom')

        result = agent.get_final_pricing(
            title='Widget', condition='USED_EXCELLENT',
            ai_suggested_price=10.0, user_price=None,
        )

        assert result['price'] == '0.00'
        assert result['confidence'] == 'low'
        assert 'warning' in result
        # A low confidence here is load-bearing: it drives the review gate in
        # apply_pre_listing_guardrails so a failed price never lists silently.
