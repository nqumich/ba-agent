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

        assert "Activated skill: test_skill" in result

    def test_invoke_nonexistent_skill(self, skills_base_dir, sample_skill):
        """Test invoking tool with non-existent skill name"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        result = tool.invoke({"skill_name": "nonexistent_skill"})

        assert "Failed to activate skill" in result
        assert "nonexistent_skill" in result

    def test_invoke_with_empty_skill_name(self, skills_base_dir, sample_skill):
        """Test invoking tool with empty skill name"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        result = tool.invoke({"skill_name": ""})

        # Should handle gracefully - either activation fails or returns error
        assert "Failed" in result or "Error" in result


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

    def test_tool_returns_string_result(self, skills_base_dir, sample_skill):
        """Test that tool returns string result"""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        tool = create_skill_tool(registry, activator)

        assert tool is not None
        result = tool.invoke({"skill_name": "test_skill"})

        assert isinstance(result, str)
        assert len(result) > 0
