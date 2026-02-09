"""
Tool Invocation Request Model

Defines the request format for tool invocation.
This is what the Agent sends when requesting a tool execution.

Design v2.0.1:
- tool_call_id MUST come from LLM (never auto-generated)
- Idempotency key excludes tool_call_id for cross-round caching
- Cache policy defaults to NO_CACHE (safe)
"""

import hashlib
import json
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .output_level import OutputLevel
from .cache_policy import ToolCachePolicy, get_default_cache_policy


class ToolInvocationRequest(BaseModel):
    """
    Tool invocation request - input to tool execution.

    CRITICAL: tool_call_id MUST come from AIMessage.tool_calls[i]["id"]
    DO NOT generate your own ID - this breaks the ReAct loop!

    Flow:
        1. LLM generates tool call with ID
        2. Agent creates ToolInvocationRequest with that ID
        3. Tool executes and returns ToolExecutionResult with same ID
        4. Result converted to ToolMessage(tool_call_id=ID)
        5. LLM receives ToolMessage and associates with original call
    """

    # ========== Core Identification ==========
    tool_call_id: str = Field(
        ...,
        description="Tool call ID from LLM (MUST use AIMessage.tool_calls[i]['id'])"
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool to invoke"
    )
    tool_version: str = Field(
        default="1.0.0",
        description="Version of the tool"
    )

    # ========== Parameters ==========
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool invocation parameters"
    )

    # ========== Output Control ==========
    output_level: Optional[OutputLevel] = Field(
        default=None,
        description="Desired output level (None = auto-detect based on data size)"
    )

    # ========== Execution Context ==========
    timeout_ms: int = Field(
        default=30000,
        description="Timeout in milliseconds (default: 30s)"
    )
    retry_on_timeout: bool = Field(
        default=True,
        description="Whether to retry on timeout"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries"
    )

    # ========== Storage ==========
    storage_dir: Optional[str] = Field(
        default=None,
        description="Directory for artifact storage (for FULL output level)"
    )

    # ========== Security ==========
    caller_id: str = Field(
        default="agent",
        description="ID of the caller (for auditing)"
    )
    permission_level: str = Field(
        default="default",
        description="Permission level for this invocation"
    )

    # ========== Idempotency ==========
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Idempotency key (None = auto-generate from semantic components)"
    )

    # ========== Caching ==========
    cache_policy: ToolCachePolicy = Field(
        default=ToolCachePolicy.NO_CACHE,
        description="Cache policy for this invocation"
    )

    def __post_init__(self) -> None:
        """Post-initialization: set default cache policy if not provided."""
        # Use tool-specific default if explicitly set to NO_CACHE
        if self.cache_policy == ToolCachePolicy.NO_CACHE:
            self.cache_policy = get_default_cache_policy(self.tool_name)

    @field_validator('tool_call_id')
    @classmethod
    def validate_tool_call_id(cls, v: str) -> str:
        """Validate that tool_call_id is not empty."""
        if not v or not v.strip():
            raise ValueError("tool_call_id cannot be empty - must come from LLM")
        return v

    @field_validator('timeout_ms')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is reasonable."""
        if v < 100:
            raise ValueError("timeout_ms must be at least 100ms")
        if v > 600000:  # 10 minutes
            raise ValueError("timeout_ms cannot exceed 600000ms (10 minutes)")
        return v

    def get_or_generate_idempotency_key(self) -> str:
        """
        Generate idempotency key for caching tool results.

        CRITICAL: Key MUST NOT include tool_call_id because:
        - tool_call_id is generated fresh by LLM for each call
        - Same query in different rounds would have different tool_call_ids
        - Including it would prevent cross-round caching

        Key components (semantic, NOT transient):
        - tool_name: Which tool to call
        - tool_version: Version of the tool
        - parameters: Canonicalized (sorted) parameters
        - caller_id: Who is calling
        - permission_level: Permission context
        - EXCLUDED: tool_call_id (transient, LLM-generated)

        Returns:
            Idempotency key as hex string
        """
        # If explicitly provided, use it
        if self.idempotency_key:
            return self.idempotency_key

        # If not cacheable, generate non-caching key
        if not self.cache_policy.is_cacheable:
            return f"uncacheable:{uuid.uuid4()}"

        # Generate semantic key from components
        params_canonical = json.dumps(self.parameters, sort_keys=True, default=str)
        key_string = ":".join([
            self.tool_name,
            self.tool_version,
            params_canonical,
            self.caller_id,
            self.permission_level,
        ])

        return hashlib.md5(key_string.encode('utf-8')).hexdigest()

    def get_output_level(self, data_size_bytes: int = 0) -> OutputLevel:
        """
        Determine output level (use specified or auto-detect).

        Args:
            data_size_bytes: Size of result data (0 = unknown)

        Returns:
            OutputLevel to use
        """
        if self.output_level:
            return self.output_level
        return OutputLevel.from_size(data_size_bytes)

    def should_retry(self, current_retry: int, error_type: Optional[str] = None) -> bool:
        """
        Determine if should retry after failure.

        Args:
            current_retry: Current retry count
            error_type: Type of error (if available)

        Returns:
            True if should retry
        """
        if current_retry >= self.max_retries:
            return False

        if error_type == "timeout" and self.retry_on_timeout:
            return True

        return False

    def with_retry(self) -> "ToolInvocationRequest":
        """Create a copy for retry (same idempotency key)."""
        return self.model_copy()

    def to_debug_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for debugging."""
        data = self.model_dump()
        # Add computed fields
        data['computed_idempotency_key'] = self.get_or_generate_idempotency_key()
        data['cache_is_allowed'] = self.cache_policy.is_cacheable
        data['cache_ttl_seconds'] = self.cache_policy.ttl_seconds
        return data


__all__ = ["ToolInvocationRequest"]
