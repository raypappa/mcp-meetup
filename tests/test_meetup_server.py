#!/usr/bin/env python3
"""
Basic tests for MCP Meetup-Claude Server
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

# Import the server components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meetup_claude_mcp_server import (
    EventQuery,
    MeetupEvent,
    EventDiscoveryEngine,
    AuthenticationManager,
    Config
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
            attendee_count=50,
            fee_amount=None,
            fee_currency=None
        )
        
        assert event.id == "123"
        assert event.title == "Test Event"
        assert event.is_online is False
        assert event.attendee_count == 50


class TestEventDiscoveryEngine:
    """Test EventDiscoveryEngine parameter extraction."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.auth_manager = Mock(spec=AuthenticationManager)
        self.engine = EventDiscoveryEngine(self.auth_manager)
    
    def test_extract_time_today(self):
        """Test extraction of 'today' time reference."""
        query = self.engine.extract_query_parameters("events today")
        assert query.start_time is not None
        assert query.start_time.date() == datetime.now().date()
    
    def test_extract_time_tomorrow(self):
        """Test extraction of 'tomorrow' time reference."""
        query = self.engine.extract_query_parameters("events tomorrow")
        assert query.start_time is not None
        assert query.start_time.date() == (datetime.now() + timedelta(days=1)).date()
    
    def test_extract_location_near_me(self):
        """Test extraction of 'near me' location reference."""
        query = self.engine.extract_query_parameters("events near me")
        assert query.location == "current_location"
    
    def test_extract_location_city(self):
        """Test extraction of city name."""
        query = self.engine.extract_query_parameters("events in San Francisco")
        assert query.location == "San Francisco"
    
    def test_extract_remote_indicator(self):
        """Test extraction of remote event indicator."""
        query = self.engine.extract_query_parameters("remote programming events")
        assert query.remote_only is True
        assert "programming" in query.keywords
    
    def test_extract_tech_keywords(self):
        """Test extraction of technology keywords."""
        query = self.engine.extract_query_parameters("python and javascript meetups")
        assert "python" in query.keywords
        assert "javascript" in query.keywords
    
    def test_extract_combined_query(self):
        """Test extraction from complex combined query."""
        query = self.engine.extract_query_parameters(
            "remote python programming events near me today"
        )
        assert query.remote_only is True
        assert "python" in query.keywords
        assert "programming" in query.keywords
        assert query.location == "current_location"
        assert query.start_time is not None
        assert query.start_time.date() == datetime.now().date()
    
    def test_extract_no_matches(self):
        """Test extraction with no matches."""
        query = self.engine.extract_query_parameters("hello world")
        assert query.location is None
        assert query.keywords == []
        assert query.remote_only is False
        assert query.start_time is None


class TestAuthenticationManager:
    """Test AuthenticationManager."""
    
    def test_oauth_url_generation(self):
        """Test OAuth URL generation."""
        # Mock the config for testing
        original_client_id = Config.MEETUP_CLIENT_ID
        original_client_secret = Config.MEETUP_CLIENT_SECRET
        
        Config.MEETUP_CLIENT_ID = "test_client_id"
        Config.MEETUP_CLIENT_SECRET = "test_client_secret"
        
        try:
            auth_manager = AuthenticationManager()
            oauth_url = auth_manager.get_oauth_url()
            
            assert "test_client_id" in oauth_url
            assert "response_type=code" in oauth_url
            assert "redirect_uri=" in oauth_url
            assert "scope=basic" in oauth_url
        
        finally:
            # Restore original config
            Config.MEETUP_CLIENT_ID = original_client_id
            Config.MEETUP_CLIENT_SECRET = original_client_secret
    
    def test_auth_headers_with_token(self):
        """Test authentication headers generation."""
        auth_manager = AuthenticationManager()
        auth_manager.access_token = "test_token"
        
        headers = auth_manager.get_auth_headers()
        
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Content-Type"] == "application/json"
    
    def test_auth_headers_without_token(self):
        """Test authentication headers without token."""
        auth_manager = AuthenticationManager()
        auth_manager.access_token = None
        
        with pytest.raises(Exception, match="No access token available"):
            auth_manager.get_auth_headers()


class TestConfig:
    """Test Config validation."""
    
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


# Fixture for sample event data
@pytest.fixture
def sample_meetup_event_data():
    """Sample Meetup event data for testing."""
    return {
        "id": "123456789",
        "name": "Python Programming Meetup",
        "description": "A meetup for Python enthusiasts",
        "link": "https://www.meetup.com/python-group/events/123456789/",
        "time": 1640995200000,  # Unix timestamp in milliseconds
        "duration": 7200000,    # 2 hours in milliseconds
        "venue": {
            "id": 12345,
            "name": "Tech Hub",
            "address_1": "123 Tech Street",
            "city": "San Francisco"
        },
        "group": {
            "id": 54321,
            "name": "SF Python Group",
            "urlname": "sf-python-group",
            "topics": [
                {"id": 1, "name": "Python"},
                {"id": 2, "name": "Programming"}
            ]
        },
        "yes_rsvp_count": 42,
        "rsvp_limit": 50,
        "status": "upcoming",
        "fee": {
            "amount": 10.0,
            "currency": "USD"
        }
    }


