"""
Pipeline Cache Module

Provides caching utilities for tool execution results.

Design v2.0.1:
- IdempotencyCache: Cross-round caching based on semantic keys
- SummaryCache: LLM summary caching with TTL
"""

from .idempotency_cache import (
    TTLCache,
    CacheEntry,
    IdempotencyCache,
    get_idempotency_cache,
)

__all__ = [
    "TTLCache",
    "CacheEntry",
    "IdempotencyCache",
    "get_idempotency_cache",
]
