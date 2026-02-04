"""
报告生成相关模型

定义日报、周报、月报等报告的结构
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date
from .base import TimestampMixin, MetadataMixin, IDMixin
from enum import Enum


class ReportType(str, Enum):
    """报告类型"""

    DAILY = "daily"           # 日报
    WEEKLY = "weekly"         # 周报
    MONTHLY = "monthly"       # 月报
    ADHOC = "adhoc"           # 临时报告


class ReportFormat(str, Enum):
    """报告格式"""

    PDF = "pdf"
    WORD = "docx"
    EXCEL = "xlsx"
    HTML = "html"
    MARKDOWN = "md"


class ChartType(str, Enum):
    """图表类型"""

    LINE = "line"             # 折线图
    BAR = "bar"              # 柱状图
    PIE = "pie"              # 饼图
    SCATTER = "scatter"        # 散点图
    HEATMAP = "heatmap"        # 热力图
    MAP = "map"              # 地图
    TABLE = "table"           # 表格


class MetricSummary(BaseModel):
    """指标摘要"""

    name: str = Field(
        ...,
        description="指标名称"
    )
    current_value: float = Field(
        ...,
        description="当前值"
    )
    previous_value: Optional[float] = Field(
        default=None,
        description="上期值"
    )
    change: Optional[float] = Field(
        default=None,
        description="变化量"
    )
    change_percent: Optional[float] = Field(
        default=None,
        description="变化百分比"
    )
    trend: str = Field(
        default="stable",
        description="趋势（up/down/stable）"
    )


class ReportSection(IDMixin):
    """报告章节"""

    title: str = Field(
        ...,
        description="章节标题"
    )
    order: int = Field(
        ...,
        description="章节顺序"
    )
    content: str = Field(
        ...,
        description="章节内容（Markdown 格式）"
    )
    charts: List[str] = Field(
        default_factory=list,
        description="包含的图表配置（ECharts JSON）"
    )
    tables: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="包含的数据表格"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="章节元数据"
    )


class ChartConfig(BaseModel):
    """图表配置"""

    id: str = Field(
        ...,
        description="图表ID"
    )
    title: str = Field(
        ...,
        description="图表标题"
    )
    type: ChartType = Field(
        ...,
        description="图表类型"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="图表数据"
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="ECharts 配置选项"
    )


class Report(IDMixin, TimestampMixin):
    """报告模型"""

    type: ReportType = Field(
        ...,
        description="报告类型"
    )
    format: ReportFormat = Field(
        default=ReportFormat.PDF,
        description="报告格式"
    )
    title: str = Field(
        ...,
        description="报告标题"
    )
    subtitle: Optional[str] = Field(
        default=None,
        description="副标题"
    )
    period_start: datetime = Field(
        ...,
        description="报告周期开始时间"
    )
    period_end: datetime = Field(
        ...,
        description="报告周期结束时间"
    )
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="生成时间"
    )
    author: str = Field(
        default="BA-Agent",
        description="生成者"
    )
    sections: List[ReportSection] = Field(
        default_factory=list,
        description="报告章节"
    )
    metrics: List[MetricSummary] = Field(
        default_factory=list,
        description="指标摘要"
    )
    charts: List[ChartConfig] = Field(
        default_factory=list,
        description="包含的图表"
    )
    anomalies: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="异动检测结果"
    )
    attributions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="归因分析结果"
    )
    insights: List[str] = Field(
        default_factory=list,
        description="关键洞察"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="建议措施"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="生成的文件路径"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "report-daily-20250204",
                "type": "daily",
                "format": "pdf",
                "title": "每日业务分析报告",
                "subtitle": "2025年2月4日",
                "period_start": "2025-02-04T00:00:00",
                "period_end": "2025-02-04T23:59:59",
                "generated_at": "2025-02-04T09:00:00",
                "author": "BA-Agent",
                "metrics": [
                    {
                        "name": "GMV",
                        "current_value": 15000.0,
                        "previous_value": 14500.0,
                        "change": 500.0,
                        "change_percent": 3.45,
                        "trend": "up"
                    }
                ],
                "insights": [
                    "GMV 环比增长 3.45%，趋势向上"
                ],
                "recommendations": [
                    "继续观察 GMV 趋势",
                    "准备针对周末的促销活动"
                ]
            }
        }


class ReportRequest(BaseModel):
    """报告生成请求"""

    type: ReportType = Field(
        default=ReportType.DAILY,
        description="报告类型"
    )
    format: ReportFormat = Field(
        default=ReportFormat.PDF,
        description="报告格式"
    )
    period_start: datetime = Field(
        ...,
        description="报告周期开始时间"
    )
    period_end: datetime = Field(
        ...,
        description="报告周期结束时间"
    )
    include_sections: List[str] = Field(
        default_factory=list,
        description="包含的章节（如：summary, anomalies, attribution）"
    )
    include_charts: bool = Field(
        default=True,
        description="是否包含图表"
    )
    custom_template: Optional[str] = Field(
        default=None,
        description="自定义模板路径"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="输出文件路径"
    )


# 导出
__all__ = [
    "ReportType",
    "ReportFormat",
    "ChartType",
    "MetricSummary",
    "ReportSection",
    "ChartConfig",
    "Report",
    "ReportRequest"
]
