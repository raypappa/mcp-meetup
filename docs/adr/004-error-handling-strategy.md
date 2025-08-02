# ADR-004: Error Handling and Resilience Strategy

## Status
Accepted

## Context
The MCP server integrates multiple external services (Meetup.com APIs, Anthropic Claude API) and performs complex data processing. We need a comprehensive error handling strategy that ensures reliability, provides meaningful feedback to users, and maintains system stability under various failure conditions.

## Decision
We will implement a multi-layered error handling strategy with graceful degradation, comprehensive logging, and user-friendly error messages.

## Error Categories and Handling

### 1. Authentication Errors
**Scenarios:**
- Missing or invalid API credentials
- Expired access tokens
- OAuth flow failures

**Handling Strategy:**
```python
try:
    headers = self.auth_manager.get_auth_headers()
except Exception as e:
    logging.error(f"Authentication error: {e}")
    return [TextContent(
        type="text", 
        text="Authentication required. Please use get_oauth_url tool to set up authentication."
    )]
```

### 2. API Communication Errors
**Scenarios:**
- Network timeouts
- HTTP error responses (4xx, 5xx)
- Rate limiting
- Service unavailability

**Handling Strategy:**
```python
try:
    async with self.session.get(url, params=params, headers=headers) as response:
        if response.status == 200:
            # Process successful response
        elif response.status == 429:
            logging.warning("Rate limited - suggest retry")
        else:
            error_text = await response.text()
            logging.error(f"API error {response.status}: {error_text}")
except aiohttp.ClientError as e:
    logging.error(f"Network error: {e}")
    # Fallback to alternative API or cached data
```

### 3. Data Processing Errors
**Scenarios:**
- Malformed API responses
- Missing required fields
- Invalid data types
- Parsing failures

**Handling Strategy:**
```python
for event_data in events_data:
    try:
        event = self._parse_rest_event(event_data)
        events.append(event)
    except Exception as e:
        logging.warning(f"Error parsing event {event_data.get('id', 'unknown')}: {e}")
        continue  # Skip malformed event, continue processing others
```

### 4. LLM Integration Errors
**Scenarios:**
- Claude API failures
- Token limit exceeded
- Content policy violations
- Service quotas exceeded

**Handling Strategy:**
```python
try:
    response = await self.claude_integration.generate_response(prompt, max_tokens=2000)
    return [TextContent(type="text", text=response)]
except Exception as e:
    logging.error(f"Claude integration error: {e}")
    return [TextContent(
        type="text",
        text="Unable to generate AI recommendations. Here are the raw events found: [event list]"
    )]
```

## Resilience Patterns

### 1. Graceful Degradation
- **Primary API Failure**: Fall back to secondary API (REST → GraphQL)
- **Claude API Failure**: Return structured event data without AI enhancement
- **Partial Data**: Continue processing with available data, log missing fields

### 2. Circuit Breaker Pattern
```python
class APICircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
```

### 3. Retry Logic
```python
async def api_call_with_retry(self, url, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await self._make_api_call(url, params)
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

### 4. Timeout Management
```python
async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
    # API calls with timeout
```

## Logging Strategy

### Log Levels and Usage:
- **ERROR**: Authentication failures, API errors, system failures
- **WARNING**: Parsing errors, fallback usage, rate limiting
- **INFO**: Successful operations, server lifecycle events
- **DEBUG**: Detailed request/response data, parameter extraction details

### Structured Logging:
```python
logging.error("API request failed", extra={
    "api_endpoint": url,
    "status_code": response.status,
    "user_query": query_text,
    "error_type": "http_error"
})
```

### Log Sanitization:
- Remove sensitive data (API keys, personal information)
- Truncate large payloads
- Hash user identifiers for privacy

## User-Facing Error Messages

### Principles:
1. **Actionable**: Tell users what they can do to fix the issue
2. **Clear**: Avoid technical jargon
3. **Helpful**: Provide alternative suggestions when possible
4. **Consistent**: Use standardized message formats

### Error Message Templates:
```python
ERROR_MESSAGES = {
    "auth_required": "Authentication required. Please use the get_oauth_url tool to set up your Meetup.com credentials.",
    "no_events_found": "No events found matching '{query}'. Try different keywords, location, or time range.",
    "api_unavailable": "Meetup.com service is temporarily unavailable. Please try again later.",
    "invalid_query": "Unable to understand query '{query}'. Try using clearer time references (today, tomorrow) and location (near me, in [city])."
}
```

## Monitoring and Alerting

### Key Metrics:
- API success/failure rates
- Response times
- Error categorization and frequency
- User query success rates
- Token usage and limits

### Health Checks:
```python
async def health_check(self):
    """Perform system health check."""
    checks = {
        "auth_status": await self._check_authentication(),
        "meetup_api": await self._check_meetup_api(),
        "claude_api": await self._check_claude_api(),
        "config_valid": Config.validate()
    }
    return checks
```

## Error Recovery Strategies

### 1. Automatic Recovery:
- Token refresh on authentication errors
- API endpoint switching on service errors
- Retry with backoff on transient errors

### 2. Manual Recovery Guidance:
- Clear instructions for credential setup
- Troubleshooting guides in documentation
- Self-service diagnostic tools

### 3. Fallback Data Sources:
- Cached event data for offline operation
- Default recommendations when personalization fails
- Static content when dynamic content unavailable

## Testing Strategy

### Error Simulation:
```python
@pytest.mark.asyncio
async def test_api_failure_handling():
    """Test handling of API failures."""
    with mock.patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = aiohttp.ClientError("Network error")
        
        result = await server._handle_search_events({"query": "test"})
        
        assert "error" in result[0].text.lower()
        assert len(result) == 1
```

### Error Injection:
- Network failure simulation
- API response corruption
- Authentication token expiration
- Rate limiting scenarios

## Benefits

### For Users:
- Consistent experience even during service issues
- Clear guidance on resolving problems
- Minimal service interruption

### For Developers:
- Comprehensive error visibility
- Easy debugging and troubleshooting
- Predictable error handling patterns

### For Operations:
- Proactive issue detection
- Clear escalation paths
- Automated recovery where possible

## Implementation Guidelines

### Exception Hierarchy:
```python
class MeetupServerError(Exception):
    """Base exception for MCP server errors."""
    pass

class AuthenticationError(MeetupServerError):
    """Authentication-related errors."""
    pass

class APIError(MeetupServerError):
    """External API communication errors."""
    pass

class DataProcessingError(MeetupServerError):
    """Data parsing and processing errors."""
    pass
```

### Error Context Preservation:
```python
try:
    events = await self.search_events_rest(query)
except APIError as e:
    logging.error(f"REST API failed: {e}", exc_info=True)
    # Preserve context for fallback
    events = await self.search_events_graphql(query)
```

## Success Metrics

- **Availability**: > 99% uptime for core functionality
- **Error Recovery**: < 5% of errors require manual intervention
- **User Experience**: < 2% of queries result in unhelpful error messages
- **Mean Time to Recovery**: < 5 minutes for transient issues

## Future Enhancements

- **Distributed Tracing**: For complex error scenarios across services
- **Predictive Error Detection**: ML-based anomaly detection
- **Self-Healing**: Automated recovery and configuration adjustment
- **Error Analytics**: Trend analysis and proactive issue prevention

---

**Date**: 2025-07-27  
**Author**: Dan Shields  
**Dependencies**: All previous ADRs
