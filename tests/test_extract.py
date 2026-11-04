"""Tests for natural-language query parameter extraction."""

from datetime import datetime, timedelta

from mcp_meetup.extract import extract_query_parameters


class TestTimePatterns:
    def test_today(self):
        query = extract_query_parameters("events today")
        assert query.start_time is not None
        assert query.start_time.date() == datetime.now().date()

    def test_tomorrow(self):
        query = extract_query_parameters("events tomorrow")
        assert query.start_time is not None
        assert query.start_time.date() == (datetime.now() + timedelta(days=1)).date()

    def test_this_week(self):
        query = extract_query_parameters("meetups this week")
        assert query.start_time is not None
        assert query.start_time.date() == datetime.now().date()

    def test_next_week(self):
        query = extract_query_parameters("meetups next week")
        assert query.start_time is not None
        assert query.start_time.date() == (datetime.now() + timedelta(weeks=1)).date()


class TestLocationPatterns:
    def test_near_me(self):
        query = extract_query_parameters("events near me")
        assert query.location == "current_location"

    def test_city(self):
        query = extract_query_parameters("events in San Francisco")
        assert query.location == "san francisco"

    def test_city_with_state(self):
        query = extract_query_parameters("meetups in new york, ny")
        assert query.location == "new york, ny"

    def test_near_me_wins_over_city(self):
        query = extract_query_parameters("meetups in san francisco near me")
        assert query.location == "current_location"

    def test_no_location(self):
        query = extract_query_parameters("python programming events")
        assert query.location is None


class TestRemoteIndicators:
    def test_remote(self):
        query = extract_query_parameters("remote programming events")
        assert query.remote_only is True
        assert "programming" in query.keywords

    def test_online(self):
        query = extract_query_parameters("online events")
        assert query.remote_only is True

    def test_virtual(self):
        query = extract_query_parameters("virtual workshops")
        assert query.remote_only is True

    def test_not_remote(self):
        query = extract_query_parameters("events in san francisco")
        assert query.remote_only is False


class TestTechKeywords:
    def test_python_javascript(self):
        query = extract_query_parameters("python and javascript meetups")
        assert "python" in query.keywords
        assert "javascript" in query.keywords

    def test_ai(self):
        query = extract_query_parameters("ai workshops in san francisco")
        assert "ai" in query.keywords

    def test_web_dev_mobile(self):
        query = extract_query_parameters("web development mobile tech meetups")
        assert "tech" in query.keywords
        assert "web development" in query.keywords
        assert "mobile" in query.keywords

    def test_no_keywords(self):
        query = extract_query_parameters("hello world")
        assert query.keywords == []


class TestCombined:
    def test_complex_query(self):
        query = extract_query_parameters(
            "remote python programming events near me today"
        )
        assert query.remote_only is True
        assert "python" in query.keywords
        assert "programming" in query.keywords
        assert query.location == "current_location"
        assert query.start_time is not None
        assert query.start_time.date() == datetime.now().date()

    def test_no_matches(self):
        query = extract_query_parameters("hello world xyz")
        assert query.location is None
        assert query.keywords == []
        assert query.remote_only is False
        assert query.start_time is None
