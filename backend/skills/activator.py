"""
Skill Activator for BA-Agent Skills System.

Handles skill activation and context injection.
"""

from typing import Dict, List, Optional, Tuple, Any

from backend.skills.formatter import SkillMessageFormatter
from backend.skills.loader import SkillLoader
from backend.skills.models import Skill
from backend.skills.registry import SkillRegistry


class SkillActivationError(Exception):
    """Raised when skill activation fails."""

    pass


class SkillActivator:
    """Activate skills and inject conversation context.

    The activator is responsible for:
    - Loading full skill content when activated
    - Creating messages to inject into conversation
    - Generating context modifiers for execution
    """

    def __init__(self, loader: SkillLoader, registry: SkillRegistry):
        """Initialize the skill activator.

        Args:
            loader: SkillLoader for loading full skill content
            registry: SkillRegistry for checking skill existence
        """
        self.loader = loader
        self.registry = registry
        self.formatter = SkillMessageFormatter()

    def activate_skill(
        self,
        skill_name: str,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Activate a skill by injecting its instructions.

        This is called when the Agent decides to activate a skill.
        The system will inject messages into the conversation and
        modify the execution context.

        Args:
            skill_name: Name of the skill to activate
            conversation_history: Current conversation history (for context)

        Returns:
            (new_messages, context_modifier)

            new_messages: Messages to inject into conversation
                - Message 1 (visible): Metadata notification
                - Message 2 (hidden): Full SKILL.md instructions
                - Message 3 (optional): Tool permissions

            context_modifier: Execution context changes
                - allowed_tools: Tools skill can use
                - model: Model override
                - disable_model_invocation: Boolean flag

        Raises:
            SkillActivationError: If skill doesn't exist or activation fails
        """
        # Check if skill exists
        if not self.registry.skill_exists(skill_name):
            raise SkillActivationError(
                f"Skill '{skill_name}' not found. "
                f"Available skills: {', '.join(self.registry.list_skill_names())}"
            )

        # Load full skill content
        skill = self.loader.load_skill_full(skill_name)
        if skill is None:
            raise SkillActivationError(
                f"Failed to load skill '{skill_name}'"
            )

        # Create messages
        messages: List[Dict[str, Any]] = []

        # Message 1: Visible metadata message
        metadata_msg = self.formatter.create_metadata_message(skill)
        messages.append(metadata_msg)

        # Message 2: Hidden instruction message
        instruction_msg = self.formatter.create_instruction_message(skill)
        messages.append(instruction_msg)

        # Message 3: Tool permissions (if needed)
        permissions_msg = self.formatter.create_permissions_message(skill)
        if permissions_msg:
            messages.append(permissions_msg)

        # Create context modifier
        context_modifier = self.formatter.create_context_modifier(skill)

        return messages, context_modifier

    def get_skill_info(self, skill_name: str) -> str:
        """Get debug information about a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Formatted debug string

        Raises:
            SkillActivationError: If skill doesn't exist
        """
        if not self.registry.skill_exists(skill_name):
            raise SkillActivationError(f"Skill '{skill_name}' not found")

        skill = self.loader.load_skill_full(skill_name)
        if skill is None:
            raise SkillActivationError(f"Failed to load skill '{skill_name}'")

        return self.formatter.format_skill_for_debug(skill)

    def list_available_skills(self) -> List[str]:
        """List all available skill names.

        Returns:
            List of skill names
        """
        return self.registry.list_skill_names()

    def get_skill_metadata(self, skill_name: str) -> Dict[str, Any]:
        """Get metadata for a specific skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Dict with skill metadata

        Raises:
            SkillActivationError: If skill doesn't exist
        """
        metadata = self.registry.get_skill_metadata(skill_name)
        if metadata is None:
            raise SkillActivationError(f"Skill '{skill_name}' not found")

        return {
            "name": metadata.name,
            "display_name": metadata.display_name,
            "description": metadata.description,
            "category": metadata.category,
            "version": metadata.version,
            "is_mode": metadata.is_mode,
            "path": str(metadata.path),
        }

    def get_all_skills_info(self) -> List[Dict[str, Any]]:
        """Get information about all available skills.

        Returns:
            List of dicts with skill information
        """
        return self.registry.get_skills_info()

    def is_mode_skill(self, skill_name: str) -> bool:
        """Check if a skill is a mode command.

        Args:
            skill_name: Name of the skill

        Returns:
            True if skill is a mode command

        Raises:
            SkillActivationError: If skill doesn't exist
        """
        metadata = self.registry.get_skill_metadata(skill_name)
        if metadata is None:
            raise SkillActivationError(f"Skill '{skill_name}' not found")
        return metadata.is_mode
