"""
记忆索引轮换管理

当索引文件超过一定大小时，自动创建新的索引文件
搜索时同时使用所有索引文件
"""

import os
import sqlite3
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from .schema import get_index_db_path, open_index_db

logger = logging.getLogger(__name__)


# 默认配置
DEFAULT_MAX_INDEX_SIZE_MB = 50.0  # 单个索引文件最大大小（MB）
DEFAULT_INDEX_PREFIX = "memory"    # 索引文件前缀
INDEX_DIR = Path("memory/.index")  # 索引目录


def _get_config():
    """获取索引轮换配置"""
    try:
        from config import get_config
        config = get_config()
        if hasattr(config, 'memory') and hasattr(config.memory, 'index_rotation'):
            return config.memory.index_rotation
    except Exception:
        pass
    return None


class IndexRotationManager:
    """索引轮换管理器"""

    def __init__(
        self,
        max_size_mb: float = DEFAULT_MAX_INDEX_SIZE_MB,
        index_dir: Path = INDEX_DIR,
        index_prefix: str = DEFAULT_INDEX_PREFIX
    ):
        """
        初始化索引轮换管理器

        Args:
            max_size_mb: 单个索引文件最大大小（MB）
            index_dir: 索引目录
            index_prefix: 索引文件前缀
        """
        self.max_size_mb = max_size_mb
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.index_dir = index_dir
        self.index_prefix = index_prefix

        # 确保索引目录存在
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def get_current_index_path(self) -> Path:
        """
        获取当前活跃的索引文件路径

        Returns:
            Path: 当前索引文件路径
        """
        # 获取所有索引文件
        index_files = self._get_index_files()

        if not index_files:
            # 没有索引文件，创建默认的 memory.db
            return self.index_dir / f"{self.index_prefix}.db"

        # 检查最新的索引文件大小
        latest_index = index_files[-1]
        latest_size = latest_index.stat().st_size

        # 如果超过大小限制，创建新的索引文件
        if latest_size >= self.max_size_bytes:
            new_index = self._create_new_index()
            logger.info(
                f"索引文件 {latest_index.name} 已达到大小限制 "
                f"({latest_size / 1024 / 1024:.2f}MB >= {self.max_size_mb}MB)，"
                f"创建新索引: {new_index.name}"
            )
            return new_index

        return latest_index

    def get_all_index_paths(self) -> List[Path]:
        """
        获取所有索引文件路径

        Returns:
            List[Path]: 所有索引文件路径列表
        """
        index_files = self._get_index_files()
        return index_files if index_files else [self.index_dir / f"{self.index_prefix}.db"]

    def _get_index_files(self) -> List[Path]:
        """
        获取所有索引文件，按创建时间排序

        Returns:
            List[Path]: 排序后的索引文件列表
        """
        if not self.index_dir.exists():
            return []

        # 查找所有匹配的索引文件
        index_files = []
        for pattern in [f"{self.index_prefix}.db", f"{self.index_prefix}-*.db"]:
            index_files.extend(self.index_dir.glob(pattern))

        # 按文件名排序（memory.db, memory-1.db, memory-2.db, ...）
        index_files.sort(key=lambda p: p.name)

        return index_files

    def _create_new_index(self) -> Path:
        """
        创建新的索引文件

        Returns:
            Path: 新索引文件路径
        """
        # 获取现有索引文件编号
        index_files = self._get_index_files()

        # 找到最大编号
        max_num = 0
        for f in index_files:
            if f.name == f"{self.index_prefix}.db":
                continue
            # 从文件名提取编号 (memory-{num}.db)
            try:
                num = int(f.stem.split("-")[-1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                pass

        # 创建新索引文件
        new_num = max_num + 1
        new_index_path = self.index_dir / f"{self.index_prefix}-{new_num}.db"

        # 创建空数据库
        conn = sqlite3.connect(new_index_path)
        conn.close()

        logger.info(f"创建新索引文件: {new_index_path.name}")

        return new_index_path

    def get_index_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息

        Returns:
            Dict: 统计信息
        """
        index_files = self._get_index_files()

        if not index_files:
            return {
                "total_files": 0,
                "total_size_mb": 0,
                "files": []
            }

        files_info = []
        total_size = 0

        for f in index_files:
            size = f.stat().st_size
            total_size += size

            # 获取记录数
            try:
                conn = sqlite3.connect(f)
                cursor = conn.execute("SELECT COUNT(*) FROM chunks")
                count = cursor.fetchone()[0]
                conn.close()
            except Exception:
                count = 0

            files_info.append({
                "name": f.name,
                "size_mb": size / 1024 / 1024,
                "chunks_count": count
            })

        return {
            "total_files": len(index_files),
            "total_size_mb": total_size / 1024 / 1024,
            "files": files_info
        }

    def check_and_rotate(self) -> Optional[Path]:
        """
        检查当前索引是否需要轮换

        Returns:
            Optional[Path]: 如果创建了新索引，返回新索引路径；否则返回 None
        """
        current_index = self.get_current_index_path()

        # 获取所有索引文件
        index_files = self._get_index_files()
        if index_files and index_files[-1] != current_index:
            # 创建了新索引
            return current_index

        return None


# 全局实例
_rotation_manager: Optional[IndexRotationManager] = None


def get_rotation_manager(
    max_size_mb: float = None,
    index_dir: Path = None,
    index_prefix: str = None
) -> IndexRotationManager:
    """
    获取索引轮换管理器实例

    Args:
        max_size_mb: 单个索引文件最大大小（MB），None 表示使用配置
        index_dir: 索引目录，None 表示使用配置
        index_prefix: 索引文件前缀，None 表示使用配置

    Returns:
        IndexRotationManager: 索引轮换管理器实例
    """
    global _rotation_manager

    # 从配置获取默认值
    if max_size_mb is None or index_dir is None or index_prefix is None:
        config = _get_config()
        if config:
            if max_size_mb is None:
                max_size_mb = config.max_size_mb
            if index_dir is None:
                index_dir = Path(config.index_dir)
            if index_prefix is None:
                index_prefix = config.index_prefix

    # 使用硬编码的默认值作为最后的回退
    if max_size_mb is None:
        max_size_mb = DEFAULT_MAX_INDEX_SIZE_MB
    if index_dir is None:
        index_dir = INDEX_DIR
    if index_prefix is None:
        index_prefix = DEFAULT_INDEX_PREFIX

    if _rotation_manager is None:
        _rotation_manager = IndexRotationManager(
            max_size_mb=max_size_mb,
            index_dir=index_dir,
            index_prefix=index_prefix
        )

    return _rotation_manager


def get_current_index_path() -> Path:
    """
    获取当前活跃的索引文件路径

    Returns:
        Path: 当前索引文件路径
    """
    manager = get_rotation_manager()
    return manager.get_current_index_path()


def get_all_index_paths() -> List[Path]:
    """
    获取所有索引文件路径

    Returns:
        List[Path]: 所有索引文件路径列表
    """
    manager = get_rotation_manager()
    return manager.get_all_index_paths()


def check_index_rotation() -> Optional[Path]:
    """
    检查是否需要索引轮换

    Returns:
        Optional[Path]: 如果创建了新索引，返回新索引路径；否则返回 None
    """
    manager = get_rotation_manager()
    return manager.check_and_rotate()
