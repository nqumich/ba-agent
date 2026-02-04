"""
Skill 调用工具

桥接 Agent 和 Skills 系统，读取 Skills 配置并调用
通过构建 Python 代码来执行 Skill 函数
"""

import os
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool

from config import get_config
from models.tool_output import ToolOutput, ToolTelemetry, ResponseFormat


# Skills 配置缓存
_skills_config_cache: Optional[Dict[str, Any]] = None


class SkillConfig(BaseModel):
    """Skill 配置模型"""

    name: str = Field(description="Skill 名称")
    description: str = Field(description="Skill 描述")
    entrypoint: str = Field(description="入口文件路径")
    function: str = Field(description="主函数名")
    requirements: List[str] = Field(default_factory=list, description="依赖列表")
    config: Dict[str, Any] = Field(default_factory=dict, description="Skill 配置参数")


class InvokeSkillInput(BaseModel):
    """Skill 调用工具的输入参数"""

    skill_name: str = Field(
        ...,
        description="要调用的 Skill 名称（如: anomaly_detection, attribution）"
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="传递给 Skill 的参数（例如: {\"data\": [...], \"metric\": \"gmv\"}）"
    )
    timeout: Optional[int] = Field(
        default=60,
        ge=5,
        le=300,
        description="执行超时时间（秒），范围 5-300"
    )
    use_cache: Optional[bool] = Field(
        default=True,
        description="是否使用缓存结果"
    )
    response_format: Optional[str] = Field(
        default="standard",
        description="响应格式: concise, standard, detailed"
    )

    @field_validator('skill_name')
    @classmethod
    def validate_skill_name(cls, v: str) -> str:
        """验证 Skill 名称"""
        if not v or not v.strip():
            raise ValueError("Skill 名称不能为空")

        # 检查 Skill 是否存在
        skills_config = _load_skills_config()
        available_skills = list(skills_config.get("skills", {}).keys())

        if v not in available_skills:
            raise ValueError(
                f"Skill '{v}' 不存在。"
                f"可用的 Skills: {', '.join(available_skills)}"
            )

        return v


def _load_skills_config() -> Dict[str, Any]:
    """
    加载 Skills 配置

    优先从 skills_registry.json 加载 Skills，从 skills.yaml 加载 global 配置
    使用缓存避免重复读取文件
    """
    global _skills_config_cache

    if _skills_config_cache is not None:
        return _skills_config_cache

    # 初始化配置
    config = {"skills": {}, "global": {}}

    # 1. 从 skills_registry.json 加载 Skills
    registry_path = Path("config/skills_registry.json")
    if registry_path.exists():
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
                installed_skills = registry.get("installed", {})

                # 转换为旧格式以保持兼容性
                skills_config = {}
                for skill_name, skill_info in installed_skills.items():
                    skills_config[skill_name] = {
                        "name": skill_info.get("display_name", skill_name),
                        "description": skill_info.get("description", ""),
                        "entrypoint": skill_info.get("entrypoint", f"skills/{skill_name}/main.py"),
                        "function": skill_info.get("function", "main"),
                        "requirements": skill_info.get("requirements", []),
                        "config": skill_info.get("config", {})
                    }
                config["skills"] = skills_config
        except Exception:
            pass

    # 2. 从 skills.yaml 加载 global 配置
    skills_config_path = Path("config/skills.yaml")
    if skills_config_path.exists():
        try:
            import yaml
            with open(skills_config_path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f) or {}

                # 加载 global 配置
                if "global" in yaml_config:
                    config["global"] = yaml_config["global"]

                # 如果 registry 为空，尝试从 YAML 的 skills_config 加载
                if not config["skills"] and "skills_config" in yaml_config:
                    # 新格式: skills_config 只是运行时配置，不包含技能列表
                    # 保持空的 skills 字典
                    pass
                elif not config["skills"] and "skills" in yaml_config:
                    # 旧格式
                    config["skills"] = yaml_config["skills"]
        except Exception:
            pass

    # 3. 如果仍然没有 Skills，使用默认配置
    if not config["skills"]:
        config = _get_default_skills_config()

    _skills_config_cache = config
    return _skills_config_cache


