"""
Integration tests for the Skills System.

Tests the complete workflow from skill loading to activation.
"""

import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.skills import (
    SkillLoader,
    SkillRegistry,
    SkillActivator,
    SkillInstaller,
    SkillInstallError,
    SkillActivationError,
    SkillMessageFormatter,
)
from backend.skills.models import SkillFrontmatter


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
description: "A test skill for integration testing"
version: "1.0.0"
category: "Testing"
tags: [test, integration]
author: "Test Author"
model: claude-sonnet-4-20250514
allowed_tools: web_search,web_reader
---

# Test Skill

This is a test skill for integration testing.

## Instructions

When activated, this skill provides test functionality.

### Usage

1. Use web_search to find information
2. Use web_reader to read content
""")

    # Create additional resources
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "test.py").write_text("print('test')")

    return skill_dir


@pytest.fixture
def sample_skill_zip(tmp_path):
    """Create a sample skill ZIP file."""
    zip_path = tmp_path / "external_skill.zip"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add SKILL.md
        skill_md_content = """---
name: external_skill
display_name: "External Skill"
description: "An external skill from ZIP"
version: "1.0.0"
category: "External"
tags:
  - external
  - zip
---

# External Skill

This skill was installed from a ZIP file.
"""
        zip_file.writestr("external_skill/SKILL.md", skill_md_content)

        # Add a script
        script_content = "# External script\nprint('external')\n"
        zip_file.writestr("external_skill/scripts/run.py", script_content)

    # Write to file
    with open(zip_path, 'wb') as f:
        f.write(zip_buffer.getvalue())

    return zip_path


class TestSkillDiscoveryFlow:
    """Test skill discovery and registry workflow."""

    def test_discover_and_register_skills(self, skills_base_dir, sample_skill):
        """Test discovering skills and registering them."""
        # Create loader
        loader = SkillLoader(skills_dirs=[skills_base_dir])

        # Create registry
        registry = SkillRegistry(loader)

        # Accessing registry methods triggers loading
        assert registry.skill_exists("test_skill")
        metadata = registry.get_skill_metadata("test_skill")
        assert metadata.name == "test_skill"
        assert metadata.display_name == "Test Skill"

    def test_get_formatted_skills_list(self, skills_base_dir, sample_skill):
        """Test getting formatted skills list for prompt."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)

        # Get formatted list (returns a string)
        skills_list = registry.get_formatted_skills_list()

        # Should contain skill info
        assert "test_skill" in skills_list
        assert "A test skill for integration testing" in skills_list

    def test_empty_registry(self, skills_base_dir):
        """Test registry with no skills."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)

        assert not registry.skill_exists("nonexistent")
        assert registry.get_skill_metadata("nonexistent") is None
        # Empty skills list should be empty string
        assert registry.get_formatted_skills_list() == ""


class TestSkillActivationFlow:
    """Test skill activation and message injection."""

    def test_activate_skill_injects_messages(self, skills_base_dir, sample_skill):
        """Test that activating a skill injects messages."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)

        activator = SkillActivator(loader, registry)

        # Activate skill
        messages, context_modifier = activator.activate_skill("test_skill")

        # Verify messages
        assert len(messages) >= 2  # metadata + instruction

        # First message: visible metadata
        metadata_msg = messages[0]
        assert metadata_msg["role"] == "user"
        assert "Test Skill" in metadata_msg["content"]
        assert metadata_msg["isMeta"] is False

        # Second message: hidden instructions
        instruction_msg = messages[1]
        assert instruction_msg["role"] == "user"
        assert "test skill for integration testing" in instruction_msg["content"]
        assert instruction_msg["isMeta"] is True

    def test_activate_skill_permissions(self, skills_base_dir, sample_skill):
        """Test that skill permissions are extracted."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)

        activator = SkillActivator(loader, registry)

        messages, context_modifier = activator.activate_skill("test_skill")

        # Should have permissions message
        permissions_msgs = [m for m in messages if isinstance(m.get("content"), dict)]
        assert len(permissions_msgs) == 1

        perm_msg = permissions_msgs[0]
        assert perm_msg["content"]["type"] == "command_permissions"
        assert "web_search" in perm_msg["content"]["allowed_tools"]
        assert "web_reader" in perm_msg["content"]["allowed_tools"]

        # Check context modifier
        assert context_modifier["allowed_tools"] == ["web_search", "web_reader"]

    def test_activate_nonexistent_skill_fails(self, skills_base_dir):
        """Test activating a non-existent skill raises error."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)
        activator = SkillActivator(loader, registry)

        with pytest.raises(SkillActivationError, match="not found"):
            activator.activate_skill("nonexistent")

    def test_conversation_history_integration(self, skills_base_dir, sample_skill):
        """Test message injection into conversation history."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)

        activator = SkillActivator(loader, registry)

        # Existing conversation
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        # Activate skill
        new_messages, _ = activator.activate_skill("test_skill", history)

        # New messages should be added
        # (The activator returns new messages, caller appends them)
        assert len(new_messages) >= 2

        # First new message should be metadata
        assert "Test Skill" in new_messages[0]["content"]


class TestExternalSkillInstallation:
    """Test external skill installation workflow."""

    def test_install_from_zip_workflow(self, skills_base_dir, sample_skill_zip):
        """Test complete ZIP installation workflow."""
        install_dir = skills_base_dir / "installed"
        install_dir.mkdir()

        # Create installer
        installer = SkillInstaller(install_dir=install_dir)

        # Install from ZIP
        skill = installer.install_from_zip(sample_skill_zip)

        # Verify skill was installed
        assert skill.metadata.name == "external_skill"
        assert skill.metadata.display_name == "External Skill"

        # Verify files exist
        skill_path = install_dir / "external_skill"
        assert skill_path.exists()
        assert (skill_path / "SKILL.md").exists()
        assert (skill_path / "scripts" / "run.py").exists()

        # Verify in registry
        installed = installer.list_installed()
        assert any(s["name"] == "external_skill" for s in installed)

    def test_install_and_discover_workflow(self, skills_base_dir, sample_skill_zip):
        """Test installing external skill and discovering it."""
        install_dir = skills_base_dir / "installed"
        install_dir.mkdir()

        # Install external skill
        installer = SkillInstaller(install_dir=install_dir)
        installer.install_from_zip(sample_skill_zip)

        # Now discover using loader
        loader = SkillLoader(skills_dirs=[install_dir])
        registry = SkillRegistry(loader)

        # Should discover the installed skill
        assert registry.skill_exists("external_skill")
        metadata = registry.get_skill_metadata("external_skill")
        assert metadata.display_name == "External Skill"

    def test_install_uninstall_workflow(self, skills_base_dir, sample_skill_zip):
        """Test installing and uninstalling a skill."""
        install_dir = skills_base_dir / "installed"
        install_dir.mkdir()

        installer = SkillInstaller(install_dir=install_dir)

        # Install
        skill = installer.install_from_zip(sample_skill_zip)
        skill_name = skill.metadata.name

        # Verify installed
        assert (install_dir / skill_name).exists()
        assert len(installer.list_installed()) == 1

        # Uninstall
        installer.uninstall(skill_name)

        # Verify removed
        assert not (install_dir / skill_name).exists()
        assert len(installer.list_installed()) == 0

    def test_duplicate_install_fails(self, skills_base_dir, sample_skill_zip):
        """Test that installing the same skill twice fails."""
        install_dir = skills_base_dir / "installed"
        install_dir.mkdir()

        installer = SkillInstaller(install_dir=install_dir)

        # First install
        installer.install_from_zip(sample_skill_zip)

        # Second install should fail
        with pytest.raises(SkillInstallError, match="already installed"):
            installer.install_from_zip(sample_skill_zip)


class TestMessageFormatting:
    """Test message formatting for Agent consumption."""

    def test_format_metadata_message(self, skills_base_dir, sample_skill):
        """Test formatting metadata message."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        skill = loader.load_skill_full("test_skill")

        formatter = SkillMessageFormatter()
        msg = formatter.create_metadata_message(skill)

        assert msg["role"] == "user"
        assert "Test Skill" in msg["content"]
        assert "test_skill" in msg["content"]
        assert msg["isMeta"] is False

    def test_format_instruction_message(self, skills_base_dir, sample_skill):
        """Test formatting instruction message."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        skill = loader.load_skill_full("test_skill")

        formatter = SkillMessageFormatter()
        msg = formatter.create_instruction_message(skill)

        assert msg["role"] == "user"
        assert "test skill for integration testing" in msg["content"]
        assert msg["isMeta"] is True

    def test_format_permissions_message(self, skills_base_dir, sample_skill):
        """Test formatting permissions message."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        skill = loader.load_skill_full("test_skill")

        formatter = SkillMessageFormatter()
        msg = formatter.create_permissions_message(skill)

        assert msg is not None
        assert msg["role"] == "user"
        assert msg["content"]["type"] == "command_permissions"
        assert "web_search" in msg["content"]["allowed_tools"]

    def test_format_permissions_no_tools(self, skills_base_dir):
        """Test formatting when skill has no allowed tools."""
        # Create skill without allowed-tools
        skill_dir = skills_base_dir / "no_tools_skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: no_tools_skill
