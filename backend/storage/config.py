"""
存储路径配置管理

支持跨平台的用户本地存储路径配置
"""

import os
import platform
from pathlib import Path
from typing import Optional
import json

from backend.models.filestore import FileStoreConfig


def get_default_storage_dir() -> Path:
    """
    获取默认的存储目录（跨平台）

    优先级:
    1. 环境变量 BA_STORAGE_DIR
    2. 用户本地目录（跨平台）

    Returns:
        默认存储目录路径
    """
    # 1. 检查环境变量
    env_dir = os.getenv("BA_STORAGE_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    # 2. 根据平台选择用户本地目录
    system = platform.system()

    if system == "Darwin":  # macOS
        # ~/Library/Application Support/ba-agent
        base = Path.home() / "Library" / "Application Support" / "ba-agent"
    elif system == "Windows":
        # %APPDATA%/ba-agent
        appdata = os.getenv("APPDATA", "")
        if appdata:
            base = Path(appdata) / "ba-agent"
        else:
            # 回退到用户主目录
            base = Path.home() / ".ba-agent"
    else:  # Linux 及其他
        # 遵循 XDG Base Directory Specification
        # $XDG_DATA_HOME/ba-agent 或 ~/.local/share/ba-agent
        xdg_data = os.getenv("XDG_DATA_HOME")
        if xdg_data:
            base = Path(xdg_data) / "ba-agent"
        else:
            base = Path.home() / ".local" / "share" / "ba-agent"

    return base


def get_project_storage_dir() -> Path:
    """
    获取项目级别的存储目录（相对路径）

    适用于开发环境和便携部署

    Returns:
        项目存储目录路径
    """
    return Path.cwd() / ".ba-agent" / "storage"


def get_storage_dir(
    use_project: bool = False,
    custom_dir: Optional[str] = None
) -> Path:
    """
    获取存储目录

    Args:
        use_project: 是否使用项目目录（开发环境）
        custom_dir: 自定义目录路径

    Returns:
        存储目录路径
    """
    # 1. 优先使用自定义目录
    if custom_dir:
        return Path(custom_dir).expanduser().resolve()

    # 2. 开发环境使用项目目录
    if use_project:
        return get_project_storage_dir()

    # 3. 生产环境使用用户本地目录
    return get_default_storage_dir()


def ensure_storage_dir(storage_dir: Optional[Path] = None) -> Path:
    """
    确保存储目录存在

    Args:
        storage_dir: 存储目录，None 时使用默认目录

    Returns:
        存储目录路径
    """
    if storage_dir is None:
        storage_dir = get_storage_dir()

    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


class StorageConfigManager:
    """
    存储配置管理器

    管理存储路径配置和初始化
    """

    def __init__(self, config_file: Optional[Path] = None):
        """
        初始化配置管理器

        Args:
            config_file: 配置文件路径，默认使用存储目录下的 storage_config.json
        """
        if config_file is None:
            storage_dir = get_storage_dir()
            config_file = storage_dir / "storage_config.json"

        self.config_file = config_file
        self.config = self._load_config()

        # 如果配置文件不存在，创建初始配置
        if not config_file.exists():
            self._save_config()

    def _load_config(self) -> dict:
        """加载配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        # 返回默认配置
        return {
            "storage_dir": str(get_default_storage_dir()),
            "initialized": False,
            "version": "1.0.0"
        }

    def _save_config(self):
        """保存配置"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def get_storage_dir(self) -> Path:
        """获取存储目录"""
        return Path(self.config.get("storage_dir", str(get_default_storage_dir())))

    def set_storage_dir(self, storage_dir: Path):
        """设置存储目录"""
        self.config["storage_dir"] = str(storage_dir.expanduser().resolve())
        self._save_config()

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self.config.get("initialized", False)

    def mark_initialized(self):
        """标记为已初始化"""
        self.config["initialized"] = True
        self._save_config()

    def get_config(self) -> FileStoreConfig:
        """获取 FileStoreConfig 对象"""
        return FileStoreConfig(
            base_dir=self.get_storage_dir(),
            initialized=self.is_initialized()
        )


def create_storage_config(
    storage_dir: Optional[Path] = None,
    force: bool = False
) -> StorageConfigManager:
    """
    创建或获取存储配置

    Args:
        storage_dir: 存储目录，None 时使用默认目录
        force: 是否强制重新初始化

    Returns:
        StorageConfigManager 实例
    """
    manager = StorageConfigManager()

    # 如果未初始化或强制重新初始化
    if not manager.is_initialized() or force:
        # 确定存储目录
        if storage_dir is None:
            storage_dir = get_storage_dir()

        # 创建目录
        storage_dir = ensure_storage_dir(storage_dir)

        # 保存配置
        manager.set_storage_dir(storage_dir)
        manager.mark_initialized()

        # 创建子目录结构
        _create_storage_structure(storage_dir)

    return manager


def _create_storage_structure(storage_dir: Path):
    """
    创建存储目录结构

    Args:
        storage_dir: 存储根目录
    """
    subdirs = [
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
        "index",
    ]

    for subdir in subdirs:
        (storage_dir / subdir).mkdir(parents=True, exist_ok=True)

    # 创建 README
    readme_path = storage_dir / "README.md"
    if not readme_path.exists():
        readme_content = f"""# BA-Agent Storage Directory

This directory contains all BA-Agent storage data.

**Location**: `{storage_dir}`

## Directory Structure

```
{storage_dir.name}/
├── artifacts/      # Tool execution artifacts
├── uploads/        # User uploaded files
├── reports/        # Generated reports
├── charts/         # Generated charts
├── cache/          # Temporary cache
├── temp/           # Temporary files
├── memory/         # Memory storage
│   ├── daily/      # Daily logs
│   ├── context/    # Context files
│   └── knowledge/  # Knowledge base
└── checkpoints/    # Session checkpoints
```

## Configuration

To change the storage location, set the `BA_STORAGE_DIR` environment variable:

```bash
export BA_STORAGE_DIR=/path/to/storage
```

Or modify `storage_config.json` in this directory.

## Cleanup

- Cache and temp files are cleaned automatically
- Old files may be removed based on TTL settings
- Check the main configuration file for retention policies
"""
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)


