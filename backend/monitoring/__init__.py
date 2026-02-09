"""
BA-Agent Monitoring System

Provides full-flow logging and monitoring capabilities for Agent execution:

Components:
- ExecutionTracer: Tracks complete execution path with spans and events
- MetricsCollector: Aggregates performance metrics and token usage
- TraceStore: Persistent storage for traces and metrics
- MonitoringAPI: REST endpoints for querying and visualization

Architecture:
    Agent execution -> ExecutionTracer -> TraceStore
                      -> MetricsCollector -> MetricsStore
                      -> Monitoring API -> Dashboard

Usage:
    from backend.monitoring import ExecutionTracer, MetricsCollector

    tracer = ExecutionTracer(conversation_id, session_id)
    metrics = MetricsCollector(conversation_id, session_id)

    # Auto-integrated with BAAgent.invoke()
"""

from backend.monitoring.execution_tracer import (
    Span,
    Event,
    Trace,
    ExecutionTracer,
    SpanType,
    SpanStatus,
)

from backend.monitoring.metrics_collector import (
    AgentMetrics,
    MetricsCollector,
    ToolCallStats,
)

from backend.monitoring.trace_store import (
    TraceStore,
    MetricsStore,
    get_trace_store,
    get_metrics_store,
)

__all__ = [
    # Execution Tracer
    "Span",
    "Event",
    "Trace",
    "ExecutionTracer",
    "SpanType",
    "SpanStatus",

    # Metrics Collector
    "AgentMetrics",
    "MetricsCollector",
    "ToolCallStats",

    # Storage
    "TraceStore",
    "MetricsStore",
    "get_trace_store",
    "get_metrics_store",
]
