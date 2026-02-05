"""
Integration tests for SkillActivator.

Tests skill activation, message formatting, and context modifiers.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from backend.skills.activator import SkillActivator, SkillActivationError
from backend.skills.loader import SkillLoader
from backend.skills.registry import SkillRegistry


@pytest.fixture
def temp_skills_dir():
    """Create a temporary skills directory for testing."""
    temp_dir = tempfile.mkdtemp()
    skills_path = Path(temp_dir)
    yield skills_path
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_skills(temp_skills_dir):
    """Create sample skills for testing."""
    # Regular skill
    skill1_dir = temp_skills_dir / "anomaly_detection"
    skill1_dir.mkdir()
    (skill1_dir / "SKILL.md").write_text(
        """---
name: anomaly_detection
display_name: "异动检测"
description: "检测数据中的异常波动并分析可能原因"
version: "1.0.0"
category: "Analysis"
allowed_tools: "Read,Write,Bash(python:*)"
tags:
  - anomaly
  - detection
examples:
  - "今天GMV有什么异常？"
---

# 异动检测分析 Skill

## 描述

检测数据中的异常波动并分析可能原因。

## 分析流程

1. 获取数据
2. 选择检测方法
3. 分析结果
"""
    )

    # Mode skill
    skill2_dir = temp_skills_dir / "dev_mode"
    skill2_dir.mkdir()
    (skill2_dir / "SKILL.md").write_text(
        """---
name: dev_mode
display_name: "开发模式"
description: "开发辅助模式"
version: "1.0.0"
mode: true
category: "Development"
---

# 开发模式

这是一个开发辅助模式。
"""
    )

    # Skill with model override
    skill3_dir = temp_skills_dir / "visualization"
    skill3_dir.mkdir()
    (skill3_dir / "SKILL.md").write_text(
        """---
name: visualization
display_name: "数据可视化"
description: "自动生成ECharts可视化代码"
version: "1.0.0"
model: "claude-3-5-sonnet-20241022"
---

