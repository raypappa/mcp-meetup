#!/usr/bin/env python3
"""
MCP Server for Meetup.com Integration with Claude - Complete Implementation
"""

import asyncio
import json
import logging
import os
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
from anthropic import AsyncAnthropic
from dateutil import parser as date_parser
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent
from pydantic import BaseModel, Field


class Config:
    """Configuration management."""
    MEETUP_CLIENT_ID = os.getenv('MEETUP_CLIENT_ID', '')
    MEETUP_CLIENT_SECRET = os.getenv('MEETUP_CLIENT_SECRET', '')
    MEETUP_REDIRECT_URI = os.getenv('MEETUP_REDIRECT_URI', 'http://localhost:8080/oauth/callback')
    MEETUP_ACCESS_TOKEN = os.getenv('MEETUP_ACCESS_TOKEN', '')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    MEETUP_BASE_URL = 'https://api.meetup.com'
    MEETUP_OAUTH_URL = 'https://secure.meetup.com/oauth2'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    MAX_EVENTS_PER_QUERY = int(os.getenv('MAX_EVENTS_PER_QUERY', '20'))
    DEFAULT_RADIUS = int(os.getenv('DEFAULT_RADIUS', '25'))
    
    @classmethod
    def validate(cls) -> bool:
        required = ['MEETUP_CLIENT_ID', 'MEETUP_CLIENT_SECRET', 'ANTHROPIC_API_KEY']
        missing = [f for f in required if not getattr(cls, f)]
        if missing:
            logging.error(f"Missing configuration: {', '.join(missing)}")
            return False
        return True


class EventQuery(BaseModel):
    """Event search query."""
    location: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    remote_only: bool = False
    max_results: int = Config.MAX_EVENTS_PER_QUERY


class MeetupEvent(BaseModel):
    """Meetup event representation."""
    id: str
    title: str
    description: str
    url: str
    start_time: datetime
    venue_name: Optional[str]
    venue_city: Optional[str]
    is_online: bool
    group_name: str
    group_url: str
    attendee_count: int
    fee_amount: Optional[float]
    fee_currency: Optional[str]


class AuthenticationManager:
    """Handles Meetup.com authentication."""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token = Config.MEETUP_ACCESS_TOKEN
        
    async def initialize(self):
        self.session = aiohttp.ClientSession()
        if self.access_token:
            logging.info("Using existing Meetup access token")
        else:
            logging.warning("No Meetup access token - authentication required")
    
    async def cleanup(self):
        if self.session:
            await self.session.close()
    
    def get_oauth_url(self) -> str:
        params = {
            'client_id': Config.MEETUP_CLIENT_ID,
            'response_type': 'code',
            'redirect_uri': Config.MEETUP_REDIRECT_URI,
            'scope': 'basic'
        }
        return f"{Config.MEETUP_OAUTH_URL}/authorize?{urllib.parse.urlencode(params)}"
    
    def get_auth_headers(self) -> Dict[str, str]:
        if not self.access_token:
            raise Exception("No access token available")
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }


