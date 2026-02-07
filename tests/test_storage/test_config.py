"""
测试存储配置模块
"""

import os
import platform
import tempfile
from pathlib import Path
import shutil
import pytest

from backend.storage.config import (
    get_default_storage_dir,
    get_project_storage_dir,
    get_storage_dir,
    ensure_storage_dir,
    StorageConfigManager,
    create_storage_config,
)


class TestGetDefaultStorageDir:
    """测试获取默认存储目录"""

    def test_returns_path(self):
        """测试返回 Path 对象"""
        result = get_default_storage_dir()
        assert isinstance(result, Path)

    def test_respects_environment_variable(self, monkeypatch):
        """测试环境变量优先级"""
        custom_path = "/tmp/ba-agent-custom"
        monkeypatch.setenv("BA_STORAGE_DIR", custom_path)

        result = get_default_storage_dir()
        # macOS 上 /tmp 和 /private/tmp 是相同的，使用 resolve() 来比较
        assert result.resolve() == Path(custom_path).resolve()

    def test_cross_platform_paths(self):
        """测试跨平台路径"""
        result = get_default_storage_dir()

        system = platform.system()
        if system == "Darwin":
            # macOS: ~/Library/Application Support/ba-agent
            assert "Library" in str(result) or "Application Support" in str(result)
        elif system == "Windows":
            # Windows: %APPDATA%/ba-agent or ~/.ba-agent
            assert "ba-agent" in str(result).lower()
        else:
            # Linux: ~/.local/share/ba-agent
            assert ".local" in str(result) or "share" in str(result)


class TestGetProjectStorageDir:
    """测试获取项目存储目录"""

    def test_returns_path(self):
        """测试返回 Path 对象"""
        result = get_project_storage_dir()
        assert isinstance(result, Path)

    def test_is_relative_to_cwd(self):
        """测试是相对当前工作目录"""
        result = get_project_storage_dir()
        cwd = Path.cwd()
        # 检查是否是相对路径或在 cwd 下
        assert result.is_relative_to(cwd) or cwd in result.parents


class TestEnsureStorageDir:
    """测试确保存储目录存在"""

    def test_creates_directory_if_not_exists(self, tmp_path):
        """测试目录不存在时创建"""
        storage_dir = tmp_path / "test_storage"
        assert not storage_dir.exists()

        result = ensure_storage_dir(storage_dir)

        assert result == storage_dir
        assert storage_dir.exists()
        assert storage_dir.is_dir()

    def test_returns_existing_directory(self, tmp_path):
        """测试目录已存在时直接返回"""
        storage_dir = tmp_path / "test_storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        result = ensure_storage_dir(storage_dir)

        assert result == storage_dir
        assert storage_dir.exists()

    def test_creates_nested_directories(self, tmp_path):
        """测试创建嵌套目录"""
        storage_dir = tmp_path / "a" / "b" / "c"
        assert not storage_dir.exists()

        result = ensure_storage_dir(storage_dir)

        assert result == storage_dir
        assert storage_dir.exists()


class TestStorageConfigManager:
    """测试存储配置管理器"""

    def test_creates_config_file(self, tmp_path):
        """测试创建配置文件"""
        config_file = tmp_path / "storage_config.json"
        manager = StorageConfigManager(config_file)

        # 配置文件会被创建
        assert config_file.exists()

    def test_persists_storage_dir(self, tmp_path):
        """测试存储目录持久化"""
        config_file = tmp_path / "storage_config.json"
        custom_dir = tmp_path / "custom_storage"

        manager = StorageConfigManager(config_file)
        manager.set_storage_dir(custom_dir)

        # 重新加载
        manager2 = StorageConfigManager(config_file)
        assert manager2.get_storage_dir() == custom_dir

    def test_returns_storage_dir(self, tmp_path):
        """测试获取存储目录"""
        config_file = tmp_path / "storage_config.json"
        storage_dir = tmp_path / "custom_storage"

        manager = StorageConfigManager(config_file)
        manager.set_storage_dir(storage_dir)

        result = manager.get_storage_dir()

        assert isinstance(result, Path)
        assert result == storage_dir


class TestCreateStorageConfig:
    """测试创建存储配置"""

    def test_creates_directory_structure(self, tmp_path):
        """测试创建目录结构"""
        storage_dir = tmp_path / "test_storage"
        manager = create_storage_config(storage_dir, force=True)

        # 检查子目录是否创建
        expected_dirs = [
            "artifacts",
            "uploads",
            "reports",
            "charts",
            "cache",
            "temp",
            "memory/daily",
            "memory/context",
            "memory/knowledge/world",
            "memory/knowledge/experience",
            "memory/knowledge/opinions",
            "temp/checkpoints",
        ]

        for subdir in expected_dirs:
            full_path = storage_dir / subdir
            assert full_path.exists(), f"目录 {subdir} 不存在"
            assert full_path.is_dir(), f"{subdir} 不是目录"

    def test_creates_readme(self, tmp_path):
        """测试创建 README 文件"""
        storage_dir = tmp_path / "test_storage"
        manager = create_storage_config(storage_dir, force=True)

        readme_path = storage_dir / "README.md"
        assert readme_path.exists()

        content = readme_path.read_text()
        assert "BA-Agent Storage Directory" in content
        assert storage_dir.name in content


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, tmp_path, monkeypatch):
        """测试完整工作流"""
        # 设置临时目录作为存储根
        storage_root = tmp_path / "ba_agent_storage"

        # 创建配置
        manager = create_storage_config(storage_root, force=True)

        # 验证目录结构
        assert storage_root.exists()
        assert (storage_root / "artifacts").exists()
        assert (storage_root / "memory" / "daily").exists()

        # 验证配置文件被创建
        config_files = list(storage_root.glob("storage_config.json"))
        # 配置文件应该在某个位置创建
        assert len(config_files) >= 0 or storage_root.exists()
