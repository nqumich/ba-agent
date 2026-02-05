"""
Formatter for BA-Agent Skills System.

Handles formatting of skill-related messages for the Agent.
"""

from typing import Any, Dict, List, Optional

from backend.skills.models import Skill


class SkillMessageFormatter:
    """Format skill-related messages for Agent consumption."""

    @staticmethod
    def create_metadata_message(skill: Skill) -> Dict[str, Any]:
        """Create visible metadata message for skill activation.

        This message is shown to the user to indicate which skill is loading.

        Args:
            skill: The skill being activated

        Returns:
            Message dict with role and content
        """
        display_name = skill.metadata.display_name or skill.metadata.name
        content = f'<command-message>The "{display_name}" skill is loading</command-message>\n<command-name>{skill.metadata.name}</command-name>'

        return {
            "role": "user",
            "content": content,
            "isMeta": False,  # Visible to user
        }

    @staticmethod
    def create_instruction_message(skill: Skill) -> Dict[str, Any]:
        """Create hidden instruction message with skill content.

        This message contains the full SKILL.md instructions and is hidden
        from the user (isMeta: true).

        Args:
            skill: The skill being activated

        Returns:
            Message dict with role and content
        """
        # Combine frontmatter info with instructions
        content = f"# {skill.metadata.display_name or skill.metadata.name} Skill\n\n"
        content += skill.instructions

        return {
            "role": "user",
            "content": content,
            "isMeta": True,  # Hidden from user, sent to API
        }

    @staticmethod
    def create_permissions_message(skill: Skill) -> Optional[Dict[str, Any]]:
        """Create tool permissions message if skill has allowed-tools.

        Args:
            skill: The skill being activated

        Returns:
            Message dict with permissions, or None if no allowed-tools
        """
        allowed_tools = skill.get_allowed_tools_list()
        if not allowed_tools:
            return None

        return {
            "role": "user",
            "content": {
                "type": "command_permissions",
                "allowed_tools": allowed_tools,
                "model": skill.metadata.model,
            }
        }

    @staticmethod
    def create_context_modifier(skill: Skill) -> Dict[str, Any]:
        """Create execution context modifier for the skill.

        This contains changes to the execution context like tool permissions
        and model overrides.

        Args:
            skill: The skill being activated

        Returns:
            Dict with context modifications
        """
        modifier: Dict[str, Any] = {}

        # Tool permissions
        allowed_tools = skill.get_allowed_tools_list()
        if allowed_tools:
            modifier["allowed_tools"] = allowed_tools

        # Model override
        if skill.metadata.model:
            modifier["model"] = skill.metadata.model

        # Disable model invocation flag
        if skill.metadata.disable_model_invocation:
            modifier["disable_model_invocation"] = True

        return modifier

    @staticmethod
    def format_skills_list_for_prompt(skills_list: str) -> str:
        """Format the skills list for the Agent's system prompt.

        Args:
            skills_list: Formatted skills list from SkillRegistry

        Returns:
            Formatted section for system prompt
        """
        return f"""## Available Skills

当用户请求需要特定领域知识或工作流程时，检查以下可用的 Skills：

<available_skills>
{skills_list}
</available_skills>

**如何使用 Skills**：
- Skills 提供专业化的指令和工作流程
- 当任务匹配某个 Skill 的描述时，该 Skill 会被激活
- 激活后，你会收到该 Skill 的详细指令
- Skill 可能包含预批准的工具权限

**示例**：
- 用户问 "今天GMV有什么异常？" → 激活 anomaly_detection
- 用户问 "帮我生成一个分析报告" → 激活 report_gen
"""

    @staticmethod
    def format_skill_for_debug(skill: Skill) -> str:
        """Format skill info for debug output.

        Args:
            skill: The skill to format

        Returns:
            Formatted debug string
        """
        lines = [
            f"Skill: {skill.metadata.name}",
            f"  Display Name: {skill.metadata.display_name or 'N/A'}",
            f"  Version: {skill.metadata.version}",
            f"  Category: {skill.metadata.category or 'N/A'}",
            f"  Description: {skill.metadata.description}",
            f"  Mode: {skill.metadata.mode}",
            f"  Allowed Tools: {skill.metadata.allowed_tools or 'None'}",
            f"  Model Override: {skill.metadata.model or 'None'}",
            f"  Base Dir: {skill.base_dir}",
            f"  Has Scripts: {skill.has_scripts()}",
            f"  Has References: {skill.has_references()}",
            f"  Has Assets: {skill.has_assets()}",
        ]
        return "\n".join(lines)
