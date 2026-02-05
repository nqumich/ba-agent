"""
Unit tests for SkillLoader.

Tests skill discovery, metadata loading, and full skill loading.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from backend.skills.loader import SkillLoader, InvalidSkillError
from backend.skills.models import SkillFrontmatter


@pytest.fixture
def temp_skills_dir():
    """Create a temporary skills directory for testing."""
    temp_dir = tempfile.mkdtemp()
    skills_path = Path(temp_dir)
    yield skills_path
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_skill(temp_skills_dir):
    """Create a sample skill for testing."""
    skill_dir = temp_skills_dir / "test_skill"
    skill_dir.mkdir()

    skill_md_content = """---
name: test_skill
display_name: "Test Skill"
description: "A test skill for unit testing"
version: "1.0.0"
category: "Testing"
author: "Test Author"
tags:
  - test
  - example
examples:
  - "test query"
---

# Test Skill

This is a test skill for unit testing purposes.

## Instructions

1. Do this
2. Do that
"""
    (skill_dir / "SKILL.md").write_text(skill_md_content)
    return skill_dir


@pytest.fixture
def sample_skill_with_resources(temp_skills_dir):
    """Create a sample skill with resource directories."""
    skill_dir = temp_skills_dir / "resource_skill"
    skill_dir.mkdir()

    # Create resource directories
    (skill_dir / "scripts").mkdir()
    (skill_dir / "references").mkdir()
    (skill_dir / "assets").mkdir()

    # Create a script file
    (skill_dir / "scripts" / "run.py").write_text("print('hello')")

    skill_md_content = """---
name: resource_skill
description: "A skill with resource directories"
version: "1.0.0"
---

