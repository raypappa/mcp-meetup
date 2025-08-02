# MCP Meetup-Claude Integration Server (Official SDK Compliant)

## Overview

This is a production-quality Model Communication Protocol (MCP) server that integrates Meetup.com's event discovery APIs with Anthropic's Claude LLM. **This implementation follows the official MCP Python SDK best practices** as defined by the [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk).

## ⚠️ **IMPORTANT UPDATE**

The original `meetup_claude_mcp_server.py` used outdated patterns. The **corrected version** is `meetup_claude_mcp_server_fixed.py` which follows current MCP SDK best practices:

- ✅ Uses `FastMCP` class (official pattern)
- ✅ Simple `@mcp.tool()` decorators
- ✅ Automatic schema generation from function signatures
- ✅ Modern SDK imports and patterns
- ✅ Compatible with MCP CLI tools (`uv run mcp dev`, `uv run mcp install`)

## Quick Start (Official SDK Way)

### Prerequisites

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) package manager (recommended by MCP team)
- Meetup.com account
- Anthropic API account

### Installation

```bash
# Create project with uv (recommended)
uv init mcp-meetup-project
cd mcp-meetup-project

# Add dependencies
uv add "mcp[cli]" anthropic aiohttp python-dateutil pydantic

# Or use the requirements file
uv pip install -r requirements_fixed.txt
```

### Configuration

```bash
# Copy and edit environment configuration
cp .env.example .env
# Edit .env with your actual API credentials
```

Required environment variables:
```bash
MEETUP_CLIENT_ID=your_meetup_client_id_here
MEETUP_CLIENT_SECRET=your_meetup_client_secret_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### Running the Server

#### Development Mode (Recommended)
```bash
# Test with MCP Inspector
uv run mcp dev meetup_claude_mcp_server_fixed.py
```

#### Install in Claude Desktop
```bash
# Install server in Claude Desktop
uv run mcp install meetup_claude_mcp_server_fixed.py --name "Meetup Events"

# With environment variables
uv run mcp install meetup_claude_mcp_server_fixed.py -f .env
```

#### Direct Execution
```bash
# Run directly
python meetup_claude_mcp_server_fixed.py

# Or with uv
uv run python meetup_claude_mcp_server_fixed.py
```

## API Setup

### 1. Meetup.com OAuth Setup

1. Visit [Meetup OAuth Consumers](https://secure.meetup.com/meetup_api/oauth_consumers/)
2. Create new OAuth consumer with:
   - **Redirect URI**: `http://localhost:8080/oauth/callback`
3. Save your **Client ID** and **Client Secret**

### 2. Anthropic API Setup

1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Generate API key
3. Add to environment configuration

## MCP Tools Available

### 1. `search_meetup_events`
```python
@mcp.tool()
async def search_meetup_events(query: str, max_results: int = 20) -> str:
    """Search for Meetup events based on natural language query."""
```

### 2. `augment_prompt_with_events_tool`
```python
@mcp.tool()
async def augment_prompt_with_events_tool(prompt: str) -> str:
    """Enhance a prompt with relevant Meetup event data."""
```

### 3. `get_event_recommendations`
```python
@mcp.tool()
async def get_event_recommendations(query: str, preferences: str = "") -> str:
    """Get AI-powered event recommendations using Claude."""
```

### 4. `get_oauth_url`
```python
@mcp.tool()
def get_oauth_url() -> str:
    """Get Meetup OAuth authorization URL for authentication."""
```

## MCP Resources Available

### 1. `meetup://config`
Current server configuration and status

### 2. `meetup://auth/status`
Authentication status with Meetup.com

## Key Differences from Original Implementation

| Aspect | Original (Outdated) | Fixed (Official SDK) |
|--------|---------------------|---------------------|
| **Server Class** | `Server("name")` | `FastMCP("name")` |
| **Tool Definition** | Manual schema with `@server.list_tools()` | `@mcp.tool()` with auto-schema |
| **Import Pattern** | `from mcp.server import Server` | `from mcp.server.fastmcp import FastMCP` |
| **Transport Setup** | Manual stdio configuration | `mcp.run(transport="stdio")` |
| **CLI Compatibility** | Not compatible | Works with `uv run mcp dev/install` |
| **Schema Generation** | Manual JSON schema | Automatic from type hints |

