from __future__ import annotations

from datetime import date

from pam.models import Lot
from pam.tax_lots import select_lots


def test_min_tax_prefers_long_term() -> None:
    as_of = date(2026, 2, 15)
    lots = [
        Lot(lot_id="A", quantity=5, cost_basis=100, purchase_date=date(2025, 2, 10)),
        Lot(lot_id="B", quantity=5, cost_basis=90, purchase_date=date(2026, 1, 10)),
    ]
    picked = select_lots(
        lots,
        sell_qty=5,
        as_of=as_of,
        current_price=110,
        long_term_days=365,
        method="MIN_TAX",
    )
    assert picked[0].lot_id == "A"
