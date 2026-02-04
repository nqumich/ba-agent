"""
Agent 相关模型

定义 Agent 对话、消息、状态等核心模型
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from .base import TimestampMixin, MetadataMixin, IDMixin
from enum import Enum


class MessageRole(str, Enum):
    """消息角色"""

    USER = "user"           # 用户消息
    ASSISTANT = "assistant"  # Agent 消息
    SYSTEM = "system"        # 系统消息
    TOOL = "tool"           # 工具调用结果


class MessageType(str, Enum):
    """消息类型"""

    TEXT = "text"           # 文本消息
    TOOL_CALL = "tool_call" # 工具调用
    TOOL_RESULT = "tool_result"  # 工具结果
    ERROR = "error"         # 错误消息
    THINKING = "thinking"   # 思考过程


class Message(IDMixin):
    """Agent 消息"""

    role: MessageRole = Field(
        ...,
        description="消息角色"
    )
    type: MessageType = Field(
        default=MessageType.TEXT,
        description="消息类型"
    )
    content: str = Field(
        ...,
        description="消息内容"
    )
    tool_calls: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="工具调用列表"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="消息元数据"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="消息时间戳"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg-001",
                "role": "assistant",
                "type": "tool_call",
                "content": "让我查询一下数据库",
                "tool_calls": [
                    {
                        "tool": "query_database",
                        "parameters": {"sql": "SELECT * FROM sales"}
                    }
                ],
                "timestamp": "2025-02-04T10:00:00"
            }
        }


class AgentState(str, Enum):
    """Agent 状态"""

    IDLE = "idle"           # 空闲
    THINKING = "thinking"   # 思考中
    TOOL_EXECUTING = "tool_executing"  # 工具执行中
    WAITING = "waiting"     # 等待用户输入
    ERROR = "error"         # 错误状态
    DONE = "done"           # 完成


class Conversation(IDMixin, TimestampMixin):
    """对话会话"""

    user_id: str = Field(
        ...,
        description="用户ID"
    )
    title: str = Field(
        ...,
        description="对话标题"
    )
    state: AgentState = Field(
        default=AgentState.IDLE,
        description="Agent 状态"
    )
    messages: List[Message] = Field(
        default_factory=list,
        description="消息历史"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="对话上下文"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="会话元数据"
    )
    last_activity: datetime = Field(
        default_factory=datetime.now,
        description="最后活动时间"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "conv-001",
                "user_id": "user-001",
                "title": "GMV 异常分析",
                "state": "thinking",
                "messages": [
                    {
                        "id": "msg-001",
                        "role": "user",
                        "type": "text",
                        "content": "昨天的GMV异常下降了，帮我分析原因"
                    }
                ],
                "context": {
                    "current_task": "anomaly_detection",
                    "target_metric": "GMV"
                },
                "last_activity": "2025-02-04T10:00:00"
            }
        }


class AgentTask(IDMixin, TimestampMixin):
    """Agent 任务"""

    conversation_id: str = Field(
        ...,
        description="关联的对话ID"
    )
    type: str = Field(
        ...,
        description="任务类型（如：anomaly_detection, attribution_analysis）"
    )
    description: str = Field(
        ...,
        description="任务描述"
    )
    status: str = Field(
        default="pending",
        description="任务状态（pending, in_progress, completed, failed）"
    )
    input_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="输入数据"
    )
    output_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="输出数据"
    )
    error: Optional[str] = Field(
        default=None,
        description="错误信息"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="开始时间"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="完成时间"
    )
    steps: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="执行步骤"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "task-001",
                "conversation_id": "conv-001",
                "type": "anomaly_detection",
                "description": "检测 GMV 异常",
                "status": "in_progress",
                "input_data": {
                    "metric": "GMV",
                    "date_range": ["2025-02-01", "2025-02-03"]
                },
                "steps": [
                    {"step": 1, "action": "query_database", "status": "completed"},
                    {"step": 2, "action": "detect_anomaly", "status": "in_progress"}
                ]
            }
        }


class AgentConfig(BaseModel):
    """Agent 配置"""

    name: str = Field(
        default="BA-Agent",
        description="Agent 名称"
    )
    model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="使用的模型"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="温度参数"
    )
    max_tokens: int = Field(
        default=4096,
        description="最大生成 tokens"
    )
    system_prompt: str = Field(
        ...,
        description="系统提示词"
    )
    tools: List[str] = Field(
        default_factory=list,
        description="可用工具列表"
    )
    skills: List[str] = Field(
        default_factory=list,
        description="可用 Skill 列表"
    )
    memory_enabled: bool = Field(
        default=True,
        description="是否启用记忆"
    )
    hooks_enabled: bool = Field(
        default=True,
        description="是否启用 hooks"
    )
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="其他配置"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "BA-Agent",
                "model": "claude-3-5-sonnet-20241022",
                "temperature": 0.7,
                "max_tokens": 4096,
                "system_prompt": "你是一个专业的商业分析助手...",
                "tools": ["query_database", "invoke_skill"],
                "memory_enabled": True,
                "hooks_enabled": True
            }
        }


# 导出
__all__ = [
    "MessageRole",
    "MessageType",
    "Message",
    "AgentState",
    "Conversation",
    "AgentTask",
    "AgentConfig"
]
