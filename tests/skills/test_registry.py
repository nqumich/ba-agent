"""
Unit tests for SkillRegistry.

Tests skill metadata caching, formatting, and retrieval.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from backend.skills.loader import SkillLoader
from backend.skills.registry import SkillRegistry


@pytest.fixture
def temp_skills_dir():
    """Create a temporary skills directory for testing."""
    temp_dir = tempfile.mkdtemp()
    skills_path = Path(temp_dir)
    yield skills_path
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_skills(temp_skills_dir):
    """Create sample skills for testing."""
    # Regular skill
    skill1_dir = temp_skills_dir / "anomaly_detection"
    skill1_dir.mkdir()
    (skill1_dir / "SKILL.md").write_text(
        """---
name: anomaly_detection
display_name: "异动检测"
description: "检测数据中的异常波动并分析可能原因"
version: "1.0.0"
category: "Analysis"
tags:
  - anomaly
  - detection
---
"""
    )

    # Mode skill
    skill2_dir = temp_skills_dir / "dev_mode"
    skill2_dir.mkdir()
    (skill2_dir / "SKILL.md").write_text(
        """---
name: dev_mode
display_name: "开发模式"
description: "开发辅助模式"
version: "1.0.0"
mode: true
category: "Development"
---
"""
    )

    # Another regular skill
    skill3_dir = temp_skills_dir / "visualization"
    skill3_dir.mkdir()
    (skill3_dir / "SKILL.md").write_text(
        """---
