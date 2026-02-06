"""
BA-Agent 数据模型

导出所有 Pydantic 模型

New Pipeline Models (v2.0.1):
- OutputLevel, ToolCachePolicy, ToolInvocationRequest, ToolExecutionResult
- Located in backend/models/pipeline/

Legacy Models (to be migrated):
- ToolInput, ToolOutput (backend/models/tool.py)
- ResponseFormat, ToolTelemetry (backend/models/tool_output.py)

Compatibility Layer:
- See backend/models/compat.py for conversion functions
"""

from .base import (
    TimestampMixin,
    MetadataMixin,
    IDMixin,
    BaseSchema
)

from .query import (
    QueryContext,
    Query,
    DataSource,
    DataPoint,
    QueryResult
)

from .tool import (
    ToolInput,
    ToolOutput,
    ToolConfig,
    ToolCall
)

from .skill import (
    SkillParameter,
    SkillConfig,
    SkillInput,
    SkillResult,
    SkillManifest
)

from .analysis import (
    AnomalyType,
    AnomalySeverity,
    Anomaly,
    AttributionType,
    AttributionFactor,
    Attribution,
    InsightType,
    Insight
)

from .report import (
    ReportType,
    ReportFormat,
    ChartType,
    MetricSummary,
    ReportSection,
    ChartConfig,
    Report,
    ReportRequest
)

from .agent import (
    MessageRole,
    MessageType,
    Message,
    AgentState,
    Conversation,
    AgentTask,
    AgentConfig
)

from .memory import (
    MemoryKind,
    MemoryLevel,
    MemoryEntry,
    DailyLog,
    LongTermMemory,
    ContextBootstrap,
    MemorySearchQuery,
    MemorySearchResult,
    MemoryWriteRequest,
    WorkingMemory
)

# 导出所有模型
__all__ = [
    # Base
    "TimestampMixin",
    "MetadataMixin",
    "IDMixin",
    "BaseSchema",
    # Query
    "QueryContext",
    "Query",
    "DataSource",
    "DataPoint",
    "QueryResult",
    # Tool
    "ToolInput",
    "ToolOutput",
    "ToolConfig",
    "ToolCall",
    # Skill
    "SkillParameter",
    "SkillConfig",
    "SkillInput",
    "SkillResult",
    "SkillManifest",
    # Analysis
    "AnomalyType",
    "AnomalySeverity",
    "Anomaly",
    "AttributionType",
    "AttributionFactor",
    "Attribution",
    "InsightType",
    "Insight",
    # Report
    "ReportType",
    "ReportFormat",
    "ChartType",
    "MetricSummary",
    "ReportSection",
    "ChartConfig",
    "Report",
    "ReportRequest",
    # Agent
    "MessageRole",
    "MessageType",
    "Message",
    "AgentState",
    "Conversation",
    "AgentTask",
    "AgentConfig",
    # Memory
    "MemoryKind",
    "MemoryLevel",
    "MemoryEntry",
    "DailyLog",
    "LongTermMemory",
    "ContextBootstrap",
    "MemorySearchQuery",
    "MemorySearchResult",
    "MemoryWriteRequest",
    "WorkingMemory",
]
