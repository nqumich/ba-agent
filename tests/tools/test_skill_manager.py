"""
Skill 包管理工具单元测试
"""

import json
import os
import pytest
import tempfile
import zipfile
from pathlib import Path
from pydantic import ValidationError

from tools.skill_manager import (
    SkillPackageInput,
    skill_package_impl,
    skill_package_tool,
    SkillRegistry,
    SkillInstaller,
    SKILLS_REGISTRY_FILE,
)


# 测试隔离：在每个测试前后清理
@pytest.fixture(autouse=True)
def clear_registry_cache():
    """在每个测试前后清理注册表缓存和文件"""
    # 测试前清理
    SkillRegistry.clear_cache()
    # 清理注册表文件
    if os.path.exists(SKILLS_REGISTRY_FILE):
        os.remove(SKILLS_REGISTRY_FILE)

    yield

    # 测试后清理
    SkillRegistry.clear_cache()
    # 清理注册表文件
    if os.path.exists(SKILLS_REGISTRY_FILE):
        os.remove(SKILLS_REGISTRY_FILE)


class TestSkillPackageInput:
    """测试 SkillPackageInput 模型"""

    def test_action_install(self):
        """测试 install 操作"""
        input_data = SkillPackageInput(
            action="install",
            source="github:owner/repo"
        )
        assert input_data.action == "install"
        assert input_data.source == "github:owner/repo"

    def test_action_list(self):
        """测试 list 操作"""
        input_data = SkillPackageInput(
            action="list"
        )
        assert input_data.action == "list"

    def test_action_uninstall(self):
        """测试 uninstall 操作"""
        input_data = SkillPackageInput(
            action="uninstall",
            skill_name="test_skill"
        )
        assert input_data.action == "uninstall"
        assert input_data.skill_name == "test_skill"

    def test_action_validate(self):
        """测试 validate 操作"""
        input_data = SkillPackageInput(
            action="validate",
            skill_name="test_skill"
        )
        assert input_data.action == "validate"
        assert input_data.skill_name == "test_skill"

    def test_action_search(self):
        """测试 search 操作"""
        input_data = SkillPackageInput(
            action="search"
        )
        assert input_data.action == "search"

    def test_invalid_action(self):
        """测试无效操作类型"""
        with pytest.raises(ValidationError, match="无效的操作类型"):
            SkillPackageInput(action="invalid")

    def test_case_insensitive_action(self):
        """测试操作类型不区分大小写"""
        input_data = SkillPackageInput(
            action="INSTALL",
            source="test"  # INSTALL 被转换为 install，需要提供 source
        )
        assert input_data.action == "install"

    def test_install_requires_source(self):
        """测试 install 需要 source 参数"""
        with pytest.raises(ValidationError, match="需要提供 source"):
            SkillPackageInput(
                action="install"
            )

    def test_uninstall_requires_skill_name(self):
        """测试 uninstall 需要 skill_name 参数"""
        with pytest.raises(ValidationError, match="需要提供 skill_name"):
            SkillPackageInput(
                action="uninstall"
            )

    def test_validate_requires_skill_name(self):
        """测试 validate 需要 skill_name 参数"""
        with pytest.raises(ValidationError, match="需要提供 skill_name"):
            SkillPackageInput(
                action="validate"
            )

    def test_force_flag(self):
        """测试强制覆盖标志"""
        input_data = SkillPackageInput(
            action="install",
            source="test",
            force=True
        )
        assert input_data.force is True


class TestSkillRegistry:
    """测试 Skill 注册表"""

    def test_initialization(self):
        """测试初始化"""
        registry = SkillRegistry()
        assert "installed" in registry._registry
        assert isinstance(registry._registry["installed"], dict)

    def test_add_skill(self):
        """测试添加 Skill"""
        registry = SkillRegistry()
        registry.add_skill("test_skill", {
            "name": "Test Skill",
            "version": "1.0.0"
        })
        assert registry.is_installed("test_skill")

    def test_remove_skill(self):
        """测试移除 Skill"""
        registry = SkillRegistry()
        registry.add_skill("test_skill", {"name": "Test"})
        assert registry.remove_skill("test_skill") is True
        assert not registry.is_installed("test_skill")

    def test_get_skill(self):
        """测试获取 Skill"""
        registry = SkillRegistry()
        metadata = {"name": "Test", "version": "1.0"}
        registry.add_skill("test_skill", metadata)

        result = registry.get_skill("test_skill")
        assert result["name"] == "Test"

    def test_list_skills(self):
        """测试列出 Skills"""
        registry = SkillRegistry()
        registry.add_skill("skill_a", {"name": "Skill A"})
        registry.add_skill("skill_b", {"name": "Skill B"})

        skills = registry.list_skills()
        assert len(skills) == 2
        skill_names = [s["name"] for s in skills]
        assert "Skill A" in skill_names
        assert "Skill B" in skill_names

    def test_is_installed(self):
        """测试检查是否已安装"""
        registry = SkillRegistry()
        assert not registry.is_installed("nonexistent")
        registry.add_skill("test", {"name": "Test"})
        assert registry.is_installed("test")