## Natural Language Processing

The server intelligently extracts parameters from queries like:

- **Time**: "today", "tomorrow", "this week", "next week"
- **Location**: "near me", "in San Francisco", "remote only"
- **Topics**: "Python", "data science", "AI", "programming"
- **Combined**: "remote Python events near me today"

## Error Handling

- **Authentication errors**: Clear setup guidance
- **API failures**: Graceful degradation with helpful messages
- **Empty results**: Suggestions for better queries
- **Configuration issues**: Detailed validation errors

## Testing with MCP Inspector

The official SDK provides excellent debugging tools:

```bash
# Interactive testing and debugging
uv run mcp dev meetup_claude_mcp_server_fixed.py

# Test specific tools
uv run mcp dev meetup_claude_mcp_server_fixed.py --test-tool search_meetup_events
```

## Architecture Decisions

See the `docs/adr/` directory for detailed architectural decision records:

- **ADR-001**: MCP Protocol Choice
- **ADR-002**: Dual API Strategy (REST + GraphQL)
- **ADR-003**: Natural Language Parameter Extraction
- **ADR-004**: Error Handling and Resilience Strategy
- **ADR-005**: Migration to Official SDK Patterns *(new)*

## Production Deployment

For production use:

```bash
# Install with specific environment
uv run mcp install meetup_claude_mcp_server_fixed.py \
  --name "Meetup Events Production" \
  -v MEETUP_CLIENT_ID=prod_client_id \
  -v MEETUP_CLIENT_SECRET=prod_client_secret \
  -v ANTHROPIC_API_KEY=prod_api_key
```

## Example Usage

### Query Examples

```bash
# In Claude Desktop (after installation)
"Find Python programming events near San Francisco this week"
"What remote data science meetups are happening today?"
"Show me free networking events in my area"
```

### MCP Inspector Testing

```bash
# Start inspector
uv run mcp dev meetup_claude_mcp_server_fixed.py

# Test search tool
> search_meetup_events("Python events today", 5)

# Test OAuth setup
> get_oauth_url()

# Check configuration
> get_server_config()
```

## Troubleshooting

### Common Issues

1. **"Module not found" errors**
   - Ensure you're using the fixed version: `meetup_claude_mcp_server_fixed.py`
   - Install with: `uv add "mcp[cli]"`

2. **Authentication failures**
   - Use `get_oauth_url()` tool to get authorization URL
   - Verify client ID and secret in `.env` file

3. **No events found**
   - Try broader search terms
   - Check if access token is set correctly

4. **MCP CLI commands not working**
   - Ensure you have `mcp[cli]` installed (not just `mcp`)
   - Use the fixed server file, not the original

### Debug Mode

```bash
# Run with debug logging
LOG_LEVEL=DEBUG uv run mcp dev meetup_claude_mcp_server_fixed.py
```

## Migration Guide

If you were using the original implementation:

1. **Switch to fixed version**: Use `meetup_claude_mcp_server_fixed.py`
2. **Update requirements**: Use `requirements_fixed.txt`
3. **Install CLI tools**: `uv add "mcp[cli]"`
4. **Test with inspector**: `uv run mcp dev meetup_claude_mcp_server_fixed.py`
5. **Reinstall in Claude**: `uv run mcp install meetup_claude_mcp_server_fixed.py`

## Contributing

When contributing to this project:

1. **Follow official SDK patterns**: Use `FastMCP` and decorators
2. **Test with MCP CLI**: Ensure compatibility with `uv run mcp dev`
3. **Update ADRs**: Document any architectural changes
4. **Add tests**: Include tests for new functionality

## Resources

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/modelcontextprotocol/python-sdk#fastmcp)
- [MCP CLI Tools](https://github.com/modelcontextprotocol/python-sdk#quickstart)

## License

MIT License - see LICENSE file for details.

## Support

For issues:

1. **Server-specific issues**: Check troubleshooting section above
2. **MCP SDK issues**: See [official SDK repository](https://github.com/modelcontextprotocol/python-sdk/issues)
3. **General questions**: Create an issue with detailed reproduction steps

---

**Version**: 2.0.0 (Official SDK Compliant)  
**Last Updated**: 2025-07-30  
**Author**: Generated for Dan Shields
