"""
Tool Execution Result Model

SINGLE SOURCE OF TRUTH for tool execution results.
v2.0.1: ToolResultMessage has been removed and merged into this class.

Design Principles:
- One result model for all tool outputs
- LangChain ToolMessage as primary conversion target
- Artifact-based storage for security (no real paths exposed)
- Comprehensive telemetry for observability
"""

import hashlib
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_serializer, model_validator

from .output_level import OutputLevel
from .cache_policy import ToolCachePolicy


class ToolExecutionResult(BaseModel):
    """
    Tool execution result - SINGLE SOURCE OF TRUTH.

    v2.0.1: Merged ToolResultMessage functionality into this class.
    All tool outputs MUST use this format.

    Core Fields:
        tool_call_id: MUST come from AIMessage.tool_calls[i]["id"]
        observation: ReAct Observation string (what LLM sees)
        output_level: Verbosity level (BRIEF/STANDARD/FULL)

    Security Fields:
        _data_file: Private real path (NEVER expose to LLM)
        artifact_id: Public safe identifier for LLM

    Telemetry Fields:
        duration_ms: Execution time
        retry_count: Number of retries
        success: Execution status
    """

    # ========== Core Identification ==========
    tool_call_id: str = Field(
        ...,
        description="Tool call ID from LLM (MUST match AIMessage.tool_calls[i]['id'])"
    )
    tool_name: str = Field(
        default="",
        description="Name of the tool that was executed"
    )

    # ========== ReAct Observation (Semantic) ==========
    observation: str = Field(
        default="",
        description="ReAct Observation string - what the LLM sees"
    )
    output_level: OutputLevel = Field(
        default=OutputLevel.STANDARD,
        description="Verbosity level of the observation"
    )

    # ========== Security: Artifact Storage ==========
    # NOTE: Pydantic doesn't allow fields with leading underscores
    # This field is excluded from serialization and should NEVER be exposed to LLM
    data_file: Optional[str] = Field(
        default=None,
        description="PRIVATE: Actual filesystem path (NEVER expose to LLM)",
        exclude=True  # Exclude from serialization
    )
    artifact_id: Optional[str] = Field(
        default=None,
        description="PUBLIC: Safe identifier for LLM (not a real path)"
    )
    data_size_bytes: int = Field(
        default=0,
        description="Size of stored data in bytes"
    )
    data_hash: Optional[str] = Field(
        default=None,
        description="Hash of stored data for verification"
    )
    data_summary: Optional[str] = Field(
        default=None,
        description="Human-readable summary of stored data"
    )

    # ========== Execution Telemetry ==========
    duration_ms: float = Field(
        default=0.0,
        description="Execution time in milliseconds"
    )
    retry_count: int = Field(
        default=0,
        description="Number of retries performed"
    )
    last_error: Optional[str] = Field(
        default=None,
        description="Last error message (if any)"
    )

    # ========== Status ==========
    success: bool = Field(
        default=True,
        description="Whether execution succeeded"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code (if failed)"
    )
    error_type: Optional[str] = Field(
        default=None,
        description="Error type (e.g., timeout, validation)"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Detailed error message"
    )

    # ========== Caching ==========
    cache_policy: ToolCachePolicy = Field(
        default=ToolCachePolicy.NO_CACHE,
        description="Cache policy for this result"
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Idempotency key for caching (without tool_call_id)"
    )

    # ========== Timestamps ==========
    created_at: float = Field(
        default_factory=time.time,
        description="Unix timestamp when result was created"
    )
    expires_at: float = Field(
        default=0.0,
        description="Unix timestamp when cache expires (0 = never)"
    )

    # ========== Metadata ==========
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    # ========== Factory Methods ==========

    @classmethod
    def create_success(
        cls,
        tool_call_id: str,
        observation: str,
        tool_name: str = "",
        output_level: OutputLevel = OutputLevel.STANDARD,
        duration_ms: float = 0.0,
        **kwargs
    ) -> "ToolExecutionResult":
        """
        Create a successful execution result.

        Args:
            tool_call_id: Tool call ID from LLM
            observation: ReAct Observation string
            tool_name: Name of the tool
            output_level: Verbosity level
            duration_ms: Execution time
            **kwargs: Additional fields

        Returns:
            ToolExecutionResult instance
        """
        return cls(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            observation=observation,
            output_level=output_level,
            success=True,
            duration_ms=duration_ms,
            **kwargs
        )

    @classmethod
    def create_error(
        cls,
        tool_call_id: str,
        error_message: str,
        error_type: str = "unknown",
        error_code: Optional[str] = None,
        tool_name: str = "",
        **kwargs
    ) -> "ToolExecutionResult":
        """
        Create a failed execution result.

        Args:
            tool_call_id: Tool call ID from LLM
            error_message: Error message
            error_type: Type of error
            error_code: Error code
            tool_name: Name of the tool
            **kwargs: Additional fields

        Returns:
            ToolExecutionResult instance
        """
        return cls(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            observation=f"Error: {error_message}",
            success=False,
            error_type=error_type,
            error_code=error_code,
            error_message=error_message,
            last_error=error_message,
            **kwargs
        )

    @classmethod
    def create_timeout(
        cls,
        tool_call_id: str,
        timeout_ms: int,
        tool_name: str = "",
        **kwargs
    ) -> "ToolExecutionResult":
        """
        Create a timeout error result.

        Args:
            tool_call_id: Tool call ID from LLM
            timeout_ms: Timeout duration in milliseconds
            tool_name: Name of the tool
            **kwargs: Additional fields

        Returns:
            ToolExecutionResult instance
        """
        return cls.create_error(
            tool_call_id=tool_call_id,
            error_message=f"Tool execution timed out after {timeout_ms}ms",
            error_type="timeout",
            error_code="TIMEOUT",
            tool_name=tool_name,
            **kwargs
        )

    @classmethod
    def from_raw_data(
        cls,
        tool_call_id: str,
        raw_data: Any,
        output_level: OutputLevel,
        tool_name: str = "",
        storage_dir: Optional[str] = None,
        cache_policy: ToolCachePolicy = ToolCachePolicy.NO_CACHE,
        **kwargs
    ) -> "ToolExecutionResult":
        """
        Create result from raw data with specified output level.

        Handles:
        - BRIEF: Just summary
        - STANDARD: Formatted key-value pairs
        - FULL: Full JSON or artifact storage

        Args:
            tool_call_id: Tool call ID from LLM
            raw_data: Raw data to format
            output_level: Desired output level
            tool_name: Name of the tool
            storage_dir: Directory for artifact storage (for FULL level)
            cache_policy: Cache policy
            **kwargs: Additional fields

        Returns:
            ToolExecutionResult instance
        """
        # Serialize raw_data to get size
        data_json = json.dumps(raw_data, ensure_ascii=False, default=str)
        data_size = len(data_json.encode('utf-8'))
        data_hash = hashlib.md5(data_json.encode()).hexdigest()

        # Generate observation based on output level
        if output_level == OutputLevel.BRIEF:
            observation = cls._format_brief(raw_data)
        elif output_level == OutputLevel.STANDARD:
            observation = cls._format_standard(raw_data)
        else:  # FULL
            if data_size >= 1_000_000 and storage_dir:
                # Use artifact storage for large data
                observation, artifact_id = cls._store_as_artifact(
                    raw_data, storage_dir, tool_name
                )
                return cls(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    observation=observation,
                    output_level=output_level,
                    artifact_id=artifact_id,
                    data_size_bytes=data_size,
                    data_hash=data_hash,
                    cache_policy=cache_policy,
                    **kwargs
                )
            else:
                observation = cls._format_full(raw_data)

        return cls(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            observation=observation,
            output_level=output_level,
            data_size_bytes=data_size,
            data_hash=data_hash,
            cache_policy=cache_policy,
            **kwargs
        )

    # ========== Conversion Methods ==========

    def to_tool_message(self) -> "ToolMessage":
        """
        Convert to LangChain ToolMessage (PRIMARY METHOD).

        This is the main conversion method for returning results to the LLM.
        Uses the observation field as content.

        Returns:
            LangChain ToolMessage instance
        """
        from langchain_core.messages import ToolMessage

        return ToolMessage(
            content=self.observation,
            tool_call_id=self.tool_call_id
        )

    def to_llm_message(self) -> Dict[str, Any]:
        """
        Convert to Claude Code format (DEPRECATED - research only).

        This method is kept for debugging/research purposes.
        Use to_tool_message() for production.

        Returns:
            Dictionary in Claude Code message format
        """
        return {
            "role": "tool",
            "tool_use_id": self.tool_call_id,
            "content": self.observation,
            "is_error": not self.success,
        }

    def to_debug_dict(self) -> Dict[str, Any]:
        """
        Convert to debug dictionary (includes all fields).

        Returns:
            Dictionary with all fields for debugging
        """
        return self.model_dump()

    # ========== Formatting Methods ==========

    @staticmethod
    def _format_brief(data: Any) -> str:
        """Format data as brief observation."""
        if isinstance(data, dict):
            if "success" in data:
                return "Success" if data["success"] else f"Error: {data.get('error', 'Unknown')}"
            if "count" in data:
                return f"Found {data['count']} items"
            if len(data) <= 3:
                return f"Result: {', '.join(f'{k}={v}' for k, v in data.items())}"
            return f"Result with {len(data)} fields"
        elif isinstance(data, list):
            return f"List of {len(data)} items"
        elif isinstance(data, str):
            return data[:100] if len(data) > 100 else data
        elif data is None:
            return "No data"
        return str(data)[:100]

    @staticmethod
    def _format_standard(data: Any) -> str:
        """Format data as standard observation."""
        if isinstance(data, dict):
            lines = [f"Result ({len(data)} fields):"]
            for k, v in list(data.items())[:10]:
                v_str = str(v)[:100]
                lines.append(f"  {k}: {v_str}")
            if len(data) > 10:
                lines.append(f"  ... and {len(data) - 10} more fields")
            return "\n".join(lines)
        elif isinstance(data, list):
            if len(data) == 0:
                return "Empty list"
            first_item = json.dumps(data[0], ensure_ascii=False)[:200]
            return f"List of {len(data)} items\nFirst item: {first_item}"
        else:
            return str(data)[:1000]

    @staticmethod
    def _format_full(data: Any) -> str:
        """Format data as full observation."""
        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def _store_as_artifact(
        data: Any,
        storage_dir: str,
        tool_name: str
    ) -> tuple[str, str]:
        """
        Store data as artifact and return observation with artifact_id.

        Args:
            data: Data to store
            storage_dir: Storage directory path
            tool_name: Tool name for prefix

        Returns:
            Tuple of (observation, artifact_id)
        """
        storage_path = Path(storage_dir)
        storage_path.mkdir(parents=True, exist_ok=True)

        # Generate artifact_id (not a real path!)
        data_hash = hashlib.md5(json.dumps(data, ensure_ascii=False).encode()).hexdigest()
        artifact_id = f"artifact_{data_hash[:16]}"
        filename = f"{artifact_id}.json"

        # Store data
        file_path = storage_path / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Generate summary
        if isinstance(data, list):
            summary = f"List with {len(data)} items"
            if len(data) > 0:
                first_keys = list(data[0].keys()) if isinstance(data[0], dict) else ["scalar"]
                summary += f". First item keys: {first_keys}"
        elif isinstance(data, dict):
            summary = f"Dict with {len(data)} keys: {list(data.keys())[:10]}"
        else:
            summary = type(data).__name__

        # Generate observation
        observation = f"""Data stored as artifact: {artifact_id}

Large dataset available for subsequent tool access.

To access this data, reference the artifact_id in your next tool call.
The system will securely retrieve the data for you.

Data summary: {summary}"""

        return observation, artifact_id

    # ========== Utility Methods ==========

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check if this result has expired."""
        if self.expires_at == 0:
            return False
        if current_time is None:
            current_time = time.time()
        return current_time > self.expires_at

    def get_cache_age_seconds(self, current_time: Optional[float] = None) -> float:
        """Get age of this cached result in seconds."""
        if current_time is None:
            current_time = time.time()
        return current_time - self.created_at

    def with_retry(self, max_retries: int = 3) -> "ToolExecutionResult":
        """Create a copy with incremented retry count."""
        return self.model_copy(update={"retry_count": self.retry_count + 1})

    def with_duration(self, duration_ms: float) -> "ToolExecutionResult":
        """Create a copy with duration set."""
        return self.model_copy(update={"duration_ms": duration_ms})

    def to_observation(self) -> str:
        """Get the ReAct observation string."""
        return self.observation


__all__ = ["ToolExecutionResult"]
