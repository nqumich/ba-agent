"""
统一工具输出格式模型

基于 Anthropic、Claude Code、Manus 等 Agent 产品的最佳实践
支持模型间上下文传递、工程遥测、ReAct 兼容性
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic

from pydantic import BaseModel, Field, field_serializer


class ResponseFormat(str, Enum):
    """
    响应格式控制

    参考 Anthropic "Writing effective tools for AI agents":
    - CONCISE: 最少 Token，仅关键信息
    - STANDARD: 平衡信息量和 Token 使用
    - DETAILED: 完整信息（调试用）
    - RAW: 原始数据
    """
    CONCISE = "concise"      # 简洁：仅关键摘要
    STANDARD = "standard"    # 标准：摘要 + 结构化数据
    DETAILED = "detailed"    # 详细：完整调试信息
    RAW = "raw"              # 原始：未经处理


class ToolTelemetry(BaseModel):
    """
    工具遥测数据（工程系统使用，不传递给模型）

    用于：
    - 性能监控
    - 错误追踪
    - 资源管理
    - 成本分析
    """
    # 执行标识
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str = ""
    tool_version: str = "1.0.0"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    # 性能指标
    latency_ms: float = 0.0              # 工具执行延迟
    duration_ms: float = 0.0             # 总耗时（包括序列化）

    # Token 统计
    input_tokens: int = 0                # 输入 Token 数（估算）
    output_tokens: int = 0               # 输出 Token 数（实际）

    # 缓存状态
    cache_hit: bool = False              # 是否命中缓存
    cache_key: Optional[str] = None

    # 错误追踪
    success: bool = True
    error_code: Optional[str] = None     # 错误类型
    error_message: Optional[str] = None  # 错误详情
    retry_count: int = 0

    # 资源使用
    memory_mb: float = 0.0               # 内存使用 (MB)
    cpu_percent: float = 0.0             # CPU 使用率 (%)

    # 自定义指标（扩展点）
    metrics: Dict[str, Any] = Field(default_factory=dict)

    @field_serializer('timestamp')
    def serialize_timestamp(self, timestamp: str) -> str:
        """序列化时间戳"""
        return timestamp


class ToolOutput(BaseModel):
    """
    统一工具输出格式

    设计原则：
    1. 模型上下文部分传递给 LLM（用于下一轮推理）
    2. 工程遥测部分供系统使用（不传递给 LLM）
    3. 支持多种响应格式（Token 效率优化）
    4. ReAct Agent 兼容的 Observation 格式
    """

    # ========== 模型上下文部分 (传递给下一轮) ==========

    # 主要结果数据（根据 response_format 决定是否包含）
    result: Optional[Any] = Field(
        default=None,
        description="主要结果数据（CONCISE 模式下为 None）"
    )

    # 人类可读的摘要（LLM 直接使用）
    summary: str = Field(
        default="",
        description="简洁的结果摘要，供 LLM 理解工具执行结果"
    )

    # ReAct Observation 格式（标准化输出）
    observation: str = Field(
        default="",
        description="ReAct 标准 Observation 格式"
    )

    # ========== Token 效率控制 ==========

    response_format: ResponseFormat = Field(
        default=ResponseFormat.CONCISE,
        description="响应格式级别"
    )

    # ========== 工程遥测部分 (不传给模型) ==========

    telemetry: ToolTelemetry = Field(
        default_factory=ToolTelemetry,
        description="工具执行遥测数据（工程系统使用）"
    )

    # 扩展元数据
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="额外的元数据信息"
    )

    # ========== 状态管理 ==========

    state_update: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Agent 状态更新（用于 LangGraph 状态传递）"
    )

    checkpoint: Optional[str] = Field(
        default=None,
        description="检查点标识（用于恢复和回滚）"
    )

    def model_dump_for_llm(self) -> Dict[str, Any]:
        """
        转换为适合传递给 LLM 的字典

        排除遥测数据（仅保留模型需要的信息）
        """
        data = self.model_dump(exclude={"telemetry", "metadata"})

        # CONCISE 模式下移除 result
        if self.response_format == ResponseFormat.CONCISE:
            data.pop("result", None)

        return data

    def to_observation(self) -> str:
        """
        生成 ReAct Observation 格式字符串

        参考 LangChain/LangGraph 的 ReAct 模式
        """
        if self.response_format == ResponseFormat.CONCISE:
            return f"Observation: {self.summary}"

        elif self.response_format == ResponseFormat.STANDARD:
            status = "Success" if self.telemetry.success else "Failed"
            result_type = type(self.result).__name__ if self.result is not None else "None"
            return f"""Observation: {self.summary}

Result Type: {result_type}
Status: {status}
"""

        elif self.response_format == ResponseFormat.DETAILED:
            status = "Success" if self.telemetry.success else "Failed"
            result_json = json.dumps(self.result, ensure_ascii=False, indent=2) if self.result is not None else "null"
            metadata_json = json.dumps(self.metadata, ensure_ascii=False)

            return f"""Observation: {self.summary}