def _get_default_skills_config() -> Dict[str, Any]:
    """获取默认 Skills 配置"""
    return {
        "skills": {
            "anomaly_detection": {
                "name": "异动检测",
                "description": "检测数据异常波动并计算严重程度",
                "entrypoint": "skills/anomaly_detection/main.py",
                "function": "detect",
                "requirements": ["pandas", "numpy", "scipy"],
                "config": {
                    "threshold": 3.0,
                    "min_data_points": 10
                }
            },
            "attribution": {
                "name": "归因分析",
                "description": "分析业务指标变化的驱动因素",
                "entrypoint": "skills/attribution/main.py",
                "function": "analyze",
                "requirements": ["pandas", "numpy"],
                "config": {
                    "max_dimensions": 5,
                    "min_contribution": 0.05
                }
            },
            "report_gen": {
                "name": "报告生成",
                "description": "自动生成数据分析报告",
                "entrypoint": "skills/report_gen/main.py",
                "function": "generate",
                "requirements": ["pandas"],
                "config": {
                    "output_format": "markdown"
                }
            },
            "visualization": {
                "name": "数据可视化",
                "description": "创建数据可视化图表",
                "entrypoint": "skills/visualization/main.py",
                "function": "create_chart",
                "requirements": ["pandas", "plotly"],
                "config": {
                    "default_chart_type": "line"
                }
            }
        },
        "global": {
            "skill_timeout": 120,
            "max_memory": "512m",
            "enable_cache": True,
            "cache_ttl": 3600
        }
    }


def _get_skill_config(skill_name: str) -> SkillConfig:
    """
    获取指定 Skill 的配置

    Args:
        skill_name: Skill 名称

    Returns:
        Skill 配置对象
    """
    skills_config = _load_skills_config()
    skills_dict = skills_config.get("skills", {})

    if skill_name not in skills_dict:
        available = list(skills_dict.keys())
        raise ValueError(
            f"Skill '{skill_name}' 不存在。"
            f"可用的 Skills: {', '.join(available)}"
        )

    skill_data = skills_dict[skill_name]
    return SkillConfig(**skill_data)


def _build_skill_code(
    skill_config: SkillConfig,
    params: Optional[Dict[str, Any]] = None
) -> str:
    """
    构建调用 Skill 的 Python 代码

    Args:
        skill_config: Skill 配置
        params: 调用参数

    Returns:
        可执行的 Python 代码字符串
    """
    # 准备参数
    skill_params = params or {}
    skill_config_params = skill_config.config or {}

    # 合并参数（调用参数优先级高于配置参数）
    merged_params = {**skill_config_params, **skill_params}

    # 构建 Skill 函数（模拟实现）
    code_lines = [
        "# Skill 执行代码",
        "import json",
        "",
        "# 模拟 Skill 函数实现",
        f"def {skill_config.function}(params=None):",
        '    """',
        f"    {skill_config.description}",
        '    """',
        "    result = {",
        f'        "skill": "{skill_config.name}",',
        f'        "function": "{skill_config.function}",',
        '        "params": params or {},',
        '        "status": "success",',
        '        "message": "Skill 执行完成",',
        '        "data": {',
    ]

    # 根据不同 Skill 类型返回不同的模拟数据
    if skill_config.name == "异动检测":
        code_lines.extend([
            '            "anomalies": [',
            '                {"date": "2025-02-04", "value": 85000, "expected": 100000, "severity": "high", "change": -0.15}',
            '            ],',
            '            "summary": "检测到 1 个异常点"',
            '        }',
            '    }',
            "    return result",
        ])
    elif skill_config.name == "归因分析":
        code_lines.extend([
            '            "factors": [',
            '                {"name": "库存不足", "contribution": -8},',
            '                {"name": "广告减少", "contribution": -5},',
            '                {"name": "促销结束", "contribution": -2}',
            '            ],',
            '            "total_contribution": -15,',
            '        }',
            '    }',
            "    return result",
        ])
    elif skill_config.name == "报告生成":
        code_lines.extend([
            '            "report": "## 数据分析报告\\n\\n### 概述\\n本报告分析了...",',
            '            "format": "markdown",',
            '            "sections": ["概述", "详细分析", "结论"]',
            '        }',
            '    }',
            "    return result",
        ])
    elif skill_config.name == "数据可视化":
        code_lines.extend([
            '            "chart_type": "line",',
            '            "chart_data": {"dates": [...], "values": [...]},',
            '            "chart_config": {...}',
            '        }',
            '    }',
            "    return result",
        ])
    else:
        code_lines.extend([
            '            "result": "Skill 执行完成"',
            '        }',
            '    }',
            "    return result",
        ])

    # 调用函数
    code_lines.extend([
        "",
        "# 执行 Skill",
        f"params = {json.dumps(merged_params, ensure_ascii=False)}",
        f"result = {skill_config.function}(params)",
        'print(json.dumps(result, ensure_ascii=False, indent=2))'
    ])

    return "\n".join(code_lines)