# 全局配置管理器实例
_global_config_manager: Optional[StorageConfigManager] = None


def get_global_config() -> StorageConfigManager:
    """
    获取全局配置管理器实例

    Returns:
        StorageConfigManager 实例
    """
    global _global_config_manager

    if _global_config_manager is None:
        _global_config_manager = create_storage_config()

    return _global_config_manager


def init_storage(
    storage_dir: Optional[str] = None,
    interactive: bool = True
) -> Path:
    """
    初始化存储配置（命令行接口）

    Args:
        storage_dir: 存储目录路径
        interactive: 是否交互式选择

    Returns:
        存储目录路径
    """
    import sys

    print("=" * 60)
    print("BA-Agent 存储配置初始化")
    print("=" * 60)

    # 确定存储目录
    if storage_dir:
        selected_dir = Path(storage_dir).expanduser().resolve()
        print(f"\n使用指定目录: {selected_dir}")
    elif interactive:
        default_dir = get_default_storage_dir()
        project_dir = get_project_storage_dir()

        print("\n请选择存储目录:")
        print(f"  1. 用户本地目录 (推荐): {default_dir}")
        print(f"  2. 项目目录 (开发环境): {project_dir}")
        print(f"  3. 自定义目录")

        choice = input("\n请选择 [1-3]: ").strip()

        if choice == "1":
            selected_dir = default_dir
        elif choice == "2":
            selected_dir = project_dir
        elif choice == "3":
            custom = input("请输入目录路径: ").strip()
            selected_dir = Path(custom).expanduser().resolve()
        else:
            print("无效选择，使用默认目录")
            selected_dir = default_dir
    else:
        selected_dir = get_default_storage_dir()
        print(f"\n使用默认目录: {selected_dir}")

    # 创建目录结构
    print(f"\n创建存储目录...")
    create_storage_config(selected_dir, force=True)

    # 显示配置信息
    print(f"\n✅ 存储配置完成!")
    print(f"   存储目录: {selected_dir}")
    print(f"   配置文件: {selected_dir / 'storage_config.json'}")
    print("\n提示: 可以通过设置 BA_STORAGE_DIR 环境变量来更改存储目录")

    return selected_dir


__all__ = [
    "get_default_storage_dir",
    "get_project_storage_dir",
    "get_storage_dir",
    "ensure_storage_dir",
    "StorageConfigManager",
    "create_storage_config",
    "get_global_config",
    "init_storage",
]
