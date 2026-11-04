"""Shared fixtures and a real Meetup event payload for unit tests."""

import pytest

from mcp_meetup.config import Config


@pytest.fixture
def config() -> Config:
    return Config(
        MEETUP_CLIENT_ID="test-client-id",
        MEETUP_CLIENT_SECRET="test-client-secret",
        MEETUP_REDIRECT_URI="http://localhost:8080/",
        MEETUP_ACCESS_TOKEN="test-access-token",
        ANTHROPIC_API_KEY="test-api-key",
        LOG_LEVEL="DEBUG",
        MAX_EVENTS_PER_QUERY=20,
        DEFAULT_RADIUS=25,
    )


SAMPLE_EVENT_DATA: dict = {
    "id": "123456789",
    "name": "Python Programming Meetup",
    "description": "A meetup for Python enthusiasts",
    "link": "https://www.meetup.com/python-group/events/123456789/",
    "time": 1640995200000,  # 2022-01-01T00:00:00Z, milliseconds
    "duration": 7200000,
    "venue": {
        "id": 12345,
        "name": "Tech Hub",
        "address_1": "123 Tech Street",
        "city": "San Francisco",
    },
    "group": {
        "id": 54321,
        "name": "SF Python Group",
        "urlname": "sf-python-group",
    },
    "yes_rsvp_count": 42,
    "status": "upcoming",
    "fee": {"amount": 10.0, "currency": "USD"},
}

ONLINE_EVENT_DATA: dict = {
    "id": "987654321",
    "name": "Online Python Meetup",
    "description": "Virtual meetup",
    "link": "https://www.meetup.com/python-group/events/987654321/",
    "time": 1640995200000,
    "venue": {"id": 1, "name": "Online Event"},
    "group": {
        "id": 54321,
        "name": "SF Python Group",
        "urlname": "sf-python-group",
    },
    "yes_rsvp_count": 50,
    "status": "upcoming",
}
