"""Meetup REST API client: geocoding, event search, and event parsing.

Meetup's legacy REST API (GET /geocoding/search, GET /find/upcoming_events)
now resolves free-geoip-style location strings server-side, so a plain
``location=<city>`` query parameter works without a separate geocoding step
and without OAuth for basic event search. The v1 API accepts ``limit``
(events per page) and ``page`` (page number) — ``page`` must not be used to
control how many results are returned; that is what ``limit`` is for.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

import aiohttp

from .config import Config
from .models import EventQuery, MeetupEvent

logger = logging.getLogger(__name__)


class MeetupClient:
    """Async client for the Meetup REST API."""

    def __init__(
        self,
        config: Config,
        session: Optional[aiohttp.ClientSession] = None,
        base_url: Optional[str] = None,
    ):
        self.config = config
        self._owns_session = session is None
        self.session = session or aiohttp.ClientSession()
        self.base_url = base_url or config.MEETUP_BASE_URL

    async def close(self) -> None:
        if self._owns_session:
            await self.session.close()

    async def search_events(self, query: EventQuery) -> list[MeetupEvent]:
        """Search upcoming events, parsing into MeetupEvent models.

        Never raises for API-level failures: an empty list is returned and the
        failure is logged, so a malformed response degrades the tool result
        gracefully instead of killing the MCP request.
        """
        params: dict[str, Any] = {"status": "upcoming", "limit": query.max_results}
        if query.location and query.location != "current_location":
            params["location"] = query.location
        if query.start_time:
            # Meetup v1 expects YYYY-MM-DDTHH:MM:SS (seconds precision).
            params["start_date_range"] = query.start_time.strftime("%Y-%m-%dT%H:%M:%S")
        if query.keywords:
            params["text"] = " ".join(query.keywords)

        url = f"{self.base_url}/find/upcoming_events"
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                else:
                    error_text = await response.text()
                    logger.error("Meetup API error %s: %s", response.status, error_text[:200])
                    return []
        except Exception:
            logger.exception("Meetup API request failed")
            return []

        events: list[MeetupEvent] = []
        for event_data in data.get("events", []):
            try:
                event = parse_rest_event(event_data)
            except Exception as exc:  # noqa: BLE001 - skip malformed items
                logger.warning("Error parsing event: %s", exc)
                continue
            if query.remote_only and not event.is_online:
                continue
            events.append(event)
        return events


def parse_rest_event(event_data: dict[str, Any]) -> MeetupEvent:
    """Parse one event dict from the Meetup REST API into a MeetupEvent.

    The legacy API returns millisecond timestamps and nests venue/group/fee
    objects (any of which may be absent or partial).
    """
    venue = event_data.get("venue") or {}
    group = event_data.get("group") or {}
    fee = event_data.get("fee") or {}

    event_id = event_data.get("id")
    time_value = event_data.get("time")
    if event_id is None or time_value is None:
        raise ValueError(f"Event data missing 'id' or 'time': {json.dumps(event_data)[:200]}")

    return MeetupEvent(
        id=str(event_id),
        title=event_data.get("name", "Untitled Event"),
        description=event_data.get("description", ""),
        url=event_data.get("link", ""),
        start_time=datetime.fromtimestamp(time_value / 1000),
        venue_name=venue.get("name"),
        venue_city=venue.get("city"),
        is_online=venue.get("id") == 1,
        group_name=group.get("name", "Unknown Group"),
        group_url=f"https://www.meetup.com/{group.get('urlname', '')}",
        attendee_count=event_data.get("yes_rsvp_count", 0) or 0,
        fee_amount=fee.get("amount"),
        fee_currency=fee.get("currency"),
    )


def build_oauth_url(config: Config) -> str:
    """OAuth2 authorization URL for the legacy Meetup REST API."""
    from urllib.parse import urlencode

    params = {
        "client_id": config.MEETUP_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": config.MEETUP_REDIRECT_URI,
        "scope": "basic",
    }
    return f"{config.MEETUP_OAUTH_URL}/authorize?{urlencode(params)}"