class EventDiscoveryEngine:
    """Event discovery using Meetup APIs."""
    
    def __init__(self, auth_manager: AuthenticationManager):
        self.auth_manager = auth_manager
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        self.session = aiohttp.ClientSession()
    
    async def cleanup(self):
        if self.session:
            await self.session.close()
    
    def extract_query_parameters(self, user_prompt: str) -> EventQuery:
        """Extract search parameters from natural language."""
        query = EventQuery()
        prompt_lower = user_prompt.lower()
        
        # Time patterns
        time_patterns = {
            r'\btoday\b': lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            r'\btomorrow\b': lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
            r'\bthis week\b': lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
        }
        
        for pattern, time_func in time_patterns.items():
            if re.search(pattern, prompt_lower):
                query.start_time = time_func()
                break
        
        # Location patterns
        location_patterns = [r'\bnear me\b', r'\bin ([A-Za-z\s,]+?)(?:\s|$)']
        for pattern in location_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                query.location = 'current_location' if 'near me' in match.group(0) else match.group(1).strip()
                break
        
        # Remote indicators
        if any(term in prompt_lower for term in ['remote', 'online', 'virtual']):
            query.remote_only = True
        
        # Tech keywords
        tech_keywords = ['programming', 'coding', 'software', 'tech', 'python', 'javascript', 'data science']
        for keyword in tech_keywords:
            if keyword in prompt_lower:
                query.keywords.append(keyword)
        
        return query
    
    async def search_events_rest(self, query: EventQuery) -> List[MeetupEvent]:
        """Search events using REST API."""
        if not self.session:
            raise RuntimeError("Discovery engine not initialized")
        
        headers = self.auth_manager.get_auth_headers()
        params = {'page': query.max_results, 'status': 'upcoming'}
        
        if query.location and query.location != 'current_location':
            params['location'] = query.location
        
        if query.start_time:
            params['start_date_range'] = query.start_time.isoformat()
        
        if query.keywords:
            params['text'] = ' '.join(query.keywords)
        
        events = []
        try:
            async with self.session.get(
                f"{Config.MEETUP_BASE_URL}/find/upcoming_events",
                params=params,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    for event_data in data.get('events', []):
                        try:
                            event = self._parse_rest_event(event_data)
                            if query.remote_only and not event.is_online:
                                continue
                            events.append(event)
                        except Exception as e:
                            logging.warning(f"Error parsing event: {e}")
                else:
                    logging.error(f"API error {response.status}")
        except Exception as e:
            logging.error(f"Search error: {e}")
        
        return events
    
    def _parse_rest_event(self, event_data: Dict[str, Any]) -> MeetupEvent:
        """Parse REST API event data."""
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


class PromptAugmentationService:
    """Enriches prompts with event data."""
    
    def __init__(self, discovery_engine: EventDiscoveryEngine):
        self.discovery_engine = discovery_engine
    
    async def augment_prompt(self, user_prompt: str) -> str:
        """Augment prompt with event data."""
        try:
            query = self.discovery_engine.extract_query_parameters(user_prompt)
            events = await self.discovery_engine.search_events_rest(query)
            
            if not events:
                return f"{user_prompt}\n\n[Note: No relevant Meetup events found.]"
            
            event_context = self._format_events_for_context(events)
            return f"{user_prompt}\n\n=== Relevant Meetup Events ===\n{event_context}\n\nPlease provide recommendations based on the above events."
        
        except Exception as e:
            logging.error(f"Error augmenting prompt: {e}")
            return f"{user_prompt}\n\n[Note: Error retrieving event data: {str(e)}]"
    
    def _format_events_for_context(self, events: List[MeetupEvent]) -> str:
        """Format events for context."""
        if not events:
            return "No events found."
        
        parts = [f"Found {len(events)} relevant events:"]
        
        for i, event in enumerate(events[:10], 1):
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


class ClaudeIntegration:
    """Claude LLM integration."""
    
    def __init__(self):
        self.client: Optional[AsyncAnthropic] = None
    
    async def initialize(self):
        if not Config.ANTHROPIC_API_KEY:
            raise Exception("Anthropic API key not configured")
        self.client = AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)
        logging.info("Claude integration initialized")
    
    async def generate_response(self, prompt: str, max_tokens: int = 1000) -> str:
        if not self.client:
            raise RuntimeError("Claude integration not initialized")
        
        try:
            message = await self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            raise


