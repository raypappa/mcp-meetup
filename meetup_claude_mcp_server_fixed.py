#!/usr/bin/env python3
"""
MCP Server for Meetup.com Integration with Claude - Official SDK Compliant
=========================================================================

A Model Communication Protocol (MCP) server that integrates Meetup.com's REST API
with Anthropic's Claude LLM using the official MCP Python SDK patterns.

Author: Generated for Dan Shields
Version: 2.0.0 (Updated for Official SDK Compliance)
License: MIT

Dependencies:
    pip install mcp anthropic aiohttp python-dateutil pydantic

Usage:
    # Development
    uv run mcp dev meetup_claude_mcp_server.py
    
    # Install in Claude Desktop
    uv run mcp install meetup_claude_mcp_server.py
    
    # Direct execution
    python meetup_claude_mcp_server.py
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
from anthropic import AsyncAnthropic
from dateutil import parser as date_parser
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field


# =============================================================================
# Configuration and Constants
# =============================================================================

class Config:
    """Central configuration management for the MCP server."""
    
    # Meetup.com API Configuration
    MEETUP_CLIENT_ID = os.getenv('MEETUP_CLIENT_ID', '')
    MEETUP_CLIENT_SECRET = os.getenv('MEETUP_CLIENT_SECRET', '')
    MEETUP_REDIRECT_URI = os.getenv('MEETUP_REDIRECT_URI', 'http://localhost:8080/')
    MEETUP_ACCESS_TOKEN = os.getenv('MEETUP_ACCESS_TOKEN', '')
    
    # Anthropic Configuration
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    
    # API Endpoints
    MEETUP_BASE_URL = 'https://api.meetup.com'
    MEETUP_OAUTH_URL = 'https://secure.meetup.com/oauth2'
    
    # Server Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    MAX_EVENTS_PER_QUERY = int(os.getenv('MAX_EVENTS_PER_QUERY', '20'))
    DEFAULT_RADIUS = int(os.getenv('DEFAULT_RADIUS', '25'))
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        required_fields = ['MEETUP_CLIENT_ID', 'MEETUP_CLIENT_SECRET', 'ANTHROPIC_API_KEY']
        missing = [field for field in required_fields if not getattr(cls, field)]
        if missing:
            logging.error(f"Missing required configuration: {', '.join(missing)}")
            return False
        return True


# =============================================================================
# Data Models
# =============================================================================

class EventQuery(BaseModel):
    """Structured representation of an event search query."""
    location: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    remote_only: bool = False
    max_results: int = Config.MAX_EVENTS_PER_QUERY


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


# =============================================================================
# Global State Management
# =============================================================================

class ServerState:
    """Global state for the MCP server."""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = Config.MEETUP_ACCESS_TOKEN
        self.claude_client: Optional[AsyncAnthropic] = None
        
    async def initialize(self):
        """Initialize global state."""
        self.session = aiohttp.ClientSession()
        
        if Config.ANTHROPIC_API_KEY:
            self.claude_client = AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)
            
        if self.access_token:
            logging.info("Using existing Meetup access token")
        else:
            logging.warning("No Meetup access token - authentication required")
    
    async def cleanup(self):
        """Clean up resources."""
        if self.session:
            await self.session.close()


# Global state instance
state = ServerState()


# =============================================================================
# MCP Server Implementation using FastMCP
# =============================================================================

# Create FastMCP server instance
mcp = FastMCP("Meetup-Claude Integration Server")


# =============================================================================
# Authentication Utilities
# =============================================================================

def get_oauth_url() -> str:
    """Generate OAuth2 authorization URL for Meetup.com."""
    import urllib.parse
    
    params = {
        'client_id': Config.MEETUP_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': Config.MEETUP_REDIRECT_URI,
        'scope': 'basic'
    }
    
    return f"{Config.MEETUP_OAUTH_URL}/authorize?{urllib.parse.urlencode(params)}"


def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers for API requests."""
    if not state.access_token:
        raise Exception("No access token available")
    
    return {
        'Authorization': f'Bearer {state.access_token}',
        'Content-Type': 'application/json'
    }


# =============================================================================
# Natural Language Processing
# =============================================================================

