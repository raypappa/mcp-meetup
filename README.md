# MCP Meetup-Claude Integration Server

## Overview

This is a production-quality Model Communication Protocol (MCP) server that seamlessly integrates Meetup.com's event discovery APIs with Anthropic's Claude LLM. The server enables intelligent event discovery, natural language querying, and AI-powered recommendations for Meetup events.

## Architecture

### Core Components

1. **MCP Protocol Handler** (`MeetupClaudeMCPServer`)
   - Manages client connections and tool definitions
   - Handles resource management and server lifecycle
   - Provides standardized MCP interface

2. **Authentication Manager** (`AuthenticationManager`)
   - OAuth2 flow implementation for Meetup.com
   - Token lifecycle management and refresh
   - Secure credential handling

3. **Event Discovery Engine** (`EventDiscoveryEngine`)
   - Natural language query parameter extraction
   - Dual API support (REST and GraphQL)
   - Intelligent event filtering and ranking

4. **Prompt Augmentation Service** (`PromptAugmentationService`)
   - Context-aware prompt enhancement
   - Event data formatting for LLM consumption
   - Smart relevance filtering

5. **Claude Integration** (`ClaudeIntegration`)
   - Anthropic API client management
   - Response generation and error handling
   - Configurable model parameters

### Data Flow

```
User Query → Parameter Extraction → Event Discovery → Data Augmentation → Claude Processing → Response
```

## Quick Start

### Prerequisites

- Python 3.8+
- Meetup.com account
- Anthropic API account

### Installation

```bash
# Clone or download the project
cd /home/daniel/work/mcp-meetup

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the server
python meetup_claude_mcp_server.py
```

## API Setup Instructions

### 1. Meetup.com OAuth Setup

1. Visit [Meetup OAuth Consumers](https://secure.meetup.com/meetup_api/oauth_consumers/)
2. Click "Create New Consumer"
3. Fill in application details:
   - **Application Name**: Your app name
   - **Application Website**: Your website or GitHub repo
   - **Redirect URI**: `http://localhost:8080/oauth/callback`
   - **Application Description**: Brief description of your use case

4. Save the generated:
   - **Client ID**
   - **Client Secret**

### 2. Anthropic API Setup

1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Create account or sign in
3. Navigate to API Keys section
4. Generate new API key
5. Copy the API key securely

### 3. Environment Configuration

Required environment variables in `.env`:
```bash
MEETUP_CLIENT_ID=your_meetup_client_id_here
MEETUP_CLIENT_SECRET=your_meetup_client_secret_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Optional configuration:
```bash
MEETUP_ACCESS_TOKEN=your_access_token_if_available
MEETUP_REDIRECT_URI=http://localhost:8080/oauth/callback
LOG_LEVEL=INFO
MAX_EVENTS_PER_QUERY=20
DEFAULT_RADIUS=25
```

## MCP Tools

### 1. `search_meetup_events`

Search for Meetup events using natural language queries.

**Parameters:**
- `query` (string, required): Natural language search query
- `max_results` (integer, optional): Maximum events to return (default: 20)

**Example:**
```json
{
  "query": "Python programming events near San Francisco this week",
  "max_results": 10
}
```

### 2. `augment_prompt_with_events`

Enhance a user prompt with relevant event data for context.

**Parameters:**
- `prompt` (string, required): User prompt to augment

**Example:**
```json
{
  "prompt": "What programming events should I attend this weekend?"
}
```

### 3. `get_event_recommendations`

Get AI-powered event recommendations using Claude with event context.

**Parameters:**
- `query` (string, required): Natural language query for recommendations
- `preferences` (string, optional): Additional preferences or constraints

**Example:**
```json
{
  "query": "I'm interested in machine learning and networking events",
  "preferences": "Prefer free events, willing to travel up to 30 miles"
}
```

### 4. `get_oauth_url`

Get Meetup OAuth authorization URL for authentication setup.

**Parameters:** None

## MCP Resources

### 1. `meetup://config`

Current server configuration and status information.

### 2. `meetup://auth/status`

Authentication status with Meetup.com including token validity.

## Natural Language Query Examples

The server intelligently extracts parameters from natural language:

**Time-based queries:**
- "events today"
- "what's happening tomorrow"
- "events this week"

**Location-based queries:**
- "events near me"
- "meetups in San Francisco"
- "remote events only"

**Topic-based queries:**
- "Python programming meetups"
- "data science events"
- "startup networking"
- "AI and machine learning"

**Combined queries:**
- "Python events near me today"
- "remote data science meetups this week"
- "free networking events in San Francisco"

## Error Handling

The server includes comprehensive error handling for:

- **Authentication errors**: Missing credentials, expired tokens
- **API errors**: Rate limiting, network failures, invalid queries
- **Data processing errors**: Malformed events, empty results

## Security Considerations

- Environment variable configuration prevents credential exposure
- OAuth2 flow implementation follows security best practices
- No persistent storage of user queries or personal data
- Configurable logging levels to control information exposure

## Development

### Project Structure

```
mcp-meetup/
├── meetup_claude_mcp_server.py    # Main server implementation
├── requirements.txt               # Python dependencies
├── .env.example                  # Environment configuration template
├── README.md                     # This documentation
├── docs/                         # Additional documentation
│   └── adr/                      # Architecture decision records
└── tests/                        # Test files (future)
```

### Testing

Basic testing can be done by running the server and using MCP client tools:

```bash
# Start the server
python meetup_claude_mcp_server.py

# In another terminal, test with MCP client
# (MCP client implementation would go here)
```

### Extending the Server

The modular design makes it easy to extend:

1. **Additional APIs**: Add other event platforms in `EventDiscoveryEngine`
2. **Enhanced filtering**: Extend `extract_query_parameters` method
3. **Caching**: Add Redis or memory caching in `PromptAugmentationService`
4. **Additional tools**: Add new MCP tools in `_setup_tools` method

## Troubleshooting

### Common Issues

1. **Authentication failures**
   - Verify client ID and secret are correct
   - Check redirect URI matches OAuth consumer settings
   - Ensure access token hasn't expired

2. **No events found**
   - Try broader search terms
   - Check location spelling and format
   - Verify time parameters are reasonable

3. **API rate limiting**
   - Reduce query frequency
   - Implement request caching
   - Check API quota usage

4. **Claude integration errors**
   - Verify Anthropic API key is valid
   - Check API quota and billing status
   - Review prompt length and complexity

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python meetup_claude_mcp_server.py
```

### Health Checks

Check server status using MCP resources:

```bash
# Check configuration
# Use MCP client to read meetup://config

# Check authentication status
# Use MCP client to read meetup://auth/status
```

## Contributing

### Development Workflow

1. Fork repository
2. Create feature branch
3. Implement changes with tests
4. Update documentation
5. Submit pull request

### Code Standards

- Follow PEP 8 style guidelines
- Use type hints throughout
- Maintain comprehensive docstrings
- Include unit tests for new features

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:

1. Check troubleshooting section
2. Review configuration and setup
3. Create detailed bug report with logs
4. Include reproduction steps and environment details

---

**Version**: 1.0.0  
**Last Updated**: 2025-07-27  
**Author**: Generated for Dan Shields
