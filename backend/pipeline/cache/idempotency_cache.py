"""
Idempotency Cache for Tool Execution Results

Design v2.0.1:
- Cache key based on semantic components (NOT tool_call_id)
- TTL support with automatic expiration
- Thread-safe operations
- Cross-round caching (same query in different rounds = cached result)
"""

import hashlib
import json
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

from backend.models.pipeline import ToolExecutionResult, ToolCachePolicy


K = TypeVar('K')
V = TypeVar('V')


class CacheEntry(BaseModel):
    """Cache entry with TTL support."""
    key: str
    value: Any  # ToolExecutionResult
    created_at: float
    expires_at: float = 0.0  # 0 = never expires
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at == 0:
            return False
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        """Get age of this entry in seconds."""
        return time.time() - self.created_at


class TTLCache(Generic[K, V], ABC):
    """
    Generic TTL Cache base class.

    Features:
    - Generic key-value pair support
    - Automatic expiration cleanup
    - Thread-safe operations
    - Maximum entry limit
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_seconds: int = 3600,
    ):
        """
        Initialize TTL cache.

        Args:
            max_size: Maximum number of entries
            default_ttl_seconds: Default TTL in seconds (0 = no expiration)
        """
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        self._cache: Dict[K, CacheEntry] = {}
        self._lock = threading.RLock()

    def get(self, key: K) -> Optional[V]:
        """Get value from cache, returns None if not found or expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            if entry.is_expired:
                # Remove expired entry
                del self._cache[key]
                return None

            # Update hit count
            entry.hit_count += 1
            return entry.value

    def set(self, key: K, value: V, ttl_seconds: Optional[int] = None) -> None:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: TTL in seconds (None = use default)
        """
        with self._lock:
            # Enforce max size
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_oldest()

            # Calculate expiration
            ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
            expires_at = time.time() + ttl if ttl > 0 else 0

            # Create or update entry
            if key in self._cache:
                # Update existing entry, preserve hit count
                entry = self._cache[key]
                entry.value = value
                entry.expires_at = expires_at
            else:
                # Create new entry
                self._cache[key] = CacheEntry(
                    key=str(key),
                    value=value,
                    created_at=time.time(),
                    expires_at=expires_at,
                    hit_count=0,
                )

    def delete(self, key: K) -> bool:
        """Delete entry from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries, returns count of removed entries."""
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items()
                if v.is_expired
            ]
            for k in expired_keys:
                del self._cache[k]
            return len(expired_keys)

    def _evict_oldest(self) -> None:
        """Evict the oldest entry (LRU)."""
        if not self._cache:
            return

        # Find oldest entry (by created_at)
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at
        )
        del self._cache[oldest_key]

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            now = time.time()
            total_hits = sum(e.hit_count for e in self._cache.values())

            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "total_hits": total_hits,
                "expired_count": sum(1 for e in self._cache.values() if e.is_expired),
                "entries": [
                    {
                        "key": e.key[:50] + "..." if len(e.key) > 50 else e.key,
                        "created_at": datetime.fromtimestamp(e.created_at).isoformat(),
                        "age_seconds": e.age_seconds,
                        "hit_count": e.hit_count,
                    }
                    for e in sorted(self._cache.values(), key=lambda x: x.created_at, reverse=True)[:10]
                ]
            }


class IdempotencyCache(TTLCache[str, ToolExecutionResult]):
    """
    Cache for tool execution results based on semantic idempotency keys.

    Key Design (v2.0.1):
    - Key MUST be based on semantic components, NOT transient IDs
    - Semantic components: tool_name, tool_version, parameters (canonicalized)
    - EXCLUDED: tool_call_id (transient, LLM-generated each round)

    This allows cross-round caching:
    Round 1: query_database("SELECT * FROM sales") → tool_call_id="call_abc123"
    Round 2: query_database("SELECT * FROM sales") → tool_call_id="call_def456"
    Same idempotency key → cache hit!
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_seconds: int = 3600,
    ):
        """
        Initialize idempotency cache.

        Args:
            max_size: Maximum number of cached results
            default_ttl_seconds: Default TTL for cacheable results
        """
        super().__init__(max_size=max_size, default_ttl_seconds=default_ttl_seconds)

    def get_idempotency_key(
        self,
        tool_name: str,
        tool_version: str,
        parameters: Dict[str, Any],
        caller_id: str = "agent",
        permission_level: str = "default",
    ) -> str:
        """
        Generate idempotency key from semantic components.

        CRITICAL: Do NOT include tool_call_id!
        tool_call_id is generated fresh each round by LLM,
        so including it would prevent cross-round caching.

        Args:
            tool_name: Name of the tool
            tool_version: Version of the tool
            parameters: Tool parameters (will be canonicalized)
            caller_id: ID of the caller
            permission_level: Permission level

        Returns:
            Idempotency key as hex string
        """
        # Canonicalize parameters (sort keys for consistent hash)
        params_canonical = json.dumps(parameters, sort_keys=True, default=str)

        # Build key string from semantic components only
        key_string = ":".join([
            tool_name,
            tool_version,
            params_canonical,
            caller_id,
            permission_level,
        ])

        # Hash for compact key
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()

    def get_or_compute(
        self,
        tool_name: str,
        tool_version: str,
        parameters: Dict[str, Any],
        compute_fn: Callable[[], ToolExecutionResult],
        cache_policy: ToolCachePolicy,
        caller_id: str = "agent",
        permission_level: str = "default",
    ) -> ToolExecutionResult:
        """
        Get cached result or compute using provided function.

        Args:
            tool_name: Name of the tool
            tool_version: Version of the tool
            parameters: Tool parameters
            compute_fn: Function to compute result if not cached
            cache_policy: Cache policy for this result
            caller_id: ID of the caller
            permission_level: Permission level

        Returns:
            Cached or computed result
        """
        # Check if caching is allowed
        if not cache_policy.is_cacheable:
            # Not cacheable, compute directly
            return compute_fn()

        # Generate idempotency key
        key = self.get_idempotency_key(
            tool_name=tool_name,
            tool_version=tool_version,
            parameters=parameters,
            caller_id=caller_id,
            permission_level=permission_level,
        )

        # Try to get from cache
        cached = self.get(key)
        if cached is not None:
            # Cache hit - return cached result
            # Update metadata to indicate cache hit
            cached.metadata = cached.metadata or {}
            cached.metadata["cache_hit"] = True
            cached.metadata["cached_at"] = time.time()
            return cached

        # Cache miss - compute and store
        result = compute_fn()

        # Only cache successful results
        if result.success:
            # Use TTL from cache policy
            ttl = cache_policy.ttl_seconds
            self.set(key, result, ttl_seconds=ttl)

            # Add metadata to indicate it was computed
            result.metadata = result.metadata or {}
            result.metadata["cache_hit"] = False

        return result

    def invalidate(
        self,
        tool_name: str,
        tool_version: str,
        parameters: Dict[str, Any],
        caller_id: str = "agent",
        permission_level: str = "default",
    ) -> bool:
        """
        Invalidate a cached result.

        Args:
            tool_name: Name of the tool
            tool_version: Version of the tool
            parameters: Tool parameters
            caller_id: ID of the caller
            permission_level: Permission level

        Returns:
            True if entry was found and removed
        """
        key = self.get_idempotency_key(
            tool_name=tool_name,
            tool_version=tool_version,
            parameters=parameters,
            caller_id=caller_id,
            permission_level=permission_level,
        )
        return self.delete(key)

    def invalidate_by_tool(self, tool_name: str) -> int:
        """
        Invalidate all cached results for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            # Find all keys that start with the tool's hash prefix
            # Since we use MD5, we need to check by recomputing the prefix
            # This is expensive, so in practice we'd want an index
            # For now, we'll do a simple scan

            count = 0
            to_delete = []

            for key_str, entry in self._cache.items():
                # Check if this entry belongs to the tool
                # We stored the tool_name in the value (ToolExecutionResult)
                if isinstance(entry.value, ToolExecutionResult):
                    if entry.value.tool_name == tool_name:
                        to_delete.append(key_str)

            for key_str in to_delete:
                del self._cache[key_str]
                count += 1

            return count


# Global singleton instance
_global_idempotency_cache: Optional[IdempotencyCache] = None


def get_idempotency_cache() -> IdempotencyCache:
    """Get global idempotency cache instance."""
    global _global_idempotency_cache
    if _global_idempotency_cache is None:
        _global_idempotency_cache = IdempotencyCache()
    return _global_idempotency_cache


__all__ = [
    "TTLCache",
    "CacheEntry",
    "IdempotencyCache",
    "get_idempotency_cache",
]
