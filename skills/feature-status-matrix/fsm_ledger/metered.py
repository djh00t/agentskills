\
"""Context manager / decorator for pipelines to record tokens+cost into the ledger.

Usage (with PYTHONPATH=~/.agents/skills/feature-status-matrix):

    from fsm_ledger.metered import metered

    with metered(model="gpt-6-luna", work_package="AB-033") as m:
        ...
        m.add(input_tokens=100, output_tokens=50)
"""
from __future__ import annotations

import functools
import os
from contextlib import ContextDecorator
from typing import Any, Callable, Optional

from .ledger import append_dict


class metered(ContextDecorator):
    """Record usage into the shared ledger on exit (or on explicit flush)."""

    def __init__(
        self,
        *,
        model: str = "",
        work_package: Optional[str] = None,
        project: Optional[str] = None,
        provider: str = "",
        harness: str = "pipeline",
        billing_mode: str = "api",
        cost_total: Optional[float] = None,
        session_id: str = "",
        run_id: str = "",
        status: str = "ok",
        cwd: Optional[str] = None,
    ) -> None:
        self.model = model
        self.work_package = work_package
        self.project = project
        self.provider = provider
        self.harness = harness
        self.billing_mode = billing_mode
        self.cost_total = cost_total
        self.session_id = session_id
        self.run_id = run_id
        self.status = status
        self.cwd = cwd or os.environ.get("PWD") or os.getcwd()
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_input_tokens = 0
        self._flushed = False
        self.last_result: Optional[dict[str, Any]] = None

    def add(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_input_tokens: int = 0,
        cost_total: Optional[float] = None,
    ) -> None:
        self.input_tokens += int(input_tokens or 0)
        self.output_tokens += int(output_tokens or 0)
        self.cached_input_tokens += int(cached_input_tokens or 0)
        if cost_total is not None:
            self.cost_total = (self.cost_total or 0.0) + float(cost_total)

    def flush(self) -> dict[str, Any]:
        raw: dict[str, Any] = {
            "model": self.model,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cachedInputTokens": self.cached_input_tokens,
            "provider": self.provider,
            "harness": self.harness,
            "billing_mode": self.billing_mode,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "status": self.status,
            "cwd": self.cwd,
        }
        if self.work_package:
            raw["workPackageId"] = self.work_package
        if self.cost_total is not None:
            raw["costTotal"] = self.cost_total
        self.last_result = append_dict(raw, project=self.project)
        self._flushed = True
        return self.last_result

    def __enter__(self) -> "metered":
        return self

    def __exit__(self, *exc: Any) -> None:
        if not self._flushed and (self.input_tokens or self.output_tokens or self.cost_total):
            self.flush()
        return None


def metered_call(
    *,
    model: str = "",
    work_package: Optional[str] = None,
    **kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: expects the wrapped function to return a dict with token fields,
    or to accept a `meter` kwarg.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kw: Any) -> Any:
            with metered(model=model, work_package=work_package, **kwargs) as m:
                try:
                    return fn(*args, meter=m, **kw)
                except TypeError:
                    result = fn(*args, **kw)
                    if isinstance(result, dict):
                        m.add(
                            input_tokens=int(result.get("input_tokens") or result.get("inputTokens") or 0),
                            output_tokens=int(result.get("output_tokens") or result.get("outputTokens") or 0),
                            cached_input_tokens=int(
                                result.get("cached_input_tokens") or result.get("cachedInputTokens") or 0
                            ),
                            cost_total=result.get("cost_total") or result.get("costTotal"),
                        )
                    return result

        return wrapper

    return decorator
