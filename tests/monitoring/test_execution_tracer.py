"""
Unit tests for ExecutionTracer
"""

import pytest
import time
from backend.monitoring.execution_tracer import (
    ExecutionTracer,
    Span,
    SpanType,
    SpanStatus,
    Trace,
)


class TestExecutionTracer:
    """Test ExecutionTracer functionality"""

    def test_tracer_initialization(self):
        """Test tracer initialization"""
        tracer = ExecutionTracer(
            conversation_id="test_conv",
            session_id="test_session",
            enabled=True
        )

        assert tracer.conversation_id == "test_conv"
        assert tracer.session_id == "test_session"
        assert tracer.enabled is True
        assert tracer.trace_id is not None
        assert len(tracer.trace_id) > 0

    def test_create_root_span(self):
        """Test root span creation"""
        tracer = ExecutionTracer("test_conv", "test_session")

        root_span = tracer.create_root_span(
            name="agent_invoke",
            span_type=SpanType.AGENT_INVOKE
        )

        assert root_span is not None
        assert root_span.name == "agent_invoke"
        assert root_span.span_type == SpanType.AGENT_INVOKE
        assert root_span.parent_span_id is None
        assert root_span.start_time > 0
        assert root_span.end_time is None
        assert root_span.status == SpanStatus.UNKNOWN

    def test_create_child_span(self):
        """Test child span creation"""
        tracer = ExecutionTracer("test_conv", "test_session")

        root_span = tracer.create_root_span("agent_invoke")
        child_span = tracer.create_span(
            name="llm_call",
            span_type=SpanType.LLM_CALL,
            parent=root_span
        )

        assert child_span is not None
        assert child_span.name == "llm_call"
        assert child_span.parent_span_id == root_span.span_id
        assert len(root_span.children) == 1
        assert root_span.children[0].span_id == child_span.span_id

    def test_span_hierarchy(self):
        """Test span hierarchy relationships"""
        tracer = ExecutionTracer("test_conv", "test_session")

        root = tracer.create_root_span("agent_invoke")
        child1 = tracer.create_span("llm_1", SpanType.LLM_CALL, parent=root)
        child2 = tracer.create_span("tool_1", SpanType.TOOL_CALL, parent=root)

        assert len(root.children) == 2
        assert child1.parent_span_id == root.span_id
        assert child2.parent_span_id == root.span_id

    def test_span_lifecycle(self):
        """Test span start and end"""
        tracer = ExecutionTracer("test_conv", "test_session")

        span = tracer.create_root_span("test_span")
        time.sleep(0.01)  # Small delay

        tracer.end_span(span, SpanStatus.SUCCESS)

        assert span.end_time is not None
        assert span.status == SpanStatus.SUCCESS
        assert span.duration_ms is not None
        assert span.duration_ms > 0

    def test_add_event(self):
        """Test adding events to spans"""
        tracer = ExecutionTracer("test_conv", "test_session")

        span = tracer.create_root_span("test_span")
        tracer.add_event("test_event", {"key": "value"})

        assert len(span.events) == 1
        assert span.events[0].name == "test_event"
        assert span.events[0].attributes["key"] == "value"

    def test_get_trace(self):
        """Test getting complete trace"""
        tracer = ExecutionTracer("test_conv", "test_session")

        root = tracer.create_root_span("agent_invoke")
        child = tracer.create_span("llm_call", SpanType.LLM_CALL, parent=root)

        tracer.end_span(child, SpanStatus.SUCCESS)
        tracer.end_span(root, SpanStatus.SUCCESS)

        trace = tracer.get_trace()

        assert trace is not None
        assert trace.conversation_id == "test_conv"
        assert trace.session_id == "test_session"
        assert trace.root_span.span_id == root.span_id

    def test_disabled_tracer(self):
        """Test that disabled tracer doesn't create spans"""
        tracer = ExecutionTracer("test_conv", "test_session", enabled=False)

        root = tracer.create_root_span("test")
        child = tracer.create_span("test_child", SpanType.LLM_CALL)

        assert root is None
        assert child is None

    def test_mermaid_generation(self):
        """Test Mermaid flowchart generation"""
        tracer = ExecutionTracer("test_conv", "test_session")

        root = tracer.create_root_span("agent_invoke")
        child = tracer.create_span("llm_call", SpanType.LLM_CALL, parent=root)

        tracer.end_span(child, SpanStatus.SUCCESS)
        tracer.end_span(root, SpanStatus.SUCCESS)

        mermaid = tracer.to_mermaid()

        assert mermaid is not None
        assert "graph TD" in mermaid
        assert "agent_invoke" in mermaid

    def test_find_span_by_id(self):
        """Test finding spans by ID"""
        tracer = ExecutionTracer("test_conv", "test_session")

        root = tracer.create_root_span("agent_invoke")
        child = tracer.create_span("llm_call", SpanType.LLM_CALL, parent=root)

        found = tracer.get_span_by_id(child.span_id)

        assert found is not None
        assert found.span_id == child.span_id

    def test_iterate_spans(self):
        """Test span iteration methods"""
        tracer = ExecutionTracer("test_conv", "test_session")

        root = tracer.create_root_span("agent_invoke")
        child1 = tracer.create_span("llm_1", SpanType.LLM_CALL, parent=root)
        child2 = tracer.create_span("tool_1", SpanType.TOOL_CALL, parent=root)

        # Depth-first should return root first
        dfs_spans = list(tracer.iter_spans_depth_first())
        assert dfs_spans[0].span_id == root.span_id

        # Breadth-first should return root, then children
        bfs_spans = list(tracer.iter_spans_breadth_first())
        assert bfs_spans[0].span_id == root.span_id


class TestSpan:
    """Test Span dataclass"""

    def test_span_creation(self):
        """Test span creation with required fields"""
        span = Span(
            trace_id="trace_123",
            span_id="span_456",
            parent_span_id=None,
            name="test_span",
            span_type=SpanType.AGENT_INVOKE,
            start_time=time.time()
        )

        assert span.trace_id == "trace_123"
        assert span.span_id == "span_456"
        assert span.name == "test_span"

    def test_span_to_dict(self):
        """Test span serialization to dictionary"""
        span = Span(
            trace_id="trace_123",
            span_id="span_456",
            parent_span_id=None,
            name="test_span",
            span_type=SpanType.AGENT_INVOKE,
            start_time=time.time()
        )

        span_dict = span.to_dict()

        assert span_dict["trace_id"] == "trace_123"
        assert span_dict["span_id"] == "span_456"
        assert span_dict["span_type"] == "agent_invoke"


class TestTrace:
    """Test Trace dataclass"""

    def test_trace_creation(self):
        """Test trace creation"""
        root_span = Span(
            trace_id="trace_123",
            span_id="span_root",
            parent_span_id=None,
            name="agent_invoke",
            span_type=SpanType.AGENT_INVOKE,
            start_time=time.time()
        )

        trace = Trace(
            trace_id="trace_123",
            conversation_id="conv_123",
            session_id="session_123",
            root_span=root_span,
            start_time=time.time()
        )

        assert trace.trace_id == "trace_123"
        assert trace.conversation_id == "conv_123"
