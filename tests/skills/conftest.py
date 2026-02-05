"""
Shared fixtures for skills tests
"""

import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def skills_base_dir(tmp_path):
    """Create a temporary skills directory."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return skills_dir


@pytest.fixture
def sample_skill(skills_base_dir):
    """Create a sample skill directory."""
    skill_dir = skills_base_dir / "test_skill"
    skill_dir.mkdir()

    # Create SKILL.md
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: test_skill
display_name: "Test Skill"
description: "A test skill for testing"
version: "1.0.0"
category: "Testing"
---

# Test Skill

This is a test skill for unit testing.
""")

    return skill_dir


@pytest.fixture
def sample_mode_skill(skills_base_dir):
    """Create a sample mode skill directory."""
    skill_dir = skills_base_dir / "mode_skill"
    skill_dir.mkdir()

    # Create SKILL.md
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: mode_skill
display_name: "Mode Skill"
description: "A mode skill for testing"
version: "1.0.0"
mode: true
---

# Mode Skill

This is a mode skill.
""")

    return skill_dir


@pytest.fixture
def sample_skill_with_resources(skills_base_dir):
    """Create a sample skill with resources."""
    skill_dir = skills_base_dir / "resource_skill"
    skill_dir.mkdir()

    # Create SKILL.md
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: resource_skill
display_name: "Resource Skill"
description: "A skill with resources"
version: "1.0.0"
allowed_tools: Read,Write
---

# Resource Skill

This skill has resources.

## Available Resources

- scripts/analysis.py - Analysis script
- references/api.md - API reference
- assets/template.json - Template file
""")

    # Create resource directories
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "analysis.py").write_text("# Analysis script")
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "api.md").write_text("# API Reference")
    (skill_dir / "assets").mkdir()
    (skill_dir / "assets" / "template.json").write_text('{}')

    return skill_dir


@pytest.fixture
def sample_skill_zip(tmp_path):
    """Create a ZIP file containing a sample skill."""
    zip_path = tmp_path / "skill.zip"

    # Create a ZIP with a skill
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("external_skill/SKILL.md", """---
name: external_skill
display_name: "External Skill"
description: "An externally installed skill"
version: "1.0.0"
---

# External Skill

This skill was installed from a ZIP file.
""")

    return zip_path
