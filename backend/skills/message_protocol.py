"""
Skill Message Protocol

Defines the standard message format for skill activation and context modification.
This ensures consistent communication between the skill system and BAAgent.
"""

from typing import Any, Dict, List, Optional, TypedDict
from dataclasses import dataclass
from enum import Enum


class MessageType(str, Enum):
    """Types of messages that can be injected during skill activation."""
    METADATA = "metadata"           # Visible: Skill loading notification
    INSTRUCTION = "instruction"     # Hidden: Full SKILL.md content
    PERMISSIONS = "permissions"     # Conditional: Tool permissions


class MessageVisibility(str, Enum):
    """Message visibility settings."""
    VISIBLE = "visible"             # Shown to user
    HIDDEN = "hidden"               # Only sent to API


@dataclass
class SkillMessage:
    """
    Standard message format for skill activation.

    Attributes:
        type: Message type (metadata, instruction, permissions)
        content: Message content (string or dict for permissions)
        visibility: Whether user can see this message
        role: Message role (always "user" for injection into conversation)
    """
    type: MessageType
    content: Any  # str for metadata/instruction, dict for permissions
    visibility: MessageVisibility
    role: str = "user"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to LangChain message format."""
        msg = {
            "role": self.role,
            "content": self.content,
        }
        # Add isMeta flag for hidden messages
        if self.visibility == MessageVisibility.HIDDEN:
            msg["isMeta"] = True
        return msg


@dataclass
class ContextModifier:
    """
    Execution context modifications requested by a skill.

    Attributes:
        allowed_tools: List of tools the skill can use without approval
        model: Override model to use for this skill
        disable_model_invocation: Prevent skill from invoking LLM itself
    """
    allowed_tools: Optional[List[str]] = None
    model: Optional[str] = None
    disable_model_invocation: bool = False

    def is_empty(self) -> bool:
        """Check if this modifier has any changes."""
        return (
            self.allowed_tools is None and
            self.model is None and
            not self.disable_model_invocation
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {}
        if self.allowed_tools is not None:
            result["allowed_tools"] = self.allowed_tools
        if self.model is not None:
            result["model"] = self.model
        if self.disable_model_invocation:
            result["disable_model_invocation"] = True
        return result


@dataclass
class SkillActivationResult:
    """
    Complete result of skill activation.

    This is what the skill system returns to BAAgent for processing.

    Attributes:
        skill_name: Name of the activated skill
        messages: Messages to inject into conversation
        context_modifier: Execution context modifications
        success: Whether activation succeeded
        error: Error message if activation failed
    """
    skill_name: str
    messages: List[SkillMessage]
    context_modifier: ContextModifier
    success: bool = True
    error: Optional[str] = None

    @classmethod
    def success_result(
        cls,
        skill_name: str,
        messages: List[SkillMessage],
        context_modifier: ContextModifier
    ) -> "SkillActivationResult":
        """Create a successful activation result."""
        return cls(
            skill_name=skill_name,
            messages=messages,
            context_modifier=context_modifier,
            success=True
        )

    @classmethod
    def failure_result(
        cls,
        skill_name: str,
        error: str
    ) -> "SkillActivationResult":
        """Create a failed activation result."""
        return cls(
            skill_name=skill_name,
            messages=[],
            context_modifier=ContextModifier(),
            success=False,
            error=error
        )


__all__ = [
    "MessageType",
    "MessageVisibility",
    "SkillMessage",
    "ContextModifier",
    "SkillActivationResult",
]
