"""
Integration tests for monitoring API endpoints
"""

import pytest
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient


class TestMonitoringAPI:
    """Test monitoring API endpoints"""

    def test_list_conversations(self, client: TestClient, auth_headers: dict):
        """Test GET /api/v1/monitoring/conversations"""
        # Mock the trace store to avoid file system issues
        with patch('backend.api.routes.monitoring.get_trace_store') as mock_store:
            mock_store.return_value.list_conversations.return_value = []

            response = client.get(
                "/api/v1/monitoring/conversations",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_trace_not_found(self, client: TestClient, auth_headers: dict):
        """Test GET /api/v1/monitoring/traces/{conversation_id} - not found"""
        with patch('backend.api.routes.monitoring.get_trace_store') as mock_store:
            mock_store.return_value.load_trace.return_value = None

            response = client.get(
                "/api/v1/monitoring/traces/nonexistent_conv",
                headers=auth_headers
            )

            assert response.status_code == 404

    def test_get_trace_found(self, client: TestClient, auth_headers: dict):
        """Test GET /api/v1/monitoring/traces/{conversation_id} - found"""
        with patch('backend.api.routes.monitoring.get_trace_store') as mock_store:
            mock_store.return_value.load_trace.return_value = {
                "trace_id": "test123",
                "conversation_id": "conv_test"
            }

            response = client.get(
                "/api/v1/monitoring/traces/conv_test",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["trace_id"] == "test123"

    def test_get_metrics(self, client: TestClient, auth_headers: dict):
        """Test GET /api/v1/monitoring/metrics"""
        with patch('backend.api.routes.monitoring.get_metrics_store') as mock_store:
            mock_store.return_value.get_aggregated_metrics.return_value = {
                "total_conversations": 0,
                "total_tokens": 0
            }

            response = client.get(
                "/api/v1/monitoring/metrics",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    def test_get_performance_summary_not_found(self, client: TestClient, auth_headers: dict):
        """Test GET /api/v1/monitoring/performance/{conversation_id} - not found"""
        with patch('backend.api.routes.monitoring.get_trace_store') as mock_store:
            mock_store.return_value.load_trace.return_value = None

            response = client.get(
                "/api/v1/monitoring/performance/nonexistent_conv",
                headers=auth_headers
            )

            assert response.status_code == 404

    def test_unauthenticated_request(self, client: TestClient):
        """Test that unauthenticated requests are rejected"""
        response = client.get("/api/v1/monitoring/conversations")

        # Should be redirected or return 401/403
        assert response.status_code in [401, 403, 307, 302]

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.api.main import app
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client: TestClient):
        """Get authentication headers for testing"""
        # First, login to get token
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )

        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token")
            if token:
                return {"Authorization": f"Bearer {token}"}

        # Return empty headers if login failed
        return {}


@pytest.fixture
def test_data():
    """Create test trace and metrics data"""
    return {
        "trace_id": "trace_test123",
        "conversation_id": "conv_test123",
        "session_id": "session_test123",
        "start_time": datetime.now().timestamp(),
        "end_time": datetime.now().timestamp() + 10,
        "total_duration_ms": 10000,
        "root_span": {
            "span_id": "span_root",
            "name": "agent_invoke",
            "span_type": "agent_invoke",
            "start_time": datetime.now().timestamp(),
            "end_time": datetime.now().timestamp() + 10,
            "duration_ms": 10000,
            "status": "success",
            "parent_span_id": None,
            "children": [],
            "events": [],
            "attributes": {}
        },
        "metrics": {
            "total_tokens": 1000,
            "total_duration_ms": 10000,
            "tool_calls_count": 2,
            "estimated_cost_usd": 0.01
        }
    }