display_name: "No Tools Skill"
description: "A skill without tool permissions"
version: "1.0.0"
---

# No Tools Skill

This skill has no tool permissions.
""")

        loader = SkillLoader(skills_dirs=[skills_base_dir])
        skill = loader.load_skill_full("no_tools_skill")

        formatter = SkillMessageFormatter()
        msg = formatter.create_permissions_message(skill)

        # Should return None when no tools
        assert msg is None

    def test_format_skills_list_for_prompt(self, skills_base_dir, sample_skill):
        """Test formatting skills list for system prompt."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)

        formatter = SkillMessageFormatter()
        # get_formatted_skills_list returns a string
        skills_list = registry.get_formatted_skills_list()
        formatted = formatter.format_skills_list_for_prompt(skills_list)

        # Should contain skill information
        assert "test_skill" in formatted
        assert "A test skill for integration testing" in formatted


class TestCompleteWorkflow:
    """Test complete end-to-end workflows."""

    def test_install_discover_activate_workflow(self, skills_base_dir, sample_skill_zip):
        """Test complete workflow: install -> discover -> activate."""
        # 1. Install external skill
        install_dir = skills_base_dir / "installed"
        install_dir.mkdir()
        installer = SkillInstaller(install_dir=install_dir)
        installer.install_from_zip(sample_skill_zip)

        # 2. Discover skills
        loader = SkillLoader(skills_dirs=[install_dir])
        registry = SkillRegistry(loader)

        # 3. Activate skill
        activator = SkillActivator(loader, registry)
        messages, context_modifier = activator.activate_skill("external_skill")

        # Verify complete workflow
        assert len(messages) >= 2
        assert "External Skill" in messages[0]["content"]
        assert registry.skill_exists("external_skill")
        assert (install_dir / "external_skill").exists()

    def test_multiple_skills_workflow(self, skills_base_dir):
        """Test workflow with multiple skills."""
        # Create multiple skills
        for i in range(3):
            skill_dir = skills_base_dir / f"skill_{i}"
            skill_dir.mkdir()

            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(f"""---
name: skill_{i}
display_name: "Skill {i}"
description: "Description {i}"
version: "1.0.0"
category: "Test"
---

# Skill {i}

This is skill {i}.
""")

        # Discover all
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)

        # Verify all discovered
        for i in range(3):
            assert registry.skill_exists(f"skill_{i}")

        # Get formatted list (string format)
        skills_list = registry.get_formatted_skills_list()
        for i in range(3):
            assert f"skill_{i}" in skills_list

        # Activate each
        activator = SkillActivator(loader, registry)
        for i in range(3):
            messages, _ = activator.activate_skill(f"skill_{i}")
            assert len(messages) >= 2

    def test_built_in_and_external_skills_workflow(self, skills_base_dir, sample_skill, sample_skill_zip):
        """Test workflow with both built-in and external skills."""
        # sample_skill is already in skills_base_dir (built-in)
        # Install external skill
        install_dir = skills_base_dir / "installed"
        install_dir.mkdir()
        installer = SkillInstaller(install_dir=install_dir)
        installer.install_from_zip(sample_skill_zip)

        # Create loader for both directories
        loader = SkillLoader(skills_dirs=[skills_base_dir, install_dir])
        registry = SkillRegistry(loader)

        # Should discover both
        assert registry.skill_exists("test_skill")  # built-in
        assert registry.skill_exists("external_skill")  # external

        # Get all skills
        skills_list = registry.get_formatted_skills_list()
        assert "test_skill" in skills_list
        assert "external_skill" in skills_list


