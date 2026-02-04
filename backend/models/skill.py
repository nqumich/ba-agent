"""
Skill 相关模型

定义可配置分析 Skill 的模型
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from .base import TimestampMixin, MetadataMixin, IDMixin


class SkillParameter(BaseModel):
    """Skill 参数定义"""

    name: str = Field(
        ...,
        description="参数名称"
    )
    type: str = Field(
        ...,
        description="参数类型 (string, int, float, bool, list, dict, object)"
    )
    description: str = Field(
        ...,
        description="参数描述"
    )
    default: Any = Field(
        default=None,
        description="默认值"
    )
    required: bool = Field(
        default=False,
        description="是否必需"
    )
    choices: Optional[List[str]] = Field(
        default=None,
        description="可选值列表"
    )


class SkillConfig(IDMixin, TimestampMixin):
    """Skill 配置 - 定义 Skill 的配置和元数据"""

    name: str = Field(
        ...,
        description="Skill 唯一名称"
    )
    version: str = Field(
        default="1.0.0",
        description="Skill 版本"
    )
    description: str = Field(
        ...,
        description="Skill 描述"
    )
    category: str = Field(
        ...,
        description="Skill 分类 (analysis, reporting, visualization)"
    )
    entrypoint: str = Field(
        ...,
        description="入口点模块路径 (如: skills.anomaly_detection.main)"
    )
    function: str = Field(
        ...,
        description="调用的函数名 (如: detect, analyze, generate)"
    )
    parameters: List[SkillParameter] = Field(
        default_factory=list,
        description="Skill 参数定义"
    )
    requirements: List[str] = Field(
        default_factory=list,
        description="依赖的 Python 包"
    )
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Skill 特定配置"
    )
    enabled: bool = Field(
        default=True,
        description="是否启用"
    )
    examples: List[str] = Field(
        default_factory=list,
        description="使用示例"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "skill-001",
                "name": "anomaly_detection",
                "description": "异动检测 Skill",
                "category": "analysis",
                "entrypoint": "skills.anomaly_detection.main",
                "function": "detect",
                "parameters": [
                    {
                        "name": "data",
                        "type": "object",
                        "description": "要检测的数据",
                        "required": True
                    },
                    {
                        "name": "method",
                        "type": "string",
                        "description": "检测方法 (3sigma, ai, hybrid)",
                        "default": "hybrid",
                        "choices": ["3sigma", "ai", "hybrid"]
                    }
                ],
                "requirements": ["pandas", "numpy", "scipy"],
                "config": {"default_threshold": 2.0}
            }
        }


class SkillInput(BaseModel):
    """Skill 调用输入"""

    skill_name: str = Field(
        ...,
        description="Skill 名称"
    )
    parameters: Dict[str, Any] = Field(
        ...,
        description="Skill 参数"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="调用上下文"
    )


class SkillResult(IDMixin, TimestampMixin):
    """Skill 执行结果"""

    skill_name: str = Field(
        description="Skill 名称"
    )
    input_hash: str = Field(
        description="输入哈希"
    )
    output: Any = Field(
        description="Skill 输出数据"
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
        description="结果元数据"
    )


class SkillManifest(BaseModel):
    """Skill 清单 - 所有可用 Skill 的注册表"""

    skills: List[SkillConfig] = Field(
        default_factory=list,
        description="已注册的 Skill 列表"
    )
    last_updated: datetime = Field(
        default_factory=datetime.now,
        description="最后更新时间"
    )

    def get_skill(self, name: str) -> Optional[SkillConfig]:
        """按名称获取 Skill 配置"""
        for skill in self.skills:
            if skill.name == name:
                return skill
        return None

    def get_skills_by_category(self, category: str) -> List[SkillConfig]:
        """按分类获取 Skill 列表"""
        return [s for s in self.skills if s.category == category]


# 导出
__all__ = [
    "SkillParameter",
    "SkillConfig",
    "SkillInput",
    "SkillResult",
    "SkillManifest"
]