def extract_query_parameters(user_prompt: str) -> EventQuery:
    """Extract search parameters from natural language prompt."""
    query = EventQuery()
    prompt_lower = user_prompt.lower()
    
    # Extract time-based parameters
    time_patterns = {
        r'\btoday\b': lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
        r'\btomorrow\b': lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
        r'\bthis week\b': lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
        r'\bnext week\b': lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(weeks=1),
    }
    
    for pattern, time_func in time_patterns.items():
        if re.search(pattern, prompt_lower):
            try:
                query.start_time = time_func()
                break
            except Exception as e:
                logging.warning(f"Error parsing time pattern {pattern}: {e}")
    
    # Extract location information
    location_patterns = [r'\bnear me\b', r'\bin ([A-Za-z\s,]+?)(?:\s|$)']
    for pattern in location_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            if 'near me' in match.group(0):
                query.location = 'current_location'
            else:
                query.location = match.group(1).strip()
            break
    
    # Extract remote/online indicators
    if any(term in prompt_lower for term in ['remote', 'online', 'virtual']):
        query.remote_only = True
    
    # Extract topic keywords
    tech_keywords = [
        'programming', 'coding', 'software', 'tech', 'python', 'javascript',
        'data science', 'machine learning', 'ai', 'web development', 'mobile'
    ]
    
    for keyword in tech_keywords:
        if keyword in prompt_lower:
            query.keywords.append(keyword)
    
    return query


# =============================================================================
# Meetup API Integration
# =============================================================================

def parse_rest_event(event_data: Dict[str, Any]) -> MeetupEvent:
    """Parse event data from REST API response."""
    venue = event_data.get('venue', {})
    group = event_data.get('group', {})
    fee = event_data.get('fee', {})
    
    return MeetupEvent(
        id=str(event_data['id']),
        title=event_data.get('name', 'Untitled Event'),
        description=event_data.get('description', ''),
        url=event_data.get('link', ''),
        start_time=datetime.fromtimestamp(event_data['time'] / 1000),
        venue_name=venue.get('name'),
        venue_city=venue.get('city'),
        is_online=venue.get('id') == 1,
        group_name=group.get('name', 'Unknown Group'),
        group_url=f"https://www.meetup.com/{group.get('urlname', '')}",
        attendee_count=event_data.get('yes_rsvp_count', 0),
        fee_amount=fee.get('amount'),
        fee_currency=fee.get('currency')
    )


async def search_events_rest(query: EventQuery) -> List[MeetupEvent]:
    """Search for events using Meetup's REST API."""
    if not state.session:
        raise RuntimeError("Session not initialized")
    
    headers = get_auth_headers()
    params = {'page': query.max_results, 'status': 'upcoming'}
    
    # Add location parameters
    if query.location and query.location != 'current_location':
        params['location'] = query.location
    
    # Add time parameters
    if query.start_time:
        params['start_date_range'] = query.start_time.isoformat()
    
    # Add topic filtering
    if query.keywords:
        params['text'] = ' '.join(query.keywords)
    
    events = []
    
    try:
        async with state.session.get(
            f"{Config.MEETUP_BASE_URL}/find/upcoming_events",
            params=params,
            headers=headers
        ) as response:
            if response.status == 200:
                data = await response.json()
                for event_data in data.get('events', []):
                    try:
                        event = parse_rest_event(event_data)
                        
                        # Apply additional filtering
                        if query.remote_only and not event.is_online:
                            continue
                        
                        events.append(event)
                    except Exception as e:
                        logging.warning(f"Error parsing event: {e}")
                        continue
            else:
                error_text = await response.text()
                logging.error(f"REST API error {response.status}: {error_text}")
    
    except Exception as e:
        logging.error(f"Error searching events: {e}")
    
    return events


