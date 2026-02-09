"""
FileStore 工厂函数

提供便捷的 FileStore 实例获取方法
"""

from pathlib import Path
from typing import Optional

from backend.filestore import FileStore
from backend.filestore.config import FileStoreConfigLoader


# 全局单例
_global_filestore: Optional[FileStore] = None


def get_file_store(
    base_dir: Optional[Path] = None,
    force_new: bool = False
) -> FileStore:
    """
    获取 FileStore 实例

    Args:
        base_dir: 存储目录，为 None 则使用配置文件
        force_new: 是否强制创建新实例

    Returns:
        FileStore 实例
    """
    global _global_filestore

    if force_new or _global_filestore is None:
        # 加载配置
        if base_dir is None:
            config = FileStoreConfigLoader.load()
            base_dir = config.base_dir

        _global_filestore = FileStore(base_dir=base_dir, config=None)

    return _global_filestore


def reset_file_store() -> None:
    """重置全局 FileStore 实例"""
    global _global_filestore

    if _global_filestore is not None:
        _global_filestore.close()
        _global_filestore = None


__all__ = [
    "get_file_store",
    "reset_file_store",
]
