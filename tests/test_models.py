"""Tests for the Pydantic data models."""

from datetime import datetime

from mcp_meetup.models import EventQuery, MeetupEvent


def test_event_query_defaults():
    query = EventQuery()
    assert query.location is None
    assert query.keywords == []
    assert query.start_time is None
    assert query.remote_only is False
    assert query.max_results == 20


def test_event_query_with_data():
    query = EventQuery(
        location="San Francisco",
        keywords=["python", "programming"],
        remote_only=True,
        max_results=10,
        start_time=datetime(2026, 11, 3, 9, 0),
    )
    assert query.location == "San Francisco"
    assert query.keywords == ["python", "programming"]
    assert query.remote_only is True
    assert query.max_results == 10


def test_meetup_event_full():
    event = MeetupEvent(
        id="123",
        title="Test Event",
        description="A test event",
        url="https://meetup.com/test",
        start_time=datetime.now(),
        venue_name="Test Venue",
        venue_city="Test City",
        is_online=False,
        group_name="Test Group",
        group_url="https://meetup.com/test-group",
        attendee_count=50,
        fee_amount=5.0,
        fee_currency="USD",
    )
    assert event.id == "123"
    assert event.venue_name == "Test Venue"
    assert event.fee_amount == 5.0


def test_meetup_event_minimal_defaults():
    event = MeetupEvent(
        id="123",
        title="Minimal",
        description="",
        url="https://meetup.com/minimal",
        start_time=datetime(2026, 11, 3),
        group_name="Group",
        group_url="https://meetup.com/group",
    )
    assert event.venue_name is None
    assert event.venue_city is None
    assert event.is_online is False
    assert event.attendee_count == 0
    assert event.fee_amount is None
    assert event.fee_currency is None
