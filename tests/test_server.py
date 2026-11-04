"""End-to-end tests for the MCP server: tools, resources, and entry point.

Three layers:
1. Tool implementations driven with a lifespan context (unit level).
2. The MCP protocol surface: ``mcp.list_tools`` / ``mcp.call_tool`` and the
   in-process ``Client`` (schema generation, validation, dispatch).
3. The real stdio entry point: ``python -m mcp_meetup`` launched as a
   subprocess and driven over stdin/stdout.
"""

import sys
from datetime import datetime
from typing import Any

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context

from mcp_meetup.config import Config
from mcp_meetup.meetup_client import MeetupClient
from mcp_meetup.models import EventQuery, MeetupEvent
from mcp_meetup.server import (
    ServerRuntime,
    augment_prompt_with_events,
    get_event_recommendations,
    get_oauth_url,
    search_meetup_events,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_event(title: str = "Python Meetup", **overrides: Any) -> MeetupEvent:
    base: dict[str, Any] = {
        "id": "1",
        "title": title,
        "description": "desc",
        "url": "https://meetup.com/1",
        "start_time": datetime(2026, 11, 15, 18, 0),
        "group_name": "SF Python",
        "group_url": "https://meetup.com/sf-python",
        "attendee_count": 25,
    }
    base.update(overrides)
    return MeetupEvent(**base)


class FakeClientSession:
    """An object whose close() records calls (no network)."""

    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeClaudeClient:
    """Mimics the slice of AsyncAnthropic used by the recommendations tool."""

    def __init__(self) -> None:
        self.messages = self
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)

        class _Message:
            content = [type("T", (), {"text": "Here are some recommendations."})()]

        return _Message()


@pytest.fixture
def config() -> Config:
    return Config(
        MEETUP_CLIENT_ID="test-client-id",
        MEETUP_CLIENT_SECRET="test-client-secret",
        MEETUP_REDIRECT_URI="http://localhost:8080/",
        MEETUP_ACCESS_TOKEN="token-123",
        ANTHROPIC_API_KEY="key-456",
        LOG_LEVEL="DEBUG",
        MAX_EVENTS_PER_QUERY=20,
        DEFAULT_RADIUS=25,
    )


def make_runtime(config: Config) -> ServerRuntime:
    fake_http = FakeClientSession()
    client = MeetupClient(config, session=fake_http)
    return ServerRuntime(config, client, FakeClaudeClient())


@pytest.fixture
def runtime(config: Config) -> ServerRuntime:
    return make_runtime(config)


def make_context(runtime: ServerRuntime) -> Context:
    """A Context carrying the test runtime via a mock request context."""

    class _MockRequestContext:
        lifespan_context = runtime

    server: MCPServer = MCPServer(name="test-server")
    return Context(
        request_context=_MockRequestContext(),
        mcp_server=server,
    )


@pytest.fixture
def context(runtime: ServerRuntime) -> Context:
    """A Context carrying the test runtime (no request needed for tools)."""
    return make_context(runtime)


def content_text(result: Any) -> str:
    """Join the text of a CallToolResult's content blocks."""
    parts = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)


@pytest.fixture
def env_vars(config: Config):
    """Set the server's environment variables from the config fixture."""
    import os

    keys = {
        "MEETUP_CLIENT_ID": config.MEETUP_CLIENT_ID,
        "MEETUP_CLIENT_SECRET": config.MEETUP_CLIENT_SECRET,
        "MEETUP_REDIRECT_URI": config.MEETUP_REDIRECT_URI,
        "MEETUP_ACCESS_TOKEN": config.MEETUP_ACCESS_TOKEN,
        "ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY,
        "MAX_EVENTS_PER_QUERY": str(config.MAX_EVENTS_PER_QUERY),
        "LOG_LEVEL": config.LOG_LEVEL,
    }
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update(keys)
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


class TestSearchMeetupEvents:
    async def test_returns_formatted_events(self, context, monkeypatch):
        async def fake_search(self, query):
            return [make_event(), make_event("JS Meetup")]

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)
        result = await search_meetup_events("python events", 20, context)
        assert "Found 2 events" in result
        assert "Python Meetup" in result
        assert "JS Meetup" in result

    async def test_empty_query_message(self, context):
        result = await search_meetup_events("", 20, context)
        assert result == "Error: Query parameter is required"

    async def test_empty_results_message(self, context, monkeypatch):
        async def fake_search(self, query):
            return []

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)
        result = await search_meetup_events("python events", 20, context)
        assert "No events found" in result

    async def test_max_results_clamped(self, context, monkeypatch):
        seen: list[int] = []

        async def fake_search(self, query):
            seen.append(query.max_results)
            return []

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)
        await search_meetup_events("events", 500, context)
        assert seen == [100]

    async def test_api_exception_returns_empty_results(self, context, monkeypatch):
        async def exploding_search(self, query):
            raise RuntimeError("connection reset")

        monkeypatch.setattr(MeetupClient, "search_events", exploding_search)
        result = await search_meetup_events("python events", 20, context)
        assert "No events found" in result