class TestEventParsing:
    """Test event data parsing."""
    
    def test_parse_rest_event(self, sample_meetup_event_data):
        """Test parsing REST API event data."""
        auth_manager = Mock(spec=AuthenticationManager)
        engine = EventDiscoveryEngine(auth_manager)
        
        event = engine._parse_rest_event(sample_meetup_event_data)
        
        assert event.id == "123456789"
        assert event.title == "Python Programming Meetup"
        assert event.venue_name == "Tech Hub"
        assert event.venue_city == "San Francisco"
        assert event.group_name == "SF Python Group"
        assert event.attendee_count == 42
        assert event.fee_amount == 10.0
        assert event.fee_currency == "USD"
        assert event.is_online is False  # venue id != 1
    
    def test_parse_online_event(self, sample_meetup_event_data):
        """Test parsing online event data."""
        # Modify sample data for online event
        sample_meetup_event_data["venue"]["id"] = 1  # Online venue indicator
        
        auth_manager = Mock(spec=AuthenticationManager)
        engine = EventDiscoveryEngine(auth_manager)
        
        event = engine._parse_rest_event(sample_meetup_event_data)
        
        assert event.is_online is True
    
    def test_parse_free_event(self, sample_meetup_event_data):
        """Test parsing free event data."""
        # Remove fee from sample data
        del sample_meetup_event_data["fee"]
        
        auth_manager = Mock(spec=AuthenticationManager)
        engine = EventDiscoveryEngine(auth_manager)
        
        event = engine._parse_rest_event(sample_meetup_event_data)
        
        assert event.fee_amount is None
        assert event.fee_currency is None


# Integration test placeholder
class TestIntegration:
    """Integration tests for the complete system."""
    
    @pytest.mark.asyncio
    async def test_server_initialization_mock(self):
        """Test that server components can be initialized with mocks."""
        from meetup_claude_mcp_server import MeetupClaudeMCPServer
        
        # Mock the config validation
        original_validate = Config.validate
        Config.validate = lambda: True
        
        # Mock the required config values
        Config.MEETUP_CLIENT_ID = "test_id"
        Config.MEETUP_CLIENT_SECRET = "test_secret"
        Config.ANTHROPIC_API_KEY = "test_key"
        
        try:
            server = MeetupClaudeMCPServer()
            
            # Mock the async initialization methods
            server.auth_manager.initialize = AsyncMock()
            server.discovery_engine.initialize = AsyncMock()
            server.claude_integration.initialize = AsyncMock()
            
            await server.initialize()
            
            # Verify initialization was called
            server.auth_manager.initialize.assert_called_once()
            server.discovery_engine.initialize.assert_called_once()
            server.claude_integration.initialize.assert_called_once()
            
        finally:
            # Restore original config
            Config.validate = original_validate


class TestPromptAugmentation:
    """Test prompt augmentation functionality."""
    
    def test_format_events_for_context_empty(self):
        """Test formatting empty event list."""
        from meetup_claude_mcp_server import PromptAugmentationService
        
        auth_manager = Mock()
        discovery_engine = EventDiscoveryEngine(auth_manager)
        service = PromptAugmentationService(discovery_engine)
        
        result = service._format_events_for_context([], EventQuery())
        assert "No events found" in result
    
    def test_format_events_for_context_with_events(self):
        """Test formatting event list with sample events."""
        from meetup_claude_mcp_server import PromptAugmentationService
        
        # Create sample events
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
                attendee_count=25,
                fee_amount=None,
                fee_currency=None
            ),
            MeetupEvent(
                id="2",
                title="Remote JavaScript Workshop",
                description="JS workshop",
                url="https://meetup.com/js",
                start_time=datetime(2024, 1, 16, 19, 0),
                venue_name=None,
                venue_city=None,
                is_online=True,
                group_name="JS Developers",
                group_url="https://meetup.com/js-dev",
                attendee_count=50,
                fee_amount=15.0,
                fee_currency="USD"
            )
        ]
        
        auth_manager = Mock()
        discovery_engine = EventDiscoveryEngine(auth_manager)
        service = PromptAugmentationService(discovery_engine)
        
        result = service._format_events_for_context(events, EventQuery())
        
        assert "Found 2 relevant events" in result
        assert "Python Meetup" in result
        assert "Remote JavaScript Workshop" in result
        assert "SF Python" in result
        assert "Tech Hub, San Francisco" in result
        assert "Online/Remote" in result
        assert "Free" in result
        assert "15.0 USD" in result


if __name__ == "__main__":
    """Run tests directly."""
    pytest.main([__file__, "-v"])
