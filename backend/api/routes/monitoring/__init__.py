"""
Monitoring API Routes

Provides REST endpoints for querying traces and metrics.

Endpoints:
- GET /api/v1/monitoring/traces/:conversation_id - Get trace for conversation
- GET /api/v1/monitoring/traces/:conversation_id/visualize - Get Mermaid visualization
- GET /api/v1/monitoring/metrics - Query aggregated metrics
- GET /api/v1/monitoring/performance/:conversation_id - Get performance summary
- GET /api/v1/monitoring/conversations - List conversations with traces
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.auth import get_current_user
from backend.monitoring import get_trace_store, get_metrics_store
from backend.monitoring.execution_tracer import ExecutionTracer
from backend.monitoring.metrics_collector import AgentMetrics


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# ===== Response Models =====

class TraceSummary(BaseModel):
    """Summary of a trace"""
    trace_id: str
    conversation_id: str
    session_id: str
    start_time: float
    end_time: Optional[float]
    duration_ms: Optional[float]
    status: str


class ConversationSummary(BaseModel):
    """Summary of a conversation"""
    conversation_id: str
    session_id: str
    start_time: float
    total_duration_ms: float
    trace_count: int
    total_tokens: int
    tool_calls: int


class MetricsSummary(BaseModel):
    """Aggregated metrics summary"""
    total_conversations: int
    total_tokens: int
    total_duration_ms: float
    total_tool_calls: int
    total_cost_usd: float
    avg_tokens_per_conv: float
    avg_duration_ms_per_conv: float


class PerformanceSummary(BaseModel):
    """Performance summary for a conversation"""
    conversation_id: str
    total_duration_ms: float
    llm_duration_ms: float
    tool_duration_ms: float
    other_duration_ms: float
    llm_percentage: float
    tool_percentage: float
    other_percentage: float
    total_tokens: int
    tool_calls_count: int
    estimated_cost_usd: float


# ===== Endpoints =====

@router.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List conversations with traces

    Returns a list of conversations that have monitoring data,
    with summary information about each.
    """
    try:
        trace_store = get_trace_store()
        conversations = trace_store.list_conversations(
            session_id=session_id,
            limit=limit
        )

        return [
            ConversationSummary(
                conversation_id=conv["conversation_id"],
                session_id=conv["session_id"],
                start_time=conv["start_time"],
                total_duration_ms=conv["total_duration_ms"],
                trace_count=conv["trace_count"],
                total_tokens=conv["total_tokens"],
                tool_calls=conv["tool_calls"]
            )
            for conv in conversations
        ]
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@router.get("/traces/{conversation_id}")
async def get_trace(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get execution trace for a conversation

    Returns the complete execution trace including all spans,
    events, and metrics.
    """
    try:
        trace_store = get_trace_store()
        trace = trace_store.load_trace(conversation_id)

        if not trace:
            raise HTTPException(status_code=404, detail=f"No trace found for conversation {conversation_id}")

        return trace
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trace: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get trace: {str(e)}")


@router.get("/traces/{conversation_id}/visualize")
async def visualize_trace(
    conversation_id: str,
    format: str = Query("mermaid", regex="^(mermaid|json)$", description="Visualization format"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get visualization of execution trace

    Returns a Mermaid flowchart or JSON representation
    of the trace for visualization in the dashboard.
    """
    try:
        trace_store = get_trace_store()
        trace = trace_store.load_trace(conversation_id)

        if not trace:
            raise HTTPException(status_code=404, detail=f"No trace found for conversation {conversation_id}")

        if format == "mermaid":
            # Generate Mermaid flowchart
            mermaid = _generate_mermaid_from_trace(trace)
            return {
                "format": "mermaid",
                "conversation_id": conversation_id,
                "mermaid": mermaid
            }
        else:  # json
            return {
                "format": "json",
                "conversation_id": conversation_id,
                "trace": trace
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to visualize trace: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to visualize trace: {str(e)}")


@router.get("/metrics")
async def get_metrics(
    conversation_id: Optional[str] = Query(None, description="Filter by conversation ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    start_time: Optional[float] = Query(None, description="Start time filter (timestamp)"),
    end_time: Optional[float] = Query(None, description="End time filter (timestamp)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Query metrics

    Returns aggregated metrics based on the provided filters.
    If conversation_id is provided, returns metrics for that specific conversation.
    Otherwise, returns aggregated metrics across conversations.
    """
    try:
        metrics_store = get_metrics_store()

        if conversation_id:
            # Get metrics for specific conversation
            metrics = metrics_store.get_metrics(
                conversation_id=conversation_id,
                start_time=start_time,
                end_time=end_time
            )
            return {
                "conversation_id": conversation_id,
                "metrics": metrics
            }
        else:
            # Get aggregated metrics
            aggregated = metrics_store.get_aggregated_metrics(
                session_id=session_id,
                start_time=start_time,
                end_time=end_time
            )
            return aggregated
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/performance/{conversation_id}")
async def get_performance_summary(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get performance summary for a conversation

    Returns breakdown of execution time, token usage,
    and cost estimation.
    """
    try:
        trace_store = get_trace_store()
        trace = trace_store.load_trace(conversation_id)

        if not trace:
            raise HTTPException(status_code=404, detail=f"No trace found for conversation {conversation_id}")

        # Extract metrics from trace
        metrics = trace.get("metrics", {})

        total_duration = metrics.get("total_duration_ms", trace.get("total_duration_ms", 0))
        llm_duration = metrics.get("llm_duration_ms", 0)
        tool_duration = metrics.get("tool_duration_ms", 0)
        other_duration = metrics.get("other_duration_ms", 0)

        # Calculate percentages
        llm_pct = (llm_duration / total_duration * 100) if total_duration > 0 else 0
        tool_pct = (tool_duration / total_duration * 100) if total_duration > 0 else 0
        other_pct = (other_duration / total_duration * 100) if total_duration > 0 else 0

        return PerformanceSummary(
            conversation_id=conversation_id,
            total_duration_ms=total_duration,
            llm_duration_ms=llm_duration,
            tool_duration_ms=tool_duration,
            other_duration_ms=other_duration,
            llm_percentage=llm_pct,
            tool_percentage=tool_pct,
            other_percentage=other_pct,
            total_tokens=metrics.get("total_tokens", 0),
            tool_calls_count=metrics.get("tool_calls_count", 0),
            estimated_cost_usd=metrics.get("estimated_cost_usd", 0)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get performance summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance summary: {str(e)}")


@router.get("/spans/{conversation_id}")
async def get_spans(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all spans for a conversation

    Returns a flattened list of all spans in the trace
    with their hierarchy information.
    """
    try:
        trace_store = get_trace_store()
        trace = trace_store.load_trace(conversation_id)

        if not trace:
            raise HTTPException(status_code=404, detail=f"No trace found for conversation {conversation_id}")

        # Extract spans from trace
        root_span = trace.get("root_span", {})
        spans = _extract_spans_recursive(root_span)

        return {
            "conversation_id": conversation_id,
            "spans": spans,
            "total_spans": len(spans)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get spans: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get spans: {str(e)}")


@router.get("/recent")
async def get_recent_activity(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get recent monitoring activity

    Returns traces and metrics from the last N hours.
    """
    try:
        trace_store = get_trace_store()

        # Calculate time range
        end_time = datetime.now().timestamp()
        start_time = (datetime.now() - timedelta(hours=hours)).timestamp()

        # Query traces by time range
        traces = trace_store.index.query_by_time_range(start_time, end_time)

        return {
            "hours": hours,
            "start_time": start_time,
            "end_time": end_time,
            "trace_count": len(traces),
            "traces": traces[:100]  # Limit to 100 most recent
        }
    except Exception as e:
        logger.error(f"Failed to get recent activity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent activity: {str(e)}")


# ===== Helper Functions =====

def _generate_mermaid_from_trace(trace: Dict[str, Any]) -> str:
    """Generate Mermaid flowchart from trace"""
    root_span = trace.get("root_span", {})

    lines = ["graph TD"]

    # Process spans recursively
    span_stack = [(root_span, None)]  # (span, parent_id)

    while span_stack:
        span, parent_id = span_stack.pop(0)

        span_id = span.get("span_id", "").replace("-", "_").replace(":", "_")
        span_type = span.get("span_type", "unknown")
        span_name = span.get("name", "unnamed")
        duration_ms = span.get("duration_ms", 0)
        status = span.get("status", "unknown")

        # Status indicator
        status_icon = "✓" if status == "success" else "✗" if status == "error" else "○"

        # Duration string
        duration_str = f"{duration_ms:.0f}ms" if duration_ms else "running"

        # Create node label
        if span_type == "agent_invoke":
            label = f"{span_name}\\n{duration_str} {status_icon}"
        else:
            label = f"{span_type}: {span_name}\\n{duration_str} {status_icon}"

        lines.append(f"    {span_id}[\"{label}\"]")

        # Add edge from parent
        if parent_id:
            parent_id_clean = parent_id.replace("-", "_").replace(":", "_")
            lines.append(f"    {parent_id_clean} --> {span_id}")

        # Add children to stack
        for child in span.get("children", []):
            span_stack.append((child, span.get("span_id")))

    return "\n".join(lines)


def _extract_spans_recursive(span: Dict[str, Any], depth: int = 0) -> List[Dict[str, Any]]:
    """Extract spans recursively into a flat list"""
    result = [{
        "span_id": span.get("span_id"),
        "parent_span_id": span.get("parent_span_id"),
        "name": span.get("name"),
        "span_type": span.get("span_type"),
        "depth": depth,
        "duration_ms": span.get("duration_ms"),
        "status": span.get("status"),
        "attributes": span.get("attributes", {}),
        "event_count": len(span.get("events", [])),
    }]

    for child in span.get("children", []):
        result.extend(_extract_spans_recursive(child, depth + 1))

    return result


__all__ = ["router"]
