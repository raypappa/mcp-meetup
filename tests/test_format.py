"""Tests for event formatting (LLM context and search results)."""

from datetime import datetime
from typing import Any

from mcp_meetup.format import (
    format_event_details,
    format_events_for_context,
    format_search_results,
)
from mcp_meetup.models import MeetupEvent


def make_event(i: int, **overrides: object) -> MeetupEvent:
    base: dict[str, Any] = {
        "id": str(i),
        "title": f"Event {i}",
        "description": f"Description {i}",
        "url": f"https://meetup.com/event{i}",
        "start_time": datetime(2026, 11, 15, 18, 0),
        "group_name": f"Group {i}",
        "group_url": f"https://meetup.com/group{i}",
        "attendee_count": i,
    }
    base.update(overrides)
    return MeetupEvent(**base)


class TestFormatEventDetails:
    def test_venue_event(self):
        event = make_event(1, venue_name="Tech Hub", venue_city="San Francisco", fee_amount=5.0, fee_currency="USD")
        details = format_event_details(event)
        assert "Event 1" in details
        assert "Group 1" in details
        assert "Tech Hub, San Francisco" in details
        assert "Fee: 5.0 USD" in details
        assert "URL: https://meetup.com/event1" in details

    def test_online_event(self):
        event = make_event(2, is_online=True)
        details = format_event_details(event)
        assert "Location: Online/Remote" in details

    def test_free_event(self):
        event = make_event(3)
        assert "Fee: Free" in format_event_details(event)


class TestFormatEventsForContext:
    def test_empty_list(self):
        assert "No events found" in format_events_for_context([])

    def test_with_events(self):
        events = [
            make_event(1, title="Python Meetup", venue_name="Tech Hub", venue_city="San Francisco"),
            make_event(2, title="Remote JS Workshop", is_online=True, fee_amount=15.0, fee_currency="USD"),
        ]
        result = format_events_for_context(events)
        assert "Found 2 relevant events" in result
        assert "Python Meetup" in result
        assert "Remote JS Workshop" in result
        assert "Tech Hub, San Francisco" in result
        assert "Online/Remote" in result
        assert "Free" in result
        assert "15.0 USD" in result

    def test_limits_to_ten_and_notes_rest(self):
        events = [make_event(i) for i in range(15)]
        result = format_events_for_context(events)
        assert "Found 15 relevant events" in result
        assert "Event 0" in result
        assert "Event 9" in result
        assert "Event 14" not in result
        assert "5 more events" in result

    def test_custom_limit(self):
        events = [make_event(i) for i in range(5)]
        result = format_events_for_context(events, limit=2)
        assert "Event 0" in result
        assert "Event 1" in result
        assert "Event 2" not in result
        assert "3 more events" in result


class TestFormatSearchResults:
    def test_empty(self):
        result = format_search_results("python events", [])
        assert "No events found" in result
        assert "python events" in result

    def test_with_events(self):
        events = [make_event(1, title="Python Meetup")]
        result = format_search_results("python events", events)
        assert "Found 1 events matching 'python events'" in result
        assert "Python Meetup" in result
