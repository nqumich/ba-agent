"""
Skill Loader for BA-Agent Skills System.

Handles discovery and loading of skills from multiple directories.
Implements progressive disclosure:
- Level 1: Load metadata only (~100 tokens/skill)
- Level 2: Load full skill content on activation (<5,000 tokens)
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from pydantic import ValidationError

from backend.skills.models import (
    Skill,
    SkillFrontmatter,
    SkillMetadata,
)


class SkillLoadError(Exception):
    """Base exception for skill loading errors."""

    pass


class InvalidSkillError(SkillLoadError):
    """Raised when a skill file is invalid."""

    pass


class SkillLoader:
    """Scan and load skills from multiple source directories.

    The loader searches for SKILL.md files in the configured directories
    and provides methods to load metadata (Level 1) or full content (Level 2).

    Directories are searched in order, with later directories overriding
    earlier ones if there are duplicate skill names.
    """

    def __init__(self, skills_dirs: List[Path]):
        """Initialize the skill loader.

        Args:
            skills_dirs: List of directories to search for skills.
                        Earlier directories have lower priority.
                        Example: [Path("skills"), Path(".claude/skills")]
        """
        self.skills_dirs = [Path(d) for d in skills_dirs]
        # Verify directories exist
        for directory in self.skills_dirs:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)

    def load_all_metadata(self) -> Dict[str, SkillMetadata]:
        """Load only skill metadata (Level 1: Progressive Disclosure).

        Scans all configured directories for SKILL.md files and parses
        only the YAML frontmatter. This is called at Agent startup.

        Returns:
            Dict mapping skill_name -> SkillMetadata
            (~100 tokens per skill)

        Raises:
            InvalidSkillError: If a skill has invalid frontmatter
        """
        metadata_dict: Dict[str, SkillMetadata] = {}

        for directory in self.skills_dirs:
            if not directory.exists():
                continue

            # Find all SKILL.md files recursively
            for skill_md in directory.rglob("SKILL.md"):
                try:
                    metadata = self._parse_metadata(skill_md)
                    # Later directories override earlier ones
                    metadata_dict[metadata.name] = metadata
                except InvalidSkillError as e:
                    # Log but continue loading other skills
                    print(f"Warning: Failed to load {skill_md}: {e}")
                except Exception as e:
                    print(f"Warning: Unexpected error loading {skill_md}: {e}")

        return metadata_dict

    def load_skill_full(self, skill_name: str) -> Optional[Skill]:
        """Load full skill content (Level 2: Progressive Disclosure).

        Called only when a skill is activated. Loads the complete
        SKILL.md file including instructions.

        Args:
            skill_name: Name of the skill to load

        Returns:
            Complete Skill object with instructions, or None if not found

        Raises:
            InvalidSkillError: If skill exists but is invalid
        """
        # Find the skill file
        skill_md_path = self._find_skill_file(skill_name)
        if skill_md_path is None:
            return None

        return self._parse_skill_full(skill_md_path)

    def _find_skill_file(self, skill_name: str) -> Optional[Path]:
        """Find a skill's SKILL.md file by name.

        Searches directories in reverse order (highest priority first).
        """
        for directory in reversed(self.skills_dirs):
            skill_path = directory / skill_name / "SKILL.md"
            if skill_path.exists():
                return skill_path

            # Also check for subdirectories (e.g., skills/analysis/anomaly_detection/SKILL.md)
            for candidate in directory.rglob("SKILL.md"):
                if candidate.parent.name == skill_name:
                    return candidate

        return None

    def _parse_metadata(self, skill_md_path: Path) -> SkillMetadata:
        """Parse only the YAML frontmatter from a SKILL.md file.

        Args:
            skill_md_path: Path to SKILL.md file

        Returns:
            SkillMetadata object

        Raises:
            InvalidSkillError: If frontmatter is invalid or missing required fields
        """
        content = skill_md_path.read_text(encoding="utf-8")

        # Extract YAML frontmatter
        frontmatter_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if not frontmatter_match:
            raise InvalidSkillError(
                f"{skill_md_path}: Missing YAML frontmatter (must start with ---)"
            )

        frontmatter_text = frontmatter_match.group(1)

        try:
            frontmatter_dict = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise InvalidSkillError(f"{skill_md_path}: Invalid YAML: {e}")

        try:
            frontmatter = SkillFrontmatter(**frontmatter_dict)
        except ValidationError as e:
            raise InvalidSkillError(f"{skill_md_path}: Validation error: {e}")

        return SkillMetadata(
            name=frontmatter.name,
            description=frontmatter.description,
            category=frontmatter.category,
            path=skill_md_path,
            version=frontmatter.version,
            is_mode=frontmatter.mode,
            display_name=frontmatter.display_name,
        )

    def _parse_skill_full(self, skill_md_path: Path) -> Skill:
        """Parse the complete SKILL.md file including instructions.

        Args:
            skill_md_path: Path to SKILL.md file

        Returns:
            Skill object with metadata and instructions

        Raises:
            InvalidSkillError: If skill is invalid
        """
        content = skill_md_path.read_text(encoding="utf-8")

        # Extract YAML frontmatter
        frontmatter_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if not frontmatter_match:
            raise InvalidSkillError(
                f"{skill_md_path}: Missing YAML frontmatter"
            )

        frontmatter_text = frontmatter_match.group(1)
        instructions = content[frontmatter_match.end():].strip()

        try:
            frontmatter_dict = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise InvalidSkillError(f"{skill_md_path}: Invalid YAML: {e}")

        try:
            frontmatter = SkillFrontmatter(**frontmatter_dict)
        except ValidationError as e:
            raise InvalidSkillError(f"{skill_md_path}: Validation error: {e}")

        return Skill(
            metadata=frontmatter,
            instructions=instructions,
            base_dir=skill_md_path.parent,
        )

    def list_all_skills(self) -> List[str]:
        """List all available skill names.

        Returns:
            List of skill names found in all directories
        """
        metadata = self.load_all_metadata()
        return sorted(metadata.keys())

    def get_skill_path(self, skill_name: str) -> Optional[Path]:
        """Get the path to a skill's directory.

        Args:
            skill_name: Name of the skill

        Returns:
            Path to skill directory, or None if not found
        """
        skill_md = self._find_skill_file(skill_name)
        if skill_md:
            return skill_md.parent
        return None