class TestErrorHandling:
    """Test error handling throughout the system."""

    def test_invalid_skill_directory(self, skills_base_dir):
        """Test handling of invalid skill directory."""
        # Create directory without SKILL.md
        invalid_dir = skills_base_dir / "invalid"
        invalid_dir.mkdir()
        (invalid_dir / "README.md").write_text("No skill here")

        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)

        # Should not discover invalid skill
        assert not registry.skill_exists("invalid")

    def test_corrupted_skill_metadata(self, skills_base_dir):
        """Test handling of corrupted SKILL.md."""
        skill_dir = skills_base_dir / "corrupted"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("Invalid: {[yaml")

        loader = SkillLoader(skills_dirs=[skills_base_dir])

        # Should raise error when loading
        with pytest.raises(Exception):
            loader.load_skill_full("corrupted")

    def test_activate_after_skill_removed(self, skills_base_dir, sample_skill):
        """Test activating after skill is removed."""
        loader = SkillLoader(skills_dirs=[skills_base_dir])
        registry = SkillRegistry(loader)

        activator = SkillActivator(loader, registry)

        # Remove skill directory
        shutil.rmtree(sample_skill)

        # Invalidate cache to force reload
        registry.invalidate_cache()

        # Activation should fail
        with pytest.raises(SkillActivationError, match="not found"):
            activator.activate_skill("test_skill")
