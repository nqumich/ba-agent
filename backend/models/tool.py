"""
工具调用相关模型

处理 Agent 工具调用的输入和输出
"""

from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
from datetime import datetime
from .base import TimestampMixin, MetadataMixin, IDMixin


class ToolInput(BaseModel):
    """工具输入 - 定义工具调用所需的参数"""

    tool_name: str = Field(
        ...,
        description="工具名称"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="工具参数"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="调用上下文"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "query_database",
                "parameters": {
                    "sql": "SELECT * FROM sales LIMIT 10",
                    "database": "production"
                }
            }
        }


class ToolOutput(IDMixin, TimestampMixin):
    """工具输出 - 工具调用的返回结果"""

    tool_name: str = Field(
        description="工具名称"
    )
    input_hash: str = Field(
        description="输入哈希（用于缓存）"
    )
    output: Any = Field(
        description="工具输出数据"
    )
    success: bool = Field(
        default=True,
        description="是否成功"
    )
    error: Optional[str] = Field(
        default=None,
        description="错误信息"
    )
    execution_time: float = Field(
        default=0.0,
        description="执行时间（秒）"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="输出元数据"
    )


class ToolConfig(BaseModel):
    """工具配置 - 定义工具的配置和约束"""

    name: str = Field(
        ...,
        description="工具名称"
    )
    description: str = Field(
        ...,
        description="工具描述"
    )
    enabled: bool = Field(
        default=True,
        description="是否启用"
    )
    timeout: int = Field(
        default=30,
        description="超时时间（秒）"
    )
    max_retries: int = Field(
        default=3,
        description="最大重试次数"
    )
    allowed_params: List[str] = Field(
        default_factory=list,
        description="允许的参数列表"
    )
    required_params: List[str] = Field(
        default_factory=list,
        description="必需的参数列表"
    )
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="工具特定配置"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "query_database",
                "description": "查询数据库",
                "enabled": True,
                "timeout": 60,
                "max_retries": 2,
                "allowed_params": ["sql", "database"],
                "required_params": ["sql"],
                "config": {
                    "databases": ["production", "analytics"]
                }
            }
        }


class ToolCall(BaseModel):
    """工具调用记录"""

    id: str = Field(
        description="调用ID"
    )
    tool_name: str = Field(
        description="工具名称"
    )
    input: ToolInput = Field(
        description="工具输入"
    )
    output: ToolOutput = Field(
        description="工具输出"
    )
    session_id: str = Field(
        description="会话ID"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="调用时间"
    )


# 导出
__all__ = [
    "ToolInput",
    "ToolOutput",
    "ToolConfig",
    "ToolCall"
]
