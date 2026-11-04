"""Pydantic models shared by the discovery and presentation layers."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

#: Page size of the discovery engine (overridable per query).
DEFAULT_MAX_RESULTS: int = 20


class EventQuery(BaseModel):
    """Structured representation of an event search request."""

    location: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    remote_only: bool = False
    max_results: int = DEFAULT_MAX_RESULTS


class MeetupEvent(BaseModel):
    """Standardized representation of a Meetup event."""

    id: str
    title: str
    description: str
    url: str
    start_time: datetime
    venue_name: Optional[str] = None
    venue_city: Optional[str] = None
    is_online: bool = False
    group_name: str
    group_url: str
    attendee_count: int = 0
    fee_amount: Optional[float] = None
    fee_currency: Optional[str] = None
