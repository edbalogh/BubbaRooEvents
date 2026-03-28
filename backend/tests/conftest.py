import pytest


@pytest.fixture
def mock_event_data():
    return {
        "title": "Test Concert",
        "source": "mock",
        "external_id": "test-001",
        "city": "Austin",
        "state": "TX",
    }
