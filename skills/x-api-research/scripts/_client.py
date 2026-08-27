from __future__ import annotations

import os
from dataclasses import dataclass

from xdk import Client

from scripts._common import SkillConfigError


@dataclass(frozen=True)
class UserContext:
    """Resolved user context values for user-authenticated operations."""

    access_token: str
    user_id: str | None


def _get_required_env(name: str, *, env: dict[str, str] | None = None) -> str:
    """Return required environment variable value or raise a config error."""
    values = env if env is not None else os.environ
    value = values.get(name)
    if value:
        return value
    raise SkillConfigError(f"Missing required environment variable: {name}")


def resolve_bearer_token(*, env: dict[str, str] | None = None) -> str:
    """Resolve the app-level bearer token required for most X API calls."""
    return _get_required_env("X_BEARER_TOKEN", env=env)


def resolve_user_context(*, env: dict[str, str] | None = None) -> UserContext:
    """Resolve user access token and optional user id for bookmark workflows."""
    values = env if env is not None else os.environ
    access_token = values.get("X_USER_ACCESS_TOKEN")
    if not access_token:
        raise SkillConfigError(
            "Missing required environment variable: X_USER_ACCESS_TOKEN "
            "(bookmark lookup requires user-context auth)"
        )
    return UserContext(access_token=access_token, user_id=values.get("X_USER_ID"))


def build_app_client(*, env: dict[str, str] | None = None) -> Client:
    """Build an XDK client for app-authenticated read operations."""
    bearer_token = resolve_bearer_token(env=env)
    return Client(bearer_token=bearer_token)


def build_user_client(*, env: dict[str, str] | None = None) -> tuple[Client, UserContext]:
    """Build an XDK client with bearer and user access token auth."""
    bearer_token = resolve_bearer_token(env=env)
    user_context = resolve_user_context(env=env)
    return Client(bearer_token=bearer_token, access_token=user_context.access_token), user_context
