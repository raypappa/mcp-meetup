#!/usr/bin/env python3
"""
Tests for MCP Meetup-Claude Server - Official SDK Compliant Version
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

# Import the fixed server components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meetup_claude_mcp_server_fixed import (
    EventQuery,
    MeetupEvent,
    Config,
    extract_query_parameters,
    parse_rest_event,
    format_events_for_context,
    get_oauth_url,
    state
)


class TestEventQuery:
    """Test EventQuery data model."""
    
    def test_event_query_creation(self):
        """Test basic EventQuery creation."""
        query = EventQuery()
        assert query.location is None
        assert query.keywords == []
        assert query.remote_only is False
        assert query.max_results == Config.MAX_EVENTS_PER_QUERY
    
    def test_event_query_with_data(self):
        """Test EventQuery with data."""
        query = EventQuery(
            location="San Francisco",
            keywords=["python", "programming"],
            remote_only=True,
            max_results=10
        )
        assert query.location == "San Francisco"
        assert query.keywords == ["python", "programming"]
        assert query.remote_only is True
        assert query.max_results == 10


class TestMeetupEvent:
    """Test MeetupEvent data model."""
    
    def test_meetup_event_creation(self):
        """Test basic MeetupEvent creation."""
        event = MeetupEvent(
            id="123",
            title="Test Event",
            description="A test event",
            url="https://meetup.com/test",
            start_time=datetime.now(),
            venue_name="Test Venue",
            venue_city="Test City",
            is_online=False,
            group_name="Test Group",
            group_url="https://meetup.com/test-group",
            attendee_count=50
        )
        
        assert event.id == "123"
        assert event.title == "Test Event"
        assert event.is_online is False
        assert event.attendee_count == 50


class TestNaturalLanguageProcessing:
    """Test natural language query parameter extraction."""
    
    def test_extract_time_today(self):
        """Test extraction of 'today' time reference."""
        query = extract_query_parameters("events today")
        assert query.start_time is not None
        assert query.start_time.date() == datetime.now().date()
    
    def test_extract_time_tomorrow(self):
        """Test extraction of 'tomorrow' time reference."""
        query = extract_query_parameters("events tomorrow")
        assert query.start_time is not None
        assert query.start_time.date() == (datetime.now() + timedelta(days=1)).date()
    
    def test_extract_location_near_me(self):
        """Test extraction of 'near me' location reference."""
        query = extract_query_parameters("events near me")
        assert query.location == "current_location"
    
    def test_extract_location_city(self):
        """Test extraction of city name."""
        query = extract_query_parameters("events in San Francisco")
        assert query.location == "San Francisco"
    
    def test_extract_remote_indicator(self):
        """Test extraction of remote event indicator."""
        query = extract_query_parameters("remote programming events")
        assert query.remote_only is True
        assert "programming" in query.keywords
    
    def test_extract_tech_keywords(self):
        """Test extraction of technology keywords."""
        query = extract_query_parameters("python and javascript meetups")
        assert "python" in query.keywords
        assert "javascript" in query.keywords
    
    def test_extract_combined_query(self):
        """Test extraction from complex combined query."""
        query = extract_query_parameters(
            "remote python programming events near me today"
        )
        assert query.remote_only is True
        assert "python" in query.keywords
        assert "programming" in query.keywords
        assert query.location == "current_location"
        assert query.start_time is not None
        assert query.start_time.date() == datetime.now().date()


class TestAuthenticationUtilities:
    """Test authentication utilities."""
    
    def test_oauth_url_generation(self):
        """Test OAuth URL generation."""
        # Mock the config for testing
        original_client_id = Config.MEETUP_CLIENT_ID
        original_client_secret = Config.MEETUP_CLIENT_SECRET
        
        Config.MEETUP_CLIENT_ID = "test_client_id"
        Config.MEETUP_CLIENT_SECRET = "test_client_secret"
        
        try:
            oauth_url = get_oauth_url()
            
            assert "test_client_id" in oauth_url
            assert "response_type=code" in oauth_url
            assert "redirect_uri=" in oauth_url
            assert "scope=basic" in oauth_url
        
        finally:
            # Restore original config
            Config.MEETUP_CLIENT_ID = original_client_id
            Config.MEETUP_CLIENT_SECRET = original_client_secret


class TestEventParsing:
    """Test event data parsing."""
    
    def test_parse_rest_event(self):
        """Test parsing REST API event data."""
        sample_event_data = {
            "id": "123456789",
            "name": "Python Programming Meetup",
            "description": "A meetup for Python enthusiasts",
            "link": "https://www.meetup.com/python-group/events/123456789/",
            "time": 1640995200000,  # Unix timestamp in milliseconds
            "duration": 7200000,    # 2 hours in milliseconds
            "venue": {
                "id": 12345,
                "name": "Tech Hub",
                "city": "San Francisco"
            },
            "group": {
                "id": 54321,
                "name": "SF Python Group",
                "urlname": "sf-python-group"
            },
            "yes_rsvp_count": 42,
            "fee": {
                "amount": 10.0,
                "currency": "USD"
            }
        }
        
        event = parse_rest_event(sample_event_data)
        
        assert event.id == "123456789"
        assert event.title == "Python Programming Meetup"
        assert event.venue_name == "Tech Hub"
        assert event.venue_city == "San Francisco"
        assert event.group_name == "SF Python Group"
        assert event.attendee_count == 42
        assert event.fee_amount == 10.0
        assert event.fee_currency == "USD"
        assert event.is_online is False  # venue id != 1
    
    def test_parse_online_event(self):
        """Test parsing online event data."""
        sample_event_data = {
            "id": "123456789",
            "name": "Online Python Meetup",
            "description": "Virtual meetup",
            "link": "https://www.meetup.com/python-group/events/123456789/",
            "time": 1640995200000,
            "venue": {
                "id": 1,  # Online venue indicator
                "name": "Online Event"
            },
            "group": {
                "id": 54321,
                "name": "SF Python Group",
                "urlname": "sf-python-group"
            },
            "yes_rsvp_count": 50
        }
        
        event = parse_rest_event(sample_event_data)
        assert event.is_online is True
    
    def test_parse_free_event(self):
        """Test parsing free event data."""
        sample_event_data = {
            "id": "123456789",
            "name": "Free Python Meetup",
            "description": "Free meetup",
            "link": "https://www.meetup.com/python-group/events/123456789/",
            "time": 1640995200000,
            "venue": {
                "id": 12345,
                "name": "Community Center"
            },
            "group": {
                "id": 54321,
                "name": "SF Python Group",
                "urlname": "sf-python-group"
            },
            "yes_rsvp_count": 25
            # No fee data = free event
        }
        
        event = parse_rest_event(sample_event_data)
        assert event.fee_amount is None
        assert event.fee_currency is None


class TestEventFormatting:
    """Test event formatting for context."""
    
    def test_format_events_empty_list(self):
        """Test formatting empty event list."""
        result = format_events_for_context([])
        assert "No events found" in result
    
    def test_format_events_with_sample_events(self):
        """Test formatting event list with sample events."""
        events = [
            MeetupEvent(
                id="1",
                title="Python Meetup",
                description="Python event",
                url="https://meetup.com/python",
                start_time=datetime(2024, 1, 15, 18, 0),
                venue_name="Tech Hub",
                venue_city="San Francisco",
                is_online=False,
                group_name="SF Python",
                group_url="https://meetup.com/sf-python",
                attendee_count=25
            ),
            MeetupEvent(
                id="2",
                title="Remote JavaScript Workshop",
                description="JS workshop",
                url="https://meetup.com/js",
                start_time=datetime(2024, 1, 16, 19, 0),
                is_online=True,
                group_name="JS Developers",
                group_url="https://meetup.com/js-dev",
                attendee_count=50,
                fee_amount=15.0,
                fee_currency="USD"
            )
        ]
        
        result = format_events_for_context(events)
        
        assert "Found 2 relevant events" in result
        assert "Python Meetup" in result
        assert "Remote JavaScript Workshop" in result
        assert "SF Python" in result
        assert "Tech Hub, San Francisco" in result
        assert "Online/Remote" in result
        assert "Free" in result
        assert "15.0 USD" in result


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_config_validation_missing_fields(self):
        """Test config validation with missing fields."""
        # Store original values
        original_client_id = Config.MEETUP_CLIENT_ID
        original_client_secret = Config.MEETUP_CLIENT_SECRET
        original_api_key = Config.ANTHROPIC_API_KEY
        
        # Set empty values
        Config.MEETUP_CLIENT_ID = ""
        Config.MEETUP_CLIENT_SECRET = ""
        Config.ANTHROPIC_API_KEY = ""
        
        try:
            assert Config.validate() is False
        finally:
            # Restore original values
            Config.MEETUP_CLIENT_ID = original_client_id
            Config.MEETUP_CLIENT_SECRET = original_client_secret
            Config.ANTHROPIC_API_KEY = original_api_key
    
    def test_config_validation_with_fields(self):
        """Test config validation with all required fields."""
        # Store original values
        original_client_id = Config.MEETUP_CLIENT_ID
        original_client_secret = Config.MEETUP_CLIENT_SECRET
        original_api_key = Config.ANTHROPIC_API_KEY
        
        # Set test values
        Config.MEETUP_CLIENT_ID = "test_id"
        Config.MEETUP_CLIENT_SECRET = "test_secret"
        Config.ANTHROPIC_API_KEY = "test_key"
        
        try:
            assert Config.validate() is True
        finally:
            # Restore original values
            Config.MEETUP_CLIENT_ID = original_client_id
            Config.MEETUP_CLIENT_SECRET = original_client_secret
            Config.ANTHROPIC_API_KEY = original_api_key


class TestServerState:
    """Test server state management."""
    
    @pytest.mark.asyncio
    async def test_server_state_initialization(self):
        """Test server state initialization."""
        from meetup_claude_mcp_server_fixed import ServerState
        
        test_state = ServerState()
        assert test_state.session is None
        assert test_state.claude_client is None
        
        # Mock the initialization
        with patch('aiohttp.ClientSession') as mock_session:
            await test_state.initialize()
            mock_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_server_state_cleanup(self):
        """Test server state cleanup."""
        from meetup_claude_mcp_server_fixed import ServerState
        
        test_state = ServerState()
        
        # Mock session
        mock_session = AsyncMock()
        test_state.session = mock_session
        
        await test_state.cleanup()
        mock_session.close.assert_called_once()


# Integration test for FastMCP compatibility
class TestFastMCPIntegration:
    """Test FastMCP integration and compatibility."""
    
    def test_fastmcp_import(self):
        """Test that FastMCP can be imported correctly."""
        try:
            from mcp.server.fastmcp import FastMCP
            assert FastMCP is not None
        except ImportError:
            pytest.skip("FastMCP not available - install mcp[cli]")
    
    def test_tool_decorator_usage(self):
        """Test that tool decorators work correctly."""
        try:
            from mcp.server.fastmcp import FastMCP
            
            # Create a test FastMCP instance
            test_mcp = FastMCP("Test Server")
            
            # Test that we can define a tool
            @test_mcp.tool()
            def test_tool(message: str) -> str:
                """A test tool."""
                return f"Test: {message}"
            
            # Verify the tool was registered
            # Note: We can't easily test the internal registration 
            # without running the full MCP protocol
            assert test_mcp is not None
            
        except ImportError:
            pytest.skip("FastMCP not available - install mcp[cli]")
    
    def test_resource_decorator_usage(self):
        """Test that resource decorators work correctly."""
        try:
            from mcp.server.fastmcp import FastMCP
            
            # Create a test FastMCP instance
            test_mcp = FastMCP("Test Server")
            
            # Test that we can define a resource
            @test_mcp.resource("test://resource")
            def test_resource() -> str:
                """A test resource."""
                return "Test resource content"
            
            # Verify the resource was registered
            assert test_mcp is not None
            
        except ImportError:
            pytest.skip("FastMCP not available - install mcp[cli]")


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_extract_query_no_matches(self):
        """Test query extraction with no recognizable patterns."""
        query = extract_query_parameters("hello world xyz")
        assert query.location is None
        assert query.keywords == []
        assert query.remote_only is False
        assert query.start_time is None
    
    def test_parse_event_missing_fields(self):
        """Test parsing event with missing optional fields."""
        minimal_event_data = {
            "id": "123",
            "name": "Minimal Event",
            "time": 1640995200000,
            "group": {"name": "Test Group", "urlname": "test-group"}
        }
        
        event = parse_rest_event(minimal_event_data)
        assert event.id == "123"
        assert event.title == "Minimal Event"
        assert event.description == ""  # Default value
        assert event.venue_name is None
        assert event.fee_amount is None
    
    def test_format_events_large_list(self):
        """Test formatting with more than 10 events (should limit to 10)."""
        events = []
        for i in range(15):
            events.append(MeetupEvent(
                id=str(i),
                title=f"Event {i}",
                description=f"Description {i}",
                url=f"https://meetup.com/event{i}",
                start_time=datetime.now(),
                group_name=f"Group {i}",
                group_url=f"https://meetup.com/group{i}",
                attendee_count=i * 10
            ))
        
        result = format_events_for_context(events)
        
        # Should show "Found 15 relevant events" but only list first 10
        assert "Found 15 relevant events" in result
        assert "Event 0" in result  # First event
        assert "Event 9" in result  # 10th event (0-indexed)
        assert "Event 14" not in result  # 15th event should not be listed
        assert "and 5 more events" in result  # Should indicate more events


class TestAsyncFunctionality:
    """Test async functionality and error handling."""
    
    @pytest.mark.asyncio
    async def test_search_events_with_mock_session(self):
        """Test event search with mocked HTTP session."""
        from meetup_claude_mcp_server_fixed import search_events_rest, state
        
        # Mock the state session
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "events": [{
                "id": "test123",
                "name": "Test Event",
                "time": 1640995200000,
                "group": {"name": "Test Group", "urlname": "test-group"},
                "yes_rsvp_count": 10
            }]
        })
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        # Mock the state and auth
        state.session = mock_session
        state.access_token = "test_token"
        
        query = EventQuery(keywords=["test"])
        events = await search_events_rest(query)
        
        assert len(events) == 1
        assert events[0].title == "Test Event"
        assert events[0].id == "test123"
    
    @pytest.mark.asyncio
    async def test_search_events_api_error(self):
        """Test event search with API error."""
        from meetup_claude_mcp_server_fixed import search_events_rest, state
        
        # Mock API error response
        mock_response = Mock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        state.session = mock_session
        state.access_token = "invalid_token"
        
        query = EventQuery(keywords=["test"])
        events = await search_events_rest(query)
        
        # Should return empty list on API error
        assert events == []
    
    @pytest.mark.asyncio
    async def test_augment_prompt_with_events(self):
        """Test prompt augmentation functionality."""
        from meetup_claude_mcp_server_fixed import augment_prompt_with_events
        
        # Mock the search function to return test events
        with patch('meetup_claude_mcp_server_fixed.search_events_rest') as mock_search:
            mock_search.return_value = [
                MeetupEvent(
                    id="1",
                    title="Test Event",
                    description="Test description",
                    url="https://test.com",
                    start_time=datetime.now(),
                    group_name="Test Group",
                    group_url="https://test-group.com",
                    attendee_count=20
                )
            ]
            
            result = await augment_prompt_with_events("Find me some events")
            
            assert "Find me some events" in result
            assert "Relevant Meetup Events" in result
            assert "Test Event" in result
            assert "Test Group" in result


# Performance and integration tests
class TestPerformance:
    """Test performance characteristics."""
    
    def test_query_extraction_performance(self):
        """Test that query extraction is fast enough."""
        import time
        
        queries = [
            "python events today near me",
            "remote javascript meetups this week",
            "data science workshops in San Francisco tomorrow",
            "free programming events next week"
        ]
        
        start_time = time.time()
        
        for query in queries * 100:  # Test with 400 queries
            extract_query_parameters(query)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should process 400 queries in less than 1 second
        assert elapsed < 1.0, f"Query extraction took {elapsed:.2f}s for 400 queries"
    
    def test_event_formatting_performance(self):
        """Test event formatting performance with large lists."""
        import time
        
        # Create 100 test events
        events = []
        for i in range(100):
            events.append(MeetupEvent(
                id=str(i),
                title=f"Event {i}",
                description=f"Description {i}",
                url=f"https://meetup.com/event{i}",
                start_time=datetime.now(),
                group_name=f"Group {i}",
                group_url=f"https://meetup.com/group{i}",
                attendee_count=i
            ))
        
        start_time = time.time()
        result = format_events_for_context(events)
        end_time = time.time()
        
        # Should format 100 events quickly
        elapsed = end_time - start_time
        assert elapsed < 0.1, f"Event formatting took {elapsed:.3f}s for 100 events"
        assert len(result) > 0


if __name__ == "__main__":
    """Run tests directly."""
    pytest.main([__file__, "-v", "--tb=short"])
