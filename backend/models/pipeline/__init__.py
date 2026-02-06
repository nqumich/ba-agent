"""
BA-Agent Information Pipeline Models

This package defines the core data models for the information pipeline architecture,
following the v2.0.1 design specification.

Key Principles:
- LangChain BaseMessage as primary protocol
- Synchronous tool execution
- Single source of truth for tool results (ToolExecutionResult)
- Artifact-based storage for security
"""

from .output_level import OutputLevel
from .cache_policy import ToolCachePolicy
from .tool_request import ToolInvocationRequest
from .tool_result import ToolExecutionResult

__all__ = [
    "OutputLevel",
    "ToolCachePolicy",
    "ToolInvocationRequest",
    "ToolExecutionResult",
]
