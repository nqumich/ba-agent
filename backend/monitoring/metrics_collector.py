"""
Metrics Collector - Aggregates performance metrics and token usage

Design principles:
- Minimal overhead during collection
- Support for multiple model pricing
- Tool call statistics
- Performance breakdown (LLM vs Tools vs Other)

Collected metrics:
- Token usage (input/output/total) by model
- Execution time breakdown
- Tool call statistics (count, success rate, by name)
- Cost estimation
- Error tracking
"""

import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


# Model pricing (USD per 1M tokens)
# Source: Anthropic, OpenAI, etc. pricing pages as of 2024
MODEL_PRICING = {
    # Claude models
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20250929": {"input": 0.8, "output": 4.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},

    # GPT models
    "gpt-4.1": {"input": 2.5, "output": 10.0},
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},

    # Default pricing
    "default": {"input": 1.0, "output": 2.0},
}


@dataclass
class ToolCallStats:
    """Statistics for a single tool"""
    tool_name: str
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def avg_duration_ms(self) -> float:
        """Average duration per call"""
        return self.total_duration_ms / self.call_count if self.call_count > 0 else 0.0

    @property
    def success_rate(self) -> float:
        """Success rate (0-1)"""
        return self.success_count / self.call_count if self.call_count > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tool_name": self.tool_name,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "avg_duration_ms": self.avg_duration_ms,
            "success_rate": self.success_rate,
        }


@dataclass
class AgentMetrics:
    """
    Complete metrics for a single agent conversation

    Contains all performance, token, and cost metrics for analysis.
    """
    conversation_id: str
    session_id: str
    timestamp: float

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    tokens_by_model: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Performance timing
    total_duration_ms: float = 0.0
    llm_duration_ms: float = 0.0
    tool_duration_ms: float = 0.0
    other_duration_ms: float = 0.0

    # Tool statistics
    tool_calls_count: int = 0
    tool_errors: int = 0
    tool_calls_by_name: Dict[str, ToolCallStats] = field(default_factory=dict)

    # Cost estimation
    estimated_cost_usd: float = 0.0

    # Model info
    primary_model: Optional[str] = None
    models_used: List[str] = field(default_factory=list)

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "tokens_by_model": self.tokens_by_model,
            "total_duration_ms": self.total_duration_ms,
            "llm_duration_ms": self.llm_duration_ms,
            "tool_duration_ms": self.tool_duration_ms,
            "other_duration_ms": self.other_duration_ms,
            "tool_calls_count": self.tool_calls_count,
            "tool_errors": self.tool_errors,
            "tool_calls_by_name": {
                name: stats.to_dict()
                for name, stats in self.tool_calls_by_name.items()
            },
            "estimated_cost_usd": self.estimated_cost_usd,
            "primary_model": self.primary_model,
            "models_used": self.models_used,
            "metadata": self.metadata,
        }

    def calculate_cost(self) -> float:
        """
        Calculate estimated cost based on token usage and model pricing

        Returns:
            Estimated cost in USD
        """
        total_cost = 0.0

        for model, tokens in self.tokens_by_model.items():
            pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
            input_cost = (tokens.get("input", 0) / 1_000_000) * pricing["input"]
            output_cost = (tokens.get("output", 0) / 1_000_000) * pricing["output"]
            total_cost += input_cost + output_cost

        self.estimated_cost_usd = total_cost
        return total_cost


