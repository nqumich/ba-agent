"""
Pipeline Context Module

Provides context management for conversation history.

Design v2.0.1:
- AdvancedContextManager: LLM-based summarization
- Synchronous compression (main thread + background thread)
- TRUNCATE/EXTRACT compression modes
"""

from .context_manager import (
    CompressionMode,
    MessagePriority,
    AdvancedContextManager,
    get_context_manager,
)

__all__ = [
    "CompressionMode",
    "MessagePriority",
    "AdvancedContextManager",
    "get_context_manager",
]
