"""Heuristic extraction of structured search parameters from natural language.

This is deliberately lightweight (no NLP dependency): pattern matching for
time references, locations, remote/online indicators, and a fixed list of
tech-topic keywords. It is good enough for casual queries like
"python meetups in san francisco this weekend" and is unit-tested directly.
"""

import re
from collections.abc import Callable
from datetime import datetime, timedelta

from .models import EventQuery

def _start_of_day() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


_TIME_PATTERNS: list[tuple[str, Callable[[], datetime]]] = [
    (r"\btoday\b", _start_of_day),
    (r"\btomorrow\b", lambda: _start_of_day() + timedelta(days=1)),
    (r"\bnext week\b", lambda: _start_of_day() + timedelta(weeks=1)),
    (r"\bthis week\b", _start_of_day),
]

_LOCATION_NEAR_ME = re.compile(r"\bnear me\b")
# Matches "in <letters, spaces, commas>" — city names like "San Francisco"
# or "New York, NY". Trailing time words are stripped in extract().
_LOCATION_CITY = re.compile(r"\bin ([A-Za-z][A-Za-z ,]*)")

#: Time words that may leak into a captured location and must be cut off.
_LOCATION_STOPWORDS = (
    " tonight",
    " today",
    " tomorrow",
    " this week",
    " next week",
    " this weekend",
    " next weekend",
    " this morning",
    " tomorrow morning",
    " in the morning",
    " in the afternoon",
    " in the evening",
)


def _clean_location(raw: str) -> str:
    """Trim trailing time words from a captured location string."""
    location = raw.strip()
    for stopword in _LOCATION_STOPWORDS:
        index = location.find(stopword)
        if index != -1:
            location = location[:index]
    return location.strip(" ,") or raw.strip()

_REMOTE_TERMS = ("remote", "online", "virtual")

TECH_KEYWORDS = (
    "programming",
    "coding",
    "software",
    "tech",
    "python",
    "javascript",
    "data science",
    "machine learning",
    "ai",
    "web development",
    "mobile",
)


def extract_query_parameters(user_prompt: str) -> EventQuery:
    """Extract time, location, remote flag, and topic keywords from a prompt."""
    query = EventQuery()
    prompt_lower = user_prompt.lower()

    for pattern, time_func in _TIME_PATTERNS:
        if re.search(pattern, prompt_lower):
            query.start_time = time_func()
            break

    if _LOCATION_NEAR_ME.search(prompt_lower):
        query.location = "current_location"
    else:
        match = _LOCATION_CITY.search(prompt_lower)
        if match:
            query.location = _clean_location(match.group(1))

    if any(term in prompt_lower for term in _REMOTE_TERMS):
        query.remote_only = True

    for keyword in TECH_KEYWORDS:
        if keyword in prompt_lower:
            query.keywords.append(keyword)

    return query
