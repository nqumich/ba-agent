"""
Tests for the Skill meta-tool

Tests the create_skill_tool function that wraps all available skills
into a single LangChain tool for Agent invocation.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.skills import (
    SkillLoader,
    SkillRegistry,
    SkillActivator,
    SkillMessageFormatter,
    create_skill_tool,
    SkillActivationInput,
)


class TestCreateSkillTool:
    """Test create_skill_tool function"""

    def test_create_tool_with_skills(self, skills_base_dir, sample_skill):
        """Test creating tool when skills are available"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        assert tool.name == "activate_skill"
        assert "Activate a skill" in tool.description
        assert "test_skill" in tool.description

    def test_create_tool_without_skills(self, skills_base_dir):
        """Test creating tool when no skills are available"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is None

    def test_create_tool_with_none_registry(self):
        """Test creating tool with None registry"""
        tool = create_skill_tool(None, None)
        assert tool is None

    def test_tool_description_contains_skills_list(self, skills_base_dir, sample_skill):
        """Test that tool description contains formatted skills list"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        description = tool.description

        # Check that description contains key sections
        assert "How to use:" in description
        assert "Available Skills:" in description
        assert "test_skill" in description
        assert "A test skill for testing" in description

    def test_tool_description_mode_skills_first(self, skills_base_dir, sample_mode_skill, sample_skill):
        """Test that mode skills are listed first in description"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        description = tool.description

        # Mode skill should appear before regular skill
        mode_pos = description.find("mode_skill")
        regular_pos = description.find("test_skill")
        assert mode_pos < regular_pos

    def test_tool_arg_schema(self, skills_base_dir, sample_skill):
        """Test that tool has correct argument schema"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        # The args_schema should be SkillActivationInput
        assert tool.args_schema == SkillActivationInput


class TestSkillToolInvocation:
    """Test invoking the skill tool"""

    def test_invoke_existing_skill(self, skills_base_dir, sample_skill):
        """Test invoking tool with existing skill name"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        result = tool.invoke({"skill_name": "test_skill"})

        # Result is now a dict with SkillActivationResult structure
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["skill_name"] == "test_skill"
        assert len(result["messages"]) >= 2  # metadata + instruction
        assert result["messages"][0]["role"] == "user"

    def test_invoke_nonexistent_skill(self, skills_base_dir, sample_skill):
        """Test invoking tool with non-existent skill name"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        result = tool.invoke({"skill_name": "nonexistent_skill"})

        # Result is a dict with failure info
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "error" in result
        assert "nonexistent_skill" in result["error"]

    def test_invoke_with_empty_skill_name(self, skills_base_dir, sample_skill):
        """Test invoking tool with empty skill name"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        result = tool.invoke({"skill_name": ""})

        # Should handle gracefully - failure result
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "error" in result

    def test_invoke_returns_message_with_isMeta(self, skills_base_dir, sample_skill):
        """Test that returned messages have isMeta field correctly set"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        result = tool.invoke({"skill_name": "test_skill"})

        # Check message structure
        messages = result["messages"]
        assert len(messages) >= 2

        # First message should be visible (no isMeta or isMeta=False)
        assert "isMeta" not in messages[0] or messages[0].get("isMeta") is False

        # Second message should be hidden (isMeta=True)
        assert messages[1].get("isMeta") is True


class TestSkillActivationInput:
    """Test SkillActivationInput schema"""

    def test_valid_input(self):
        """Test creating valid input"""
        input_data = SkillActivationInput(skill_name="test_skill")
        assert input_data.skill_name == "test_skill"

    def test_input_with_examples(self):
        """Test that schema has examples"""
        schema = SkillActivationInput.model_json_schema()
        assert "examples" in schema.get("$defs", {}).get("examples", [{}])[0] or "examples" in schema


class TestSkillToolIntegration:
    """Test skill tool integration with BAAgent"""

    def test_tool_in_langchain_format(self, skills_base_dir, sample_skill):
        """Test that tool is in correct LangChain format"""
        from langchain_core.tools import BaseTool

        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        assert isinstance(tool, BaseTool)
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")
        assert hasattr(tool, "_run")
        assert hasattr(tool, "args_schema")

    def test_tool_returns_structured_result(self, skills_base_dir, sample_skill):
        """Test that tool returns structured SkillActivationResult"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        result = tool.invoke({"skill_name": "test_skill"})

        # Result should be a dict with SkillActivationResult structure
        assert isinstance(result, dict)
        assert "skill_name" in result
        assert "messages" in result
        assert "context_modifier" in result
        assert "success" in result

        # Messages should be a list
        assert isinstance(result["messages"], list)
        assert len(result["messages"]) > 0
