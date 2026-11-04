"""Tests for environment-based configuration."""

from mcp_meetup.config import Config, _to_int


def test_from_env_reads_all_values():
    env = {
        "MEETUP_CLIENT_ID": "id-123",
        "MEETUP_CLIENT_SECRET": "secret-456",
        "MEETUP_REDIRECT_URI": "http://example.com/cb",
        "MEETUP_ACCESS_TOKEN": "token-789",
        "ANTHROPIC_API_KEY": "key-abc",
        "LOG_LEVEL": "DEBUG",
        "MAX_EVENTS_PER_QUERY": "50",
        "DEFAULT_RADIUS": "10",
    }
    config = Config.from_env(env)
    assert config.MEETUP_CLIENT_ID == "id-123"
    assert config.MEETUP_CLIENT_SECRET == "secret-456"
    assert config.MEETUP_REDIRECT_URI == "http://example.com/cb"
    assert config.MEETUP_ACCESS_TOKEN == "token-789"
    assert config.ANTHROPIC_API_KEY == "key-abc"
    assert config.LOG_LEVEL == "DEBUG"
    assert config.MAX_EVENTS_PER_QUERY == 50
    assert config.DEFAULT_RADIUS == 10


def test_from_env_defaults_when_unset():
    config = Config.from_env({})
    assert config.MEETUP_CLIENT_ID == ""
    assert config.MEETUP_ACCESS_TOKEN == ""
    assert config.MEETUP_REDIRECT_URI == "http://localhost:8080/"
    assert config.MAX_EVENTS_PER_QUERY == 20
    assert config.DEFAULT_RADIUS == 25


def test_from_env_invalid_int_falls_back():
    config = Config.from_env({"MAX_EVENTS_PER_QUERY": "not-a-number"})
    assert config.MAX_EVENTS_PER_QUERY == 20


def test_validate_lists_missing_required_fields(config):
    missing = config.validate()
    assert missing == []


def test_validate_reports_each_missing_field():
    config = Config(
        MEETUP_CLIENT_ID="",
        MEETUP_CLIENT_SECRET="",
        MEETUP_REDIRECT_URI="http://localhost:8080/",
        MEETUP_ACCESS_TOKEN="token",
        ANTHROPIC_API_KEY="",
        LOG_LEVEL="INFO",
        MAX_EVENTS_PER_QUERY=20,
        DEFAULT_RADIUS=25,
    )
    assert sorted(config.validate()) == ["ANTHROPIC_API_KEY", "MEETUP_CLIENT_ID", "MEETUP_CLIENT_SECRET"]


def test_helpers(config):
    assert config.has_access_token is True
    assert config.oauth_available is True

    no_token = Config(
        MEETUP_CLIENT_ID="id",
        MEETUP_CLIENT_SECRET="",
        MEETUP_REDIRECT_URI="http://localhost:8080/",
        MEETUP_ACCESS_TOKEN="",
        ANTHROPIC_API_KEY="key",
        LOG_LEVEL="INFO",
        MAX_EVENTS_PER_QUERY=20,
        DEFAULT_RADIUS=25,
    )
    assert no_token.has_access_token is False
    assert no_token.oauth_available is False


def test_to_int():
    assert _to_int(None, 5) == 5
    assert _to_int("", 5) == 5
    assert _to_int("  ", 5) == 5
    assert _to_int("7", 5) == 7
    assert _to_int("7.5", 5) == 5
    assert _to_int("-3", 5) == -3
