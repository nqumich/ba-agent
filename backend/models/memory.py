"""
记忆管理相关模型

定义三层记忆管理系统的模型
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime, date
from .base import TimestampMixin, MetadataMixin, IDMixin
from enum import Enum


class MemoryKind(str, Enum):
    """记忆类型"""

    DAILY = "daily"         # 每日日志 (Layer 1)
    LONG_TERM = "long_term" # 长期记忆 (Layer 2)
    CONTEXT = "context"     # 上下文引导 (Layer 3)
    WORKING = "working"     # 工作记忆（当前会话）


class MemoryLevel(str, Enum):
    """记忆层级"""

    LAYER_1 = "layer_1"     # 每日日志 - memory/YYYY-MM-DD.md
    LAYER_2 = "layer_2"     # 长期记忆 - MEMORY.md
    LAYER_3 = "layer_3"     # 上下文引导 - CLAUDE.md, AGENTS.md, USER.md
    WORKING = "working"     # 工作记忆 - 当前对话上下文


class MemoryEntry(IDMixin, TimestampMixin):
    """记忆条目 - 通用的记忆存储单位"""

    level: MemoryLevel = Field(
        ...,
        description="记忆层级"
    )
    kind: MemoryKind = Field(
        ...,
        description="记忆类型"
    )
    content: str = Field(
        ...,
        description="记忆内容（Markdown 格式）"
    )
    source: str = Field(
        ...,
        description="来源（如：conversation_id, task_id, manual）"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="标签（用于检索）"
    )
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="重要性评分"
    )
    access_count: int = Field(
        default=0,
        description="访问次数"
    )
    last_accessed: Optional[datetime] = Field(
        default=None,
        description="最后访问时间"
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="向量嵌入（用于语义搜索）"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="附加元数据"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "mem-001",
                "level": "layer_1",
                "kind": "daily",
                "content": "# 2025-02-04 工作日志\n\n完成了 US-002 模型定义",
                "source": "task-002",
                "tags": ["US-002", "models", "pydantic"],
                "importance": 0.8,
                "access_count": 2,
                "last_accessed": "2025-02-04T15:00:00"
            }
        }


class DailyLog(MemoryEntry):
    """每日日志 (Layer 1) - memory/YYYY-MM-DD.md"""

    log_date: date = Field(
        ...,
        description="日志日期",
        alias="date"
    )
    tasks_completed: List[str] = Field(
        default_factory=list,
        description="完成的任务"
    )
    findings: List[str] = Field(
        default_factory=list,
        description="发现和洞察"
    )
    decisions: List[str] = Field(
        default_factory=list,
        description="做出的决策"
    )
    next_steps: List[str] = Field(
        default_factory=list,
        description="下一步计划"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-02-04",
                "content": "# 工作日志 - 2025-02-04\n\n## 完成任务\n- US-002: 核心数据模型定义",
                "tasks_completed": ["US-002"],
                "findings": ["Pydantic 模型验证需要添加测试"],
                "decisions": ["使用 Pydantic v2"],
                "next_steps": ["添加模型验证测试"]
            }
        }
        populate_by_name = True


class LongTermMemory(MemoryEntry):
    """长期记忆 (Layer 2) - MEMORY.md"""

    category: str = Field(
        ...,
        description="记忆类别（user_preferences, decisions, patterns, lessons）"
    )
    key: str = Field(
        ...,
        description="记忆键（用于快速检索）"
    )
    value: Any = Field(
        ...,
        description="记忆值"
    )
    expiration: Optional[datetime] = Field(
        default=None,
        description="过期时间（可选）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "category": "user_preferences",
                "key": "preferred_report_format",
                "value": "pdf",
                "content": "用户偏好 PDF 格式的报告",
                "importance": 0.9
            }
        }


class ContextBootstrap(MemoryEntry):
    """上下文引导 (Layer 3) - CLAUDE.md, AGENTS.md, USER.md"""

    file: str = Field(
        ...,
        description="文件名（CLAUDE.md, AGENTS.md, USER.md）"
    )
    section: str = Field(
        ...,
        description="所属章节"
    )
    priority: int = Field(
        default=0,
        description="优先级（数字越大越优先加载）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "file": "AGENTS.md",
                "section": "Identity",
                "content": "你是 BA-Agent，专业的商业分析助手",
                "priority": 10
            }
        }


class MemorySearchQuery(BaseModel):
    """记忆搜索查询"""

    query: str = Field(
        ...,
        description="搜索查询（自然语言或关键词）"
    )
    level: Optional[MemoryLevel] = Field(
        default=None,
        description="限定搜索层级"
    )
    kind: Optional[MemoryKind] = Field(
        default=None,
        description="限定记忆类型"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="限定标签"
    )
    date_from: Optional[date] = Field(
        default=None,
        description="起始日期"
    )
    date_to: Optional[date] = Field(
        default=None,
        description="结束日期"
    )
    limit: int = Field(
        default=10,
        description="返回结果数量限制"
    )
    use_semantic_search: bool = Field(
        default=False,
        description="是否使用语义搜索"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "用户偏好的报告格式",
                "kind": "long_term",
                "limit": 5
            }
        }


class MemorySearchResult(BaseModel):
    """记忆搜索结果"""

    query: MemorySearchQuery = Field(
        ...,
        description="搜索查询"
    )
    results: List[MemoryEntry] = Field(
        default_factory=list,
        description="匹配的记忆条目"
    )
    total: int = Field(
        ...,
        description="总匹配数"
    )
    search_time: float = Field(
        ...,
        description="搜索耗时（秒）"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="搜索元数据"
    )


class MemoryWriteRequest(BaseModel):
    """记忆写入请求"""

    level: MemoryLevel = Field(
        ...,
        description="目标层级"
    )
    kind: MemoryKind = Field(
        ...,
        description="记忆类型"
    )
    content: str = Field(
        ...,
        description="记忆内容"
    )
    source: str = Field(
        ...,
        description="来源"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="标签"
    )
    importance: float = Field(
        default=0.5,
        description="重要性"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="附加元数据"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "level": "layer_1",
                "kind": "daily",
                "content": "完成了模型验证测试",
                "source": "manual",
                "tags": ["test", "validation"],
                "importance": 0.6
            }
        }


class WorkingMemory(BaseModel):
    """工作记忆 - 当前对话的临时记忆"""

    conversation_id: str = Field(
        ...,
        description="对话ID"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="对话上下文"
    )
    active_task: Optional[str] = Field(
        default=None,
        description="当前活动任务"
    )
    recent_tools: List[str] = Field(
        default_factory=list,
        description="最近使用的工具"
    )
    attention_focus: List[str] = Field(
        default_factory=list,
        description="当前关注点（用于 focus_manager）"
    )
    step_count: int = Field(
        default=0,
        description="步数计数器"
    )
    last_focus_update: Optional[datetime] = Field(
        default=None,
        description="上次焦点更新时间"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv-001",
                "context": {
                    "current_metric": "GMV",
                    "analysis_type": "anomaly_detection"
                },
                "active_task": "task-001",
                "recent_tools": ["query_database", "detect_anomaly"],
                "attention_focus": ["task_plan.md", "US-002"],
                "step_count": 3,
                "last_focus_update": "2025-02-04T10:05:00"
            }
        }


# 导出
__all__ = [
    "MemoryKind",
    "MemoryLevel",
    "MemoryEntry",
    "DailyLog",
    "LongTermMemory",
    "ContextBootstrap",
    "MemorySearchQuery",
    "MemorySearchResult",
    "MemoryWriteRequest",
    "WorkingMemory"
]
