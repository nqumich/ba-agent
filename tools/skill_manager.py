"""
Skill 包管理工具

支持从外部源（GitHub、本地文件、URL）安装和配置 Skills
"""

import os
import json
import shutil
import zipfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from langchain_core.tools import StructuredTool

from config import get_config
from models.tool_output import ToolOutput, ToolTelemetry, ResponseFormat


# Skill 注册表文件
SKILLS_REGISTRY_FILE = "config/skills_registry.json"


class SkillPackageInput(BaseModel):
    """Skill 包管理工具的输入参数"""

    action: str = Field(
        ...,
        description="操作类型: install, uninstall, list, search, validate"
    )
    source: Optional[str] = Field(
        default=None,
        description="Skill 源 (GitHub URL, 本地路径, 或 Skill 名称)"
    )
    skill_name: Optional[str] = Field(
        default=None,
        description="Skill 名称（用于 uninstall 或 validate）"
    )
    force: Optional[bool] = Field(
        default=False,
        description="强制覆盖已存在的 Skill"
    )
    response_format: Optional[str] = Field(
        default="standard",
        description="响应格式: concise, standard, detailed"
    )

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        """验证操作类型"""
        valid_actions = ["install", "uninstall", "list", "search", "validate"]
        v = v.lower().strip()
        if v not in valid_actions:
            raise ValueError(
                f"无效的操作类型 '{v}'。"
                f"支持的操作: {', '.join(valid_actions)}"
            )
        return v

    @model_validator(mode='after')
    def validate_action_params(self) -> "SkillPackageInput":
        """验证操作所需参数"""
        if self.action == "install" and not self.source:
            raise ValueError("install 操作需要提供 source 参数")
        if self.action == "uninstall" and not self.skill_name:
            raise ValueError("uninstall 操作需要提供 skill_name 参数")
        if self.action == "validate" and not self.skill_name:
            raise ValueError("validate 操作需要提供 skill_name 参数")
        return self


