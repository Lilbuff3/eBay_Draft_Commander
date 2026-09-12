"""Selling costs: one fee formula, and the callers that must agree with it.

The agreement tests are the point. The fee formula used to be written six ways
(jobs_api, ledger, sourcing, pricing_engine twice, lib/fees.ts) and the copies
drifted on which shipping number counts as a cost. These fail if a caller
grows its own copy again.
"""
import pytest

from backend.app.core import selling_costs
from backend.app.core.constants import ACTIVE_TO_SOLD_FACTOR


class TestFees:
    def test_fvf_plus_processing(self):
        # 100 * 0.1325 + 0.30
        assert selling_costs.fees(100) == pytest.approx(13.55)

    def test_no_sale_means_no_fees(self):
        # a $0 order must not report the $0.30 processing fee
        assert selling_costs.fees(0) == 0.0
        assert selling_costs.fees(None) == 0.0
        assert selling_costs.fees(-5) == 0.0


class TestNet:
    def test_subtracts_fees_ship_and_cogs(self):
        # 100 - 13.55 - 5.00 - 8.00
        assert selling_costs.net(100, ship=5.0, cogs=8.0) == pytest.approx(73.45)

    def test_cogs_defaults_to_zero(self):
        assert selling_costs.net(100, ship=5.0) == pytest.approx(81.45)

    def test_zero_price_is_zero_not_negative_fees(self):
        assert selling_costs.net(0, ship=5.0) == 0.0

    def test_ship_none_reads_the_knob(self):
        # default SOURCING_SHIP_COST is 5.00
        assert selling_costs.net(100) == pytest.approx(selling_costs.net(100, ship=5.0))


class TestCallersAgree:
    def test_ledger_matches(self):
        from backend.app.services.ledger import estimate_net
        got = estimate_net(54.99, cogs=8.00, ship_cost=5.00)
        assert got['fees_est'] == round(selling_costs.fees(54.99), 2)
        assert got['net'] == round(selling_costs.net(54.99, 5.00, 8.00), 2)

    def test_sourcing_matches(self):
        from backend.app.services.sourcing import compute_verdict
        verdict = compute_verdict(30.0, 8, [30.0], min_profit=5.0,
                                  roi_multiple=3.0, ship_cost=5.0)
        assumed_list = 30.0 * ACTIVE_TO_SOLD_FACTOR + 5.0
        assert verdict['net_proceeds'] == pytest.approx(
            selling_costs.net(assumed_list, 5.0), abs=0.01)

    def test_frontend_mirror_still_matches(self):
        """lib/fees.ts hand-mirrors these. Catch the drift that already bit us."""
        from pathlib import Path
        src = (Path(__file__).resolve().parents[2]
               / 'frontend' / 'src' / 'lib' / 'fees.ts').read_text(encoding='utf-8')
        assert 'EBAY_FINAL_VALUE_FEE_RATE = 0.1325' in src
        assert 'EBAY_PAYMENT_PROCESSING_FEE = 0.30' in src
        assert f'DEFAULT_SHIP_COST = {selling_costs.DEFAULT_SHIP_COST:g}' in src
