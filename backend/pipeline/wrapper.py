"""
Pipeline Tool Wrapper

Wraps LangChain tools to use the new information pipeline models.
This provides timeout handling, artifact storage, and unified result format.

Usage:
    # Wrap existing tools
    wrapped_tool = PipelineToolWrapper(
        tool=original_tool,
        storage_dir="/tmp/artifacts"
    )

    # Or use decorator
    @pipeline_tool
    def my_tool(params: dict) -> dict:
        return {"result": "data"}
"""

import time
from typing import Any, Callable, Dict, Optional, Union

from langchain_core.tools import BaseTool, StructuredTool, Tool
from langchain_core.messages import ToolMessage

from backend.models.pipeline import (
    ToolInvocationRequest,
    ToolExecutionResult,
    OutputLevel,
    ToolCachePolicy,
)
from backend.pipeline.timeout import ToolTimeoutHandler
from backend.pipeline.storage import DataStorage, get_data_storage


class PipelineToolWrapper:
    """
    Wrapper for LangChain tools to use pipeline models.

    Intercepts tool calls and wraps them with:
    1. ToolInvocationRequest creation
    2. Timeout handling via ToolTimeoutHandler
    3. Artifact storage for large results
    4. ToolExecutionResult conversion to ToolMessage
    """

    def __init__(
        self,
        tool: BaseTool,
        storage_dir: Optional[str] = None,
        default_timeout_ms: int = 30000,
        default_cache_policy: ToolCachePolicy = ToolCachePolicy.NO_CACHE,
    ):
        """
        Initialize wrapper.

        Args:
            tool: Original LangChain tool to wrap
            storage_dir: Directory for artifact storage (None = use default)
            default_timeout_ms: Default timeout for tool execution
            default_cache_policy: Default cache policy
        """
        self.tool = tool
        self.storage = get_data_storage() if storage_dir is None else DataStorage(storage_dir)
        self.default_timeout_ms = default_timeout_ms
        self.default_cache_policy = default_cache_policy

    def invoke(
        self,
        tool_input: Union[str, Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None,
        tool_call_id: Optional[str] = None,
    ) -> ToolMessage:
        """
        Invoke the wrapped tool using pipeline models.

        Args:
            tool_input: Tool input (string or dict)
            config: Optional configuration
            tool_call_id: Tool call ID from LLM (REQUIRED for pipeline!)

        Returns:
            ToolMessage with observation

        Raises:
            ValueError: If tool_call_id is not provided
        """
        if tool_call_id is None:
            raise ValueError("tool_call_id is REQUIRED for pipeline tool execution")

        # Normalize input to dict
        if isinstance(tool_input, str):
            parameters = {"input": tool_input}
        else:
            parameters = dict(tool_input)

        # Create invocation request
        request = ToolInvocationRequest(
            tool_call_id=tool_call_id,
            tool_name=self.tool.name,
            parameters=parameters,
            timeout_ms=self.default_timeout_ms,
            storage_dir=str(self.storage.storage_dir),
            cache_policy=self.default_cache_policy,
        )

        # Execute with timeout
        start_time = time.time()
        result = self._execute_with_pipeline(request)
        duration_ms = (time.time() - start_time) * 1000

        # Update duration
        result = result.with_duration(duration_ms)

        # Convert to ToolMessage
        return result.to_tool_message()

    def _execute_with_pipeline(self, request: ToolInvocationRequest) -> ToolExecutionResult:
        """
        Execute tool with pipeline handling.

        Args:
            request: Tool invocation request

        Returns:
            Tool execution result
        """
        try:
            # Execute with timeout
            raw_result = ToolTimeoutHandler.execute_with_timeout(
                func=lambda: self.tool._run(**request.parameters),
                tool_call_id=request.tool_call_id,
                timeout_ms=request.timeout_ms,
            )

            # Convert to ToolExecutionResult
            output_level = request.get_output_level()
            return ToolExecutionResult.from_raw_data(
                tool_call_id=request.tool_call_id,
                raw_data=raw_result,
                output_level=output_level,
                tool_name=request.tool_name,
                storage_dir=request.storage_dir,
                cache_policy=request.cache_policy,
            )

        except Exception as e:
            # Return error result
            return ToolExecutionResult.create_error(
                tool_call_id=request.tool_call_id,
                error_message=str(e),
                error_type=type(e).__name__,
                tool_name=request.tool_name,
            )

    def to_langchain_tool(self) -> BaseTool:
        """
        Convert wrapped tool back to LangChain format.

        Returns a StructuredTool that uses this wrapper's invoke method.
        """
        def wrapped_invoke(input: Union[str, Dict[str, Any]], **kwargs) -> str:
            """Inner invoke that returns string (for LangChain compatibility)."""
            tool_call_id = kwargs.pop("tool_call_id", None)
            if tool_call_id is None:
                tool_call_id = f"call_{self.tool.name}_{time.time_ns()}"

            tool_msg = self.invoke(input, tool_call_id=tool_call_id)
            return tool_msg.content

        if isinstance(self.tool, StructuredTool):
            return StructuredTool.from_function(
                func=wrapped_invoke,
                name=self.tool.name,
                description=self.tool.description,
                args_schema=self.tool.args_schema,
            )
        else:
            return Tool(
                name=self.tool.name,
                description=self.tool.description,
                func=wrapped_invoke,
            )


def wrap_tool(
    tool: BaseTool,
    storage_dir: Optional[str] = None,
    timeout_ms: int = 30000,
) -> BaseTool:
    """
    Convenience function to wrap a tool with pipeline models.

    Args:
        tool: LangChain tool to wrap
        storage_dir: Directory for artifact storage
        timeout_ms: Default timeout

    Returns:
        Wrapped LangChain tool
    """
    wrapper = PipelineToolWrapper(
        tool=tool,
        storage_dir=storage_dir,
        default_timeout_ms=timeout_ms,
    )
    return wrapper.to_langchain_tool()


def wrap_tools(
    tools: list[BaseTool],
    storage_dir: Optional[str] = None,
    timeout_ms: int = 30000,
) -> list[BaseTool]:
    """
    Wrap multiple tools with pipeline models.

    Args:
        tools: List of LangChain tools to wrap
        storage_dir: Directory for artifact storage
        timeout_ms: Default timeout

    Returns:
        List of wrapped LangChain tools
    """
    return [wrap_tool(tool, storage_dir, timeout_ms) for tool in tools]


__all__ = [
    "PipelineToolWrapper",
    "wrap_tool",
    "wrap_tools",
]