class TestAugmentPrompt:
    async def test_no_events(self, context, monkeypatch):
        async def fake_search(self, query):
            return []

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)
        result = await augment_prompt_with_events("find me events", context)
        assert "No relevant Meetup events found" in result

    async def test_with_events(self, context, monkeypatch):
        async def fake_search(self, query):
            return [make_event()]

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)
        result = await augment_prompt_with_events("recommend some events", context)
        assert "=== Relevant Meetup Events ===" in result
        assert "Python Meetup" in result

    async def test_empty_prompt_message(self, context):
        result = await augment_prompt_with_events("", context)
        assert result == "Error: Prompt parameter is required"


class TestRecommendations:
    async def test_with_claude(self, runtime, context, monkeypatch):
        async def fake_search(self, query):
            return [make_event()]

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)
        result = await get_event_recommendations("tech events", "prefer free", context)
        assert result == "Here are some recommendations."
        assert runtime.claude.calls, "Claude should have been called"
        call = runtime.claude.calls[0]
        assert call["model"] == "claude-3-sonnet-20240229"
        assert call["max_tokens"] == 2000
        message = call["messages"][0]["content"]
        assert "tech events" in message
        assert "Additional preferences: prefer free" in message
        assert "Python Meetup" in message

    async def test_without_claude(self, runtime, context, monkeypatch):
        runtime.claude = None

        async def fake_search(self, query):
            return [make_event()]

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)
        result = await get_event_recommendations("tech events", "", context)
        assert "Claude integration not configured" in result
        assert "Python Meetup" in result

    async def test_claude_error_falls_back(self, runtime, context, monkeypatch):
        async def fake_search(self, query):
            return [make_event()]

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)

        async def failing_create(**kwargs):
            raise RuntimeError("boom")

        runtime.claude.messages.create = failing_create  # type: ignore[method-assign]
        result = await get_event_recommendations("tech events", "", context)
        assert "Claude API unavailable" in result
        assert "Python Meetup" in result

    async def test_empty_query_message(self, context):
        result = await get_event_recommendations("", "", context)
        assert result == "Error: Query parameter is required"


class TestOAuthTool:
    def test_with_credentials(self, context):
        result = get_oauth_url(context)
        assert "https://secure.meetup.com/oauth2/authorize" in result
        assert "client_id=test-client-id" in result

    def test_without_credentials(self, context):
        import os

        config = Config(
            MEETUP_CLIENT_ID="",
            MEETUP_CLIENT_SECRET="",
            MEETUP_REDIRECT_URI="http://localhost:8080/",
            MEETUP_ACCESS_TOKEN="token-123",
            ANTHROPIC_API_KEY="key",
            LOG_LEVEL="INFO",
            MAX_EVENTS_PER_QUERY=20,
            DEFAULT_RADIUS=25,
        )
        saved_id = os.environ.get("MEETUP_CLIENT_ID")
        saved_secret = os.environ.get("MEETUP_CLIENT_SECRET")
        try:
            os.environ["MEETUP_CLIENT_ID"] = ""
            os.environ["MEETUP_CLIENT_SECRET"] = ""
            result = get_oauth_url(make_context(make_runtime(config)))
        finally:
            for key, value in (
                ("MEETUP_CLIENT_ID", saved_id),
                ("MEETUP_CLIENT_SECRET", saved_secret),
            ):
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        assert "MEETUP_CLIENT_ID and MEETUP_CLIENT_SECRET" in result


# ---------------------------------------------------------------------------
# Resources (read the server environment — env vars set from the fixture)
# ---------------------------------------------------------------------------


class TestResources:
    def test_config_resource(self, env_vars):
        import json

        from mcp_meetup.server import get_server_config

        data = json.loads(get_server_config())
        assert data["meetup_client_id"] == "test-cli..."
        assert data["meetup_client_secret"] == "Set"
        assert data["anthropic_api_key"] == "Set"
        assert data["max_events_per_query"] == 20
        assert data["default_radius"] == 25

    def test_auth_status_resource(self, env_vars):
        import json

        from mcp_meetup.server import get_auth_status

        data = json.loads(get_auth_status())
        assert data == {
            "has_access_token": True,
            "oauth_url_available": True,
            "claude_integration": True,
        }

    def test_auth_status_no_credentials(self, config):
        import json
        import os

        env_config = Config(
            MEETUP_CLIENT_ID="",
            MEETUP_CLIENT_SECRET="",
            MEETUP_REDIRECT_URI=config.MEETUP_REDIRECT_URI,
            MEETUP_ACCESS_TOKEN="",
            ANTHROPIC_API_KEY="",
            LOG_LEVEL="INFO",
            MAX_EVENTS_PER_QUERY=20,
            DEFAULT_RADIUS=25,
        )
        keys = {
            "MEETUP_CLIENT_ID": env_config.MEETUP_CLIENT_ID,
            "MEETUP_CLIENT_SECRET": env_config.MEETUP_CLIENT_SECRET,
            "MEETUP_ACCESS_TOKEN": env_config.MEETUP_ACCESS_TOKEN,
            "ANTHROPIC_API_KEY": env_config.ANTHROPIC_API_KEY,
        }
        saved = {k: os.environ.get(k) for k in keys}
        os.environ.update(keys)
        try:
            from mcp_meetup.server import get_auth_status

            data = json.loads(get_auth_status())
            assert data["has_access_token"] is False
            assert data["oauth_url_available"] is False
            assert data["claude_integration"] is False
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


