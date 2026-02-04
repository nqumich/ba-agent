"""
统一工具包装器基类

提供统一的工具输出格式，支持：
1. 模型间上下文传递
2. 工程遥测收集
3. ReAct Observation 格式
4. Token 效率优化
"""

import functools
import json
from typing import Any, Callable, Dict, Optional, TypeVar

from pydantic import ValidationError

from backend.models.tool_output import (
    ResponseFormat,
    ToolOutput,
    ToolTelemetry,
    get_telemetry_collector,
    extract_summary,
)


T = TypeVar('T')


def unified_tool(
    tool_name: str,
    response_format: ResponseFormat = ResponseFormat.STANDARD,
    extract_summary_func: Optional[Callable[[Any], str]] = None,
):
    """
    统一工具装饰器

    将现有工具函数包装为返回统一格式的函数

    Args:
        tool_name: 工具名称（用于遥测）
        response_format: 响应格式级别
        extract_summary_func: 自定义摘要提取函数

    Returns:
        装饰后的函数

    示例:
        @unified_tool("file_reader", ResponseFormat.STANDARD)
        def read_file(path: str) -> dict:
            # ... 原有实现
            return {"success": True, "data": "..."}

        # 返回格式：
        # {
        #   "summary": "成功读取文件...",
        #   "result": {...},
        #   "observation": "Observation: 成功读取文件...",
        #   "response_format": "standard"
        # }
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
                import time
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
                import time
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


class ToolOutputParser:
    """
    工具输出解析器

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
    def get_observation(output_json: str) -> str:
        """从 JSON 中提取 Observation 字符串"""
        try:
            data = json.loads(output_json)
            return data.get("observation", "")
        except json.JSONDecodeError:
            return output_json  # 降级：返回原始字符串

    @staticmethod
    def get_summary(output_json: str) -> str:
        """从 JSON 中提取 Summary 字符串"""
        try:
            data = json.loads(output_json)
            return data.get("summary", "")
        except json.JSONDecodeError:
            return ""

    @staticmethod
    def is_success(output_json: str) -> bool:
        """判断工具执行是否成功"""
        try:
            data = json.loads(output_json)
            # 检查是否有 error 字段或 telemetry.success
            if "telemetry" in data:
                # 新格式
                return True  # 如果有 telemetry，假设成功（失败会有 error）
            return "error" not in str(data).lower()
        except json.JSONDecodeError:
            return True  # 无法解析时假设成功


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
    def format_observation(tool_output: str) -> str:
        """
        格式化 Observation

        直接使用 ToolOutput 中的 observation 字段
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
    "unified_tool",
    "ToolOutputParser",
    "ReActFormatter",
    "TokenOptimizer",
]