def format_events_for_context(events: List[MeetupEvent]) -> str:
    """Format events in a readable context for Claude."""
    if not events:
        return "No events found matching your criteria."
    
    parts = [f"Found {len(events)} relevant events:"]
    
    for i, event in enumerate(events[:10], 1):  # Limit to top 10
        info = [
            f"**{event.title}**",
            f"  - Group: {event.group_name}",
            f"  - Date: {event.start_time.strftime('%Y-%m-%d %H:%M')}",
        ]
        
        if event.is_online:
            info.append("  - Location: Online/Remote")
        elif event.venue_name:
            location = event.venue_name
            if event.venue_city:
                location += f", {event.venue_city}"
            info.append(f"  - Location: {location}")
        
        if event.attendee_count:
            info.append(f"  - Attendees: {event.attendee_count}")
        
        if event.fee_amount:
            info.append(f"  - Fee: {event.fee_amount} {event.fee_currency or 'USD'}")
        else:
            info.append("  - Fee: Free")
        
        info.append(f"  - URL: {event.url}")
        parts.append(f"\n{i}. " + "\n".join(info))
    
    return "\n".join(parts)


async def augment_prompt_with_events(user_prompt: str) -> str:
    """Augment user prompt with relevant event data."""
    try:
        query = extract_query_parameters(user_prompt)
        events = await search_events_rest(query)
        
        if not events:
            return f"{user_prompt}\n\n[Note: No relevant Meetup events found.]"
        
        event_context = format_events_for_context(events)
        return f"{user_prompt}\n\n=== Relevant Meetup Events ===\n{event_context}\n\nPlease provide recommendations based on the above events."
    
    except Exception as e:
        logging.error(f"Error augmenting prompt: {e}")
        return f"{user_prompt}\n\n[Note: Error retrieving event data: {str(e)}]"


# =============================================================================
# MCP Tools using FastMCP Decorators
# =============================================================================

@mcp.tool()
async def search_meetup_events(
    query: str,
    max_results: int = Config.MAX_EVENTS_PER_QUERY
) -> str:
    """
    Search for Meetup events based on natural language query.
    
    Args:
        query: Natural language search query (e.g., 'tech events near me today')
        max_results: Maximum number of events to return (default: 20)
    
    Returns:
        Formatted list of events matching the search criteria
    """
    if not query:
        return "Error: Query parameter is required"
    
    try:
        # Extract query parameters
        event_query = extract_query_parameters(query)
        event_query.max_results = max_results
        
        # Search for events
        events = await search_events_rest(event_query)
        
        if events:
            result = f"Found {len(events)} events matching '{query}':\n\n"
            
            for i, event in enumerate(events, 1):
                result += f"{i}. **{event.title}**\n"
                result += f"   Group: {event.group_name}\n"
                result += f"   Date: {event.start_time.strftime('%Y-%m-%d %H:%M')}\n"
                
                if event.is_online:
                    result += "   Location: Online/Remote\n"
                elif event.venue_name:
                    result += f"   Location: {event.venue_name}"
                    if event.venue_city:
                        result += f", {event.venue_city}"
                    result += "\n"
                
                if event.attendee_count:
                    result += f"   Attendees: {event.attendee_count}\n"
                
                result += f"   Fee: {'Free' if not event.fee_amount else f'{event.fee_amount} {event.fee_currency or \"USD\"}'}\n"
                result += f"   URL: {event.url}\n\n"
            
            return result
        else:
            return f"No events found matching '{query}'. Try different keywords or location."
    
    except Exception as e:
        logging.error(f"Error searching events: {e}")
        return f"Error searching events: {str(e)}"


@mcp.tool()
async def augment_prompt_with_events_tool(prompt: str) -> str:
    """
    Enhance a prompt with relevant Meetup event data.
    
    Args:
        prompt: User prompt to augment with event data
    
    Returns:
        Enhanced prompt with relevant event information
    """
    if not prompt:
        return "Error: Prompt parameter is required"
    
    try:
        return await augment_prompt_with_events(prompt)
    except Exception as e:
        logging.error(f"Error augmenting prompt: {e}")
        return f"Error augmenting prompt: {str(e)}"


