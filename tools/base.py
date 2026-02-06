"""
统一工具包装器基类 (v2.1 - Pipeline Only)

提供统一的工具输出格式，支持：
1. 模型间上下文传递
2. 工程遥测收集
3. ReAct Observation 格式
4. Token 效率优化
5. Pipeline v2.1 模型 (ToolExecutionResult)

v2.1 变更：
- 移除旧模型 (ResponseFormat, ToolOutput, ToolTelemetry)
- 仅保留新模型 (OutputLevel, ToolExecutionResult)
- 简化装饰器逻辑
"""

import functools
import json
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from pydantic import ValidationError

# Pipeline v2.1 模型
from backend.models.pipeline import (
    OutputLevel,
    ToolExecutionResult,
    ToolCachePolicy,
)


T = TypeVar('T')


def pipeline_tool(
    tool_name: str,
    output_level: OutputLevel = OutputLevel.STANDARD,
    timeout_ms: int = 30000,
    cache_policy: ToolCachePolicy = ToolCachePolicy.NO_CACHE,
    extract_summary_func: Optional[Callable[[Any], str]] = None,
):
    """
    Pipeline 工具装饰器 (v2.1) - 唯一推荐的工具装饰器

    使用 ToolExecutionResult 模型，支持：
    - OutputLevel (BRIEF/STANDARD/FULL)
    - 超时处理
    - 缓存策略
    - artifact 存储

    Args:
        tool_name: 工具名称
        output_level: 输出级别 (BRIEF/STANDARD/FULL)
        timeout_ms: 超时时间（毫秒）
        cache_policy: 缓存策略
        extract_summary_func: 自定义摘要提取函数

    Returns:
        装饰后的函数，返回 ToolExecutionResult

    示例:
        @pipeline_tool("query_database", OutputLevel.STANDARD)
        def query(sql: str) -> dict:
            return {"rows": [...]}
    """

    def decorator(func: Callable[..., T]) -> Callable[..., ToolExecutionResult]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> ToolExecutionResult:
            # 生成 tool_call_id (临时，实际应由 LLM 提供)
            import uuid
            tool_call_id = f"call_{tool_name}_{uuid.uuid4().hex[:12]}"

            # 提取 output_level 参数（如果提供）
            level = kwargs.pop('output_level', output_level)

            start_time = time.time()

            try:
                # 执行原始工具
                raw_result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                # 创建成功结果
                result = ToolExecutionResult.from_raw_data(
                    tool_call_id=tool_call_id,
                    raw_data=raw_result,
                    output_level=level,
                    tool_name=tool_name,
                    cache_policy=cache_policy,
                )
                result.duration_ms = duration_ms

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                # 创建错误结果
                return ToolExecutionResult.create_error(
                    tool_call_id=tool_call_id,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    tool_name=tool_name,
                ).with_duration(duration_ms)

        return wrapper

    return decorator


# 简化的 tool 装饰器（别名，向后兼容）
def tool(
    tool_name: str,
    format: Union[OutputLevel, str] = "standard",
    **kwargs
):
    """
    工具装饰器 - 简化版 (v2.1)

    仅支持 OutputLevel 格式。

    Args:
        tool_name: 工具名称
        format: 输出级别 (BRIEF/STANDARD/FULL 或字符串 "brief"/"standard"/"full")
        **kwargs: 其他参数传递给 pipeline_tool

    Returns:
        装饰后的函数，返回 ToolExecutionResult
    """
    # 转换字符串为 OutputLevel
    if isinstance(format, str):
        format_lower = format.lower()
        if format_lower == "brief" or format_lower == "concise":
            output_level = OutputLevel.BRIEF
        elif format_lower == "full" or format_lower == "detailed":
            output_level = OutputLevel.FULL
        else:
            output_level = OutputLevel.STANDARD
    else:
        output_level = format

    return pipeline_tool(
        tool_name=tool_name,
        output_level=output_level,
        **kwargs
    )


class ToolOutputParser:
    """
    工具输出解析器 (v2.1 - 简化版)

    仅支持 ToolExecutionResult 格式。
    """

    @staticmethod
    def get_observation(result: Any) -> str:
        """
        从工具结果中提取 observation。

        Args:
            result: 工具结果 (ToolExecutionResult 或其他)

        Returns:
            observation 字符串
        """
        if isinstance(result, ToolExecutionResult):
            return result.observation
        elif isinstance(result, str):
            return result
        elif isinstance(result, dict):
            # 从字典中提取
            if "observation" in result:
                return result["observation"]
            elif "summary" in result:
                return result["summary"]
            else:
                return json.dumps(result, ensure_ascii=False)
        else:
            return str(result)

    @staticmethod
    def is_success(result: Any) -> bool:
        """
        检查工具执行是否成功。

        Args:
            result: 工具结果

        Returns:
            是否成功
        """
        if isinstance(result, ToolExecutionResult):
            return result.success
        elif isinstance(result, dict):
            return not result.get("error")
        else:
            return True  # 默认成功

    @staticmethod
    def get_summary(result: Any) -> Optional[str]:
        """
        从工具结果中提取摘要。

        Args:
            result: 工具结果

        Returns:
            摘要字符串
        """
        if isinstance(result, ToolExecutionResult):
            # 从 observation 中提取摘要（第一行或前100字符）
            obs = result.observation
            lines = obs.split('\n')
            if lines:
                first_line = lines[0]
                return first_line[:100] if len(first_line) > 100 else first_line
            return obs[:100]
        elif isinstance(result, dict):
            return result.get("summary") or str(result).get("result", "")[:100]
        elif isinstance(result, str):
            return result[:100]
        else:
            return str(result)[:100]


__all__ = [
    "pipeline_tool",
    "tool",
    "ToolOutputParser",
]
