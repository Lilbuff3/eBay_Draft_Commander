"""Profit ledger tests: SaleModel, fee math, sweep, summary, COGS parsing."""
from datetime import datetime, timezone

import pytest

from backend.app.core.database import init_db, SaleModel


@pytest.fixture
def session_factory(tmp_path):
    return init_db(tmp_path / "test_ledger.db")


class TestSaleModel:
    def test_sale_row_roundtrip(self, session_factory):
        session = session_factory()
        try:
            sale = SaleModel(
                order_id="12-34567-89012",
                listing_id="256789012345",
                job_id="a1b2c3d4",
                title="Aiwa CSD-ES227 Boombox",
                quantity=1,
                sale_total=54.99,
                sold_at=datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc),
                fees_est=7.58,
                ship_est=5.00,
                cogs=8.00,
            )
            session.add(sale)
            session.commit()

            row = session.query(SaleModel).one()
            assert row.order_id == "12-34567-89012"
            assert row.sale_total == 54.99
            assert row.cogs == 8.00
            assert row.created_at is not None
        finally:
            session.close()

    def test_cogs_nullable(self, session_factory):
        session = session_factory()
        try:
            session.add(SaleModel(order_id="x-1", sale_total=10.0))
            session.commit()
            assert session.query(SaleModel).one().cogs is None
        finally:
            session.close()


from backend.app.services.ledger import estimate_net


class TestEstimateNet:
    def test_full_math(self):
        # 54.99 sale, $8 cogs, $5 ship: fees = 54.99*0.1325 + 0.30 = 7.5862
        result = estimate_net(54.99, cogs=8.00, ship_cost=5.00)
        assert result['fees_est'] == 7.59
        assert result['ship_est'] == 5.00
        # net = 54.99 - 7.5862 - 5 - 8 = 34.40 (rounded)
        assert result['net'] == 34.40

    def test_unknown_cogs_gives_null_net(self):
        result = estimate_net(20.00, cogs=None, ship_cost=5.00)
        assert result['net'] is None
        assert result['fees_est'] == 2.95  # 20*0.1325 + 0.30

    def test_ship_cost_defaults_from_settings(self):
        # explicit ship_cost=None falls back to SOURCING_SHIP_COST (default 5.0)
        result = estimate_net(20.00, cogs=1.00)
        assert result['ship_est'] == 5.00