name: visualization
display_name: "数据可视化"
description: "自动生成ECharts可视化代码"
version: "1.0.0"
category: "Visualization"
---
"""
    )

    return {
        "anomaly_detection": skill1_dir,
        "dev_mode": skill2_dir,
        "visualization": skill3_dir,
    }


@pytest.fixture
def loader(temp_skills_dir):
    """Create a SkillLoader for testing."""
    return SkillLoader([temp_skills_dir])


@pytest.fixture
def registry(loader):
    """Create a SkillRegistry for testing."""
    return SkillRegistry(loader)


class TestSkillRegistry:
    """Test SkillRegistry class."""

    def test_init(self, loader):
        """Test registry initialization."""
        registry = SkillRegistry(loader)
        assert registry.loader is loader
        assert registry._metadata_cache is None

    def test_get_all_metadata(self, registry, sample_skills):
        """Test getting all skill metadata."""
        metadata_dict = registry.get_all_metadata()

        assert len(metadata_dict) == 3
        assert "anomaly_detection" in metadata_dict
        assert "dev_mode" in metadata_dict
        assert "visualization" in metadata_dict

    def test_get_all_metadata_caching(self, registry, sample_skills):
        """Test that metadata is cached after first call."""
        # First call loads from disk
        metadata1 = registry.get_all_metadata()
        cache1 = registry._metadata_cache

        # Second call should use cache
        metadata2 = registry.get_all_metadata()
        cache2 = registry._metadata_cache

        assert cache1 is cache2
        assert metadata1 is metadata2

    def test_get_formatted_skills_list(self, registry, sample_skills):
        """Test formatting skills list for Agent."""
        formatted = registry.get_formatted_skills_list()

        # Should contain all skills
        assert '"anomaly_detection"' in formatted
        assert '"dev_mode"' in formatted
        assert '"visualization"' in formatted

        # Should contain descriptions
        assert "检测数据中的异常波动" in formatted
        assert "开发辅助模式" in formatted
        assert "自动生成ECharts" in formatted

    def test_get_formatted_skills_list_mode_first(self, registry, sample_skills):
        """Test that mode skills are listed first."""
        formatted = registry.get_formatted_skills_list()
        lines = formatted.strip().split("\n")

        # Mode skill should be first
        assert lines[0].startswith('"dev_mode"')

    def test_get_skill_metadata(self, registry, sample_skills):
        """Test getting metadata for specific skill."""
        metadata = registry.get_skill_metadata("anomaly_detection")

        assert metadata is not None
        assert metadata.name == "anomaly_detection"
        assert metadata.display_name == "异动检测"
        assert metadata.category == "Analysis"

    def test_get_skill_metadata_not_found(self, registry):
        """Test getting metadata for non-existent skill."""
        metadata = registry.get_skill_metadata("nonexistent")
        assert metadata is None

    def test_get_skill_full(self, registry, sample_skills):
        """Test loading full skill content."""
        skill = registry.get_skill_full("anomaly_detection")

        assert skill is not None
        assert skill.metadata.name == "anomaly_detection"
        assert skill.base_dir == sample_skills["anomaly_detection"]

    def test_get_skill_full_not_found(self, registry):
        """Test loading non-existent skill."""
        skill = registry.get_skill_full("nonexistent")
        assert skill is None

    def test_skill_exists(self, registry, sample_skills):
        """Test checking if skill exists."""
        assert registry.skill_exists("anomaly_detection") is True
        assert registry.skill_exists("nonexistent") is False

    def test_list_skill_names(self, registry, sample_skills):
        """Test listing all skill names."""
        names = registry.list_skill_names()
        assert len(names) == 3
        assert "anomaly_detection" in names
        assert "dev_mode" in names
        assert "visualization" in names

    def test_list_skill_names_sorted(self, registry, sample_skills):
        """Test that skill names are sorted."""
        names = registry.list_skill_names()
        # Should be alphabetically sorted
        assert names == sorted(names)

    def test_list_mode_skills(self, registry, sample_skills):
        """Test listing mode skills."""
        mode_skills = registry.list_mode_skills()
        assert len(mode_skills) == 1
        assert "dev_mode" in mode_skills
        assert "anomaly_detection" not in mode_skills

    def test_invalidate_cache(self, registry, sample_skills):
        """Test cache invalidation."""
        # Load metadata
        registry.get_all_metadata()
        assert registry._metadata_cache is not None

        # Invalidate cache
        registry.invalidate_cache()
        assert registry._metadata_cache is None

    def test_get_skills_by_category(self, registry, sample_skills):
        """Test getting skills by category."""
        analysis_skills = registry.get_skills_by_category("Analysis")
        assert "anomaly_detection" in analysis_skills
        assert "dev_mode" not in analysis_skills

        dev_skills = registry.get_skills_by_category("Development")
        assert "dev_mode" in dev_skills

    def test_get_all_categories(self, registry, sample_skills):
        """Test getting all unique categories."""
        categories = registry.get_all_categories()
        assert len(categories) == 3
        assert "Analysis" in categories
        assert "Development" in categories
        assert "Visualization" in categories

    def test_get_all_categories_sorted(self, registry, sample_skills):
        """Test that categories are sorted."""
        categories = registry.get_all_categories()
        assert categories == sorted(categories)

    def test_get_skills_info(self, registry, sample_skills):
        """Test getting detailed info about all skills."""
        info_list = registry.get_skills_info()
        assert len(info_list) == 3

        # Check structure of one entry
        anomaly_info = next(i for i in info_list if i["name"] == "anomaly_detection")
        assert anomaly_info["display_name"] == "异动检测"
        assert anomaly_info["category"] == "Analysis"
        assert anomaly_info["version"] == "1.0.0"
        assert anomaly_info["is_mode"] is False
        assert "path" in anomaly_info

    def test_cache_invalidation_after_invalidate(self, registry, sample_skills):
        """Test that get_all_metadata reloads after invalidation."""
        # First load
        metadata1 = registry.get_all_metadata()
        cache1 = registry._metadata_cache

        # Invalidate
        registry.invalidate_cache()

        # Second load should create new cache
        metadata2 = registry.get_all_metadata()
        cache2 = registry._metadata_cache

        # Caches should be different objects
        assert cache1 is not cache2
        # Content should be the same
        assert metadata1.keys() == metadata2.keys()

    def test_empty_registry(self, temp_skills_dir):
        """Test registry with no skills."""
        loader = SkillLoader([temp_skills_dir])
        registry = SkillRegistry(loader)

        assert len(registry.get_all_metadata()) == 0
        assert registry.list_skill_names() == []
        assert registry.list_mode_skills() == []
        assert registry.get_all_categories() == []