Tool: {self.telemetry.tool_name}
Execution ID: {self.telemetry.execution_id}
Status: {status}
Latency: {self.telemetry.latency_ms:.2f}ms
Output Tokens: {self.telemetry.output_tokens}

Result: {result_json}

Metadata: {metadata_json}
"""

        else:  # RAW
            return self.summary or str(self.result)


# 遥测收集器
class TelemetryCollector:
    """
    工具遥测数据收集器

    功能：
    - 收集所有工具执行的遥测数据
    - 聚合统计（总调用、平均延迟、错误率等）
    - 生成监控报告
    """

    def __init__(self):
        self.metrics: List[ToolTelemetry] = []
        self._aggregated: Dict[str, Any] = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_latency_ms": 0,
            "error_count": 0,
            "cache_hit_count": 0,
        }

    def record(self, telemetry: ToolTelemetry) -> None:
        """记录遥测数据"""
        self.metrics.append(telemetry)
        self._update_aggregated(telemetry)

    def _update_aggregated(self, telemetry: ToolTelemetry) -> None:
        """更新聚合统计"""
        self._aggregated["total_calls"] += 1
        self._aggregated["total_tokens"] += telemetry.output_tokens
        self._aggregated["total_latency_ms"] += telemetry.latency_ms

        if not telemetry.success:
            self._aggregated["error_count"] += 1
        if telemetry.cache_hit:
            self._aggregated["cache_hit_count"] += 1

    @property
    def aggregated(self) -> Dict[str, Any]:
        """获取聚合统计"""
        total = self._aggregated["total_calls"]
        if total == 0:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "avg_latency_ms": 0,
                "error_rate": 0.0,
                "cache_hit_rate": 0.0,
            }

        return {
            "total_calls": total,
            "total_tokens": self._aggregated["total_tokens"],
            "avg_latency_ms": self._aggregated["total_latency_ms"] / total,
            "error_rate": self._aggregated["error_count"] / total,
            "cache_hit_rate": self._aggregated["cache_hit_count"] / total,
        }

    def get_report(self) -> str:
        """生成遥测报告"""
        agg = self.aggregated
        return f"""
工具执行统计报告:
==================
总调用次数: {agg['total_calls']}
总 Token 使用: {agg['total_tokens']}
平均延迟: {agg['avg_latency_ms']:.2f}ms
错误率: {agg['error_rate']:.2%}
缓存命中率: {agg['cache_hit_rate']:.2%}

最近调用:
{self._format_recent_calls(5)}
"""

    def _format_recent_calls(self, count: int) -> str:
        """格式化最近的调用记录"""
        recent = self.metrics[-count:]
        lines = []
        for m in recent:
            status = "✓" if m.success else "✗"
            lines.append(
                f"  {status} {m.tool_name} | {m.latency_ms:.1f}ms | "
                f"{m.output_tokens} tokens | {m.timestamp}"
            )
        return "\n".join(lines) if lines else "  (无)"

    def get_metrics_by_tool(self, tool_name: str) -> List[ToolTelemetry]:
        """获取特定工具的遥测数据"""
        return [m for m in self.metrics if m.tool_name == tool_name]

    def reset(self) -> None:
        """重置收集器"""
        self.metrics.clear()
        self._aggregated = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_latency_ms": 0,
            "error_count": 0,
            "cache_hit_count": 0,
        }


# 全局遥测收集器实例
_global_collector: Optional[TelemetryCollector] = None


def get_telemetry_collector() -> TelemetryCollector:
    """获取全局遥测收集器"""
    global _global_collector
    if _global_collector is None:
        _global_collector = TelemetryCollector()
    return _global_collector


def extract_summary(data: Any, max_length: int = 200) -> str:
    """
    从数据中提取简洁摘要

    用于 CONCISE 模式下生成 summary
    """
    if isinstance(data, dict):
        # 字典：提取关键信息
        if "success" in data:
            status = "成功" if data.get("success") else "失败"
            if "error" in data:
                return f"{status}：{data['error']}"
            if "rows" in data:
                return f"{status}：{data.get('rows', 0)} 行"
            if "count" in data:
                return f"{status}：{data.get('count', 0)} 项"
            return status
        elif "error" in data:
            return f"错误：{data['error']}"
        else:
            keys = list(data.keys())[:3]
            return f"包含 {len(data)} 个字段: {', '.join(keys)}"

    elif isinstance(data, list):
        return f"列表，包含 {len(data)} 项"

    elif isinstance(data, str):
        return data[:max_length] if len(data) > max_length else data

    elif data is None:
        return "无返回数据"

    else:
        return str(data)[:max_length]


# 导出
__all__ = [
    "ResponseFormat",
    "ToolTelemetry",
    "ToolOutput",
    "TelemetryCollector",
    "get_telemetry_collector",
    "extract_summary",
]
