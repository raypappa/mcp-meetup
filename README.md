# MCP Meetup-Claude Integration Server

An MCP (Model Context Protocol) server that integrates Meetup.com's event
discovery API with Anthropic's Claude LLM. It enables intelligent event
discovery, natural-language querying, and AI-powered recommendations for
Meetup events.

Built on the MCP SDK v2 (`MCPServer`), packaged as an installable Python
package, and managed with [uv](https://docs.astral.sh/uv/).

## MCP Tools

1. **`search_meetup_events`** — Search Meetup events with a natural-language
   query. Parameters: `query` (required), `max_results` (optional, default 20,
   capped at 100).

2. **`augment_prompt_with_events`** — Augment a user prompt with relevant
   event data. Parameters: `prompt` (required).

3. **`get_event_recommendations`** — AI-powered event recommendations via
   Claude, with event context. Parameters: `query` (required), `preferences`
   (optional). Falls back to the raw event list when no Anthropic key is
   configured.

4. **`get_oauth_url`** — Returns the Meetup OAuth2 authorization URL for the
   configured client, or an instruction to set the required credentials.

## MCP Resources

- **`meetup://config`** — Current server configuration (values redacted to
  `Set` / `Not Set`) and limits.
- **`meetup://auth/status`** — Boolean status: access token present, OAuth
  URL available, Claude integration enabled.

## Quick Start

### Prerequisites

- Python 3.10+ (3.13 recommended)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A Meetup.com account
- An Anthropic API account

### Installation

```bash
git clone git@github.com:raypappa/mcp-meetup.git
cd mcp-meetup
uv sync
```

### Configure

```bash
cp .env.example .env
# edit .env with your credentials, then:
export $(grep -v '^#' .env | xargs)
```

Required environment variables:

```bash
MEETUP_CLIENT_ID=your_meetup_client_id_here
MEETUP_CLIENT_SECRET=your_meetup_client_secret_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Optional:

```bash
MEETUP_ACCESS_TOKEN=your_access_token_if_available
MEETUP_REDIRECT_URI=http://localhost:8080/
LOG_LEVEL=INFO
MAX_EVENTS_PER_QUERY=20
DEFAULT_RADIUS=25
```

### Run

```bash
uv run mcp-meetup
# or, without the console script:
uv run python -m mcp_meetup
```

The server speaks MCP over stdio — launch it from your MCP client of choice
(Claude Desktop, `claude mcp add`, etc.):

```bash
claude mcp add meetup -- uv run mcp-meetup
```

## Meetup.com API Setup

1. Visit [Meetup OAuth Consumers](https://secure.meetup.com/meetup_api/oauth_consumers/)
2. Click "Create New Consumer" and fill in:
   - **Application Name**: your app name
   - **Application Website**: your website or GitHub repo
   - **Redirect URI**: `http://localhost:8080/`
   - **Application Description**: brief description of your use case
3. Save the generated **Client ID** and **Client Secret**
4. If you have an OAuth consumer, you can skip the token flow by setting
   `MEETUP_ACCESS_TOKEN` directly.

## Project Structure

```
mcp-meetup/
├── pyproject.toml              # uv-managed project metadata + dependencies
├── uv.lock                     # Locked dependency graph (commit it)
├── .python-version             # Pinned interpreter (3.13)
├── src/
│   └── mcp_meetup/
│       ├── __init__.py
│       ├── __main__.py         # Entry point: python -m mcp_meetup
│       ├── server.py           # MCPServer, tools, resources, lifespan
│       ├── config.py           # Environment configuration (Config)
│       ├── meetup_client.py    # Meetup API client (aiohttp)
│       ├── models.py           # Pydantic models (MeetupEvent, EventQuery)
│       ├── extract.py          # Natural-language query parameter extraction
│       └── format.py           # Event formatting for LLM consumption
└── tests/
    ├── conftest.py
    ├── test_server.py          # Tool implementations, protocol, stdio e2e
    ├── test_meetup_client.py
    ├── test_extract.py
    ├── test_format.py
    ├── test_models.py
    └── test_config.py
```

## Development

```bash
uv sync                  # install deps + dev group (pytest, pytest-asyncio)
uv run pytest            # run the test suite
uv run pytest -k testname  # run a single test
```

The suite covers the tool implementations, the MCP protocol surface
(`list_tools`, `call_tool`, `list_resources` with schema generation and
validation), an in-process `Client`, and a real subprocess stdio handshake
that launches `python -m mcp_meetup` and drives it over stdin/stdout.

## Error Handling

- Missing/empty `query` or `prompt` returns a clear `"Error: …"` message.
- Meetup API failures (network, rate limits, malformed events) return a
  `"No events found"` result instead of raising through the protocol.
- Claude failures fall back to the raw event list with an explanatory note.
- Timestamps are parsed leniently (`Z` suffixes, fractional seconds) via
  `dateutil`.

## License

MIT — see [LICENSE](LICENSE).
