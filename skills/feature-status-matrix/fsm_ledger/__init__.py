"""fsm_ledger — shared usage ledger for feature-status-matrix.

Stdlib + optional PyYAML. Soft-imports agent-brain pricing when on PYTHONPATH.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .ledger import append_event, append_dict
from .schema import UNALLOCATED, UsageEvent, normalize_event

__all__ = [
    "UNALLOCATED",
    "UsageEvent",
    "append_dict",
    "append_event",
    "normalize_event",
    "__version__",
]
