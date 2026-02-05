"""
Unit tests for skill models.

Tests SkillFrontmatter, SkillMetadata, and Skill models.
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

from backend.skills.models import (
    SkillFrontmatter,
    Skill,
    SkillMetadata,
    SkillSourceInfo,
)


class TestSkillFrontmatter:
    """Test SkillFrontmatter model validation."""

    def test_valid_minimal_frontmatter(self):
        """Test valid frontmatter with minimal required fields."""
        data = {
            "name": "test_skill",
            "description": "A test skill for unit testing",
        }
        frontmatter = SkillFrontmatter(**data)
        assert frontmatter.name == "test_skill"
        assert frontmatter.description == "A test skill for unit testing"
        assert frontmatter.version == "1.0.0"  # default
        assert frontmatter.mode is False  # default

    def test_valid_complete_frontmatter(self):
        """Test valid frontmatter with all fields."""
        data = {
            "name": "my_skill",
            "display_name": "My Skill",
            "description": "A complete skill definition",
            "version": "2.1.0",
            "category": "Analysis",
            "author": "Test Author",
            "license": "MIT",
            "entrypoint": "skills/my_skill/main.py",
            "function": "run",
            "requirements": ["pandas>=2.0.0", "numpy>=1.24.0"],
            "allowed_tools": "Read,Write,Bash",
            "model": "claude-3-5-sonnet-20241022",
            "disable_model_invocation": False,
            "mode": True,
            "tags": ["test", "example"],
            "examples": ["Test query", "Another query"],
        }
        frontmatter = SkillFrontmatter(**data)
        assert frontmatter.name == "my_skill"
        assert frontmatter.display_name == "My Skill"
        assert frontmatter.mode is True
        assert len(frontmatter.requirements) == 2
        assert len(frontmatter.tags) == 2

    def test_name_validation_invalid_format(self):
        """Test name validation rejects invalid formats."""
        # Uppercase not allowed
        with pytest.raises(ValidationError):
            SkillFrontmatter(name="InvalidName", description="test")

        # Cannot start with underscore
        with pytest.raises(ValidationError):
            SkillFrontmatter(name="_invalid", description="test")

        # Cannot start with hyphen
        with pytest.raises(ValidationError):
            SkillFrontmatter(name="-invalid", description="test")

        # Too long
        with pytest.raises(ValidationError):
            SkillFrontmatter(name="a" * 51, description="test")

        # Empty
        with pytest.raises(ValidationError):
            SkillFrontmatter(name="", description="test")

    def test_name_validation_valid_formats(self):
        """Test name validation accepts valid formats."""
        valid_names = [
            "test",
            "test_skill",
            "test-skill",
            "test_skill_123",
            "my-skill-v2",
            "skill",
        ]
        for name in valid_names:
            frontmatter = SkillFrontmatter(name=name, description="test")
            assert frontmatter.name == name

    def test_description_validation_too_long(self):
        """Test description validation rejects too long descriptions."""
        long_desc = "a" * 501
        with pytest.raises(ValidationError, match="Description must be <= 500"):
            SkillFrontmatter(name="test", description=long_desc)

    def test_version_validation_invalid_format(self):
        """Test version validation rejects invalid formats."""
        with pytest.raises(ValidationError, match="Version should follow"):
            SkillFrontmatter(name="test", description="test", version="1")

    def test_version_validation_valid_formats(self):
        """Test version validation accepts valid formats."""
        valid_versions = [
            "1.0.0",
            "2.1.3",
            "0.0.1",
            "10.20.30",
            "1.0",
            "2.1",
        ]
        for version in valid_versions:
            frontmatter = SkillFrontmatter(
                name="test", description="test", version=version
            )
            assert frontmatter.version == version


class TestSkillMetadata:
    """Test SkillMetadata dataclass."""

    def test_create_metadata(self):
        """Test creating skill metadata."""
        metadata = SkillMetadata(
            name="test_skill",
            description="A test skill",
            category="Analysis",
            path=Path("/skills/test/SKILL.md"),
            version="1.0.0",
            is_mode=False,
            display_name="Test Skill",
        )
        assert metadata.name == "test_skill"
        assert metadata.description == "A test skill"
        assert metadata.category == "Analysis"
        assert metadata.version == "1.0.0"
        assert metadata.is_mode is False

    def test_metadata_defaults(self):
        """Test metadata optional fields default to None."""
        metadata = SkillMetadata(
            name="test",
            description="Test",
            path=Path("/test.md"),
            version="1.0.0",
        )
        assert metadata.category is None
        assert metadata.display_name is None
        assert metadata.is_mode is False


class TestSkill:
    """Test Skill model."""

    def test_create_skill(self, tmp_path):
        """Test creating a skill object."""
        frontmatter = SkillFrontmatter(
            name="test_skill",
            description="Test skill description",
        )
        skill = Skill(
            metadata=frontmatter,
            instructions="# Instructions\n\nThis is a test skill.",
            base_dir=tmp_path,
        )
        assert skill.metadata.name == "test_skill"
        assert skill.instructions == "# Instructions\n\nThis is a test skill."
        assert skill.base_dir == tmp_path

    def test_skill_properties(self, tmp_path):
        """Test skill directory properties."""
        # Create test directories
        (tmp_path / "scripts").mkdir()
        (tmp_path / "references").mkdir()
        (tmp_path / "assets").mkdir()

        frontmatter = SkillFrontmatter(
            name="test_skill",
            description="Test",
        )
        skill = Skill(
            metadata=frontmatter,
            instructions="Test instructions",
            base_dir=tmp_path,
        )

        assert skill.has_scripts()
        assert skill.has_references()
        assert skill.has_assets()
        assert skill.scripts_dir == tmp_path / "scripts"
        assert skill.references_dir == tmp_path / "references"
        assert skill.assets_dir == tmp_path / "assets"

    def test_skill_has_methods(self, tmp_path):
        """Test skill has_* methods."""
        frontmatter = SkillFrontmatter(name="test", description="test")
        skill = Skill(
            metadata=frontmatter,
            instructions="Test",
            base_dir=tmp_path,
        )

        # No directories exist
        assert not skill.has_scripts()
        assert not skill.has_references()
        assert not skill.has_assets()

        # Create one directory
        (tmp_path / "scripts").mkdir()
        assert skill.has_scripts()
        assert not skill.has_references()

    def test_get_allowed_tools_list(self, tmp_path):
        """Test parsing allowed_tools into list."""
        frontmatter = SkillFrontmatter(
            name="test",
            description="test",
            allowed_tools="Read,Write,Bash(python:*)",
        )
        skill = Skill(
            metadata=frontmatter,
            instructions="Test",
            base_dir=tmp_path,
        )

        tools = skill.get_allowed_tools_list()
        assert tools == ["Read", "Write", "Bash(python:*)"]

    def test_get_allowed_tools_list_none(self, tmp_path):
        """Test get_allowed_tools_list when not specified."""
        frontmatter = SkillFrontmatter(name="test", description="test")
        skill = Skill(
            metadata=frontmatter,
            instructions="Test",
            base_dir=tmp_path,
        )

        assert skill.get_allowed_tools_list() is None


class TestSkillSourceInfo:
    """Test SkillSourceInfo model."""

    def test_github_source(self):
        """Test GitHub source info."""
        source = SkillSourceInfo(
            source_type="github",
            location="anthropics/skills",
            subdirectory="sql-analyzer",
            ref="v1.0.0",
            sha="abc123",
            installed_at="2025-01-01T00:00:00Z",
        )
        assert source.source_type == "github"
        assert source.location == "anthropics/skills"
        assert source.subdirectory == "sql-analyzer"

    def test_local_source(self):
        """Test local source info."""
        source = SkillSourceInfo(
            source_type="local",
            location="/path/to/skill",
            installed_at="2025-01-01T00:00:00Z",
        )
        assert source.source_type == "local"
        assert source.location == "/path/to/skill"
        assert source.subdirectory is None
