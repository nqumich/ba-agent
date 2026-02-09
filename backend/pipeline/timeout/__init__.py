"""
Pipeline Timeout Handler

Synchronous timeout handler for tool execution.
Uses threading (not asyncio) because tools are synchronous.

Design v2.0.1:
- execute_with_timeout(): Execute function with timeout
- create_timeout_result(): Return ToolExecutionResult on timeout
- Raises TimeoutException (not enum value)
"""

import queue
import threading
import time
from typing import Any, Callable, Optional, TypeVar

from backend.models.pipeline import ToolExecutionResult, OutputLevel


T = TypeVar('T')


class TimeoutException(Exception):
    """Exception raised when tool execution times out."""

    def __init__(self, message: str, timeout_ms: int):
        super().__init__(message)
        self.timeout_ms = timeout_ms


class ToolTimeoutHandler:
    """
    Synchronous timeout handler for tool execution.

    Uses threading.Timer (NOT asyncio) because tools are synchronous functions.

    Design v2.0.1: Fixed from async version to support sync tools.
    """

    @staticmethod
    def execute_with_timeout(
        func: Callable[[], T],
        tool_call_id: str,
        timeout_ms: int = 30000,
    ) -> T:
        """
        Execute function with timeout handling (synchronous).

        Uses threading to run the function in a separate thread and waits
        for completion or timeout. This works with synchronous functions.

        Args:
            func: Function to execute (must be sync, no await)
            tool_call_id: Tool call ID for error reporting
            timeout_ms: Timeout in milliseconds

        Returns:
            Result of the function

        Raises:
            TimeoutException: If execution exceeds timeout
            Exception: Any exception from the function itself
        """
        result_queue: queue.Queue = queue.Queue()
        exception_queue: queue.Queue = queue.Queue()

        def target():
            """Execute function and capture result or exception."""
            try:
                result = func()
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)

        # Start worker thread
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

        # Wait for completion or timeout
        thread.join(timeout=timeout_ms / 1000)

        # Check if thread is still running (timeout)
        if thread.is_alive():
            # Thread is still running, timeout occurred
            raise TimeoutException(
                f"Tool execution for {tool_call_id} timed out after {timeout_ms}ms",
                timeout_ms
            )

        # Check for exceptions
        if not exception_queue.empty():
            raise exception_queue.get()

        # Get result
        if result_queue.empty():
            raise TimeoutException(
                f"Tool execution for {tool_call_id} completed without result",
                timeout_ms
            )

        return result_queue.get()

    @staticmethod
    def create_timeout_result(
        tool_call_id: str,
        timeout_ms: int,
        tool_name: str = "",
    ) -> ToolExecutionResult:
        """
        Create a timeout error result.

        Returns a ToolExecutionResult instead of raising an exception.
        Use this when you want to handle timeouts gracefully.

        Args:
            tool_call_id: Tool call ID
            timeout_ms: Timeout that occurred
            tool_name: Name of the tool

        Returns:
            ToolExecutionResult with timeout error
        """
        return ToolExecutionResult.create_timeout(
            tool_call_id=tool_call_id,
            timeout_ms=timeout_ms,
            tool_name=tool_name,
        )

    @staticmethod
    def safe_execute(
        func: Callable[[], Any],
        tool_call_id: str,
        timeout_ms: int = 30000,
        tool_name: str = "",
    ) -> ToolExecutionResult:
        """
        Execute function with timeout, returning ToolExecutionResult.

        This is a convenience method that catches TimeoutException
        and converts it to a ToolExecutionResult.

        Args:
            func: Function to execute
            tool_call_id: Tool call ID
            timeout_ms: Timeout in milliseconds
            tool_name: Name of the tool

        Returns:
            ToolExecutionResult with success or timeout error
        """
        start_time = time.time()

        try:
            result = ToolTimeoutHandler.execute_with_timeout(
                func=func,
                tool_call_id=tool_call_id,
                timeout_ms=timeout_ms,
            )
            duration_ms = (time.time() - start_time) * 1000

            # Convert result to observation
            observation = ToolTimeoutHandler._format_result(result)

            return ToolExecutionResult.create_success(
                tool_call_id=tool_call_id,
                observation=observation,
                tool_name=tool_name,
                duration_ms=duration_ms,
            )

        except TimeoutException as e:
            duration_ms = (time.time() - start_time) * 1000
            return ToolExecutionResult.create_timeout(
                tool_call_id=tool_call_id,
                timeout_ms=timeout_ms,
                tool_name=tool_name,
            ).with_duration(duration_ms)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ToolExecutionResult.create_error(
                tool_call_id=tool_call_id,
                error_message=str(e),
                error_type=type(e).__name__,
                tool_name=tool_name,
            ).with_duration(duration_ms)

    @staticmethod
    def _format_result(result: Any) -> str:
        """Format execution result as observation string."""
        if result is None:
            return "Success (no output)"
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return f"Success: {len(result)} fields returned"
        if isinstance(result, list):
            return f"Success: {len(result)} items returned"
        return f"Success: {type(result).__name__}"


__all__ = [
    "TimeoutException",
    "ToolTimeoutHandler",
]
