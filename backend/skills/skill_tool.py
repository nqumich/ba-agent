"""
Skill Meta-Tool for BAAgent

This module creates a meta-tool that wraps all available skills.
The Agent uses LLM reasoning to decide when to invoke this tool based on user requests.

Following Claude Code's architecture:
- Single "activate_skill" tool in the tools array
- Tool description contains formatted list of all available skills
- Agent selects skills through semantic matching
- When invoked, injects skill instructions into conversation
"""

import logging
from typing import Any, Dict, List, Optional
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from backend.skills import SkillRegistry, SkillActivator, SkillMessageFormatter

logger = logging.getLogger(__name__)


def create_skill_tool(
    skill_registry: SkillRegistry,
    skill_activator: SkillActivator,
) -> Optional[BaseTool]:
    """
    Create a Skill meta-tool that wraps all available skills.

    This tool follows Claude Code's architecture:
    - Tool description contains the formatted skills list for semantic discovery
    - Agent uses LLM reasoning to decide when to invoke based on user intent
    - When invoked, loads full SKILL.md and injects into conversation

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
        Function that activates skills
    """
    def _activate(skill_name: str) -> str:
        """
        Activate a skill by name.

        Args:
            skill_name: Name of the skill to activate

        Returns:
            Result message indicating the skill was activated
        """
        from backend.skills import SkillActivationError

        try:
            # Activate the skill
            messages, context_modifier = skill_activator.activate_skill(skill_name)

            # Log activation (hidden from user)
            logger.info(
                f"Activated skill '{skill_name}': "
                f"{len(messages)} messages injected, "
                f"context_modifier={context_modifier}"
            )

            # Return a message that will be shown to the user
            # The actual skill instructions are injected as hidden messages
            return f"Activated skill: {skill_name}"

        except SkillActivationError as e:
            logger.error(f"Failed to activate skill '{skill_name}': {e}")
            return f"Failed to activate skill '{skill_name}': {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error activating skill '{skill_name}': {e}")
            return f"Error activating skill '{skill_name}': {str(e)}"

    return _activate


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
