"""
基础模型类

定义所有 Pydantic 模型的基类和混入类
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class TimestampMixin(BaseModel):
    """时间戳混入类 - 为模型添加创建和更新时间"""

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="更新时间"
    )


class MetadataMixin(BaseModel):
    """元数据混入类 - 为模型添加元数据字段"""

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="模型元数据"
    )


class IDMixin(BaseModel):
    """ID 混入类 - 为模型添加唯一标识符"""

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="唯一标识符"
    )


class BaseSchema(BaseModel):
    """基础 Schema 类 - 组合所有混入类"""

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="唯一标识符"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="更新时间"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="模型元数据"
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# 导出
__all__ = [
    "TimestampMixin",
    "MetadataMixin",
    "IDMixin",
    "BaseSchema"
]