# ---------------------------------------------------------------------------
# MCP protocol surface (registry, schemas, validation, dispatch)
# ---------------------------------------------------------------------------


class TestServerRegistry:
    def test_tool_names(self):
        from mcp_meetup.server import mcp

        tools = mcp._tool_manager.list_tools()
        names = {t.name for t in tools}
        assert names == {
            "search_meetup_events",
            "augment_prompt_with_events",
            "get_event_recommendations",
            "get_oauth_url",
        }

    def test_search_tool_schema(self):
        from mcp_meetup.server import mcp

        tool = mcp._tool_manager.get_tool("search_meetup_events")
        assert tool is not None
        assert tool.parameters.get("type") == "object"
        assert "query" in tool.parameters.get("properties", {})
        assert tool.parameters.get("required") == ["query"]

    def test_resource_uris(self):
        from mcp_meetup.server import mcp

        resources = mcp._resource_manager.list_resources()
        uris = {r.uri for r in resources}
        assert uris == {"meetup://config", "meetup://auth/status"}


class TestMCPProtocol:
    async def test_list_tools(self):
        from mcp_meetup.server import mcp

        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        assert names == {
            "search_meetup_events",
            "augment_prompt_with_events",
            "get_event_recommendations",
            "get_oauth_url",
        }

    async def test_call_tool_search_returns_text(self, context, monkeypatch):
        from mcp_meetup.server import mcp

        async def fake_search(self, query):
            return [make_event()]

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)
        result = await mcp.call_tool(
            "search_meetup_events", {"query": "python events"}, context
        )
        assert "Found 1 events" in content_text(result)

    async def test_call_tool_oauth_url(self, context):
        from mcp_meetup.server import mcp

        result = await mcp.call_tool("get_oauth_url", {}, context)
        assert "https://secure.meetup.com/oauth2/authorize" in content_text(result)

    async def test_call_tool_unknown_name(self, context):
        from mcp_meetup.server import mcp

        with pytest.raises(Exception):
            await mcp.call_tool("nope", {}, context)

    async def test_list_resources(self):
        from mcp_meetup.server import mcp

        resources = await mcp.list_resources()
        uris = {r.uri for r in resources}
        assert uris == {"meetup://config", "meetup://auth/status"}


# ---------------------------------------------------------------------------
# In-process client (schema generation + validation + dispatch end to end)
# ---------------------------------------------------------------------------


class TestClientProtocol:
    async def test_client_lists_and_calls_tools(self, monkeypatch):
        from mcp_meetup.server import mcp

        async def fake_search(self, query):
            return [make_event()]

        monkeypatch.setattr(MeetupClient, "search_events", fake_search)

        async with Client(mcp) as client:
            tools_result = await client.list_tools()
            names = {t.name for t in tools_result.tools}
            assert "search_meetup_events" in names

            result = await client.call_tool(
                "search_meetup_events", {"query": "python events"}
            )
            assert "Found 1 events" in content_text(result)
            assert "Python Meetup" in content_text(result)

    async def test_client_reads_resources(self):
        from mcp_meetup.server import mcp

        async with Client(mcp) as client:
            resources = await client.list_resources()
            uris = {r.uri for r in resources.resources}
            assert uris == {"meetup://config", "meetup://auth/status"}

            config_result = await client.read_resource("meetup://config")
            assert config_result.contents


# ---------------------------------------------------------------------------
# Stdio entry point: launch `python -m mcp_meetup` and drive the protocol
# ---------------------------------------------------------------------------


class TestStdioServer:
    async def test_stdio_server_lists_and_calls_tools(self, config):
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        env = {
            "MEETUP_CLIENT_ID": config.MEETUP_CLIENT_ID,
            "MEETUP_CLIENT_SECRET": config.MEETUP_CLIENT_SECRET,
            "MEETUP_REDIRECT_URI": config.MEETUP_REDIRECT_URI,
            "MEETUP_ACCESS_TOKEN": config.MEETUP_ACCESS_TOKEN,
            "ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY,
            "LOG_LEVEL": config.LOG_LEVEL,
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_meetup"],
            env=env,
        )

        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                names = {t.name for t in tools_result.tools}
                assert "search_meetup_events" in names
                assert "get_oauth_url" in names

                result = await session.call_tool("get_oauth_url", {})
                assert "https://secure.meetup.com/oauth2/authorize" in content_text(result)
