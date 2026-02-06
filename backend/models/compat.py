"""
Compatibility Layer: Old and New Tool Output Models

Provides adapters between legacy tool output formats and the new pipeline models.
This allows gradual migration without breaking existing tools.

Usage:
    # Convert old ToolOutput to new ToolExecutionResult
    new_result = tool_output_to_execution_result(old_tool_output)

    # Convert old ResponseFormat to new OutputLevel
    new_level = response_format_to_output_level(ResponseFormat.STANDARD)
"""

from typing import Optional, Any

# Old models (legacy)
try:
    from backend.models.tool_output import ResponseFormat, ToolOutput, ToolTelemetry
    OLD_MODELS_AVAILABLE = True
except ImportError:
    OLD_MODELS_AVAILABLE = False

    # Create stubs for type hints if old models not available
    class ResponseFormat:  # type: ignore
        CONCISE = "concise"
        STANDARD = "standard"
        DETAILED = "detailed"
        RAW = "raw"

    class ToolOutput:  # type: ignore
        pass

    class ToolTelemetry:  # type: ignore
        pass

# New models (pipeline)
from backend.models.pipeline import OutputLevel, ToolExecutionResult, ToolCachePolicy


def response_format_to_output_level(response_format: str) -> OutputLevel:
    """
    Convert old ResponseFormat to new OutputLevel.

    Mapping:
        CONCISE -> BRIEF
        STANDARD -> STANDARD
        DETAILED -> FULL
        RAW -> FULL

    Args:
        response_format: Old ResponseFormat value

    Returns:
        New OutputLevel
    """
    mapping = {
        "concise": OutputLevel.BRIEF,
        "standard": OutputLevel.STANDARD,
        "detailed": OutputLevel.FULL,
        "raw": OutputLevel.FULL,
    }
    return mapping.get(response_format, OutputLevel.STANDARD)


def output_level_to_response_format(output_level: OutputLevel) -> str:
    """
    Convert new OutputLevel to old ResponseFormat.

    Mapping:
        BRIEF -> CONCISE
        STANDARD -> STANDARD
        FULL -> DETAILED

    Args:
        output_level: New OutputLevel

    Returns:
        Old ResponseFormat value
    """
    mapping = {
        OutputLevel.BRIEF: "concise",
        OutputLevel.STANDARD: "standard",
        OutputLevel.FULL: "detailed",
    }
    return mapping.get(output_level, "standard")


def tool_output_to_execution_result(
    tool_output: Any,
    tool_call_id: str,
) -> ToolExecutionResult:
    """
    Convert old ToolOutput to new ToolExecutionResult.

    Args:
        tool_output: Old ToolOutput instance
        tool_call_id: Tool call ID from LLM

    Returns:
        New ToolExecutionResult instance
    """
    if not OLD_MODELS_AVAILABLE:
        raise ImportError("Old ToolOutput model not available")

    # Get telemetry if available
    telemetry = getattr(tool_output, 'telemetry', None)
    if telemetry is None:
        telemetry = ToolTelemetry()

    # Convert ResponseFormat to OutputLevel
    response_format = getattr(tool_output, 'response_format', ResponseFormat.STANDARD)
    output_level = response_format_to_output_level(response_format.value if hasattr(response_format, 'value') else response_format)

    # Get observation
    observation = getattr(tool_output, 'observation', '')
    if not observation:
        # Generate from summary
        summary = getattr(tool_output, 'summary', '')
        observation = summary or f"Tool executed: {telemetry.tool_name}"

    # Create ToolExecutionResult
    return ToolExecutionResult(
        tool_call_id=tool_call_id,
        tool_name=telemetry.tool_name,
        observation=observation,
        output_level=output_level,
        success=telemetry.success,
        duration_ms=telemetry.latency_ms,
        error_message=telemetry.error_message if not telemetry.success else None,
        error_type=telemetry.error_code if not telemetry.success else None,
        metadata={
            "legacy_tool_output": True,
            "legacy_response_format": response_format.value if hasattr(response_format, 'value') else response_format,
        }
    )


def execution_result_to_tool_output(execution_result: ToolExecutionResult) -> Any:
    """
    Convert new ToolExecutionResult to old ToolOutput.

    Args:
        execution_result: New ToolExecutionResult instance

    Returns:
        Old ToolOutput instance (or None if old models unavailable)
    """
    if not OLD_MODELS_AVAILABLE:
        return None

    # Convert OutputLevel to ResponseFormat
    response_format_value = output_level_to_response_format(execution_result.output_level)

    # Create telemetry
    telemetry = ToolTelemetry(
        tool_name=execution_result.tool_name,
        latency_ms=execution_result.duration_ms,
        success=execution_result.success,
        error_code=execution_result.error_code,
        error_message=execution_result.error_message,
    )

    # Create ToolOutput
    return ToolOutput(
        summary=execution_result.observation.split('\n')[0],  # First line as summary
        observation=execution_result.observation,
        response_format=ResponseFormat(response_format_value),
        telemetry=telemetry,
    )


__all__ = [
    "response_format_to_output_level",
    "output_level_to_response_format",
    "tool_output_to_execution_result",
    "execution_result_to_tool_output",
]
