from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Literal

from pam.models import Lot


Method = Literal["FIFO", "LIFO", "MIN_TAX", "HARVEST_LOSS", "MIN_GAIN", "MAX_GAIN"]


@dataclass(frozen=True)
class SelectedLot:
    lot_id: str
    quantity: float
    purchase_date: date
    cost_basis: float


def _long_term(purchase: date, as_of: date, long_term_days: int) -> bool:
    return (as_of - purchase).days >= long_term_days


def select_lots(
    lots: List[Lot],
    sell_qty: float,
    as_of: date,
    current_price: float,
    long_term_days: int,
    method: Method,
) -> List[SelectedLot]:
    def gain_per_share(lot: Lot) -> float:
        return current_price - lot.cost_basis

    if method == "FIFO":
        ordered = sorted(lots, key=lambda lot: (lot.purchase_date, lot.lot_id))
    elif method == "LIFO":
        ordered = sorted(lots, key=lambda lot: (lot.purchase_date, lot.lot_id), reverse=True)
    elif method == "MIN_TAX":
        ordered = sorted(
            lots,
            key=lambda lot: (
                0 if _long_term(lot.purchase_date, as_of, long_term_days) else 1,
                lot.purchase_date,
                lot.lot_id,
            ),
        )
    elif method == "HARVEST_LOSS":
        ordered = sorted(lots, key=lambda lot: (gain_per_share(lot), lot.purchase_date, lot.lot_id))
    elif method == "MIN_GAIN":
        ordered = sorted(lots, key=lambda lot: (gain_per_share(lot), lot.purchase_date, lot.lot_id))
    elif method == "MAX_GAIN":
        ordered = sorted(
            lots,
            key=lambda lot: (gain_per_share(lot), lot.purchase_date, lot.lot_id),
            reverse=True,
        )
    else:
        ordered = sorted(lots, key=lambda lot: (lot.purchase_date, lot.lot_id))

    remaining = sell_qty
    out: List[SelectedLot] = []
    for lot in ordered:
        if remaining <= 0:
            break
        take = min(lot.quantity, remaining)
        if take > 0:
            out.append(
                SelectedLot(
                    lot_id=lot.lot_id,
                    quantity=take,
                    purchase_date=lot.purchase_date,
                    cost_basis=lot.cost_basis,
                )
            )
            remaining -= take
    return out
