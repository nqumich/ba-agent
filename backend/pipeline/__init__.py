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
    - Cache: Idempotency cache for tool results
    - Token: Dynamic token counter
    - Context: Advanced context manager
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

# Phase 5: Advanced features
from backend.pipeline.cache import IdempotencyCache, get_idempotency_cache
from backend.pipeline.token import DynamicTokenCounter, get_token_counter
from backend.pipeline.context import AdvancedContextManager, CompressionMode, get_context_manager

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

    # Cache (Phase 5)
    "IdempotencyCache",
    "get_idempotency_cache",

    # Token (Phase 5)
    "DynamicTokenCounter",
    "get_token_counter",

    # Context (Phase 5)
    "AdvancedContextManager",
    "CompressionMode",
    "get_context_manager",
]
