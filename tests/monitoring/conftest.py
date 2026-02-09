"""
Pytest configuration and fixtures for monitoring tests
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def temp_storage_dir():
    """Temporary directory for trace storage"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_file_store(temp_storage_dir):
    """Mock FileStore for testing"""
    mock_store = Mock()
    mock_store.storage_dir = temp_storage_dir

    # Mock store_file method
    mock_store.store_file = Mock()

    return mock_store


@pytest.fixture
def mock_app_state(mock_file_store):
    """Mock application state"""
    with patch('backend.monitoring.trace_store.get_app_state') as mock_get_state:
        mock_get_state.return_value = {
            "file_store": mock_file_store
        }
        yield mock_get_state


@pytest.fixture
def sample_trace_data():
    """Sample trace data for testing"""
    return {
        "trace_id": "trace_test123",
        "conversation_id": "conv_test123",
        "session_id": "session_test123",
        "start_time": 1675840000.0,
        "end_time": 1675840010.5,
        "total_duration_ms": 10500,
        "root_span": {
            "span_id": "span_root",
            "name": "agent_invoke",
            "span_type": "agent_invoke",
            "start_time": 1675840000.0,
            "end_time": 1675840010.5,
            "duration_ms": 10500,
            "status": "success",
            "parent_span_id": None,
            "children": [
                {
                    "span_id": "span_llm_1",
                    "name": "llm_call: claude-3-sonnet-4",
                    "span_type": "llm_call",
                    "parent_span_id": "span_root",
                    "duration_ms": 2000,
                    "status": "success",
                    "children": [],
                    "events": [],
                    "attributes": {
                        "input_tokens": 1500,
                        "output_tokens": 300
                    }
                }
            ],
            "events": [],
            "attributes": {}
        },
        "metrics": {
            "total_tokens": 1800,
            "total_duration_ms": 10500,
            "tool_calls": 1,
            "estimated_cost_usd": 0.0036
        }
    }