class MeetupClaudeMCPServer:
    """Main MCP Server."""
    
    def __init__(self):
        self.server = Server("meetup-claude-mcp")
        self.auth_manager = AuthenticationManager()
        self.discovery_engine = EventDiscoveryEngine(self.auth_manager)
        self.prompt_service = PromptAugmentationService(self.discovery_engine)
        self.claude_integration = ClaudeIntegration()
        self._setup_tools()
        self._setup_resources()
    
    def _setup_tools(self):
        @self.server.list_tools()
        async def handle_list_tools():
            return [
                Tool(
                    name="search_meetup_events",
                    description="Search for Meetup events based on natural language query",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Natural language event search query"},
                            "max_results": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="augment_prompt_with_events",
                    description="Enhance a prompt with relevant Meetup event data",
                    inputSchema={
                        "type": "object",
                        "properties": {"prompt": {"type": "string", "description": "User prompt to augment"}},
                        "required": ["prompt"]
                    }
                ),
                Tool(
                    name="get_event_recommendations",
                    description="Get AI-powered event recommendations using Claude",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Query for recommendations"},
                            "preferences": {"type": "string", "default": "", "description": "Additional preferences"}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_oauth_url",
                    description="Get Meetup OAuth authorization URL",
                    inputSchema={"type": "object", "properties": {}, "required": []}
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict):
            try:
                if name == "search_meetup_events":
                    return await self._handle_search_events(arguments)
                elif name == "augment_prompt_with_events":
                    return await self._handle_augment_prompt(arguments)
                elif name == "get_event_recommendations":
                    return await self._handle_get_recommendations(arguments)
                elif name == "get_oauth_url":
                    return await self._handle_get_oauth_url(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logging.error(f"Tool error {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    def _setup_resources(self):
        @self.server.list_resources()
        async def handle_list_resources():
            return [
                Resource(
                    uri="meetup://config",
                    name="Server Configuration",
                    description="Current server configuration and status",
                    mimeType="application/json"
                ),
                Resource(
                    uri="meetup://auth/status",
                    name="Authentication Status",
                    description="Current authentication status with Meetup.com",
                    mimeType="application/json"
                )
            ]
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str):
            try:
                if uri == "meetup://config":
                    return await self._handle_read_config()
                elif uri == "meetup://auth/status":
                    return await self._handle_read_auth_status()
                else:
                    raise ValueError(f"Unknown resource: {uri}")
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def initialize(self):
        """Initialize server."""
        logging.info("Initializing MCP Meetup-Claude Server...")
        
        if not Config.validate():
            raise Exception("Invalid configuration")
        
        await self.auth_manager.initialize()
        await self.discovery_engine.initialize()
        await self.claude_integration.initialize()
        
        logging.info("Server initialized successfully")
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.auth_manager.cleanup()
        await self.discovery_engine.cleanup()
    
    # Tool handlers
    async def _handle_search_events(self, arguments: dict) -> List[TextContent]:
        query_text = arguments.get("query", "")
        max_results = arguments.get("max_results", Config.MAX_EVENTS_PER_QUERY)
        
        if not query_text:
            return [TextContent(type="text", text="Error: Query required")]
        
        try:
            query = self.discovery_engine.extract_query_parameters(query_text)
            query.max_results = max_results
            events = await self.discovery_engine.search_events_rest(query)
            
            if events:
                result = f"Found {len(events)} events matching '{query_text}':\n\n"
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
                
                return [TextContent(type="text", text=result)]
            else:
                return [TextContent(type="text", text=f"No events found matching '{query_text}'")]
        
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching events: {str(e)}")]
    
    async def _handle_augment_prompt(self, arguments: dict) -> List[TextContent]:
        prompt = arguments.get("prompt", "")
        if not prompt:
            return [TextContent(type="text", text="Error: Prompt required")]
        
        try:
            augmented_prompt = await self.prompt_service.augment_prompt(prompt)
            return [TextContent(type="text", text=augmented_prompt)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error augmenting prompt: {str(e)}")]
    
    async def _handle_get_recommendations(self, arguments: dict) -> List[TextContent]:
        query = arguments.get("query", "")
        preferences = arguments.get("preferences", "")
        
        if not query:
            return [TextContent(type="text", text="Error: Query required")]
        
        try:
            full_prompt = query
            if preferences:
                full_prompt += f"\n\nPreferences: {preferences}"
            
            augmented_prompt = await self.prompt_service.augment_prompt(full_prompt)
            response = await self.claude_integration.generate_response(augmented_prompt, max_tokens=2000)
            
            return [TextContent(type="text", text=response)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting recommendations: {str(e)}")]
    
    async def _handle_get_oauth_url(self, arguments: dict) -> List[TextContent]:
        try:
            oauth_url = self.auth_manager.get_oauth_url()
            return [TextContent(
                type="text",
                text=f"Meetup OAuth URL:\n{oauth_url}\n\n"
                     "Instructions:\n"
                     "1. Visit the URL above\n"
                     "2. Log in to your Meetup account\n"
                     "3. Authorize the application\n"
                     "4. Copy the authorization code\n"
                     "5. Exchange code for access token"
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error generating OAuth URL: {str(e)}")]
    
    # Resource handlers
    async def _handle_read_config(self) -> List[TextContent]:
        config_data = {
            "meetup_client_id": Config.MEETUP_CLIENT_ID[:8] + "..." if Config.MEETUP_CLIENT_ID else "Not set",
            "meetup_client_secret": "Set" if Config.MEETUP_CLIENT_SECRET else "Not set",
            "anthropic_api_key": "Set" if Config.ANTHROPIC_API_KEY else "Not set",
            "max_events_per_query": Config.MAX_EVENTS_PER_QUERY,
            "default_radius": Config.DEFAULT_RADIUS
        }
        return [TextContent(type="text", text=json.dumps(config_data, indent=2))]
    
    async def _handle_read_auth_status(self) -> List[TextContent]:
        auth_status = {
            "has_access_token": bool(self.auth_manager.access_token),
            "oauth_url_available": bool(Config.MEETUP_CLIENT_ID and Config.MEETUP_CLIENT_SECRET)
        }
        return [TextContent(type="text", text=json.dumps(auth_status, indent=2))]


async def main():
    """Main server entry point."""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = MeetupClaudeMCPServer()
    
    try:
        await server.initialize()
        
        async with stdio_server() as (read_stream, write_stream):
            await server.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="meetup-claude-mcp",
                    server_version="1.0.0",
                    capabilities={"tools": {}, "resources": {}}
                )
            )
    
    except KeyboardInterrupt:
        logging.info("Server interrupted")
    except Exception as e:
        logging.error(f"Server error: {e}")
        raise
    finally:
        await server.cleanup()


if __name__ == "__main__":
    """
    Environment Variables Required:
    MEETUP_CLIENT_ID=your_meetup_client_id
    MEETUP_CLIENT_SECRET=your_meetup_client_secret
    MEETUP_ACCESS_TOKEN=your_meetup_access_token (optional)
    ANTHROPIC_API_KEY=your_anthropic_api_key
    
    Usage:
    python meetup_claude_mcp_server.py
    """
    asyncio.run(main())
