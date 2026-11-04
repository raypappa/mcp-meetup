"""Formatting of Meetup events for display and for LLM context."""


def format_event_details(event) -> str:  # type: ignore[no-untyped-def]
    """Render a single event as a few human-readable lines."""
    lines = [
        event.title,
        f"   Group: {event.group_name}",
        f"   Date: {event.start_time.strftime('%Y-%m-%d %H:%M')}",
    ]

    if event.is_online:
        lines.append("   Location: Online/Remote")
    elif event.venue_name:
        location = event.venue_name
        if event.venue_city:
            location += f", {event.venue_city}"
        lines.append(f"   Location: {location}")

    if event.attendee_count:
        lines.append(f"   Attendees: {event.attendee_count}")

    if event.fee_amount:
        lines.append(f"   Fee: {event.fee_amount} {event.fee_currency or 'USD'}")
    else:
        lines.append("   Fee: Free")

    lines.append(f"   URL: {event.url}")
    return "\n".join(lines)


def format_events_for_context(events, *, limit: int = 10) -> str:
    """Format up to ``limit`` events as a block suitable for Claude's context.

    The header reports the full count; when more events were found than are
    listed, a "and N more events" footer makes the truncation explicit.
    """
    if not events:
        return "No events found matching your criteria."

    parts = [f"Found {len(events)} relevant events:"]
    for i, event in enumerate(events[:limit], 1):
        parts.append(f"\n{i}. " + format_event_details(event))

    if len(events) > limit:
        parts.append(f"\n(and {len(events) - limit} more events not listed)")

    return "\n".join(parts)


def format_search_results(query_text: str, events) -> str:
    """Format a search tool result: header + numbered event details."""
    if not events:
        return f"No events found matching '{query_text}'. Try different keywords or location."

    parts = [f"Found {len(events)} events matching '{query_text}':", ""]
    for i, event in enumerate(events, 1):
        parts.append(f"{i}. " + format_event_details(event))
        parts.append("")
    return "\n".join(parts)
