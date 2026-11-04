"""Configuration for the MCP Meetup-Claude server.

Values are read from environment variables at import time (overridable via
``env`` for tests). The environment template lives in ``.env.example``.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Immutable snapshot of the server configuration."""

    MEETUP_CLIENT_ID: str
    MEETUP_CLIENT_SECRET: str
    MEETUP_REDIRECT_URI: str
    MEETUP_ACCESS_TOKEN: str
    ANTHROPIC_API_KEY: str
    LOG_LEVEL: str
    MAX_EVENTS_PER_QUERY: int
    DEFAULT_RADIUS: int

    #: Meetup REST v1 base URL (legacy find/geocoding API).
    MEETUP_BASE_URL: str = "https://api.meetup.com"
    #: OAuth2 endpoints for the legacy REST API.
    MEETUP_OAUTH_URL: str = "https://secure.meetup.com/oauth2"

    def validate(self) -> list[str]:
        """Return the names of missing required fields (empty when complete)."""
        required = ("MEETUP_CLIENT_ID", "MEETUP_CLIENT_SECRET", "ANTHROPIC_API_KEY")
        return [name for name in required if not getattr(self, name)]

    @property
    def has_access_token(self) -> bool:
        return bool(self.MEETUP_ACCESS_TOKEN)

    @property
    def oauth_available(self) -> bool:
        return bool(self.MEETUP_CLIENT_ID and self.MEETUP_CLIENT_SECRET)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        """Build a Config from ``os.environ`` (or the given mapping)."""
        if env is None:
            env = os.environ
        return cls(
            MEETUP_CLIENT_ID=env.get("MEETUP_CLIENT_ID", ""),
            MEETUP_CLIENT_SECRET=env.get("MEETUP_CLIENT_SECRET", ""),
            MEETUP_REDIRECT_URI=env.get("MEETUP_REDIRECT_URI", "http://localhost:8080/"),
            MEETUP_ACCESS_TOKEN=env.get("MEETUP_ACCESS_TOKEN", ""),
            ANTHROPIC_API_KEY=env.get("ANTHROPIC_API_KEY", ""),
            LOG_LEVEL=env.get("LOG_LEVEL", "INFO"),
            MAX_EVENTS_PER_QUERY=_to_int(env.get("MAX_EVENTS_PER_QUERY"), 20),
            DEFAULT_RADIUS=_to_int(env.get("DEFAULT_RADIUS"), 25),
        )


def _to_int(value: str | None, default: int) -> int:
    """Parse an int env value, falling back to ``default`` when unset/invalid."""
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default