class SkillRegistry:
    """Skill 注册表管理器"""

    # 类级别的注册表缓存（用于测试隔离）
    # 使用 registry_file 作为 key，共享同一个文件的所有实例
    _class_registry_cache: Dict[str, Dict[str, Any]] = {}

    def __init__(self, registry_file: str = SKILLS_REGISTRY_FILE):
        self.registry_file = registry_file
        # 从缓存加载或从文件加载
        if registry_file in SkillRegistry._class_registry_cache:
            self._registry = SkillRegistry._class_registry_cache[registry_file].copy()
        else:
            self._registry = self._load_registry()
            SkillRegistry._class_registry_cache[registry_file] = self._registry.copy()

    def _load_registry(self) -> Dict[str, Any]:
        """加载注册表"""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"installed": {}, "last_update": None}

    def _save_registry(self) -> None:
        """保存注册表"""
        os.makedirs(os.path.dirname(os.path.abspath(self.registry_file)), exist_ok=True)
        self._registry["last_update"] = __import__("datetime").datetime.now().isoformat()
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self._registry, f, indent=2, ensure_ascii=False)

        # 更新缓存
        SkillRegistry._class_registry_cache[self.registry_file] = self._registry.copy()

    def add_skill(self, skill_name: str, metadata: Dict[str, Any]) -> None:
        """添加 Skill 到注册表"""
        if skill_name not in self._registry["installed"]:
            self._registry["installed"][skill_name] = {}
        self._registry["installed"][skill_name].update(metadata)
        self._save_registry()

    def remove_skill(self, skill_name: str) -> bool:
        """从注册表移除 Skill"""
        if skill_name in self._registry["installed"]:
            del self._registry["installed"][skill_name]
            self._save_registry()
            return True
        return False

    def get_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """获取 Skill 信息"""
        return self._registry["installed"].get(skill_name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """列出所有已安装的 Skills"""
        skills = []
        for name, metadata in self._registry["installed"].items():
            skills.append({
                "name": name,
                **metadata
            })
        return sorted(skills, key=lambda x: x["name"])

    def is_installed(self, skill_name: str) -> bool:
        """检查 Skill 是否已安装"""
        return skill_name in self._registry["installed"]

    @classmethod
    def clear_cache(cls) -> None:
        """清除缓存（用于测试隔离）"""
        cls._class_registry_cache.clear()


class SkillInstaller:
    """Skill 安装器"""

    # 支持的 Skill 源
    GITHUB_PATTERNS = [
        r"^https?://github\.com/[\w-]+/[\w-]+(?:\.git)?$",
        r"^github:([\w-]+)/([\w-]+)$",
        r"^([\w-]+)/([\w-]+)$",  # 简短格式 owner/repo
    ]

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(exist_ok=True)
        self.registry = SkillRegistry()

    def _is_github_url(self, source: str) -> bool:
        """检查是否为 GitHub URL"""
        import urllib.parse

        # 特殊处理 github:owner/repo 格式
        if source.startswith("github:"):
            return True

        # 检查是否匹配 GitHub URL 模式
        for pattern in self.GITHUB_PATTERNS:
            if self._match_github_pattern(source, pattern):
                # 如果是完整 URL，检查协议
                parsed = urllib.parse.urlparse(source)
                # 允许: http, https, 或 owner/repo 格式(无协议)
                if parsed.scheme in ["http", "https", ""]:
                    return True
        return False

    def _match_github_pattern(self, source: str, pattern: str) -> bool:
        """匹配 GitHub 模式"""
        import re
        return re.match(pattern, source) is not None

    def _parse_github_url(self, source: str) -> tuple[str, str]:
        """解析 GitHub URL 获取 owner/repo"""
        import re
        import urllib.parse

        # 标准完整 URL
        parsed = urllib.parse.urlparse(source)
        if parsed.netloc == "github.com":
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) >= 2:
                return path_parts[0], path_parts[1].replace(".git", "")

        # github:owner/repo 格式
        match = re.match(r"^github:([\w-]+)/([\w-]+)$", source)
        if match:
            return match.group(1), match.group(2)

        # owner/repo 简短格式
        match = re.match(r"^([\w-]+)/([\w-]+)$", source)
        if match:
            return match.group(1), match.group(2)

        raise ValueError(f"无法解析 GitHub URL: {source}")

    def _clone_from_github(self, source: str, skill_name: str) -> Path:
        """从 GitHub 克隆 Skill"""
        owner, repo = self._parse_github_url(source)

        # 目标路径
        target_path = self.skills_dir / skill_name

        if target_path.exists():
            raise FileExistsError(f"Skill 目录已存在: {target_path}")

        # 克隆仓库
        clone_url = f"https://github.com/{owner}/{repo}.git"
        try:
            import subprocess
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(target_path)],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git 克隆失败: {e.stderr}")

        return target_path

    def _install_from_local(self, source: str, skill_name: str) -> Path:
        """从本地路径安装 Skill"""
        source_path = Path(source)

        if not source_path.exists():
            raise FileNotFoundError(f"源路径不存在: {source_path}")

        # 如果是 ZIP 文件，解压
        if source_path.suffix == ".zip":
            return self._extract_zip(source_path, skill_name)

        # 如果是目录，复制
        if source_path.is_dir():
            target_path = self.skills_dir / skill_name
            if target_path.exists():
                raise FileExistsError(f"Skill 目录已存在: {target_path}")
            shutil.copytree(source_path, target_path)
            return target_path

        raise ValueError(f"不支持的本地源类型: {source_path}")

    def _extract_zip(self, zip_path: Path, skill_name: str) -> Path:
        """从 ZIP 文件提取 Skill"""
        target_path = self.skills_dir / skill_name
        target_path.mkdir(exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 验证 ZIP 结构
            file_list = zip_ref.namelist()
            if not any("SKILL.md" == f.split("/")[-1] for f in file_list):
                # 检查根目录是否有 SKILL.md
                root_files = [f for f in file_list if "/" not in f]
                if "SKILL.md" not in root_files:
                    raise ValueError("ZIP 文件必须包含 SKILL.md 文件")

            # 解压
            zip_ref.extractall(target_path)

        return target_path

    def _validate_skill_structure(self, skill_path: Path) -> Dict[str, Any]:
        """验证 Skill 结构"""
        skill_md_path = skill_path / "SKILL.md"

        if not skill_md_path.exists():
            raise FileNotFoundError(f"SKILL.md 文件不存在: {skill_md_path}")

        # 读取并解析 SKILL.md
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 解析 YAML frontmatter
        if not content.startswith("---"):
            raise ValueError("SKILL.md 必须以 YAML frontmatter 开头（---）")

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("SKILL.md 格式错误：需要 YAML frontmatter")

        import yaml
        try:
            metadata = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            raise ValueError(f"YAML frontmatter 解析失败: {e}")

        # 验证必需字段
        required_fields = ["name", "description"]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"SKILL.md 缺少必需字段: {field}")

        return metadata

    def install(self, source: str, skill_name: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        安装 Skill

        Args:
            source: Skill 源（GitHub URL、本地路径、ZIP 文件）
            skill_name: 指定的 Skill 名称（可选）
            force: 是否强制覆盖

        Returns:
            安装的 Skill 信息
        """
        # 确定 Skill 名称
        if skill_name:
            pass  # 使用指定的名称
        elif self._is_github_url(source):
            owner, repo = self._parse_github_url(source)
            skill_name = repo.replace("-", "_").replace(" ", "_").lower()
        elif source.endswith(".zip"):
            skill_name = Path(source).stem.replace("-", "_")
        else:
            skill_name = Path(source).name.replace("-", "_")

        # 检查是否已安装
        if not force and self.registry.is_installed(skill_name):
            raise ValueError(f"Skill '{skill_name}' 已安装。使用 force=True 强制重装")

        # 安装
        if self._is_github_url(source):
            skill_path = self._clone_from_github(source, skill_name)
        else:
            skill_path = self._install_from_local(source, skill_name)

        # 验证结构
        metadata = self._validate_skill_structure(skill_path)

        # 添加到注册表
        self.registry.add_skill(skill_name, {
            **metadata,
            "path": str(skill_path),
            "installed_at": __import__("datetime").datetime.now().isoformat(),
            "source": source
        })

        return {
            "name": skill_name,
            "metadata": metadata,
            "path": str(skill_path)
        }

    def uninstall(self, skill_name: str, remove_files: bool = False) -> Dict[str, Any]:
        """
        卸载 Skill

        Args:
            skill_name: Skill 名称
            remove_files: 是否删除文件

        Returns:
            卸载结果
        """
        skill_info = self.registry.get_skill(skill_name)
        if not skill_info:
            raise ValueError(f"Skill '{skill_name}' 未安装")

        # 删除文件
        if remove_files and "path" in skill_info:
            skill_path = Path(skill_info["path"])
            if skill_path.exists():
                shutil.rmtree(skill_path)

        # 从注册表移除
        self.registry.remove_skill(skill_name)

        return {
            "name": skill_name,
            "removed": True
        }

    def validate(self, skill_name: str) -> Dict[str, Any]:
        """
        验证已安装的 Skill

        Args:
            skill_name: Skill 名称

        Returns:
            验证结果
        """
        skill_info = self.registry.get_skill(skill_name)
        if not skill_info:
            raise ValueError(f"Skill '{skill_name}' 未安装")

        skill_path = Path(skill_info["path"])
        if not skill_path.exists():
            return {
                "name": skill_name,
                "valid": False,
                "error": "Skill 目录不存在"
            }

        try:
            metadata = self._validate_skill_structure(skill_path)
            return {
                "name": skill_name,
                "valid": True,
                "metadata": metadata
            }
        except Exception as e:
            return {
                "name": skill_name,
                "valid": False,
                "error": str(e)
            }


def skill_package_impl(
    action: str,
    source: Optional[str] = None,
    skill_name: Optional[str] = None,
    force: bool = False,
    response_format: str = "standard"
) -> str:
    """
    Skill 包管理实现函数

    Args:
        action: 操作类型
        source: Skill 源
        skill_name: Skill 名称
        force: 是否强制覆盖
        response_format: 响应格式

    Returns:
        操作结果 JSON 字符串
    """
    import time
    start_time = time.time()
    telemetry = ToolTelemetry(tool_name="skill_package")

    try:
        installer = SkillInstaller()

        if action == "list":
            # 列出已安装的 Skills
            skills = installer.registry.list_skills()
            telemetry.latency_ms = (time.time() - start_time) * 1000
            telemetry.success = True

            summary = f"找到 {len(skills)} 个已安装的 Skill"
            if skills:
                skill_names = [s["name"] for s in skills]
                summary += f": {', '.join(skill_names)}"

            output = ToolOutput(
                result={"skills": skills} if response_format != "concise" else None,
                summary=summary,
                observation=f"Observation: {summary}\nStatus: Success",
                telemetry=telemetry,
                response_format=ResponseFormat(response_format)
            )

        elif action == "install":
            # 安装 Skill
            if not source:
                raise ValueError("install 操作需要提供 source 参数")

            result = installer.install(source, force=force)
            telemetry.latency_ms = (time.time() - start_time) * 1000
            telemetry.success = True

            summary = f"Skill '{result['name']}' 安装成功"
            if "metadata" in result:
                summary += f": {result['metadata'].get('description', '')}"

            output = ToolOutput(
                result=result if response_format != "concise" else None,
                summary=summary,
                observation=f"Observation: {summary}\nStatus: Success",
                telemetry=telemetry,
                response_format=ResponseFormat(response_format)
            )

        elif action == "uninstall":
            # 卸载 Skill
            if not skill_name:
                raise ValueError("uninstall 操作需要提供 skill_name 参数")

            result = installer.uninstall(skill_name, remove_files=True)
            telemetry.latency_ms = (time.time() - start_time) * 1000
            telemetry.success = True

            summary = f"Skill '{skill_name}' 卸载成功"

            output = ToolOutput(
                result=result if response_format != "concise" else None,
                summary=summary,
                observation=f"Observation: {summary}\nStatus: Success",
                telemetry=telemetry,
                response_format=ResponseFormat(response_format)
            )

        elif action == "validate":
            # 验证 Skill
            if not skill_name:
                raise ValueError("validate 操作需要提供 skill_name 参数")

            result = installer.validate(skill_name)
            telemetry.latency_ms = (time.time() - start_time) * 1000
            telemetry.success = True

            status = "有效" if result["valid"] else "无效"
            summary = f"Skill '{skill_name}' {status}"
            if not result["valid"]:
                summary += f": {result.get('error', '未知错误')}"

            output = ToolOutput(
                result=result if response_format != "concise" else None,
                summary=summary,
                observation=f"Observation: {summary}\nStatus: Success",
                telemetry=telemetry,
                response_format=ResponseFormat(response_format)
            )

        elif action == "search":
            # 搜索 Skills（这里返回简化的示例）
            telemetry.latency_ms = (time.time() - start_time) * 1000
            telemetry.success = True

            # 示例：推荐一些有用的 Skills
            recommended = [
                {
                    "name": "python-analyzer",
                    "description": "Python 代码分析和优化建议",
                    "source": "https://github.com/example/python-analyzer-skill",
                    "category": "Development"
                },
                {
                    "name": "data-viz",
                    "description": "数据可视化和图表生成",
                    "source": "https://github.com/example/data-viz-skill",
                    "category": "Analysis"
                }
            ]

            summary = f"找到 {len(recommended)} 个推荐 Skills"

            output = ToolOutput(
                result={"recommended": recommended} if response_format != "concise" else None,
                summary=summary,
                observation=f"Observation: {summary}\nStatus: Success",
                telemetry=telemetry,
                response_format=ResponseFormat(response_format)
            )

        else:
            raise ValueError(f"不支持的操作: {action}")

        return output.model_dump_json()

    except Exception as e:
        telemetry.latency_ms = (time.time() - start_time) * 1000
        telemetry.success = False
        telemetry.error_code = type(e).__name__
        telemetry.error_message = str(e)

        output = ToolOutput(
            summary=f"操作失败: {str(e)}",
            observation=f"Observation: 操作失败 - {str(e)}\nStatus: Error",
            telemetry=telemetry,
            response_format=ResponseFormat(response_format)
        )

        return output.model_dump_json()


# 创建 LangChain 工具
skill_package_tool = StructuredTool.from_function(
    func=skill_package_impl,
    name="skill_package",
    description="""
管理 Skill 包（安装、卸载、列表、验证）。

支持的操作：
- install: 从外部源安装 Skill
- uninstall: 卸载已安装的 Skill
- list: 列出所有已安装的 Skills
- validate: 验证 Skill 结构
- search: 搜索推荐的外部 Skills

支持的 Skill 源：
- GitHub 仓库: github:owner/repo 或完整 URL
- 本地 ZIP 文件: /path/to/skill.zip
- 本地目录: /path/to/skill_folder

使用场景：
- 安装 Skill: skill_package(action="install", source="github:example/analysis-skill")
- 列出 Skills: skill_package(action="list")
- 验证 Skill: skill_package(action="validate", skill_name="analysis")
- 卸载 Skill: skill_package(action="uninstall", skill_name="analysis")

参数说明：
- action: 操作类型（必需）
- source: Skill 源（install 时必需）
- skill_name: Skill 名称（uninstall/validate 时必需）
- force: 强制覆盖已安装的 Skill（默认 false）
""",
    args_schema=SkillPackageInput
)


__all__ = [
    "SkillPackageInput",
    "skill_package_impl",
    "skill_package_tool",
    "SkillRegistry",
    "SkillInstaller",
]
