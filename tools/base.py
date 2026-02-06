"""
统一工具包装器基类 (v2.1 - Pipeline Support)

提供统一的工具输出格式，支持：
1. 模型间上下文传递
2. 工程遥测收集
3. ReAct Observation 格式
4. Token 效率优化
5. 新：Pipeline v2.0.1 模型支持 (ToolExecutionResult)

兼容性：
- 旧模型：ResponseFormat, ToolOutput, ToolTelemetry
- 新模型：OutputLevel, ToolExecutionResult
- 自动转换：两种格式可以共存
"""

import functools
import json
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from pydantic import ValidationError

# 旧模型 (保持兼容)
from backend.models.tool_output import (
    ResponseFormat,
    ToolOutput,
    ToolTelemetry,
    get_telemetry_collector,
    extract_summary,
)

# 新模型 (Pipeline v2.0.1)
from backend.models.pipeline import (
    OutputLevel,
    ToolExecutionResult,
    ToolCachePolicy,
)

# 兼容层
from backend.models.compat import (
    response_format_to_output_level,
    output_level_to_response_format,
    tool_output_to_execution_result,
    execution_result_to_tool_output,
)


T = TypeVar('T')


# 新的 pipeline_tool 装饰器（推荐使用）
def pipeline_tool(
    tool_name: str,
    output_level: OutputLevel = OutputLevel.STANDARD,
    timeout_ms: int = 30000,
    cache_policy: ToolCachePolicy = ToolCachePolicy.NO_CACHE,
    extract_summary_func: Optional[Callable[[Any], str]] = None,
):
    """
    Pipeline 工具装饰器 (v2.0.1) - 推荐使用

    使用新的 ToolExecutionResult 模型，支持：
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

                # 提取摘要
                if extract_summary_func:
                    summary = extract_summary_func(raw_result)
                else:
                    summary = extract_summary(raw_result)

                # 使用 ToolExecutionResult.from_raw_data
                result = ToolExecutionResult.from_raw_data(
                    tool_call_id=tool_call_id,
                    raw_data=raw_result,
                    output_level=level,
                    tool_name=tool_name,
                    cache_policy=cache_policy,
                )

                # 更新 summary 和 duration
                result.observation = summary if level == OutputLevel.BRIEF else result.observation
                result.duration_ms = duration_ms

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                return ToolExecutionResult.create_error(
                    tool_call_id=tool_call_id,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    tool_name=tool_name,
                ).with_duration(duration_ms)

        return wrapper

    return decorator


# 旧的 unified_tool 装饰器（保持兼容）
def unified_tool(
    tool_name: str,
    response_format: ResponseFormat = ResponseFormat.STANDARD,
    extract_summary_func: Optional[Callable[[Any], str]] = None,
):
    """
    统一工具装饰器 (v1.0 - 保持兼容)

    将现有工具函数包装为返回统一格式的函数

    Args:
        tool_name: 工具名称（用于遥测）
        response_format: 响应格式级别
        extract_summary_func: 自定义摘要提取函数

    Returns:
        装饰后的函数，返回 JSON 字符串

    注意：新代码推荐使用 @pipeline_tool 装饰器
    """

    def decorator(func: Callable[..., T]) -> Callable[..., str]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> str:
            # 初始化遥测
            telemetry = ToolTelemetry(
                tool_name=tool_name,
                timestamp="",  # 会在模型中自动设置
            )

            # 提取 response_format 参数（如果提供）
            fmt = kwargs.pop('response_format', response_format)

            try:
                # 执行原始工具
                start_time = time.time()
                raw_result = func(*args, **kwargs)
                end_time = time.time()

                # 更新遥测
                telemetry.latency_ms = (end_time - start_time) * 1000
                telemetry.success = True

                # 提取摘要
                if extract_summary_func:
                    summary = extract_summary_func(raw_result)
                else:
                    summary = extract_summary(raw_result)

                # 构建 ToolOutput
                output = ToolOutput(
                    result=raw_result if fmt != ResponseFormat.CONCISE else None,
                    summary=summary,
                    observation="",  # 稍后生成
                    response_format=fmt,
                    telemetry=telemetry,
                )

                # 生成 Observation
                output.observation = output.to_observation()

                # 估算输出 Token（粗略：字符数 / 4）
                output_json = output.model_dump_for_llm()
                telemetry.output_tokens = len(json.dumps(output_json, ensure_ascii=False)) // 4

            except Exception as e:
                import traceback

                telemetry.latency_ms = (time.time() - start_time) * 1000 if 'start_time' in locals() else 0
                telemetry.success = False
                telemetry.error_code = type(e).__name__
                telemetry.error_message = str(e)

                # 构建错误输出
                output = ToolOutput(
                    result=None,
                    summary=f"错误：{str(e)}",
                    observation=f"Observation: Error - {str(e)}",
                    response_format=fmt,
                    telemetry=telemetry,
                    metadata={"traceback": traceback.format_exc()},
                )

            # 记录遥测
            collector = get_telemetry_collector()
            collector.record(telemetry)

            # 返回 JSON（排除遥测数据）
            return output.model_dump_json(exclude={"telemetry"})

        return wrapper

    return decorator


# 智能装饰器（自动选择）
def tool(
    tool_name: str,
    format: Union[ResponseFormat, OutputLevel, str] = "standard",
    **kwargs
):
    """
    智能工具装饰器 - 自动选择新/旧格式

    根据 format 参数自动选择：
    - ResponseFormat → 使用 unified_tool
    - OutputLevel → 使用 pipeline_tool
    - 字符串 → 自动转换

    Args:
        tool_name: 工具名称
        format: 输出格式 (ResponseFormat 或 OutputLevel 或字符串)
        **kwargs: 其他参数传递给对应装饰器

    Returns:
        装饰后的函数
    """
    # 检测 format 类型
    if isinstance(format, str):
        # 字符串：自动选择
        format_lower = format.lower()
        if format_lower in ("concise", "standard", "detailed", "raw"):
            # 旧格式
            return unified_tool(
                tool_name=tool_name,
                response_format=ResponseFormat(format_lower),
                **kwargs
            )
        elif format_lower in ("brief", "full"):
            # 新格式
            return pipeline_tool(
                tool_name=tool_name,
                output_level=OutputLevel(format_lower),
                **kwargs
            )
        else:
            # 默认使用 standard
            return unified_tool(
                tool_name=tool_name,
                response_format=ResponseFormat.STANDARD,
                **kwargs
            )

    elif isinstance(format, OutputLevel):
        # 新格式
        return pipeline_tool(
            tool_name=tool_name,
            output_level=format,
            **kwargs
        )

    else:
        # 旧格式 (ResponseFormat)
        return unified_tool(
            tool_name=tool_name,
            response_format=format,
            **kwargs
        )


class ToolOutputParser:
    """
    工具输出解析器 (支持新旧格式)

    用于解析统一格式的工具输出
    """

    @staticmethod
    def parse(output_json: str) -> ToolOutput:
        """解析 JSON 字符串为 ToolOutput"""
        try:
            data = json.loads(output_json)
            return ToolOutput(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            # 降级处理：返回错误格式的 ToolOutput
            return ToolOutput(
                summary=f"解析输出失败: {str(e)}",
                observation=f"Observation: Parse Error - {str(e)}",
                telemetry=ToolTelemetry(
                    success=False,
                    error_code="ParseError",
                    error_message=str(e),
                ),
            )

    @staticmethod
    def parse_pipeline(result: Any) -> ToolExecutionResult:
        """
        解析为 ToolExecutionResult

        支持输入：
        - ToolExecutionResult (直接返回)
        - ToolOutput (转换)
        - JSON 字符串 (解析后转换)
        """
        if isinstance(result, ToolExecutionResult):
            return result

        if isinstance(result, ToolOutput):
            # 转换旧格式到新格式
            import uuid
            tool_call_id = f"call_legacy_{uuid.uuid4().hex[:12]}"
            return tool_output_to_execution_result(result, tool_call_id)

        if isinstance(result, str):
            try:
                data = json.loads(result)
                if "observation" in data and "tool_call_id" in data:
                    # 新格式
                    return ToolExecutionResult(**data)
                else:
                    # 旧格式
                    tool_output = ToolOutput(**data)
                    import uuid
                    tool_call_id = f"call_legacy_{uuid.uuid4().hex[:12]}"
                    return tool_output_to_execution_result(tool_output, tool_call_id)
            except (json.JSONDecodeError, ValidationError):
                pass

        # 降级：创建错误结果
        import uuid
        tool_call_id = f"call_error_{uuid.uuid4().hex[:12]}"
        return ToolExecutionResult.create_error(
            tool_call_id=tool_call_id,
            error_message=f"Cannot parse result: {type(result)}",
            error_type="ParseError",
        )

    @staticmethod
    def get_observation(output: Any) -> str:
        """从输出中提取 Observation 字符串"""
        if isinstance(output, ToolExecutionResult):
            return output.observation

        if isinstance(output, ToolOutput):
            return output.observation

        if isinstance(output, str):
            try:
                data = json.loads(output)
                return data.get("observation", "")
            except json.JSONDecodeError:
                return output  # 降级：返回原始字符串

        return str(output)

    @staticmethod
    def get_summary(output: Any) -> str:
        """从输出中提取 Summary 字符串"""
        if isinstance(output, ToolExecutionResult):
            return output.observation.split('\n')[0]  # 第一行作为摘要

        if isinstance(output, ToolOutput):
            return output.summary

        if isinstance(output, str):
            try:
                data = json.loads(output)
                return data.get("summary", "")
            except json.JSONDecodeError:
                return ""

        return ""

    @staticmethod
    def is_success(output: Any) -> bool:
        """判断工具执行是否成功"""
        if isinstance(output, ToolExecutionResult):
            return output.success

        if isinstance(output, ToolOutput):
            return output.telemetry.success

        if isinstance(output, str):
            try:
                data = json.loads(output)
                if "telemetry" in data:
                    return data.get("telemetry", {}).get("success", True)
                return "error" not in str(data).lower()
            except json.JSONDecodeError:
                return True

        return True


class ReActFormatter:
    """
    ReAct 格式化工具

    参考 LangChain ReAct 模式的 Thought → Action → Observation 循环
    """

    @staticmethod
    def format_action(tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        格式化 Action

        示例：
        Action: file_reader[path="./data/test.csv"]
        """
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in tool_input.items())
        return f"Action: {tool_name}[{args_str}]"

    @staticmethod
    def format_thought(thought: str) -> str:
        """
        格式化 Thought

        示例：
        Thought: 我需要读取文件来获取数据
        """
        return f"Thought: {thought}"

    @staticmethod
    def format_observation(tool_output: Any) -> str:
        """
        格式化 Observation

        支持 ToolOutput, ToolExecutionResult, 或字符串
        """
        return ToolOutputParser.get_observation(tool_output)

    @staticmethod
    def format_step(
        thought: Optional[str] = None,
        action: Optional[str] = None,
        observation: Optional[str] = None,
    ) -> str:
        """
        格式化完整的 ReAct 步骤

        示例：
        Thought: 我需要读取文件
        Action: file_reader[path="./data/test.csv"]
        Observation: 成功读取了文件，共 1000 行
        """
        parts = []
        if thought:
            parts.append(ReActFormatter.format_thought(thought))
        if action:
            parts.append(action)
        if observation:
            parts.append(observation)
        return "\n".join(parts)


