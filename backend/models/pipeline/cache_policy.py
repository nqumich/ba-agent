"""
Tool Cache Policy Enum

Defines cache behavior for tool execution results.
Provides explicit cache control with safe defaults.

Design v2.0.1: ToolCachePolicy
- Default is NO_CACHE (safe for tools with side effects)
- Opt-in caching for idempotent read operations
- TTL-based expiration for different data types
"""

from enum import Enum
from typing import Dict, Any


class ToolCachePolicy(str, Enum):
    """
    Cache policy for tool execution results.

    IMPORTANT: Default is NO_CACHE (safe default).
    Tools must explicitly declare they are cacheable.

    Policy Levels:
        NO_CACHE: Never cache (default)
            - Tools with side effects (write, execute, delete)
            - Examples: file_write, execute_command, database_write

        CACHEABLE: Indefinitely cacheable
            - Idempotent read operations with stable data
            - Examples: static lookups, configuration reads

        TTL_SHORT: 5 minutes (300 seconds)
            - Frequently changing but cacheable data
            - Examples: current time, session status

        TTL_MEDIUM: 1 hour (3600 seconds)
            - Moderately stable data
            - Examples: user profiles, API rate limits

        TTL_LONG: 24 hours (86400 seconds)
            - Stable reference data
            - Examples: database schemas, API documentation
    """

    NO_CACHE = "no_cache"
    CACHEABLE = "cacheable"
    TTL_SHORT = "ttl_short"
    TTL_MEDIUM = "ttl_medium"
    TTL_LONG = "ttl_long"

    @property
    def is_cacheable(self) -> bool:
        """Whether this policy allows caching."""
        return self != self.NO_CACHE

    @property
    def ttl_seconds(self) -> int:
        """Time-to-live in seconds (0 = indefinite)."""
        return {
            self.NO_CACHE: 0,
            self.CACHEABLE: 0,  # Indefinite
            self.TTL_SHORT: 300,  # 5 minutes
            self.TTL_MEDIUM: 3600,  # 1 hour
            self.TTL_LONG: 86400,  # 24 hours
        }[self]

    @property
    def description(self) -> str:
        """Human-readable description."""
        return {
            self.NO_CACHE: "Never cache - for tools with side effects",
            self.CACHEABLE: "Cache indefinitely - for stable idempotent data",
            self.TTL_SHORT: "Cache for 5 minutes - for frequently changing data",
            self.TTL_MEDIUM: "Cache for 1 hour - for moderately stable data",
            self.TTL_LONG: "Cache for 24 hours - for stable reference data",
        }[self]

    def get_expiration_timestamp(self, created_at: float) -> float:
        """
        Calculate expiration timestamp.

        Args:
            created_at: Unix timestamp when cache entry was created

        Returns:
            Expiration timestamp (0 = never expires)
        """
        if self.ttl_seconds == 0:
            return 0  # Never expires
        return created_at + self.ttl_seconds

    def is_expired(self, created_at: float, current_time: float) -> bool:
        """
        Check if a cache entry has expired.

        Args:
            created_at: Unix timestamp when cache entry was created
            current_time: Current Unix timestamp

        Returns:
            True if expired, False otherwise
        """
        if self.ttl_seconds == 0:
            return False  # Never expires
        return current_time > (created_at + self.ttl_seconds)


# Predefined cache policies for common tool types
TOOL_CACHE_PRESETS: Dict[str, ToolCachePolicy] = {
    # Read operations (cacheable)
    "web_search": ToolCachePolicy.TTL_MEDIUM,
    "query_database": ToolCachePolicy.TTL_SHORT,
    "file_reader": ToolCachePolicy.CACHEABLE,
    "vector_search": ToolCachePolicy.TTL_SHORT,
    "api_get": ToolCachePolicy.TTL_MEDIUM,

    # Write operations (never cache)
    "file_write": ToolCachePolicy.NO_CACHE,
    "execute_command": ToolCachePolicy.NO_CACHE,
    "database_write": ToolCachePolicy.NO_CACHE,
    "api_post": ToolCachePolicy.NO_CACHE,
    "api_delete": ToolCachePolicy.NO_CACHE,

    # Analysis operations (short cache)
    "analyze_data": ToolCachePolicy.TTL_SHORT,
    "generate_report": ToolCachePolicy.TTL_SHORT,
}


def get_default_cache_policy(tool_name: str) -> ToolCachePolicy:
    """
    Get default cache policy for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Default cache policy (NO_CACHE if not found in presets)
    """
    return TOOL_CACHE_PRESETS.get(tool_name, ToolCachePolicy.NO_CACHE)


__all__ = [
    "ToolCachePolicy",
    "TOOL_CACHE_PRESETS",
    "get_default_cache_policy",
]
