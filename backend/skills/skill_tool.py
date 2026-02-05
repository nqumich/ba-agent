"""
Skill Meta-Tool for BAAgent

This module creates a meta-tool that wraps all available skills.
The Agent uses LLM reasoning to decide when to invoke this tool based on user requests.

Following Claude Code's architecture:
- Single "activate_skill" tool in the tools array
- Tool description contains formatted list of all available skills
- Agent selects skills through semantic matching
- When invoked, returns structured result for message injection
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from backend.skills import (
    SkillRegistry,
    SkillActivator,
    SkillMessageFormatter,
    MessageType,
    MessageVisibility,
    SkillMessage,
    ContextModifier,
    SkillActivationResult,
)
from backend.skills.models import Skill

logger = logging.getLogger(__name__)


def create_skill_tool(
    skill_registry: SkillRegistry,
    skill_activator: SkillActivator,
) -> Optional[StructuredTool]:
    """
    Create a Skill meta-tool that wraps all available skills.

    This tool follows Claude Code's architecture:
    - Tool description contains the formatted skills list for semantic discovery
    - Agent uses LLM reasoning to decide when to invoke based on user intent
    - When invoked, returns SkillActivationResult for BAAgent to process

    Args:
        skill_registry: SkillRegistry instance containing all available skills
        skill_activator: SkillActivator instance for activating skills

    Returns:
        StructuredTool instance, or None if no skills are available
    """
    # Check if there are any skills available
    if skill_registry is None or not skill_registry.list_skill_names():
        logger.info("No skills available, skipping skill tool creation")
        return None

    # Get the formatted skills list
    skills_list = skill_registry.get_formatted_skills_list()

    # Format the tool description
    description = _build_skill_description(skills_list)

    # Create the tool
    tool = StructuredTool.from_function(
        name="activate_skill",
        description=description,
        func=_activate_skill_wrapper(skill_activator),
        args_schema=SkillActivationInput,
    )

    logger.info(f"Created skill meta-tool with {len(skill_registry.list_skill_names())} skills")
    return tool


def _build_skill_description(skills_list: str) -> str:
    """
    Build the tool description with formatted skills list.

    Args:
        skills_list: Formatted skills list from SkillRegistry

    Returns:
        Complete tool description
    """
    return f"""Activate a skill to provide specialized instructions for a specific task.

When a user asks for something that might require specialized knowledge or workflows, check if any of the available skills below can help. Skills provide detailed instructions and context for specific domains.

**How to use:**
1. Match the user's request to a skill by semantic similarity
2. Invoke this tool with the skill name
3. The skill's instructions will be injected into the conversation
4. Follow the skill's workflow to complete the task

**Available Skills:**

{skills_list}

**Important Notes:**
- Only activate a skill when the user's request clearly matches the skill's purpose
- Skills inject specialized instructions - read them carefully and follow the workflow
- Some skills may modify tool permissions or switch to a different model
- After activation, continue the conversation following the skill's guidance
"""


def _activate_skill_wrapper(skill_activator: SkillActivator):
    """
    Create a wrapper function for skill activation.

    Args:
        skill_activator: SkillActivator instance

    Returns:
        Function that activates skills and returns SkillActivationResult
    """
    def _activate(skill_name: str) -> Dict[str, Any]:
        """
        Activate a skill by name.

        Returns a SkillActivationResult serialized as dict for BAAgent to process.

        Args:
            skill_name: Name of the skill to activate

        Returns:
            Dict representation of SkillActivationResult with:
            - skill_name: str
            - messages: List[Dict] - messages to inject
            - context_modifier: Dict - execution context changes
            - success: bool
            - error: Optional[str]
        """
        from backend.skills import SkillActivationError

        try:
            # Activate the skill using SkillActivator
            # This returns (messages, context_modifier) tuple
            raw_messages, context_dict = skill_activator.activate_skill(skill_name)

            # Convert raw messages to SkillMessage format
            messages = _convert_to_skill_messages(raw_messages)

            # Convert context dict to ContextModifier
            context_modifier = ContextModifier(
                allowed_tools=context_dict.get("allowed_tools"),
                model=context_dict.get("model"),
                disable_model_invocation=context_dict.get("disable_model_invocation", False)
            )

            # Create success result
            result = SkillActivationResult.success_result(
                skill_name=skill_name,
                messages=messages,
                context_modifier=context_modifier
            )

            # Log activation
            logger.info(
                f"Activated skill '{skill_name}': "
                f"{len(messages)} messages prepared, "
                f"context_modifier={context_modifier.to_dict()}"
            )

            # Return as dict for JSON serialization
            return _serialize_activation_result(result)

        except SkillActivationError as e:
            logger.error(f"Failed to activate skill '{skill_name}': {e}")
            result = SkillActivationResult.failure_result(skill_name, str(e))
            return _serialize_activation_result(result)

        except Exception as e:
            logger.error(f"Unexpected error activating skill '{skill_name}': {e}")
            result = SkillActivationResult.failure_result(skill_name, str(e))
            return _serialize_activation_result(result)

    return _activate


def _convert_to_skill_messages(raw_messages: list) -> list:
    """
    Convert messages from SkillActivator to SkillMessage format.

    Args:
        raw_messages: List of message dicts from SkillActivator

    Returns:
        List of SkillMessage objects
    """
    skill_messages = []

    for msg in raw_messages:
        if msg.get("isMeta") is False:
            # Visible metadata message
            skill_messages.append(SkillMessage(
                type=MessageType.METADATA,
                content=msg["content"],
                visibility=MessageVisibility.VISIBLE
            ))
        elif msg.get("isMeta") is True:
            # Hidden instruction message
            skill_messages.append(SkillMessage(
                type=MessageType.INSTRUCTION,
                content=msg["content"],
                visibility=MessageVisibility.HIDDEN
            ))
        else:
            # Message without isMeta - assume it's content-based
            if isinstance(msg.get("content"), dict):
                # Permissions message
                skill_messages.append(SkillMessage(
                    type=MessageType.PERMISSIONS,
                    content=msg["content"],
                    visibility=MessageVisibility.HIDDEN
                ))
            else:
                # Regular message - treat as instruction
                skill_messages.append(SkillMessage(
                    type=MessageType.INSTRUCTION,
                    content=msg["content"],
                    visibility=MessageVisibility.VISIBLE
                ))

    return skill_messages


def _serialize_activation_result(result: SkillActivationResult) -> Dict[str, Any]:
    """
    Serialize SkillActivationResult to dict for JSON transport.

    Args:
        result: SkillActivationResult to serialize

    Returns:
        Dict with all fields serialized
    """
    return {
        "skill_name": result.skill_name,
        "messages": [msg.to_dict() for msg in result.messages],
        "context_modifier": result.context_modifier.to_dict(),
        "success": result.success,
        "error": result.error,
    }


class SkillActivationInput(BaseModel):
    """Input schema for skill activation."""

    skill_name: str = Field(
        description="Name of the skill to activate. Must be one of the available skill names."
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"skill_name": "anomaly_detection"},
                {"skill_name": "attribution"},
                {"skill_name": "report_gen"},
            ]
        }


__all__ = [
    "create_skill_tool",
    "SkillActivationInput",
]
