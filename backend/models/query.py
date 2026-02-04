"""
查询相关模型

处理用户的自然语言查询和查询结果
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from .base import TimestampMixin, MetadataMixin, IDMixin


class QueryContext(BaseModel):
    """查询上下文 - 包含查询的额外信息"""

    conversation_id: Optional[str] = Field(
        default=None,
        description="对话会话ID"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="用户ID"
    )
    previous_queries: List[str] = Field(
        default_factory=list,
        description="历史查询"
    )
    session_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="会话元数据"
    )


class Query(BaseModel):
    """用户查询 - 表示用户的自然语言查询"""

    id: Optional[str] = Field(
        default=None,
        description="查询ID"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="用户ID"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="对话ID"
    )
    text: str = Field(
        ...,
        description="查询文本（自然语言）"
    )
    intent: Optional[str] = Field(
        default=None,
        description="识别的意图（如：异动检测、归因分析、报告生成）"
    )
    entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="提取的实体（如：时间范围、指标、维度）"
    )
    context: QueryContext = Field(
        default_factory=QueryContext,
        description="查询上下文"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "query-001",
                "user_id": "user-001",
                "conversation_id": "conv-001",
                "text": "昨天的GMV异常下降了，帮我分析原因",
                "intent": "anomaly_detection",
                "entities": {
                    "date": "2025-02-03",
                    "metric": "GMV"
                }
            }
        }


class DataSource(BaseModel):
    """数据源信息"""

    type: str = Field(
        description="数据源类型 (database, file, api)"
    )
    name: str = Field(
        description="数据源名称"
    )
    connection: Optional[str] = Field(
        default=None,
        description="连接字符串或路径"
    )
    query: Optional[str] = Field(
        default=None,
        description="查询语句或文件路径"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="数据源元数据"
    )


class DataPoint(BaseModel):
    """数据点"""

    dimension: Dict[str, Any] = Field(
        description="维度值（如：日期、地区、品类）"
    )
    metric: str = Field(
        description="指标名称（如：GMV、订单量）"
    )
    value: float = Field(
        description="指标值"
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="时间戳"
    )


class QueryResult(IDMixin, TimestampMixin):
    """查询结果 - 包含查询返回的数据"""

    query_id: str = Field(
        description="关联的查询ID"
    )
    data: List[DataPoint] = Field(
        default_factory=list,
        description="查询结果数据"
    )
    sources: List[DataSource] = Field(
        default_factory=list,
        description="数据来源"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="结果元数据"
    )
    status: str = Field(
        default="success",
        description="状态 (success, error, partial)"
    )
    message: Optional[str] = Field(
        default=None,
        description="状态消息或错误信息"
    )
    execution_time: float = Field(
        default=0.0,
        description="执行时间（秒）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "query-001",
                "data": [
                    {
                        "dimension": {"date": "2025-02-03"},
                        "metric": "GMV",
                        "value": 15000.0,
                        "timestamp": "2025-02-03T00:00:00"
                    }
                ],
                "sources": [
                    {
                        "type": "database",
                        "name": "production_db",
                        "query": "SELECT date, gmv FROM sales WHERE date = '2025-02-03'"
                    }
                ],
                "status": "success",
                "execution_time": 0.5
            }
        }


# 导出
__all__ = [
    "QueryContext",
    "Query",
    "DataSource",
    "DataPoint",
    "QueryResult"
]
