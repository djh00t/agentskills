from __future__ import annotations

import pytest

from scripts._client import resolve_bearer_token, resolve_user_context
from scripts._common import SkillConfigError


def test_resolve_bearer_token_from_env() -> None:
    token = resolve_bearer_token(env={"X_BEARER_TOKEN": "abc123"})
    assert token == "abc123"


def test_resolve_bearer_token_missing_raises() -> None:
    with pytest.raises(SkillConfigError):
        resolve_bearer_token(env={})


def test_resolve_user_context_requires_access_token() -> None:
    with pytest.raises(SkillConfigError):
        resolve_user_context(env={})


def test_resolve_user_context_reads_optional_user_id() -> None:
    ctx = resolve_user_context(env={"X_USER_ACCESS_TOKEN": "tok", "X_USER_ID": "42"})
    assert ctx.access_token == "tok"
    assert ctx.user_id == "42"
