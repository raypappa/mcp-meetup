"""MCP Meetup-Claude server: tools, resources, and the MCPServer instance.

Built on the MCP Python SDK v2 (``mcp.server.mcpserver.MCPServer``) using the
FastMCP-style decorators: ``@mcp.tool()`` and ``@mcp.resource(uri)``.

The shared ``ServerRuntime`` (config, HTTP session, Claude client) is created
once in the server lifespan and handed to handlers through the MCP ``Context``
lifespan — no per-import global state, and the HTTP session's event loop is
always the server's.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context

from . import __version__
from .config import Config
from .extract import extract_query_parameters
from .format import format_events_for_context, format_search_results
from .meetup_client import MeetupClient, build_oauth_url
from .models import EventQuery, MeetupEvent

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-3-sonnet-20240229"


class ServerRuntime:
    """Shared runtime state for the server, created in the lifespan."""

    def __init__(self, config: Config, client: MeetupClient, claude: Any | None = None):
        self.config = config
        self.client = client
        self.claude = claude

    @property
    def claude_configured(self) -> bool:
        return self.claude is not None


async def server_lifespan(server: MCPServer) -> AsyncIterator[ServerRuntime]:
    """Create (once) and dispose (once) the shared runtime state."""
    config = Config.from_env()
    missing = config.validate()
    if missing:
        logger.warning(
            "Missing configuration (tools will report it): %s", ", ".join(missing)
        )

    client = MeetupClient(config)
    claude = None
    if config.ANTHROPIC_API_KEY:
        from anthropic import AsyncAnthropic

        claude = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

    try:
        logger.info(
            "MCP Meetup-Claude server ready (access_token=%s, claude=%s)",
            config.has_access_token,
            claude is not None,
        )
        yield ServerRuntime(config, client, claude)
    finally:
        await client.close()
        if claude is not None:
            await claude.close()


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = MCPServer(
    name="meetup-claude-mcp",
    version=__version__,
    description="Meetup.com event discovery with Claude-powered recommendations.",
    lifespan=asynccontextmanager(server_lifespan),
)


def _runtime_from_context(context: Context | None) -> ServerRuntime:
    """Fetch the ServerRuntime carried in the lifespan context."""
    if context is None:
        raise RuntimeError("Server context not available")
    request_context = context.request_context
    if request_context is None:
        raise RuntimeError("Server context not available")
    lifespan = request_context.lifespan_context
    if not isinstance(lifespan, ServerRuntime):
        raise RuntimeError("Server lifespan not initialized")
    return lifespan


async def _get_meetup_events(
    context: Context, query: EventQuery
) -> list[MeetupEvent]:
    """Search Meetup; on API failure return an empty list and log the cause."""
    runtime = _runtime_from_context(context)
    try:
        return await runtime.client.search_events(query)
    except Exception as exc:
        logger.exception("Meetup search failed")
        return []


async def _augment_prompt(runtime: ServerRuntime, user_prompt: str) -> str:
    """Prepend a block of relevant Meetup events to a user prompt."""
    query = extract_query_parameters(user_prompt)
    events = await runtime.client.search_events(query)

    if not events:
        return f"{user_prompt}\n\n[Note: No relevant Meetup events found.]"

    event_context = format_events_for_context(events)
    return (
        f"{user_prompt}\n\n"
        f"=== Relevant Meetup Events ===\n{event_context}\n\n"
        "Please provide recommendations based on the above events."
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_meetup_events(
    query: str,
    max_results: int = 20,
    context: Context | None = None,
) -> str:
    """Search for Meetup events from a natural language query.

    Args:
        query: Natural language search query (e.g. "python meetups in san francisco today").
        max_results: Maximum number of events to return (default 20, max 100).
    """
    if not query:
        return "Error: Query parameter is required"
    if context is None:
        return "Error: Server context not available"

    try:
        runtime = _runtime_from_context(context)
        parsed = extract_query_parameters(query)
        parsed.max_results = max(1, min(max_results, 100))
        events = await _get_meetup_events(context, parsed)
        return format_search_results(query, events)
    except Exception as exc:
        logger.exception("Error searching events")
        return f"Error searching events: {exc}"


@mcp.tool()
async def augment_prompt_with_events(
    prompt: str,
    context: Context | None = None,
) -> str:
    """Enhance a prompt with relevant Meetup event data.

    Args:
        prompt: User prompt to augment with event data.
    """
    if not prompt:
        return "Error: Prompt parameter is required"
    if context is None:
        return "Error: Server context not available"

    try:
        runtime = _runtime_from_context(context)
        return await _augment_prompt(runtime, prompt)
    except Exception as exc:
        logger.exception("Error augmenting prompt")
        return f"Error augmenting prompt: {exc}"


@mcp.tool()
async def get_event_recommendations(
    query: str,
    preferences: str = "",
    context: Context | None = None,
) -> str:
    """Get AI-powered event recommendations from Claude.

    The query is first augmented with matching Meetup events; if the Anthropic
    API key is not configured, the event data is returned instead.

    Args:
        query: Natural language query for event recommendations.
        preferences: Additional preferences or constraints.
    """
    if not query:
        return "Error: Query parameter is required"
    if context is None:
        return "Error: Server context not available"

    try:
        runtime = _runtime_from_context(context)
        full_prompt = query
        if preferences:
            full_prompt += f"\n\nAdditional preferences: {preferences}"

        augmented_prompt = await _augment_prompt(runtime, full_prompt)

        claude = runtime.claude
        if claude is None:
            return (
                "Claude integration not configured. Here's the event data:\n\n"
                f"{augmented_prompt}"
            )

        try:
            message = await claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": augmented_prompt}],
            )
            return message.content[0].text
        except Exception as exc:
            logger.error("Claude API error: %s", exc)
            return (
                f"Claude API unavailable. Here's the event data instead:\n\n"
                f"{augmented_prompt}"
            )
    except Exception as exc:
        logger.exception("Error getting recommendations")
        return f"Error getting recommendations: {exc}"


@mcp.tool()
def get_oauth_url(context: Context | None = None) -> str:
    """Get the Meetup OAuth authorization URL for authentication."""
    if context is None:
        return "Error: Server context not available"

    try:
        runtime = _runtime_from_context(context)
        if not runtime.config.oauth_available:
            return (
                "Error: MEETUP_CLIENT_ID and MEETUP_CLIENT_SECRET must be set "
                "to generate an OAuth URL."
            )
        url = build_oauth_url(runtime.config)
        return (
            f"Meetup OAuth Authorization URL:\n{url}\n\n"
            "Instructions:\n"
            "1. Visit the URL above\n"
            "2. Log in to your Meetup account\n"
            "3. Authorize the application\n"
            "4. Copy the authorization code from the redirect\n"
            "5. Exchange the code for an access token"
        )
    except Exception as exc:
        logger.exception("Error generating OAuth URL")
        return f"Error generating OAuth URL: {exc}"


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("meetup://config", description="Current server configuration and status")
def get_server_config() -> str:
    """Current server configuration and status (read from the server environment)."""
    config = Config.from_env()
    data = {
        "meetup_client_id": (config.MEETUP_CLIENT_ID[:8] + "...")
        if config.MEETUP_CLIENT_ID
        else "Not set",
        "meetup_client_secret": "Set" if config.MEETUP_CLIENT_SECRET else "Not set",
        "anthropic_api_key": "Set" if config.ANTHROPIC_API_KEY else "Not set",
        "max_events_per_query": config.MAX_EVENTS_PER_QUERY,
        "default_radius": config.DEFAULT_RADIUS,
        "log_level": config.LOG_LEVEL,
    }
    return json.dumps(data, indent=2)


@mcp.resource("meetup://auth/status", description="Current authentication status with Meetup.com")
def get_auth_status() -> str:
    """Current authentication status with Meetup.com."""
    config = Config.from_env()
    status = {
        "has_access_token": bool(config.MEETUP_ACCESS_TOKEN),
        "oauth_url_available": config.oauth_available,
        "claude_integration": bool(config.ANTHROPIC_API_KEY),
    }
    return json.dumps(status, indent=2)