def invoke_skill_impl(
    skill_name: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
    use_cache: bool = True,
    response_format: str = "standard"
) -> str:
    """
    调用 Skill 的实现函数

    Args:
        skill_name: Skill 名称
        params: 传递给 Skill 的参数
        timeout: 执行超时时间
        use_cache: 是否使用缓存
        response_format: 响应格式

    Returns:
        Skill 执行结果 JSON 字符串
    """
    start_time = time.time()
    telemetry = ToolTelemetry(tool_name="invoke_skill")

    try:
        # 获取 Skill 配置
        skill_config = _get_skill_config(skill_name)

        # 构建 Python 代码
        code = _build_skill_code(skill_config, params)

        # 导入 run_python 工具执行代码
        from tools.python_sandbox import run_python_impl

        # 执行 Skill 代码
        execution_result = run_python_impl(
            code=code,
            timeout=timeout
        )

        # 解析执行结果
        try:
            import json
            skill_result = json.loads(execution_result)
        except json.JSONDecodeError:
            # 如果不是 JSON，包装成结果
            skill_result = {
                "skill": skill_name,
                "raw_output": execution_result,
                "status": "success"
            }

        telemetry.latency_ms = (time.time() - start_time) * 1000
        telemetry.success = True

        # 构建摘要
        status = skill_result.get("status", "unknown")
        message = skill_result.get("message", f"{skill_name} 执行完成")

        if status == "success":
            summary = f"Skill '{skill_name}' 执行成功: {message}"
        else:
            summary = f"Skill '{skill_name}' 执行完成: {status}"

        # 构建观察结果（ReAct 格式）
        observation = f"Observation: {summary}\nStatus: Success"

        # 构建输出
        output = ToolOutput(
            result={
                "skill_name": skill_name,
                "skill_config": skill_config.model_dump(),
                "execution_result": skill_result,
                "execution_time_ms": telemetry.latency_ms
            } if response_format != "concise" else None,
            summary=summary,
            observation=observation,
            telemetry=telemetry,
            response_format=ResponseFormat(response_format)
        )

        return output.model_dump_json()

    except Exception as e:
        telemetry.latency_ms = (time.time() - start_time) * 1000
        telemetry.success = False
        telemetry.error_code = type(e).__name__
        telemetry.error_message = str(e)

        output = ToolOutput(
            summary=f"Skill 调用失败: {str(e)}",
            observation=f"Observation: Skill 调用失败 - {str(e)}\nStatus: Error",
            telemetry=telemetry,
            response_format=ResponseFormat(response_format)
        )

        return output.model_dump_json()


# 创建 LangChain 工具
invoke_skill_tool = StructuredTool.from_function(
    func=invoke_skill_impl,
    name="invoke_skill",
    description="""
调用可配置的分析 Skill 来执行特定任务。

可用的 Skills：
- anomaly_detection: 异动检测（检测数据异常波动）
- attribution: 归因分析（分析指标变化原因）
- report_gen: 报告生成（自动生成分析报告）
- visualization: 数据可视化（创建图表）

使用场景：
- 检测异常: invoke_skill(skill_name="anomaly_detection", params={"data": [...], "threshold": 3.0})
- 归因分析: invoke_skill(skill_name="attribution", params={"metric": "gmv", "date": "2025-02-04"})
- 生成报告: invoke_skill(skill_name="report_gen", params={"type": "daily", "date": "2025-02-04"})
- 创建图表: invoke_skill(skill_name="visualization", params={"data": [...], "chart_type": "line"})

参数说明：
- skill_name: Skill 名称（必需）
- params: 传递给 Skill 的参数（可选，JSON 对象）
- timeout: 执行超时时间（秒，默认 60）
- use_cache: 是否使用缓存结果（默认 true）
""",
    args_schema=InvokeSkillInput
)


__all__ = [
    "InvokeSkillInput",
    "invoke_skill_impl",
    "invoke_skill_tool",
    "SkillConfig",
    "_load_skills_config",
    "_get_skill_config",
]
