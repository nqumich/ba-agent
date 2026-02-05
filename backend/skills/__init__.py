"""
BA-Agent Skills System

This module implements a skill system based on Anthropic's Agent Skills specification.
Skills are instruction packages that modify Agent behavior through progressive disclosure
rather than being invoked as tools.

Architecture:
- Level 1 (Startup): Load skill metadata only (~100 tokens/skill)
- Level 2 (Activation): Load full SKILL.md instructions (<5,000 tokens)
- Level 3 (On-demand): Load resources (scripts/, references/, assets/)

Components:
- SkillLoader: Scan and load skills from directories
- SkillRegistry: Maintain skill metadata cache
- SkillActivator: Handle skill activation and message injection
- SkillFormatter: Format skill-related messages
- SkillInstaller: Install external skills from GitHub/git/ZIP
"""

from backend.skills.activator import SkillActivator, SkillActivationError
from backend.skills.formatter import SkillMessageFormatter
from backend.skills.installer import SkillInstaller, SkillInstallError
from backend.skills.loader import SkillLoader
from backend.skills.models import (
    Skill,
    SkillFrontmatter,
    SkillMetadata,
)
from backend.skills.registry import SkillRegistry
from backend.skills.skill_tool import create_skill_tool, SkillActivationInput

__all__ = [
    # Models
    "SkillFrontmatter",
    "Skill",
    "SkillMetadata",
    # Core components
    "SkillLoader",
    "SkillRegistry",
    "SkillActivator",
    "SkillMessageFormatter",
    "SkillInstaller",
    # Tool
    "create_skill_tool",
    "SkillActivationInput",
    # Exceptions
    "SkillActivationError",
    "SkillInstallError",
]
