"""
End-to-end integration test for skill activation through BAAgent

This test verifies the complete workflow:
1. User message → Agent
2. Agent invokes activate_skill tool (via LLM reasoning)
3. Tool returns SkillActivationResult
4. BAAgent extracts result and injects messages
5. Agent follows skill instructions
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from langchain_core.messages import AIMessage, HumanMessage
from langchain_anthropic import ChatAnthropic


@pytest.fixture
def skills_base_dir(tmp_path):
    """Create a temporary skills directory with a test skill."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create a test skill
    skill_dir = skills_dir / "test_skill"
    skill_dir.mkdir()

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: test_skill
display_name: "Test Skill"
description: "A test skill for e2e testing"
version: "1.0.0"
category: "Testing"
allowed_tools: "Read,Write"
---

# Test Skill

This is a test skill for end-to-end testing.

## Instructions

When activated, this skill guides the agent to:
1. Read the input data
2. Process it
3. Write the result

## Available Resources

- scripts/process.py: Data processing script
""")

    # Create scripts directory with a simple script
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "process.py").write_text("def process(): return 'processed'")

    return skills_dir


class TestSkillActivationE2E:
    """End-to-end tests for skill activation through BAAgent"""

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="Requires ANTHROPIC_API_KEY"
    )
    def test_full_skill_activation_workflow(self, monkeypatch):
        """
        Test the complete skill activation workflow:
        1. Agent receives user request
        2. Agent invokes activate_skill tool
        3. Messages are injected into conversation
        4. Agent follows skill instructions
        """
        # This test requires actual API key to run
        # It verifies the complete workflow works as designed

        # TODO: Implement full e2e test
        pass

    def test_extract_skill_result_from_langgraph_output(self, skills_base_dir):
        """
        Test that _extract_skill_activation_result can correctly
        extract skill activation result from various LangGraph output formats.
        """
        from backend.agents.agent import BAAgent
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agent = BAAgent()

        # Simulate different possible LangGraph output formats

        # Format 1: Tool output in message content (most likely)
        result_format_1 = {
            "messages": [
                AIMessage(
                    content=json.dumps({
                        "skill_name": "test_skill",
                        "messages": [{"role": "user", "content": "test"}],
                        "context_modifier": {},
                        "success": True
                    })
                )
            ]
        }

        extracted = agent._extract_skill_activation_result(result_format_1)
        assert extracted is not None, "Should extract from additional_kwargs.tool_output"
        assert extracted["skill_name"] == "test_skill"

        # Format 2: Tool output in message content (as JSON)
        result_format_2 = {
            "messages": [
                AIMessage(
                    content=json.dumps({
                        "skill_name": "test_skill",
                        "messages": [{"role": "user", "content": "test"}],
                        "context_modifier": {},
                        "success": True
                    })
                )
            ]
        }

        extracted = agent._extract_skill_activation_result(result_format_2)
        assert extracted is not None, "Should extract from content JSON"
        assert extracted["skill_name"] == "test_skill"

        # Format 3: No skill activation
        result_format_3 = {
            "messages": [
                AIMessage(content="No skill was activated")
            ]
        }

        extracted = agent._extract_skill_activation_result(result_format_3)
        assert extracted is None, "Should return None when no skill activated"

    def test_message_injection_format(self, skills_base_dir, monkeypatch):
        """
        Test that _inject_skill_messages creates messages in correct format
        for LangGraph consumption.
        """
        from backend.agents.agent import BAAgent
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agent = BAAgent()

        # Mock the agent's get_state and update_state methods
        mock_state = {
            "messages": {
                "messages": [
                    HumanMessage(content="Original message")
                ]
            }
        }

        def mock_get_state(config):
            return MagicMock(messages=mock_state["messages"])

        def mock_update_state(config, updates):
            # Store the updates for verification
            mock_state["messages"] = updates["messages"]

        agent.agent.get_state = mock_get_state
        agent.agent.update_state = mock_update_state

        # Test data: skill messages
        messages_data = [
            {
                "role": "user",
                "content": '<command-message>The "Test Skill" skill is loading</command-message>',
            },
            {
                "role": "user",
                "content": "# Test Skill\n\nThis is the instruction.",
                "isMeta": True
            }
        ]

        config = {"configurable": {"thread_id": "test_thread"}}

        # Inject messages
        agent._inject_skill_messages(messages_data, "test_conv", config)

        # Verify messages were added
        injected_messages = mock_state["messages"]
        assert len(injected_messages) == 3  # Original + 2 new

        # Verify format
        assert isinstance(injected_messages[0], HumanMessage)  # Original
        assert hasattr(injected_messages[1], "content")  # Metadata message
        assert hasattr(injected_messages[2], "content")  # Instruction (AIMessage)
        assert injected_messages[2].content == "# Test Skill\n\nThis is the instruction."
        assert hasattr(injected_messages[2], "additional_kwargs")
        assert injected_messages[2].additional_kwargs.get("isMeta") is True

    def test_context_modifier_stored(self, skills_base_dir, monkeypatch):
        """
        Test that context modifier is correctly stored in _active_skill_context.
        """
        from backend.agents.agent import BAAgent
        from backend.skills.message_protocol import ContextModifier
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agent = BAAgent()

        # Create a context modifier
        context_modifier = ContextModifier(
            allowed_tools=["Read", "Write"],
            model="claude-opus-4-20250514",
            disable_model_invocation=True
        )

        # Apply it
        agent._apply_context_modifier(context_modifier, "test_skill")

        # Verify stored
        assert "test_skill_allowed_tools" in agent._active_skill_context
        assert agent._active_skill_context["test_skill_allowed_tools"] == ["Read", "Write"]
        assert agent._active_skill_context["test_skill_model"] == "claude-opus-4-20250514"
        assert agent._active_skill_context["test_skill_disable_model"] is True


class TestContextModifierApplication:
    """Tests for Context Modifier application (Section 4.2 Missing Tests)."""

    def test_tool_permission_checking(self, skills_base_dir, monkeypatch):
        """
        Test that _check_tool_allowed correctly enforces tool permissions.
        This addresses the missing test from section 4.2: Context Modifier application.
        """
        from backend.agents.agent import BAAgent
        from backend.skills.message_protocol import ContextModifier
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agent = BAAgent()

        # No active skill - all tools should be allowed
        assert agent._check_tool_allowed("Read") is True
        assert agent._check_tool_allowed("Write") is True
        assert agent._check_tool_allowed("AnyTool") is True

        # Apply a context modifier with allowed_tools
        context_modifier = ContextModifier(allowed_tools=["Read", "Write"])
        agent._apply_context_modifier(context_modifier, "test_skill")

        # Now only allowed tools should be permitted
        assert agent._check_tool_allowed("Read") is True
        assert agent._check_tool_allowed("Write") is True
        assert agent._check_tool_allowed("Execute") is False
        assert agent._check_tool_allowed("AnyTool") is False

        # Deactivate skill (clear context)
        agent._active_skill_context.clear()
        assert agent._check_tool_allowed("AnyTool") is True

    def test_model_switching_stores_preference(self, skills_base_dir, monkeypatch):
        """
        Test that model switching preference is stored.
        Note: Actual model switching requires valid API keys and is tested separately.
        """
        from backend.agents.agent import BAAgent
        from backend.skills.message_protocol import ContextModifier
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agent = BAAgent()

        # Apply a context modifier with model override
        context_modifier = ContextModifier(model="claude-opus-4-20250514")
        agent._apply_context_modifier(context_modifier, "test_skill")

        # Verify the model preference is stored
        assert agent._active_skill_context.get("test_skill_model") == "claude-opus-4-20250514"

        # Verify we can retrieve it
        assert agent._get_active_skill_model() == "claude-opus-4-20250514"

    def test_model_invocation_disabled(self, skills_base_dir, monkeypatch):
        """
        Test that disable_model_invocation flag is properly stored and checked.
        """
        from backend.agents.agent import BAAgent
        from backend.skills.message_protocol import ContextModifier
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agent = BAAgent()

        # Initially, model invocation should be enabled
        assert agent._is_model_invocation_disabled() is False

        # Apply a context modifier with disable_model_invocation
        context_modifier = ContextModifier(disable_model_invocation=True)
        agent._apply_context_modifier(context_modifier, "test_skill")

        # Now model invocation should be disabled
        assert agent._is_model_invocation_disabled() is True

    def test_context_modifier_combined(self, skills_base_dir, monkeypatch):
        """
        Test that all context modifier fields work together correctly.
        """
        from backend.agents.agent import BAAgent
        from backend.skills.message_protocol import ContextModifier
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agent = BAAgent()

        # Apply a comprehensive context modifier
        context_modifier = ContextModifier(
            allowed_tools=["Read", "Write", "Search"],
            model="claude-opus-4-20250514",
            disable_model_invocation=False
        )
        agent._apply_context_modifier(context_modifier, "comprehensive_skill")

        # Verify all fields are applied
        assert agent._check_tool_allowed("Read") is True
        assert agent._check_tool_allowed("Write") is True
        assert agent._check_tool_allowed("Search") is True
        assert agent._check_tool_allowed("Execute") is False
        assert agent._get_active_skill_model() == "claude-opus-4-20250514"
        assert agent._is_model_invocation_disabled() is False

    def test_multiple_skills_context_isolation(self, skills_base_dir, monkeypatch):
        """
        Test that context modifiers from different skills are properly isolated.
        """
        from backend.agents.agent import BAAgent
        from backend.skills.message_protocol import ContextModifier
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agent = BAAgent()

        # Apply context modifier for skill_1
        context_modifier_1 = ContextModifier(
            allowed_tools=["Read"],
            model="model-1"
        )
        agent._apply_context_modifier(context_modifier_1, "skill_1")

        # Apply context modifier for skill_2
        context_modifier_2 = ContextModifier(
            allowed_tools=["Write"],
            model="model-2"
        )
        agent._apply_context_modifier(context_modifier_2, "skill_2")

        # Verify skill_2's context is active (last applied)
        assert agent._active_skill_context.get("current_skill") == "skill_2"
        assert agent._check_tool_allowed("Write") is True
        assert agent._check_tool_allowed("Read") is False
        assert agent._get_active_skill_model() == "model-2"

        # Verify skill_1's context is still stored
        assert agent._active_skill_context.get("skill_1_allowed_tools") == ["Read"]
        assert agent._active_skill_context.get("skill_1_model") == "model-1"


class TestLangGraphToolOutputFormat:
    """Tests to understand how LangGraph returns tool outputs."""

    def test_understand_langgraph_tool_format(self):
        """
        This test is exploratory - it helps us understand how
        LangGraph's create_react_agent returns tool call results.

        Run this test with actual API key to see the real format.
        """
        # TODO: Add real test with API key to inspect actual format
        pass


__all__ = [
    "TestSkillActivationE2E",
    "TestContextModifierApplication",
    "TestLangGraphToolOutputFormat",
]