class MetricsCollector:
    """
    Metrics Collector - aggregates metrics during agent execution

    Thread-safe metrics collection with minimal overhead.

    Usage:
        collector = MetricsCollector(conversation_id, session_id)

        # Record LLM call
        collector.record_llm_call(
            model="claude-sonnet-4-5-20250929",
            input_tokens=1000,
            output_tokens=500,
            duration_ms=2000
        )

        # Record tool call
        collector.record_tool_call(
            tool_name="query_database",
            duration_ms=500,
            success=True
        )

        # Get final metrics
        metrics = collector.get_metrics()
    """

    def __init__(
        self,
        conversation_id: str,
        session_id: Optional[str] = None,
        enabled: bool = True
    ):
        """
        Initialize MetricsCollector

        Args:
            conversation_id: Unique conversation identifier
            session_id: Session identifier
            enabled: Whether metrics collection is enabled
        """
        self.conversation_id = conversation_id
        self.session_id = session_id or "default"
        self.enabled = enabled
        self.start_time = time.time()

        # Metrics storage
        self._metrics = AgentMetrics(
            conversation_id=conversation_id,
            session_id=self.session_id,
            timestamp=time.time()
        )

    @property
    def is_active(self) -> bool:
        """Check if collector is active"""
        return self.enabled

    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
        cached: bool = False
    ) -> None:
        """
        Record an LLM API call

        Args:
            model: Model name/identifier
            input_tokens: Input token count
            output_tokens: Output token count
            duration_ms: Call duration in milliseconds
            cached: Whether result was cached (no cost)
        """
        if not self.enabled:
            return

        # Update token counts
        self._metrics.total_input_tokens += input_tokens
        self._metrics.total_output_tokens += output_tokens
        self._metrics.total_tokens += input_tokens + output_tokens

        # Track by model
        if model not in self._metrics.tokens_by_model:
            self._metrics.tokens_by_model[model] = {"input": 0, "output": 0, "calls": 0}
            self._metrics.models_used.append(model)

        if not cached:
            self._metrics.tokens_by_model[model]["input"] += input_tokens
            self._metrics.tokens_by_model[model]["output"] += output_tokens

        self._metrics.tokens_by_model[model]["calls"] += 1

        # Update timing
        self._metrics.llm_duration_ms += duration_ms

        # Set primary model (first one used)
        if self._metrics.primary_model is None:
            self._metrics.primary_model = model

    def record_tool_call(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool = True,
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> None:
        """
        Record a tool/function call

        Args:
            tool_name: Name of the tool
            duration_ms: Execution duration
            success: Whether the call succeeded
            input_tokens: Input tokens for tool (if applicable)
            output_tokens: Output tokens from tool (if applicable)
        """
        if not self.enabled:
            return

        self._metrics.tool_calls_count += 1

        if not success:
            self._metrics.tool_errors += 1

        # Update per-tool stats
        if tool_name not in self._metrics.tool_calls_by_name:
            self._metrics.tool_calls_by_name[tool_name] = ToolCallStats(tool_name=tool_name)

        stats = self._metrics.tool_calls_by_name[tool_name]
        stats.call_count += 1
        if success:
            stats.success_count += 1
        else:
            stats.error_count += 1
        stats.total_duration_ms += duration_ms
        stats.total_input_tokens += input_tokens
        stats.total_output_tokens += output_tokens

        # Update timing
        self._metrics.tool_duration_ms += duration_ms

    def record_memory_flush(
        self,
        tokens_before: int,
        tokens_after: int,
        duration_ms: float
    ) -> None:
        """
        Record a memory flush/context compression event

        Args:
            tokens_before: Token count before compression
            tokens_after: Token count after compression
            duration_ms: Compression duration
        """
        if not self.enabled:
            return

        self._metrics.other_duration_ms += duration_ms

        # Add to metadata
        if "memory_flushes" not in self._metrics.metadata:
            self._metrics.metadata["memory_flushes"] = []

        self._metrics.metadata["memory_flushes"].append({
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "tokens_saved": tokens_before - tokens_after,
            "duration_ms": duration_ms,
            "timestamp": time.time()
        })

    def record_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record an error event

        Args:
            error_type: Type of error (e.g., "LLMError", "ToolError")
            error_message: Error message
            context: Additional context
        """
        if not self.enabled:
            return

        if "errors" not in self._metrics.metadata:
            self._metrics.metadata["errors"] = []

        self._metrics.metadata["errors"].append({
            "type": error_type,
            "message": error_message,
            "context": context or {},
            "timestamp": time.time()
        })

    def finalize(self) -> AgentMetrics:
        """
        Finalize metrics collection

        Calculates totals, costs, and prepares final metrics.

        Returns:
            Final AgentMetrics object
        """
        if not self.enabled:
            return self._metrics

        # Calculate total duration
        self._metrics.total_duration_ms = (time.time() - self.start_time) * 1000

        # Calculate "other" duration (total - llm - tools)
        accounted = self._metrics.llm_duration_ms + self._metrics.tool_duration_ms
        self._metrics.other_duration_ms = max(0, self._metrics.total_duration_ms - accounted)

        # Calculate cost
        self._metrics.calculate_cost()

        return self._metrics

    def get_metrics(self) -> AgentMetrics:
        """
        Get current metrics (without finalizing)

        Returns:
            Current metrics snapshot
        """
        return self._metrics

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        # Finalize first
        self.finalize()
        return self._metrics.to_dict()


# Global collector registry
_collector_registry: Dict[str, MetricsCollector] = {}


def get_metrics_collector(conversation_id: str, session_id: Optional[str] = None) -> MetricsCollector:
    """Get or create metrics collector for a conversation"""
    key = f"{conversation_id}:{session_id or 'default'}"
    if key not in _collector_registry:
        _collector_registry[key] = MetricsCollector(conversation_id, session_id)
    return _collector_registry[key]


def remove_metrics_collector(conversation_id: str, session_id: Optional[str] = None) -> Optional[AgentMetrics]:
    """
    Remove and return finalized metrics for a conversation

    Args:
        conversation_id: Conversation identifier
        session_id: Session identifier

    Returns:
        Finalized metrics or None if not found
    """
    key = f"{conversation_id}:{session_id or 'default'}"
    collector = _collector_registry.pop(key, None)
    if collector:
        return collector.finalize()
    return None


__all__ = [
    "MODEL_PRICING",
    "ToolCallStats",
    "AgentMetrics",
    "MetricsCollector",
    "get_metrics_collector",
    "remove_metrics_collector",
]