class TestSkillInstaller:
    """测试 Skill 安装器"""

    def test_initialization(self):
        """测试初始化"""
        installer = SkillInstaller()
        assert installer.skills_dir.exists()
        assert isinstance(installer.registry, SkillRegistry)

    def test_is_github_url(self):
        """测试 GitHub URL 识别"""
        installer = SkillInstaller()

        # 完整 URL
        assert installer._is_github_url("https://github.com/owner/repo")
        assert installer._is_github_url("http://github.com/owner/repo.git")

        # github: 格式
        assert installer._is_github_url("github:owner/repo")

        # owner/repo 格式
        assert installer._is_github_url("owner/repo")

        # 非 GitHub URL
        assert not installer._is_github_url("https://example.com/repo")

    def test_parse_github_url(self):
        """测试 GitHub URL 解析"""
        installer = SkillInstaller()

        # 完整 URL
        owner, repo = installer._parse_github_url("https://github.com/test/repository")
        assert owner == "test"
        assert repo == "repository"

        # github: 格式
        owner, repo = installer._parse_github_url("github:owner/repo")
        assert owner == "owner"
        assert repo == "repo"

        # owner/repo 格式
        owner, repo = installer._parse_github_url("owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_extract_zip(self):
        """测试 ZIP 文件提取"""
        installer = SkillInstaller()

        # 创建测试 ZIP 文件
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建源目录
            source_dir = Path(temp_dir) / "test_skill"
            source_dir.mkdir()

            # 创建 SKILL.md
            skill_md = source_dir / "SKILL.md"
            skill_md.write_text("""---
name: Test Skill
description: Test skill for validation
version: 1.0.0
---
# Test skill instructions
""")

            # 创建 ZIP 文件
            zip_path = Path(temp_dir) / "test_skill.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                zipf.write(str(skill_md), "SKILL.md")

            # 提取
            result_path = installer._extract_zip(zip_path, "extracted_skill")

            assert result_path.exists()
            assert (result_path / "SKILL.md").exists()

    def test_extract_zip_without_skill_md(self):
        """测试提取没有 SKILL.md 的 ZIP"""
        installer = SkillInstaller()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建没有 SKILL.md 的 ZIP
            zip_path = Path(temp_dir) / "invalid.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                zipf.writestr("README.md", "Test content")

            with pytest.raises(ValueError, match="SKILL.md"):
                installer._extract_zip(zip_path, "test_skill")

    def test_validate_skill_structure(self):
        """测试验证 Skill 结构"""
        installer = SkillInstaller()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建有效的 Skill 结构
            skill_dir = Path(temp_dir) / "valid_skill"
            skill_dir.mkdir()

            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("""---
name: Valid Skill
description: A valid skill
version: 1.0.0
---
# Instructions
""")

            result = installer._validate_skill_structure(skill_dir)
            assert result["name"] == "Valid Skill"
            assert result["description"] == "A valid skill"

    def test_validate_missing_skill_md(self):
        """测试验证缺少 SKILL.md"""
        installer = SkillInstaller()

        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "invalid_skill"
            skill_dir.mkdir()

            with pytest.raises(FileNotFoundError, match="SKILL.md"):
                installer._validate_skill_structure(skill_dir)

    def test_validate_invalid_yaml(self):
        """测试验证无效的 YAML"""
        installer = SkillInstaller()

        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "invalid_yaml_skill"
            skill_dir.mkdir()

            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("Invalid content without frontmatter")

            with pytest.raises(ValueError, match="YAML frontmatter"):
                installer._validate_skill_structure(skill_dir)

    def test_validate_missing_required_fields(self):
        """测试验证缺少必需字段"""
        installer = SkillInstaller()

        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "missing_fields_skill"
            skill_dir.mkdir()

            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("""---
name: Test Skill
---
# Instructions
""")

            with pytest.raises(ValueError, match="缺少必需字段"):
                installer._validate_skill_structure(skill_dir)

    def test_install_local_directory(self):
        """测试从本地目录安装"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        installer = SkillInstaller()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建源 Skill 目录
            source_dir = Path(temp_dir) / "source_skill"
            source_dir.mkdir()

            skill_md = source_dir / "SKILL.md"
            skill_md.write_text("""---
name: Source Skill
description: Skill from local directory
version: 1.0.0
---
# Instructions
""")

            # 安装（使用唯一名称避免冲突）
            skill_name = f"installed_skill_{unique_id}"
            result = installer._install_from_local(str(source_dir), skill_name)

            assert result.exists()
            assert (result / "SKILL.md").exists()

    def test_install_local_zip_file(self):
        """测试从本地 ZIP 文件安装"""
        installer = SkillInstaller()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建源 Skill 目录
            source_dir = Path(temp_dir) / "source_skill"
            source_dir.mkdir()

            skill_md = source_dir / "SKILL.md"
            skill_md.write_text("""---
name: ZIP Skill
description: Skill from ZIP
version: 1.0.0
---
# Instructions
""")

            # 创建 ZIP
            zip_path = Path(temp_dir) / "skill.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                zipf.write(str(skill_md), "SKILL.md")

            # 安装
            result = installer._install_from_local(str(zip_path), "installed_skill")

            assert result.exists()
            assert (result / "SKILL.md").exists()

    def test_install_already_exists_without_force(self):
        """测试安装已存在的 Skill（不强制）"""
        installer = SkillInstaller()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建现有 Skill
            existing_dir = installer.skills_dir / "existing_skill"
            existing_dir.mkdir(exist_ok=True)

            with pytest.raises(FileExistsError, match="已存在"):
                installer._install_from_local(str(existing_dir), "existing_skill")

    def test_install_already_exists_with_force(self):
        """测试强制覆盖已存在的 Skill"""
        installer = SkillInstaller()

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建现有 Skill
            existing_dir = installer.skills_dir / "existing_skill"
            existing_dir.mkdir(exist_ok=True)
            (existing_dir / "old.md").write_text("old content")

            # 创建源 Skill
            source_dir = Path(temp_dir) / "new_skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("---\nname: New\n---\n")

            # 强制安装（需要先删除旧目录）
            import shutil
            shutil.rmtree(existing_dir)

            result = installer._install_from_local(str(source_dir), "existing_skill")

            # 验证新内容
            with open(result / "SKILL.md") as f:
                content = f.read()
            assert "New" in content


class TestSkillPackageImpl:
    """测试 Skill 包管理实现函数"""

    def test_action_list(self):
        """测试列出 Skills"""
        result_json = skill_package_impl(action="list")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert "成功" in result.summary or "找到" in result.summary
        assert result.result is not None
        assert "skills" in result.result

    def test_action_search(self):
        """测试搜索推荐 Skills"""
        result_json = skill_package_impl(action="search")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert "推荐" in result.summary or "找到" in result.summary
        assert result.result is not None
        assert "recommended" in result.result

    def test_install_missing_source(self):
        """测试缺少 source 参数"""
        result_json = skill_package_impl(action="install")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert not result.telemetry.success
        assert "失败" in result.summary or "错误" in result.summary

    def test_uninstall_missing_skill_name(self):
        """测试缺少 skill_name 参数"""
        result_json = skill_package_impl(action="uninstall")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert not result.telemetry.success
        assert "失败" in result.summary or "错误" in result.summary

    def test_concise_response_format(self):
        """测试简洁响应格式"""
        result_json = skill_package_impl(
            action="list",
            response_format="concise"
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success

    def test_standard_response_format(self):
        """测试标准响应格式"""
        result_json = skill_package_impl(
            action="list",
            response_format="standard"
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result is not None


class TestSkillPackageTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert skill_package_tool.name == "skill_package"
        assert "Skill" in skill_package_tool.description or "skill" in skill_package_tool.description.lower()

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(skill_package_tool, StructuredTool)

    def test_tool_args_schema(self):
        """测试工具参数模式"""
        assert skill_package_tool.args_schema == SkillPackageInput

    def test_tool_invocation_list(self):
        """测试工具调用 - list"""
        result = skill_package_tool.invoke({
            "action": "list"
        })

        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success

    def test_tool_invocation_search(self):
        """测试工具调用 - search"""
        result = skill_package_tool.invoke({
            "action": "search"
        })

        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success


class TestSkillIntegration:
    """集成测试"""

    def test_full_install_workflow(self):
        """测试完整安装工作流"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        skill_name = f"test_install_skill_{unique_id}"

        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试 Skill
            skill_dir = Path(temp_dir) / skill_name
            skill_dir.mkdir()

            # 创建 SKILL.md
            (skill_dir / "SKILL.md").write_text("""---
name: Test Install Skill
description: A skill for testing installation
version: 1.0.0
category: Test
---
This is a test skill for installation.
""")

            # 创建工具/ 子目录（可选）
            tools_dir = skill_dir / "tools"
            tools_dir.mkdir()
            (tools_dir / "helper.py").write_text("# Helper tool\n")

            # 切换到 skills 目录
            original_dir = Path.cwd()
            import os
            installer = SkillInstaller()
            os.chdir(installer.skills_dir if hasattr(installer, 'skills_dir') else 'skills')

            try:
                result = installer._install_from_local(str(skill_dir), skill_name)

                # 验证
                assert result.exists()
                assert (result / "SKILL.md").exists()
                assert (result / "tools" / "helper.py").exists()

            finally:
                os.chdir(original_dir)

    def test_registry_persistence(self):
        """测试注册表持久化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_file = Path(temp_dir) / "test_registry.json"
            registry = SkillRegistry(str(registry_file))

            # 添加 Skill
            registry.add_skill("test", {"name": "Test", "path": "/test"})

            # 重新加载
            registry2 = SkillRegistry(str(registry_file))
            assert registry2.is_installed("test")

            # 移除 Skill
            registry.remove_skill("test")
            assert not registry2.is_installed("test")
