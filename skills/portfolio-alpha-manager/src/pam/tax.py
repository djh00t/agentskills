from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TaxNote:
    note: str
    days_held: int
    days_to_long_term: int


def holding_period_note(
    purchase_date: date,
    as_of: date,
    long_term_days: int,
    prefer_hold_days_remaining: int,
) -> TaxNote:
    days_held = (as_of - purchase_date).days
    days_to_lt = max(0, long_term_days - days_held)

    if days_to_lt == 0:
        note = "Long-term holding period met."
    elif days_to_lt <= prefer_hold_days_remaining:
        note = f"Tax-aware: {days_to_lt} days until long-term threshold; avoid churn if possible."
    else:
        note = f"Short-term holding period: {days_to_lt} days until long-term threshold."

    return TaxNote(note=note, days_held=days_held, days_to_long_term=days_to_lt)
