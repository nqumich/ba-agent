"""
Cache Store - 缓存文件存储

TODO: 完整实现
"""

from pathlib import Path
from typing import Optional
from backend.filestore.stores.placeholder import PlaceholderStore


class CacheStore(PlaceholderStore):
    """缓存文件存储（占位符）"""

    def __init__(self, base_dir: Optional[Path] = None):
        super().__init__(base_dir=base_dir, category="cache")


__all__ = ["CacheStore"]
