"""
Skill data models for the BA-Agent skills system.

Defines Pydantic models for:
- SkillFrontmatter: YAML frontmatter from SKILL.md
- SkillMetadata: Minimal metadata for Level 1 progressive disclosure
- Skill: Complete skill with content
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


class SkillFrontmatter(BaseModel):
    """YAML frontmatter parsed from SKILL.md files.

    This model represents the metadata section at the top of each SKILL.md file,
    enclosed in YAML delimiters (---).
    """

    name: str = Field(
        ...,
        description="Skill name (lowercase, underscores or hyphens)",
        pattern=r"^[a-z][a-z0-9_-]*$",
    )
    display_name: Optional[str] = Field(
        None,
        description="Human-readable display name (e.g., '异动检测')",
    )
    description: str = Field(
        ...,
        description="What the skill does AND when to use it. This is shown to the Agent for skill discovery.",
    )
    version: str = Field(
        default="1.0.0",
        description="Skill version (semantic versioning)",
    )
    category: Optional[str] = Field(
        None,
        description="Skill category for grouping (e.g., 'Analysis', 'Visualization')",
    )
    author: Optional[str] = Field(
        None,
        description="Author name or team",
    )
    license: Optional[str] = Field(
        None,
        description="License identifier (e.g., 'MIT', 'Apache-2.0')",
    )

    # Execution configuration
    entrypoint: Optional[str] = Field(
        default=None,
        description="Path to main.py entrypoint file (relative to skill directory)",
    )
    function: Optional[str] = Field(
        default="main",
        description="Function name to call in entrypoint",
    )
    requirements: List[str] = Field(
        default_factory=list,
        description="Python package requirements (e.g., ['pandas>=2.0.0'])",
    )

    # Permissions and configuration
    allowed_tools: Optional[str] = Field(
        default=None,
        description="Comma-separated list of tools this skill can use (e.g., 'Read,Write,Bash(python:*)')",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model override for this skill (e.g., 'claude-3-5-sonnet-20241022')",
    )
    disable_model_invocation: bool = Field(
        default=False,
        description="If True, prevents the skill from invoking the model directly",
    )
    mode: bool = Field(
        default=False,
        description="If True, this is a mode command (shown first in skill list)",
    )

    # Metadata for discovery
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization and search",
    )
    examples: List[str] = Field(
        default_factory=list,
        description="Example user queries that would trigger this skill",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate skill name format."""
        if not v or len(v) > 50:
            raise ValueError("Skill name must be 1-50 characters")
        if v.startswith(("_", "-")):
            raise ValueError("Skill name cannot start with _, -")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate description length."""
        if len(v) > 500:
            raise ValueError("Description must be <= 500 characters")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format (basic check)."""
        parts = v.split(".")
        if len(parts) < 2:
            raise ValueError("Version should follow semantic versioning (e.g., 1.0.0)")
        return v


@dataclass
class SkillMetadata:
    """Minimal metadata loaded at startup (~100 tokens per skill).

    This is the Level 1 progressive disclosure data - only what's needed
    for the Agent to decide which skill to activate.
    """

    name: str  # "anomaly_detection"
    description: str  # From frontmatter
    path: Path  # Path to SKILL.md
    version: str  # "1.0.0"
    category: Optional[str] = None  # "Analysis"
    is_mode: bool = False  # Mode command (shown first)
    display_name: Optional[str] = None  # Human-readable name


class Skill(BaseModel):
    """Complete skill with all content.

    This is the Level 2 progressive disclosure data - loaded only when
    the skill is activated.
    """

    metadata: SkillFrontmatter
    instructions: str  # Markdown content from SKILL.md (after frontmatter)
    base_dir: Path  # Directory containing SKILL.md

    @property
    def scripts_dir(self) -> Path:
        """Path to scripts directory (if exists)."""
        return self.base_dir / "scripts"

    @property
    def references_dir(self) -> Path:
        """Path to references directory (if exists)."""
        return self.base_dir / "references"

    @property
    def assets_dir(self) -> Path:
        """Path to assets directory (if exists)."""
        return self.base_dir / "assets"

    def has_scripts(self) -> bool:
        """Check if skill has scripts directory."""
        return self.scripts_dir.exists() and self.scripts_dir.is_dir()

    def has_references(self) -> bool:
        """Check if skill has references directory."""
        return self.references_dir.exists() and self.references_dir.is_dir()

    def has_assets(self) -> bool:
        """Check if skill has assets directory."""
        return self.assets_dir.exists() and self.assets_dir.is_dir()

    def get_allowed_tools_list(self) -> Optional[List[str]]:
        """Parse allowed_tools string into list."""
        if not self.metadata.allowed_tools:
            return None
        return [t.strip() for t in self.metadata.allowed_tools.split(",")]


class SkillSourceInfo(BaseModel):
    """Information about where a skill was installed from.

    Used for updates and reinstallation.
    """

    source_type: str = Field(
        ...,
        description="Type of source: 'local', 'github', 'git_url', 'zip'",
    )
    location: str = Field(
        ...,
        description="Source location (repo path, URL, or local path)",
    )
    subdirectory: Optional[str] = Field(
        None,
        description="Subdirectory within source (if applicable)",
    )
    ref: Optional[str] = Field(
        None,
        description="Branch/tag reference (for git sources)",
    )
    sha: Optional[str] = Field(
        None,
        description="Commit SHA (for pinned version)",
    )
    installed_at: str = Field(
        ...,
        description="ISO timestamp of installation",
    )