class TokenOptimizer:
    """
    Token 优化工具

    提供各种 Token 高效的数据格式
    """

    @staticmethod
    def to_compact(data: Dict[str, Any]) -> str:
        """
        转换为紧凑格式（类 TOON）

        格式：key1:value1|key2:value2|...
        """
        parts = []
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool)):
                parts.append(f"{k}:{v}")
            elif isinstance(v, list):
                parts.append(f"{k}:[{len(v)} items]")
            elif isinstance(v, dict):
                parts.append(f"{k}:{{{len(v)} keys}}")
            else:
                parts.append(f"{k}:{type(v).__name__}")
        return "|".join(parts)

    @staticmethod
    def to_safe_yaml(data: Dict[str, Any]) -> str:
        """
        转换为安全的 YAML 格式

        仅支持基本类型，避免复杂嵌套
        """
        lines = []
        for k, v in data.items():
            if isinstance(v, str):
                lines.append(f"{k}: {v}")
            elif isinstance(v, (int, float, bool)):
                lines.append(f"{k}: {v}")
            elif v is None:
                lines.append(f"{k}: null")
            else:
                lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        return "\n".join(lines)

    @staticmethod
    def to_xml(
        tool_name: str,
        summary: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        转换为 XML 格式（LLM 友好）

        示例：
        <tool_result name="file_reader">
          <summary>成功读取文件</summary>
          <metadata tokens="100" latency="45.2"/>
        </tool_result>
        """
        lines = [f'<tool_result name="{tool_name}">']
        lines.append(f"  <summary>{summary}</summary>")

        if data:
            data_str = json.dumps(data, ensure_ascii=False)
            lines.append(f"  <data>{data_str}</data>")

        if metadata:
            meta_attrs = " ".join(f'{k}="{v}"' for k, v in metadata.items())
            lines.append(f"  <metadata {meta_attrs}/>")

        lines.append("</tool_result>")
        return "\n".join(lines)


# 导出
__all__ = [
    # 新装饰器 (推荐)
    "pipeline_tool",
    "tool",

    # 旧装饰器 (保持兼容)
    "unified_tool",

    # 工具类
    "ToolOutputParser",
    "ReActFormatter",
    "TokenOptimizer",
]
