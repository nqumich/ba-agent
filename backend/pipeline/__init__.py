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
    - FileStore: Unified file storage management (lazy import to avoid circular dependency)
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

# FileStore Integration (lazy import to avoid circular dependency)
def _get_file_store():
    """Lazy import FileStore to avoid circular dependency"""
    from backend.filestore import FileStore
    return FileStore


def _get_file_store_factory():
    """Lazy import get_file_store to avoid circular dependency"""
    from backend.filestore.factory import get_file_store
    return get_file_store


def _get_filestore_integration():
    """Lazy import FileStorePipelineIntegration"""
    from backend.pipeline.filestore_integration import FileStorePipelineIntegration
    return FileStorePipelineIntegration


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

    # FileStore (lazy - use these properties/functions instead)
    "FileStore",           # Use: from backend.filestore import FileStore
    "get_file_store",      # Use: from backend.filestore.factory import get_file_store
]
