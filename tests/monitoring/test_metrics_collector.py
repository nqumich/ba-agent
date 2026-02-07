"""
Unit tests for MetricsCollector
"""

import pytest
import time
from backend.monitoring.metrics_collector import (
    MetricsCollector,
    AgentMetrics,
    ToolCallStats,
    MODEL_PRICING,
)


class TestMetricsCollector:
    """Test MetricsCollector functionality"""

    def test_collector_initialization(self):
        """Test collector initialization"""
        collector = MetricsCollector(
            conversation_id="test_conv",
            session_id="test_session",
            enabled=True
        )

        assert collector.conversation_id == "test_conv"
        assert collector.session_id == "test_session"
        assert collector.enabled is True
        assert isinstance(collector.get_metrics(), AgentMetrics)

    def test_record_llm_call(self):
        """Test recording LLM call metrics"""
        collector = MetricsCollector("test_conv", "test_session")

        collector.record_llm_call(
            model="claude-sonnet-4-5-20250929",
            input_tokens=1000,
            output_tokens=500,
            duration_ms=2000
        )

        metrics = collector.get_metrics()
        assert metrics.total_input_tokens == 1000
        assert metrics.total_output_tokens == 500
        assert metrics.total_tokens == 1500
        assert metrics.llm_duration_ms == 2000
        assert metrics.primary_model == "claude-sonnet-4-5-20250929"

    def test_record_multiple_llm_calls(self):
        """Test recording multiple LLM calls"""
        collector = MetricsCollector("test_conv", "test_session")

        collector.record_llm_call("claude-sonnet-4-5-20250929", 1000, 500, 2000)
        collector.record_llm_call("claude-sonnet-4-5-20250929", 500, 300, 1500)

        metrics = collector.get_metrics()
        assert metrics.total_input_tokens == 1500
        assert metrics.total_output_tokens == 800
        assert metrics.total_tokens == 2300
        assert metrics.llm_duration_ms == 3500

    def test_record_tool_call(self):
        """Test recording tool call metrics"""
        collector = MetricsCollector("test_conv", "test_session")

        collector.record_tool_call(
            tool_name="query_database",
            duration_ms=500,
            success=True
        )

        metrics = collector.get_metrics()
        assert metrics.tool_calls_count == 1
        assert metrics.tool_errors == 0
        assert "query_database" in metrics.tool_calls_by_name

        tool_stats = metrics.tool_calls_by_name["query_database"]
        assert tool_stats.call_count == 1
        assert tool_stats.success_count == 1

    def test_record_tool_call_failure(self):
        """Test recording failed tool call"""
        collector = MetricsCollector("test_conv", "test_session")

        collector.record_tool_call(
            tool_name="failing_tool",
            duration_ms=100,
            success=False
        )

        metrics = collector.get_metrics()
        assert metrics.tool_calls_count == 1
        assert metrics.tool_errors == 1

        tool_stats = metrics.tool_calls_by_name["failing_tool"]
        assert tool_stats.success_count == 0
        assert tool_stats.error_count == 1

    def test_record_memory_flush(self):
        """Test recording memory flush metrics"""
        collector = MetricsCollector("test_conv", "test_session")

        collector.record_memory_flush(
            tokens_before=10000,
            tokens_after=5000,
            duration_ms=500
        )

        metrics = collector.get_metrics()
        assert "memory_flushes" in metrics.metadata
        assert len(metrics.metadata["memory_flushes"]) == 1

        flush_info = metrics.metadata["memory_flushes"][0]
        assert flush_info["tokens_before"] == 10000
        assert flush_info["tokens_after"] == 5000
        assert flush_info["tokens_saved"] == 5000

    def test_record_error(self):
        """Test recording error events"""
        collector = MetricsCollector("test_conv", "test_session")

        collector.record_error(
            error_type="TestError",
            error_message="Test error message",
            context={"key": "value"}
        )

        metrics = collector.get_metrics()
        assert "errors" in metrics.metadata
        assert len(metrics.metadata["errors"]) == 1

        error_info = metrics.metadata["errors"][0]
        assert error_info["type"] == "TestError"
        assert error_info["message"] == "Test error message"

    def test_finalize_metrics(self):
        """Test metrics finalization"""
        collector = MetricsCollector("test_conv", "test_session")

        collector.record_llm_call("claude-sonnet-4-5-20250929", 1000, 500, 2000)
        collector.record_tool_call("test_tool", 500, True)

        time.sleep(0.01)  # Small delay for duration

        finalized = collector.finalize()

        assert finalized.total_duration_ms > 0
        assert finalized.total_tokens == 1500
        assert finalized.tool_calls_count == 1

    def test_cost_calculation(self):
        """Test cost calculation for different models"""
        collector = MetricsCollector("test_conv", "test_session")

        # Claude Sonnet 4.5
        collector.record_llm_call(
            model="claude-sonnet-4-5-20250929",
            input_tokens=1_000_000,  # 1M input
            output_tokens=1_000_000,  # 1M output
            duration_ms=5000
        )

        metrics = collector.finalize()
        # Cost should be approximately (1M * $3/1M) + (1M * $15/1M) = $18
        assert abs(metrics.estimated_cost_usd - 18.0) < 0.01

    def test_disabled_collector(self):
        """Test that disabled collector doesn't record"""
        collector = MetricsCollector("test_conv", "test_session", enabled=False)

        collector.record_llm_call("claude-sonnet-4-5-20250929", 1000, 500, 2000)

        metrics = collector.get_metrics()
        assert metrics.total_input_tokens == 0
        assert metrics.total_output_tokens == 0

    def test_to_dict(self):
        """Test metrics serialization to dictionary"""
        collector = MetricsCollector("test_conv", "test_session")

        collector.record_llm_call("claude-sonnet-4-5-20250929", 1000, 500, 2000)
        collector.record_tool_call("test_tool", 500, True)

        metrics_dict = collector.to_dict()

        assert metrics_dict["conversation_id"] == "test_conv"
        assert metrics_dict["total_tokens"] == 1500
        assert metrics_dict["tool_calls_count"] == 1


class TestToolCallStats:
    """Test ToolCallStats dataclass"""

    def test_stats_initialization(self):
        """Test stats initialization"""
        stats = ToolCallStats(tool_name="test_tool")

        assert stats.tool_name == "test_tool"
        assert stats.call_count == 0
        assert stats.success_count == 0
        assert stats.error_count == 0

    def test_stats_calculation(self):
        """Test derived statistics"""
        stats = ToolCallStats(tool_name="test_tool")
        stats.call_count = 10
        stats.success_count = 8
        stats.error_count = 2
        stats.total_duration_ms = 5000

        assert stats.avg_duration_ms == 500.0
        assert stats.success_rate == 0.8


class TestModelPricing:
    """Test model pricing configuration"""

    def test_pricing_entries_exist(self):
        """Test that pricing entries exist for common models"""
        assert "claude-sonnet-4-5-20250929" in MODEL_PRICING
        assert "gpt-4o" in MODEL_PRICING
        assert "default" in MODEL_PRICING

    def test_pricing_format(self):
        """Test that pricing entries have correct format"""
        for model, pricing in MODEL_PRICING.items():
            assert "input" in pricing
            assert "output" in pricing
            assert isinstance(pricing["input"], (int, float))
            assert isinstance(pricing["output"], (int, float))
            assert pricing["input"] >= 0
            assert pricing["output"] >= 0