# Resource Skill
"""
    (skill_dir / "SKILL.md").write_text(skill_md_content)
    return skill_dir


class TestSkillLoader:
    """Test SkillLoader class."""

    def test_init_creates_directories(self, tmp_path):
        """Test that initialization creates directories if they don't exist."""
        new_dir = tmp_path / "new_skills"
        loader = SkillLoader([new_dir])
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_init_with_existing_directory(self, temp_skills_dir):
        """Test initialization with existing directory."""
        loader = SkillLoader([temp_skills_dir])
        assert loader.skills_dirs[0] == temp_skills_dir

    def test_load_all_metadata(self, temp_skills_dir, sample_skill):
        """Test loading all skill metadata."""
        loader = SkillLoader([temp_skills_dir])
        metadata_dict = loader.load_all_metadata()

        assert "test_skill" in metadata_dict
        metadata = metadata_dict["test_skill"]
        assert metadata.name == "test_skill"
        assert metadata.display_name == "Test Skill"
        assert metadata.description == "A test skill for unit testing"
        assert metadata.category == "Testing"
        assert metadata.version == "1.0.0"
        assert metadata.is_mode is False

    def test_load_all_metadata_mode_skill(self, temp_skills_dir):
        """Test loading mode skill metadata."""
        skill_dir = temp_skills_dir / "mode_skill"
        skill_dir.mkdir()

        skill_md_content = """---
name: mode_skill
description: "A mode skill"
mode: true
version: "1.0.0"
---
"""
        (skill_dir / "SKILL.md").write_text(skill_md_content)

        loader = SkillLoader([temp_skills_dir])
        metadata_dict = loader.load_all_metadata()

        assert metadata_dict["mode_skill"].is_mode is True

    def test_load_all_metadata_multiple_skills(self, temp_skills_dir):
        """Test loading multiple skills."""
        # Create multiple skills
        for i in range(3):
            skill_dir = temp_skills_dir / f"skill_{i}"
            skill_dir.mkdir()
            skill_md_content = f"""---
name: skill_{i}
description: "Skill number {i}"
version: "1.0.0"
---
"""
            (skill_dir / "SKILL.md").write_text(skill_md_content)

        loader = SkillLoader([temp_skills_dir])
        metadata_dict = loader.load_all_metadata()

        assert len(metadata_dict) == 3
        assert all(f"skill_{i}" in metadata_dict for i in range(3))

    def test_load_all_metadata_priority(self, tmp_path):
        """Test that later directories override earlier ones."""
        dir1 = tmp_path / "skills1"
        dir2 = tmp_path / "skills2"
        dir1.mkdir()
        dir2.mkdir()

        # Create skill in first directory
        skill1_dir = dir1 / "test_skill"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text(
            """---
name: test_skill
description: "First version"
version: "1.0.0"
---
"""
        )

        # Create skill with same name in second directory
        skill2_dir = dir2 / "test_skill"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text(
            """---
name: test_skill
description: "Second version (should win)"
version: "2.0.0"
---
"""
        )

        loader = SkillLoader([dir1, dir2])
        metadata_dict = loader.load_all_metadata()

        # Should use the version from dir2 (later directory)
        assert metadata_dict["test_skill"].description == "Second version (should win)"
        assert metadata_dict["test_skill"].version == "2.0.0"

    def test_load_all_metadata_empty_directory(self, temp_skills_dir):
        """Test loading from empty directory."""
        loader = SkillLoader([temp_skills_dir])
        metadata_dict = loader.load_all_metadata()
        assert len(metadata_dict) == 0

    def test_load_skill_full(self, temp_skills_dir, sample_skill):
        """Test loading full skill content."""
        loader = SkillLoader([temp_skills_dir])
        skill = loader.load_skill_full("test_skill")

        assert skill is not None
        assert skill.metadata.name == "test_skill"
        assert skill.metadata.description == "A test skill for unit testing"
        assert "This is a test skill" in skill.instructions
        assert skill.base_dir == sample_skill

    def test_load_skill_full_not_found(self, temp_skills_dir):
        """Test loading non-existent skill."""
        loader = SkillLoader([temp_skills_dir])
        skill = loader.load_skill_full("nonexistent")
        assert skill is None

    def test_load_skill_full_with_resources(
        self, temp_skills_dir, sample_skill_with_resources
    ):
        """Test loading skill with resource directories."""
        loader = SkillLoader([temp_skills_dir])
        skill = loader.load_skill_full("resource_skill")

        assert skill is not None
        assert skill.has_scripts()
        assert skill.has_references()
        assert skill.has_assets()
        assert (skill.scripts_dir / "run.py").exists()

    def test_parse_metadata_invalid_yaml(self, temp_skills_dir):
        """Test parsing invalid YAML frontmatter."""
        skill_dir = temp_skills_dir / "invalid_yaml"
        skill_dir.mkdir()

        # Invalid YAML
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            """---
name: test
description: "unclosed string [
version: "1.0.0"
---
"""
        )

        loader = SkillLoader([temp_skills_dir])
        with pytest.raises(InvalidSkillError, match="Invalid YAML"):
            loader._parse_metadata(skill_md)

    def test_parse_metadata_missing_frontmatter(self, temp_skills_dir):
        """Test parsing SKILL.md without frontmatter."""
        skill_dir = temp_skills_dir / "no_frontmatter"
        skill_dir.mkdir()

        # No frontmatter
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("# Just content\n\nNo frontmatter here.")

        loader = SkillLoader([temp_skills_dir])
        with pytest.raises(InvalidSkillError, match="Missing YAML frontmatter"):
            loader._parse_metadata(skill_md)

    def test_parse_metadata_missing_required_field(self, temp_skills_dir):
        """Test parsing frontmatter missing required field."""
        skill_dir = temp_skills_dir / "missing_field"
        skill_dir.mkdir()

        # Missing description (required)
        (skill_dir / "SKILL.md").write_text(
            """---
name: test
version: "1.0.0"
---
"""
        )

        loader = SkillLoader([temp_skills_dir])
        # Should raise validation error
        metadata_dict = loader.load_all_metadata()
        # Skill with missing field should be skipped with warning
        assert "test" not in metadata_dict

    def test_find_skill_file(self, temp_skills_dir, sample_skill):
        """Test finding a skill file by name."""
        loader = SkillLoader([temp_skills_dir])
        path = loader._find_skill_file("test_skill")
        assert path is not None
        assert path.name == "SKILL.md"
        assert path.parent.name == "test_skill"

    def test_find_skill_file_not_found(self, temp_skills_dir):
        """Test finding non-existent skill file."""
        loader = SkillLoader([temp_skills_dir])
        path = loader._find_skill_file("nonexistent")
        assert path is None

    def test_list_all_skills(self, temp_skills_dir, sample_skill):
        """Test listing all skill names."""
        loader = SkillLoader([temp_skills_dir])
        skills = loader.list_all_skills()
        assert "test_skill" in skills

    def test_get_skill_path(self, temp_skills_dir, sample_skill):
        """Test getting skill directory path."""
        loader = SkillLoader([temp_skills_dir])
        path = loader.get_skill_path("test_skill")
        assert path is not None
        assert path == sample_skill

    def test_get_skill_path_not_found(self, temp_skills_dir):
        """Test getting path for non-existent skill."""
        loader = SkillLoader([temp_skills_dir])
        path = loader.get_skill_path("nonexistent")
        assert path is None

    def test_nested_skill_directory(self, temp_skills_dir):
        """Test finding skill in nested directory structure."""
        nested_dir = temp_skills_dir / "analysis" / "anomaly_detection"
        nested_dir.mkdir(parents=True)

        (nested_dir / "SKILL.md").write_text(
            """---
name: anomaly_detection
description: "Detect anomalies"
version: "1.0.0"
---
"""
        )

        loader = SkillLoader([temp_skills_dir])
        skill = loader.load_skill_full("anomaly_detection")
        assert skill is not None
        assert skill.metadata.name == "anomaly_detection"
