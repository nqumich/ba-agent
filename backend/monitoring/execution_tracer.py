"""
Execution Tracer - Core component for tracking Agent execution flow

Design principles:
- Low overhead (<5% total execution time)
- OpenTelemetry-compatible span structure
- Parent-child relationships for call chains
- Event-based timestamping
- Compatible with existing AgentLogger and FileStore

Span types:
- agent_invoke: Root span for entire agent execution
- llm_call: LLM API call
- tool_call: Tool/function execution
- memory_flush: Context compression
- skill_activation: Skill activation flow
- error: Error tracking span
"""

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Iterator


class SpanType(str, Enum):
    """Span type classification"""
    AGENT_INVOKE = "agent_invoke"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    MEMORY_FLUSH = "memory_flush"
    SKILL_ACTIVATION = "skill_activation"
    CONTEXT_COMPRESSION = "context_compression"
    ERROR = "error"
    CUSTOM = "custom"


class SpanStatus(str, Enum):
    """Span execution status"""
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class Event:
    """
    Event - timestamped point within a span

    Events represent discrete points in time during span execution:
    - Token count updates
    - Cache hits/misses
    - Error occurrences
    - State changes
    """
    timestamp: float
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class Span:
    """
    Span - execution unit with timing and metadata

    Similar to OpenTelemetry span with:
    - Unique span_id for identification
    - parent_span_id for hierarchy
    - start_time/end_time for duration
    - status for execution result
    - events for detailed timeline
    - attributes for metadata
    """
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    span_type: SpanType
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: SpanStatus = SpanStatus.UNKNOWN
    events: List[Event] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    children: List['Span'] = field(default_factory=list)

    def __post_init__(self):
        """Convert string span_type to Enum if needed"""
        if isinstance(self.span_type, str):
            self.span_type = SpanType(self.span_type)
        if isinstance(self.status, str):
            self.status = SpanStatus(self.status)

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to this span"""
        event = Event(
            timestamp=time.time(),
            name=name,
            attributes=attributes or {}
        )
        self.events.append(event)

    def end(self, status: SpanStatus = SpanStatus.SUCCESS) -> None:
        """Mark span as ended and calculate duration"""
        self.end_time = time.time()
        self.status = status
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time) * 1000

    def add_child(self, child: 'Span') -> None:
        """Add a child span"""
        self.children.append(child)

    def to_dict(self, recursive: bool = True) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "span_type": self.span_type.value if isinstance(self.span_type, SpanType) else self.span_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value if isinstance(self.status, SpanStatus) else self.status,
            "events": [e.to_dict() for e in self.events],
            "attributes": self.attributes,
        }
        if recursive:
            result["children"] = [child.to_dict(recursive=True) for child in self.children]
        return result

    def find_span_by_id(self, span_id: str) -> Optional['Span']:
        """Find a span by ID in the hierarchy"""
        if self.span_id == span_id:
            return self
        for child in self.children:
            found = child.find_span_by_id(span_id)
            if found:
                return found
        return None

    def get_all_spans(self) -> List['Span']:
        """Get all spans in the hierarchy (flattened)"""
        result = [self]
        for child in self.children:
            result.extend(child.get_all_spans())
        return result


@dataclass
class Trace:
    """
    Trace - complete execution trace for a conversation

    Contains:
    - Root span representing the entire agent invocation
    - All child spans (LLM calls, tool calls, etc.)
    - Aggregated metrics
    - Conversation and session metadata
    """
    trace_id: str
    conversation_id: str
    session_id: str
    root_span: Span
    start_time: float
    end_time: Optional[float] = None
    total_duration_ms: Optional[float] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def end(self) -> None:
        """Mark trace as ended"""
        self.end_time = time.time()
        if self.start_time:
            self.total_duration_ms = (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "trace_id": self.trace_id,
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": self.total_duration_ms,
            "root_span": self.root_span.to_dict(recursive=True),
            "metrics": self.metrics,
            "attributes": self.attributes,
        }


class ExecutionTracer:
    """
    Execution Tracer - manages span lifecycle and trace collection

    Features:
    - Automatic span hierarchy management
    - Thread-local storage for concurrent execution
    - Low overhead timing
    - Event recording
    - Compatible with FileStore persistence

    Usage:
        tracer = ExecutionTracer(conversation_id, session_id)

        # Create root span
        root = tracer.create_root_span("agent_invoke")

        # Create child spans
        llm_span = tracer.create_span("llm_call", parent=root)
        # ... do work ...
        llm_span.end()

        tool_span = tracer.create_span("tool_call", parent=root)
        # ... do work ...
        tool_span.end()

        root.end()

        # Get complete trace
        trace = tracer.get_trace()
    """

    def __init__(
        self,
        conversation_id: str,
        session_id: Optional[str] = None,
        enabled: bool = True
    ):
        """
        Initialize ExecutionTracer

        Args:
            conversation_id: Unique conversation identifier
            session_id: Session identifier (optional)
            enabled: Whether tracing is enabled (for conditional monitoring)
        """
        self.conversation_id = conversation_id
        self.session_id = session_id or "default"
        self.enabled = enabled

        # Generate trace ID
        self.trace_id = f"trace_{uuid.uuid4().hex[:16]}_{int(time.time())}"

        # Root span (created when invoke starts)
        self._root_span: Optional[Span] = None

        # Active span stack for hierarchy management
        self._span_stack: List[Span] = []

        # All spans for quick lookup
        self._spans: Dict[str, Span] = {}

    @property
    def is_active(self) -> bool:
        """Check if tracer is active (enabled and has root span)"""
        return self.enabled and self._root_span is not None

    def create_root_span(
        self,
        name: str,
        span_type: SpanType = SpanType.AGENT_INVOKE,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Optional[Span]:
        """
        Create the root span for this trace

        Should be called once at the start of agent execution.

        Args:
            name: Span name (e.g., "agent_invoke")
            span_type: Type of span
            attributes: Initial attributes

        Returns:
            Created span or None if disabled
        """
        if not self.enabled:
            return None

        span_id = f"span_root_{self.trace_id}"
        span = Span(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=None,
            name=name,
            span_type=span_type,
            start_time=time.time(),
            attributes=attributes or {}
        )

        self._root_span = span
        self._span_stack = [span]
        self._spans[span_id] = span

        return span

    def create_span(
        self,
        name: str,
        span_type: SpanType,
        parent: Optional[Span] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Optional[Span]:
        """
        Create a new span

        Automatically establishes parent-child relationship.
        If parent is not specified, uses the current active span.

        Args:
            name: Span name
            span_type: Type of span
            parent: Parent span (auto-detected if None)
            attributes: Initial attributes

        Returns:
            Created span or None if disabled
        """
        if not self.enabled:
            return None

        # Determine parent
        if parent is None:
            parent = self._span_stack[-1] if self._span_stack else self._root_span

        if parent is None:
            # No root span yet, can't create child
            return None

        # Generate span ID
        span_id = f"span_{span_type.value}_{uuid.uuid4().hex[:8]}"

        # Create span
        span = Span(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=parent.span_id,
            name=name,
            span_type=span_type,
            start_time=time.time(),
            attributes=attributes or {}
        )

        # Add to parent's children
        parent.add_child(span)

        # Register in tracking
        self._spans[span_id] = span
        self._span_stack.append(span)

        return span

    def end_span(self, span: Span, status: SpanStatus = SpanStatus.SUCCESS) -> None:
        """
        End a span and calculate duration

        Args:
            span: Span to end
            status: Final status
        """
        if span is None:
            return

        span.end(status)

        # Remove from stack if present
        if self._span_stack and self._span_stack[-1] == span:
            self._span_stack.pop()

    def end_active_span(self, status: SpanStatus = SpanStatus.SUCCESS) -> Optional[Span]:
        """
        End the currently active span

        Args:
            status: Final status

        Returns:
            The ended span or None
        """
        if not self._span_stack:
            return None
        span = self._span_stack.pop()
        span.end(status)
        return span

    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        span: Optional[Span] = None
    ) -> None:
        """
        Add an event to a span

        Args:
            name: Event name
            attributes: Event attributes
            span: Target span (uses active span if None)
        """
        if not self.enabled:
            return

        target = span or (self._span_stack[-1] if self._span_stack else None)
        if target:
            target.add_event(name, attributes)

    def get_trace(self) -> Optional[Trace]:
        """
        Get the complete trace

        Args:
            metrics: Optional aggregated metrics to include

        Returns:
            Complete Trace object or None if no root span
        """
        if self._root_span is None:
            return None

        return Trace(
            trace_id=self.trace_id,
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            root_span=self._root_span,
            start_time=self._root_span.start_time,
            end_time=self._root_span.end_time,
            total_duration_ms=self._root_span.duration_ms,
        )

    def get_span_by_id(self, span_id: str) -> Optional[Span]:
        """Find a span by ID"""
        return self._spans.get(span_id)

    def get_all_spans(self) -> List[Span]:
        """Get all spans in the trace"""
        return list(self._spans.values())

    def iter_spans_breadth_first(self) -> Iterator[Span]:
        """Iterate spans in breadth-first order"""
        if self._root_span is None:
            return

        queue = [self._root_span]
        while queue:
            span = queue.pop(0)
            yield span
            queue.extend(span.children)

    def iter_spans_depth_first(self) -> Iterator[Span]:
        """Iterate spans in depth-first order"""
        if self._root_span is None:
            return

        stack = [self._root_span]
        while stack:
            span = stack.pop()
            yield span
            # Add children in reverse order for proper DFS
            stack.extend(reversed(span.children))

    def to_dict(self) -> Optional[Dict[str, Any]]:
        """Convert trace to dictionary"""
        trace = self.get_trace()
        return trace.to_dict() if trace else None

    def to_mermaid(self) -> Optional[str]:
        """
        Generate Mermaid flowchart representation

        Creates a visual graph of the span hierarchy.

        Returns:
            Mermaid flowchart string or None
        """
        if self._root_span is None:
            return None

        lines = ["graph TD"]

        # Build node definitions
        for span in self.iter_spans_breadth_first():
            # Node ID
            node_id = span.span_id.replace("-", "_").replace(":", "_")

            # Label with duration
            duration_str = f"{span.duration_ms:.0f}ms" if span.duration_ms else "running"

            # Status indicator
            status_icon = "✓" if span.status == SpanStatus.SUCCESS else "✗" if span.status == SpanStatus.ERROR else "○"

            # Node label
            label = f"{span.name}\\n{duration_str} {status_icon}"
            if span.span_type != SpanType.AGENT_INVOKE:
                label = f"{span.span_type.value}: {label}"

            lines.append(f"    {node_id}[\"{label}\"]")

            # Edge from parent
            if span.parent_span_id:
                parent_id = span.parent_span_id.replace("-", "_").replace(":", "_")
                # Add edge label with timing if available
                lines.append(f"    {parent_id} --> {node_id}")

        return "\n".join(lines)


# Global tracer registry (for multi-tenant scenarios)
_tracer_registry: Dict[str, ExecutionTracer] = {}


def get_tracer(conversation_id: str, session_id: Optional[str] = None) -> ExecutionTracer:
    """Get or create tracer for a conversation"""
    key = f"{conversation_id}:{session_id or 'default'}"
    if key not in _tracer_registry:
        _tracer_registry[key] = ExecutionTracer(conversation_id, session_id)
    return _tracer_registry[key]


def remove_tracer(conversation_id: str, session_id: Optional[str] = None) -> None:
    """Remove tracer from registry"""
    key = f"{conversation_id}:{session_id or 'default'}"
    _tracer_registry.pop(key, None)


__all__ = [
    "SpanType",
    "SpanStatus",
    "Event",
    "Span",
    "Trace",
    "ExecutionTracer",
    "get_tracer",
    "remove_tracer",
]
