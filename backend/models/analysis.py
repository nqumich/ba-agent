"""
业务分析模型

定义异动检测、归因分析等业务分析相关的模型
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime, date
from .base import TimestampMixin, MetadataMixin, IDMixin
from enum import Enum


class AnomalyType(str, Enum):
    """异动类型"""

    SPIKE = "spike"           # 突然升高
    DROP = "drop"             # 突然下降
    TREND = "trend"          # 趋势异常
    OUTLIER = "outlier"      # 离群值
    PATTERN = "pattern"      # 模式异常


class AnomalySeverity(str, Enum):
    """异动严重程度"""

    LOW = "low"               # 轻度（±10%以内）
    MEDIUM = "medium"         # 中度（±10-30%）
    HIGH = "high"             # 重度（±30-50%）
    CRITICAL = "critical"     # 严重（>50%）


class Anomaly(IDMixin, TimestampMixin):
    """异动检测结果"""

    metric: str = Field(
        ...,
        description="指标名称（如：GMV、订单量）"
    )
    anomaly_type: AnomalyType = Field(
        ...,
        description="异动类型"
    )
    severity: AnomalySeverity = Field(
        ...,
        description="严重程度"
    )
    baseline: float = Field(
        ...,
        description="基准值（正常值）"
    )
    actual: float = Field(
        ...,
        description="实际值"
    )
    deviation: float = Field(
        ...,
        description="偏差百分比"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.95,
        description="置信度"
    )
    timestamp: datetime = Field(
        ...,
        description="异动时间"
    )
    dimensions: Dict[str, Any] = Field(
        default_factory=dict,
        description="维度信息（如：地区、品类）"
    )
    detection_method: str = Field(
        default="hybrid",
        description="检测方法（3sigma、ai、hybrid）"
    )
    explanation: Optional[str] = Field(
        default=None,
        description="异动解释"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "anomaly-001",
                "metric": "GMV",
                "anomaly_type": "drop",
                "severity": "high",
                "baseline": 15000.0,
                "actual": 10500.0,
                "deviation": -30.0,
                "confidence": 0.95,
                "timestamp": "2025-02-03T00:00:00",
                "dimensions": {"region": "华东", "category": "electronics"},
                "detection_method": "hybrid",
                "explanation": "GMV相比前一日下降30%，主要由electronics品类下降导致"
            }
        }


class AttributionType(str, Enum):
    """归因类型"""

    DIMENSION = "dimension"     # 维度下钻
    EVENT = "event"           # 事件影响
    EXTERNAL = "external"       # 外部因素
    SEASONAL = "seasonal"       # 季节性
    COMPETITOR = "competitor"   # 竞争影响


class AttributionFactor(BaseModel):
    """归因因子"""

    factor: str = Field(
        ...,
        description="因子名称"
    )
    type: AttributionType = Field(
        ...,
        description="归因类型"
    )
    contribution: float = Field(
        ...,
        description="贡献度（百分比）"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.8,
        description="置信度"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="详细信息"
    )


class Attribution(IDMixin, TimestampMixin):
    """归因分析结果"""

    metric: str = Field(
        ...,
        description="指标名称"
    )
    change: float = Field(
        ...,
        description="变化量（绝对值）"
    )
    change_percent: float = Field(
        ...,
        description="变化百分比"
    )
    baseline: float = Field(
        ...,
        description="基准值"
    )
    actual: float = Field(
        ...,
        description="实际值"
    )
    period_start: datetime = Field(
        ...,
        description="分析周期开始时间"
    )
    period_end: datetime = Field(
        ...,
        description="分析周期结束时间"
    )
    factors: List[AttributionFactor] = Field(
        default_factory=list,
        description="归因因子列表"
    )
    top_factor: Optional[str] = Field(
        default=None,
        description="最主要原因"
    )
    explanation: str = Field(
        ...,
        description="归因分析总结"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="建议措施"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "attr-001",
                "metric": "GMV",
                "change": -4500.0,
                "change_percent": -30.0,
                "baseline": 15000.0,
                "actual": 10500.0,
                "period_start": "2025-02-03T00:00:00",
                "period_end": "2025-02-03T23:59:59",
                "factors": [
                    {
                        "factor": "electronics品类下降",
                        "type": "dimension",
                        "contribution": -22.0,
                        "confidence": 0.95
                    },
                    {
                        "factor": "促销活动结束",
                        "type": "event",
                        "contribution": -8.0,
                        "confidence": 0.8
                    }
                ],
                "top_factor": "electronics品类下降",
                "explanation": "GMV下降30%主要由electronics品类下降22%和促销活动结束导致",
                "recommendations": ["恢复促销活动", "调整electronics品类定价"]
            }
        }


class InsightType(str, Enum):
    """洞察类型"""

    TREND = "trend"           # 趋势
    OPPORTUNITY = "opportunity"  # 机会
    RISK = "risk"             # 风险
    ANOMALY = "anomaly"        # 异动


class Insight(IDMixin, TimestampMixin):
    """业务洞察"""

    type: InsightType = Field(
        ...,
        description="洞察类型"
    )
    title: str = Field(
        ...,
        description="洞察标题"
    )
    description: str = Field(
        ...,
        description="详细描述"
    )
    metric: str = Field(
        ...,
        description="相关指标"
    )
    value: float = Field(
        ...,
        description="指标值"
    )
    impact: str = Field(
        ...,
        description="影响程度（high/medium/low）"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.8,
        description="置信度"
    )
    period_start: datetime = Field(
        ...,
        description="分析周期开始"
    )
    period_end: datetime = Field(
        ...,
        description="分析周期结束"
    )
    action_items: List[str] = Field(
        default_factory=list,
        description="建议行动"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "insight-001",
                "type": "opportunity",
                "title": "用户增长趋势",
                "description": "新用户增长呈上升趋势，建议加大营销投入",
                "metric": "新用户数",
                "value": 1500.0,
                "impact": "high",
                "confidence": 0.85,
                "period_start": "2025-02-01T00:00:00",
                "period_end": "2025-02-03T23:59:59",
                "action_items": ["增加营销预算", "推出新用户优惠"]
            }
        }


# 导出
__all__ = [
    "AnomalyType",
    "AnomalySeverity",
    "Anomaly",
    "AttributionType",
    "AttributionFactor",
    "Attribution",
    "InsightType",
    "Insight"
]
