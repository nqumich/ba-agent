"""
BA-Agent Information Pipeline

This package provides the information pipeline architecture for tool execution,
following the v2.0.1 design specification.

Architecture:
    ToolInvocationRequest (Agent → Tool)
        ↓
    ToolTimeoutHandler (execution with timeout)
        ↓
    ToolExecutionResult (Tool → Agent)
        ↓
    ToolMessage (Agent → LLM)

Components:
    - Models: ToolInvocationRequest, ToolExecutionResult, OutputLevel, ToolCachePolicy
    - Timeout: Synchronous timeout handler for tools
    - Storage: Artifact-based file storage with security
    - Wrapper: Tool wrapper for LangChain integration
    - Cache: Idempotency cache for tool results (TODO)
    - Token: Dynamic token counter (TODO)
    - Context: Advanced context manager (TODO)
"""

# Models
from backend.models.pipeline import (
    OutputLevel,
    ToolCachePolicy,
    ToolInvocationRequest,
    ToolExecutionResult,
)

# Pipeline components
from backend.pipeline.timeout import ToolTimeoutHandler, TimeoutException
from backend.pipeline.storage import DataStorage, get_data_storage, ArtifactMetadata
from backend.pipeline.wrapper import PipelineToolWrapper, wrap_tool, wrap_tools

__all__ = [
    # Models
    "OutputLevel",
    "ToolCachePolicy",
    "ToolInvocationRequest",
    "ToolExecutionResult",

    # Timeout
    "ToolTimeoutHandler",
    "TimeoutException",

    # Storage
    "DataStorage",
    "get_data_storage",
    "ArtifactMetadata",

    # Wrapper
    "PipelineToolWrapper",
    "wrap_tool",
    "wrap_tools",
]
