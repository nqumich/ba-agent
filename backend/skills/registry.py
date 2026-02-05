"""
Skill Registry for BA-Agent Skills System.

Maintains a registry of all available skills and provides formatted
output for the Agent's system prompt.
"""

from typing import Dict, List, Optional

from backend.skills.loader import SkillLoader
from backend.skills.models import Skill, SkillMetadata


class SkillRegistry:
    """Central registry for all available skills.

    The registry caches skill metadata and provides methods to:
    - Get formatted skills list for Agent's system prompt
    - Get metadata for specific skills
    - Load full skill content on activation
    """

    def __init__(self, loader: SkillLoader):
        """Initialize the skill registry.

        Args:
            loader: SkillLoader instance for loading skills
        """
        self.loader = loader
        self._metadata_cache: Optional[Dict[str, SkillMetadata]] = None

    def get_all_metadata(self) -> Dict[str, SkillMetadata]:
        """Get all skill metadata, loading from cache if available.

        Returns:
            Dict mapping skill_name -> SkillMetadata
        """
        if self._metadata_cache is None:
            self._metadata_cache = self.loader.load_all_metadata()
        return self._metadata_cache

    def get_formatted_skills_list(self) -> str:
        """Format skills for Agent's system prompt.

        Creates a compact list of skills with their descriptions.
        Mode skills (if any) are listed first for visibility.

        Returns:
            Formatted string like:
            "anomaly_detection: 检测数据异常波动并分析可能原因
             attribution: 分析业务指标变化的驱动因素
             ..."
        """
        metadata_dict = self.get_all_metadata()
        lines: List[str] = []

        # Mode skills first (if any)
        mode_skills = [m for m in metadata_dict.values() if m.is_mode]
        regular_skills = [m for m in metadata_dict.values() if not m.is_mode]

        for skill in mode_skills + regular_skills:
            # Use quoted format for clarity
            display = skill.display_name or skill.name
            lines.append(f'"{skill.name}": {skill.description}')

        return "\n".join(lines)

    def get_skill_metadata(self, skill_name: str) -> Optional[SkillMetadata]:
        """Get metadata for a specific skill.

        Args:
            skill_name: Name of the skill

        Returns:
            SkillMetadata or None if not found
        """
        metadata_dict = self.get_all_metadata()
        return metadata_dict.get(skill_name)

    def get_skill_full(self, skill_name: str) -> Optional[Skill]:
        """Load full skill content.

        Args:
            skill_name: Name of the skill to load

        Returns:
            Complete Skill object or None if not found
        """
        return self.loader.load_skill_full(skill_name)

    def skill_exists(self, skill_name: str) -> bool:
        """Check if a skill exists.

        Args:
            skill_name: Name of the skill

        Returns:
            True if skill exists, False otherwise
        """
        return skill_name in self.get_all_metadata()

    def list_skill_names(self) -> List[str]:
        """List all available skill names.

        Returns:
            Sorted list of skill names
        """
        return sorted(self.get_all_metadata().keys())

    def list_mode_skills(self) -> List[str]:
        """List all mode command skills.

        Returns:
            List of skill names that are mode commands
        """
        metadata_dict = self.get_all_metadata()
        return [name for name, meta in metadata_dict.items() if meta.is_mode]

    def invalidate_cache(self) -> None:
        """Force reload of metadata on next access.

        Useful after installing/uninstalling skills.
        """
        self._metadata_cache = None

    def get_skills_by_category(self, category: str) -> List[str]:
        """Get all skills in a specific category.

        Args:
            category: Category name

        Returns:
            List of skill names in the category
        """
        metadata_dict = self.get_all_metadata()
        return [
            name
            for name, meta in metadata_dict.items()
            if meta.category == category
        ]

    def get_all_categories(self) -> List[str]:
        """Get all unique skill categories.

        Returns:
            Sorted list of category names
        """
        metadata_dict = self.get_all_metadata()
        categories = {meta.category for meta in metadata_dict.values() if meta.category}
        return sorted(categories)

    def get_skills_info(self) -> List[Dict[str, any]]:
        """Get detailed info about all skills.

        Returns:
            List of dictionaries with skill information
        """
        metadata_dict = self.get_all_metadata()
        return [
            {
                "name": meta.name,
                "display_name": meta.display_name,
                "description": meta.description,
                "category": meta.category,
                "version": meta.version,
                "is_mode": meta.is_mode,
                "path": str(meta.path),
            }
            for meta in metadata_dict.values()
        ]