@mcp.tool()
async def get_event_recommendations(
    query: str,
    preferences: str = ""
) -> str:
    """
    Get AI-powered event recommendations using Claude.
    
    Args:
        query: Natural language query for event recommendations
        preferences: Additional preferences or constraints
    
    Returns:
        AI-generated recommendations based on relevant events
    """
    if not query:
        return "Error: Query parameter is required"
    
    try:
        # Augment the query with event data
        full_prompt = query
        if preferences:
            full_prompt += f"\n\nAdditional preferences: {preferences}"
        
        augmented_prompt = await augment_prompt_with_events(full_prompt)
        
        # Get Claude's recommendations if available
        if state.claude_client:
            try:
                message = await state.claude_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": augmented_prompt}]
                )
                return message.content[0].text
            except Exception as e:
                logging.error(f"Claude API error: {e}")
                return f"Claude API unavailable. Here's the event data instead:\n\n{augmented_prompt}"
        else:
            return f"Claude integration not configured. Here's the event data:\n\n{augmented_prompt}"
    
    except Exception as e:
        logging.error(f"Error getting recommendations: {e}")
        return f"Error getting recommendations: {str(e)}"


@mcp.tool()
def get_oauth_url() -> str:
    """
    Get Meetup OAuth authorization URL for authentication.
    
    Returns:
        OAuth authorization URL and setup instructions
    """
    try:
        oauth_url = get_oauth_url()
        return (
            f"Meetup OAuth Authorization URL:\n{oauth_url}\n\n"
            "Instructions:\n"
            "1. Visit the URL above\n"
            "2. Log in to your Meetup account\n"
            "3. Authorize the application\n"
            "4. Copy the authorization code from the redirect\n"
            "5. Use the code to exchange for an access token"
        )
    except Exception as e:
        logging.error(f"Error generating OAuth URL: {e}")
        return f"Error generating OAuth URL: {str(e)}"


# =============================================================================
# MCP Resources using FastMCP Decorators
# =============================================================================

@mcp.resource("meetup://config")
def get_server_config() -> str:
    """Get current server configuration and status."""
    config_data = {
        "meetup_client_id": Config.MEETUP_CLIENT_ID[:8] + "..." if Config.MEETUP_CLIENT_ID else "Not set",
        "meetup_client_secret": "Set" if Config.MEETUP_CLIENT_SECRET else "Not set",
        "anthropic_api_key": "Set" if Config.ANTHROPIC_API_KEY else "Not set",
        "max_events_per_query": Config.MAX_EVENTS_PER_QUERY,
        "default_radius": Config.DEFAULT_RADIUS,
        "log_level": Config.LOG_LEVEL
    }
    return json.dumps(config_data, indent=2)


@mcp.resource("meetup://auth/status")
def get_auth_status() -> str:
    """Get current authentication status with Meetup.com."""
    auth_status = {
        "has_access_token": bool(state.access_token),
        "oauth_url_available": bool(Config.MEETUP_CLIENT_ID and Config.MEETUP_CLIENT_SECRET),
        "claude_integration": bool(state.claude_client)
    }
    return json.dumps(auth_status, indent=2)


# =============================================================================
# Server Lifecycle Management
# =============================================================================

async def server_startup():
    """Initialize server on startup."""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logging.info("Initializing MCP Meetup-Claude Server...")
    
    if not Config.validate():
        raise Exception("Invalid configuration - check required environment variables")
    
    await state.initialize()
    logging.info("Server initialized successfully")


async def server_shutdown():
    """Clean up server on shutdown."""
    logging.info("Shutting down MCP Server...")
    await state.cleanup()
    logging.info("Server shutdown complete")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for the MCP server."""
    # Set up startup and shutdown handlers
    async def run_with_lifecycle():
        try:
            await server_startup()
            # FastMCP handles the actual server execution
            await mcp.run(transport="stdio")
        except KeyboardInterrupt:
            logging.info("Server interrupted by user")
        except Exception as e:
            logging.error(f"Server error: {e}")
            raise
        finally:
            await server_shutdown()
    
    # Run the server
    asyncio.run(run_with_lifecycle())


if __name__ == "__main__":
    """
    Environment Variables Required:
    MEETUP_CLIENT_ID=your_meetup_client_id
    MEETUP_CLIENT_SECRET=your_meetup_client_secret
    MEETUP_ACCESS_TOKEN=your_meetup_access_token (optional)
    ANTHROPIC_API_KEY=your_anthropic_api_key
    
    Usage:
    # Development with MCP CLI
    uv run mcp dev meetup_claude_mcp_server.py
    
    # Install in Claude Desktop
    uv run mcp install meetup_claude_mcp_server.py
    
    # Direct execution
    python meetup_claude_mcp_server.py
    """
    main()
