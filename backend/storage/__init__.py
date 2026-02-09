"""
存储模块

跨平台存储路径配置管理
"""

from .config import (
    get_default_storage_dir,
    get_project_storage_dir,
    get_storage_dir,
    ensure_storage_dir,
    StorageConfigManager,
    create_storage_config,
    get_global_config,
    init_storage,
)

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
