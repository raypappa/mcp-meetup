"""Tests for Meetup REST API event parsing and OAuth URL construction."""

import pytest

from mcp_meetup.config import Config
from mcp_meetup.meetup_client import build_oauth_url, parse_rest_event
from conftest import ONLINE_EVENT_DATA, SAMPLE_EVENT_DATA


class TestParseRestEvent:
    def test_parse_full_event(self):
        event = parse_rest_event(SAMPLE_EVENT_DATA)
        assert event.id == "123456789"
        assert event.title == "Python Programming Meetup"
        assert event.description == "A meetup for Python enthusiasts"
        assert event.url == "https://www.meetup.com/python-group/events/123456789/"
        assert event.venue_name == "Tech Hub"
        assert event.venue_city == "San Francisco"
        assert event.group_name == "SF Python Group"
        assert event.group_url == "https://www.meetup.com/sf-python-group"
        assert event.attendee_count == 42
        assert event.fee_amount == 10.0
        assert event.fee_currency == "USD"
        assert event.is_online is False

    def test_millisecond_timestamp_converted(self):
        event = parse_rest_event(SAMPLE_EVENT_DATA)
        # 1640995200000 ms = 2022-01-01T00:00:00Z
        assert event.start_time.year == 2022
        assert event.start_time.month == 1
        assert event.start_time.day == 1

    def test_parse_online_event(self):
        event = parse_rest_event(ONLINE_EVENT_DATA)
        assert event.is_online is True

    def test_parse_event_missing_venue_and_fee(self):
        data = {
            "id": "555",
            "name": "No Venue Event",
            "description": "",
            "link": "https://www.meetup.com/x/events/555",
            "time": 1640995200000,
            "group": {"name": "G", "urlname": "g"},
        }
        event = parse_rest_event(data)
        assert event.venue_name is None
        assert event.venue_city is None
        assert event.is_online is False
        assert event.fee_amount is None
        assert event.fee_currency is None

    def test_parse_event_missing_time_raises(self):
        with pytest.raises(ValueError):
            parse_rest_event({"id": "1", "name": "No Time"})

    def test_parse_event_missing_id_raises(self):
        with pytest.raises(ValueError):
            parse_rest_event({"name": "No Id", "time": 1640995200000})

    def test_parse_event_null_venue_treated_as_absent(self):
        data = dict(SAMPLE_EVENT_DATA)
        data["venue"] = None
        event = parse_rest_event(data)
        assert event.venue_name is None
        assert event.is_online is False

    def test_parse_event_null_group_treated_as_absent(self):
        data = dict(SAMPLE_EVENT_DATA)
        data["group"] = None
        event = parse_rest_event(data)
        assert event.group_name == "Unknown Group"


class TestBuildOAuthUrl:
    def test_contains_required_params(self, config):
        url = build_oauth_url(config)
        assert url.startswith("https://secure.meetup.com/oauth2/authorize?")
        assert "client_id=test-client-id" in url
        assert "response_type=code" in url
        assert "redirect_uri=" in url
        assert "scope=basic" in url

    def test_redirect_uri_is_url_encoded(self):
        config = Config(
            MEETUP_CLIENT_ID="id",
            MEETUP_CLIENT_SECRET="secret",
            MEETUP_REDIRECT_URI="http://localhost:8080/cb",
            MEETUP_ACCESS_TOKEN="",
            ANTHROPIC_API_KEY="",
            LOG_LEVEL="INFO",
            MAX_EVENTS_PER_QUERY=20,
            DEFAULT_RADIUS=25,
        )
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fcb" in build_oauth_url(config)
