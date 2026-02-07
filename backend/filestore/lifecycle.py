"""
生命周期管理

提供文件清理和存储使用统计功能
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from backend.filestore.file_store import FileStore
from backend.models.filestore import FileCategory, CleanupStats, StorageStats

logger = logging.getLogger(__name__)


class FileLifecycleManager:
    """
    文件生命周期管理器

    负责:
    - 定期清理过期文件
    - 监控存储使用情况
    - 自动触发清理
    """

    # 默认 TTL 配置（小时）
    DEFAULT_TTL_CONFIG = {
        'artifact': 24,
        'upload': 168,     # 7 days
        'report': 720,     # 30 days
        'chart': 168,      # 7 days
        'cache': 1,
        'temp': 0,         # 立即清理
        'memory': 8760,    # 永久（不清理）
        'checkpoint': 24,
    }

    def __init__(self, file_store: FileStore, ttl_config: Optional[Dict[str, int]] = None):
        """
        初始化生命周期管理器

        Args:
            file_store: FileStore 实例
            ttl_config: 自定义 TTL 配置（小时）
        """
        self.file_store = file_store
        self.ttl_config = ttl_config or self.DEFAULT_TTL_CONFIG.copy()

    def cleanup_expired_files(
        self,
        ttl_override: Optional[Dict[str, int]] = None,
        dry_run: bool = False
    ) -> CleanupStats:
        """
        清理过期文件

        Args:
            ttl_override: TTL 覆盖配置
            dry_run: 是否只模拟不实际删除

        Returns:
            清理统计信息
        """
        ttl_config = ttl_override or self.ttl_config
        deleted_count = 0
        freed_space = 0
        category_stats: Dict[str, int] = {}
        start_time = time.time()

        for category_str, ttl_hours in ttl_config.items():
            # 跳不过期的类别
            if ttl_hours == 0:
                continue

            try:
                category = FileCategory(category_str)
                store = self.file_store.get_store(category)

                if not store:
                    continue

                # 获取过期文件
                cutoff_time = time.time() - (ttl_hours * 3600)
                expired = self._get_expired_files(store, cutoff_time)

                category_deleted = 0
                for file_meta in expired:
                    if not dry_run:
                        if store.delete(file_meta.file_ref):
                            deleted_count += 1
                            freed_space += file_meta.file_ref.size_bytes
                            category_deleted += 1
                    else:
                        # Dry run: 只计数
                        deleted_count += 1
                        freed_space += file_meta.file_ref.size_bytes
                        category_deleted += 1

                if category_deleted > 0:
                    category_stats[category_str] = category_deleted

            except ValueError:
                # 无效的类别，跳过
                continue
            except Exception as e:
                logger.error(f"Error cleaning {category_str}: {e}")
                continue

        duration = time.time() - start_time

        stats = CleanupStats(
            deleted_count=deleted_count,
            freed_space_bytes=freed_space,
            category_stats=category_stats,
            duration_seconds=duration
        )

        if not dry_run:
            logger.info(
                f"Cleanup completed: {deleted_count} files deleted, "
                f"{freed_space} bytes freed in {duration:.2f}s"
            )
        else:
            logger.info(
                f"Dry run cleanup: {deleted_count} files would be deleted, "
                f"{freed_space} bytes would be freed"
            )

        return stats

    def _get_expired_files(self, store, cutoff_time: float) -> List:
        """
        获取过期文件列表

        Args:
            store: Store 实例
            cutoff_time: 截止时间戳

        Returns:
            过期文件列表
        """
        all_files = store.list_files()
        expired = []

        for file_meta in all_files:
            file_time = file_meta.created_at.timestamp()
            if file_time < cutoff_time:
                expired.append(file_meta)

        return expired

    def check_storage_usage(self) -> List[StorageStats]:
        """
        检查存储使用情况

        Returns:
            各类别存储统计
        """
        stats = self.file_store.get_storage_stats()
        return stats

    def get_total_storage_usage(self) -> Dict[str, Any]:
        """
        获取总存储使用情况

        Returns:
            总使用统计
        """
        stats_list = self.check_storage_usage()

        total_size = sum(s.total_size_bytes for s in stats_list)
        total_files = sum(s.file_count for s in stats_list)

        # 按类别统计
        by_category = {}
        for stats in stats_list:
            by_category[stats.category.value] = {
                'file_count': stats.file_count,
                'size_bytes': stats.total_size_bytes
            }

        return {
            'total_size_bytes': total_size,
            'total_files': total_files,
            'by_category': by_category
        }

    def cleanup_if_needed(
        self,
        threshold_percent: float = 90.0,
        max_size_gb: float = 10.0
    ) -> bool:
        """
        如果存储使用超过阈值，执行清理

        Args:
            threshold_percent: 触发清理的使用率阈值（百分比）
            max_size_gb: 最大存储容量（GB）

        Returns:
            是否执行了清理
        """
        usage = self.get_total_storage_usage()
        max_size_bytes = max_size_gb * 1024 ** 3

        usage_percent = (usage['total_size_bytes'] / max_size_bytes) * 100

        if usage_percent > threshold_percent:
            logger.warning(
                f"Storage usage {usage_percent:.1f}% exceeds threshold {threshold_percent}%, "
                f"triggering cleanup"
            )

            # 先清理 cache 和 temp
            urgent_cleanup = {
                'cache': self.ttl_config['cache'],
                'temp': self.ttl_config['temp']
            }

            self.cleanup_expired_files(ttl_override=urgent_cleanup)

            # 如果还是超过阈值，清理所有过期文件
            usage_after = self.get_total_storage_usage()
            usage_percent_after = (usage_after['total_size_bytes'] / max_size_bytes) * 100

            if usage_percent_after > threshold_percent:
                self.cleanup_expired_files()

            return True

        return False

    def get_file_age(self, file_ref) -> Optional[float]:
        """
        获取文件年龄（小时）

        Args:
            file_ref: 文件引用

        Returns:
            文件年龄（小时），如果文件不存在返回 None
        """
        if not self.file_store.file_exists(file_ref):
            return None

        files = self.file_store.list_files(category=file_ref.category)

        for file_meta in files:
            if file_meta.file_ref.file_id == file_ref.file_id:
                age_seconds = time.time() - file_meta.created_at.timestamp()
                return age_seconds / 3600

        return None

    def will_expire_soon(
        self,
        file_ref,
        within_hours: float = 1.0
    ) -> bool:
        """
        检查文件是否即将过期

        Args:
            file_ref: 文件引用
            within_hours: 时间范围（小时）

        Returns:
            是否即将过期
        """
        ttl_hours = self.ttl_config.get(file_ref.category.value, 0)

        if ttl_hours == 0:
            return False  # 不过期

        file_age = self.get_file_age(file_ref)

        if file_age is None:
            return False

        return (ttl_hours - file_age) <= within_hours


class StorageMonitor:
    """
    存储监控器

    定期检查存储使用情况并触发清理
    """

    def __init__(
        self,
        lifecycle_manager: FileLifecycleManager,
        check_interval_seconds: int = 3600,  # 1 hour
        threshold_percent: float = 90.0,
        max_size_gb: float = 10.0
    ):
        """
        初始化存储监控器

        Args:
            lifecycle_manager: 生命周期管理器
            check_interval_seconds: 检查间隔（秒）
            threshold_percent: 触发清理的阈值
            max_size_gb: 最大存储容量
        """
        self.lifecycle_manager = lifecycle_manager
        self.check_interval = check_interval_seconds
        self.threshold_percent = threshold_percent
        self.max_size_gb = max_size_gb
        self._running = False

    def start(self) -> None:
        """启动监控（需要在单独的线程中运行）"""
        import threading

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止监控"""
        self._running = False

    def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                # 检查存储使用
                self.lifecycle_manager.cleanup_if_needed(
                    threshold_percent=self.threshold_percent,
                    max_size_gb=self.max_size_gb
                )

                # 等待下次检查
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in storage monitor: {e}")
                time.sleep(60)  # 出错后等待1分钟再试

    def check_now(self) -> Dict[str, Any]:
        """
        立即检查存储使用情况

        Returns:
            存储使用统计
        """
        usage = self.lifecycle_manager.get_total_storage_usage()

        max_size_bytes = self.max_size_gb * 1024 ** 3
        usage_percent = (usage['total_size_bytes'] / max_size_bytes) * 100

        return {
            'usage_bytes': usage['total_size_bytes'],
            'usage_percent': usage_percent,
            'max_size_gb': self.max_size_gb,
            'needs_cleanup': usage_percent > self.threshold_percent,
            'by_category': usage['by_category']
        }


__all__ = [
    "FileLifecycleManager",
    "StorageMonitor",
]
