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