# 可视化 Skill
"""
    )

    return temp_skills_dir


@pytest.fixture
def loader(sample_skills):
    """Create a SkillLoader for testing."""
    return SkillLoader([sample_skills])


@pytest.fixture
def registry(loader):
    """Create a SkillRegistry for testing."""
    return SkillRegistry(loader)


@pytest.fixture
def activator(loader, registry):
    """Create a SkillActivator for testing."""
    return SkillActivator(loader, registry)


class TestSkillActivator:
    """Test SkillActivator class."""

    def test_init(self, loader, registry):
        """Test activator initialization."""
        activator = SkillActivator(loader, registry)
        assert activator.loader is loader
        assert activator.registry is registry
        assert activator.formatter is not None

    def test_activate_skill_basic(self, activator):
        """Test basic skill activation."""
        messages, context = activator.activate_skill("anomaly_detection")

        # Should return 2 messages (metadata + instructions)
        assert len(messages) == 3  # metadata + instructions + permissions

        # Check metadata message
        metadata_msg = messages[0]
        assert metadata_msg["role"] == "user"
        assert metadata_msg["isMeta"] is False
        assert "异动检测" in metadata_msg["content"]
        assert "anomaly_detection" in metadata_msg["content"]

        # Check instruction message
        instruction_msg = messages[1]
        assert instruction_msg["role"] == "user"
        assert instruction_msg["isMeta"] is True
        assert "异动检测分析 Skill" in instruction_msg["content"]
        assert "分析流程" in instruction_msg["content"]

        # Check permissions message
        permissions_msg = messages[2]
        assert permissions_msg["role"] == "user"
        assert permissions_msg["content"]["type"] == "command_permissions"
        assert permissions_msg["content"]["allowed_tools"] == ["Read", "Write", "Bash(python:*)"]

        # Check context modifier
        assert context["allowed_tools"] == ["Read", "Write", "Bash(python:*)"]

    def test_activate_skill_without_permissions(self, activator):
        """Test activating skill without allowed_tools."""
        messages, context = activator.activate_skill("dev_mode")

        # Should return 2 messages (metadata + instructions, no permissions)
        assert len(messages) == 2

        # Check no permissions message
        # Content can be string or dict, so check properly
        for msg in messages:
            if isinstance(msg["content"], dict):
                assert msg["content"].get("type") != "command_permissions"

        # Check context has no allowed_tools
        assert "allowed_tools" not in context

    def test_activate_skill_with_model_override(self, activator):
        """Test activating skill with model override."""
        messages, context = activator.activate_skill("visualization")

        # Check context has model override
        assert context["model"] == "claude-3-5-sonnet-20241022"

    def test_activate_skill_not_found(self, activator):
        """Test activating non-existent skill."""
        with pytest.raises(SkillActivationError, match="not found"):
            activator.activate_skill("nonexistent")

    def test_get_skill_info(self, activator):
        """Test getting skill debug information."""
        info = activator.get_skill_info("anomaly_detection")

        assert "Skill: anomaly_detection" in info
        assert "Display Name: 异动检测" in info
        assert "Category: Analysis" in info
        assert "Version: 1.0.0" in info
        assert "Allowed Tools: Read,Write,Bash(python:*)" in info

    def test_get_skill_info_not_found(self, activator):
        """Test getting info for non-existent skill."""
        with pytest.raises(SkillActivationError, match="not found"):
            activator.get_skill_info("nonexistent")

    def test_list_available_skills(self, activator):
        """Test listing all available skills."""
        skills = activator.list_available_skills()
        assert len(skills) == 3
        assert "anomaly_detection" in skills
        assert "dev_mode" in skills
        assert "visualization" in skills

    def test_get_skill_metadata(self, activator):
        """Test getting skill metadata."""
        metadata = activator.get_skill_metadata("anomaly_detection")

        assert metadata["name"] == "anomaly_detection"
        assert metadata["display_name"] == "异动检测"
        assert metadata["category"] == "Analysis"
        assert metadata["version"] == "1.0.0"
        assert metadata["is_mode"] is False
        assert "path" in metadata

    def test_get_skill_metadata_not_found(self, activator):
        """Test getting metadata for non-existent skill."""
        with pytest.raises(SkillActivationError, match="not found"):
            activator.get_skill_metadata("nonexistent")

    def test_get_all_skills_info(self, activator):
        """Test getting all skills info."""
        info_list = activator.get_all_skills_info()

        assert len(info_list) == 3

        # Find anomaly_detection info
        anomaly_info = next(i for i in info_list if i["name"] == "anomaly_detection")
        assert anomaly_info["display_name"] == "异动检测"
        assert anomaly_info["category"] == "Analysis"

    def test_is_mode_skill(self, activator):
        """Test checking if skill is a mode command."""
        assert activator.is_mode_skill("dev_mode") is True
        assert activator.is_mode_skill("anomaly_detection") is False

    def test_is_mode_skill_not_found(self, activator):
        """Test is_mode_skill for non-existent skill."""
        with pytest.raises(SkillActivationError, match="not found"):
            activator.is_mode_skill("nonexistent")

    def test_activate_with_conversation_history(self, activator):
        """Test activation with conversation history."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        messages, context = activator.activate_skill("anomaly_detection", history)

        # Should still work the same
        assert len(messages) == 3
        assert context["allowed_tools"] == ["Read", "Write", "Bash(python:*)"]


class TestSkillActivationIntegration:
    """Integration tests for complete skill activation workflow."""

    def test_full_activation_workflow(self, temp_skills_dir):
        """Test complete workflow from loader to activation."""
        # Create skill
        skill_dir = temp_skills_dir / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            """---
name: test_skill
display_name: "Test Skill"
description: "A test skill"
version: "1.0.0"
allowed_tools: "Read"
model: "claude-3-5-sonnet-20241022"
---

# Test Skill Instructions

This is a test skill.
"""
        )

        # Initialize components
        loader = SkillLoader([temp_skills_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        # Check skill is available
        assert "test_skill" in registry.list_skill_names()

        # Activate skill
        messages, context = activator.activate_skill("test_skill")

        # Verify messages
        assert len(messages) == 3
        assert messages[0]["isMeta"] is False  # Visible metadata
        assert messages[1]["isMeta"] is True   # Hidden instructions

        # Verify context
        assert context["allowed_tools"] == ["Read"]
        assert context["model"] == "claude-3-5-sonnet-20241022"

    def test_multiple_skill_activation(self, temp_skills_dir):
        """Test activating multiple skills."""
        # Create two skills
        for i in range(2):
            skill_dir = temp_skills_dir / f"skill_{i}"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                f"""---
name: skill_{i}
description: "Skill number {i}"
version: "1.0.0"
---
"""
            )

        loader = SkillLoader([temp_skills_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        # Activate both skills
        messages_0, context_0 = activator.activate_skill("skill_0")
        messages_1, context_1 = activator.activate_skill("skill_1")

        # Each should work independently
        assert len(messages_0) == 2  # No allowed_tools
        assert len(messages_1) == 2
        assert "skill_0" in messages_0[0]["content"]
        assert "skill_1" in messages_1[0]["content"]
