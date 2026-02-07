"""
统一文件存储管理器

提供所有文件类型的统一管理接口
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from backend.models.filestore import (
    FileRef,
    FileCategory,
    FileMetadata,
    FileStoreConfig,
    StorageStats,
    CleanupStats,
)
from backend.filestore.stores import (
    ArtifactStore,
    UploadStore,
    ReportStore,
    ChartStore,
    CacheStore,
    TempStore,
    MemoryStore,
    CheckpointStore,
    CodeStore,
)

logger = logging.getLogger(__name__)


class FileStore:
    """
    统一文件存储管理器

    单一入口管理所有文件类型，提供统一的存取接口

    示例:
        >>> file_store = FileStore()
        >>> file_ref = file_store.store_file(
        ...     content=b"Hello World",
        ...     category=FileCategory.ARTIFACT,
        ...     session_id="session_123"
        ... )
        >>> content = file_store.get_file(file_ref)
    """

    # 默认存储目录
    DEFAULT_BASE_DIR = Path("/var/lib/ba-agent")

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        config: Optional[FileStoreConfig] = None
    ):
        """
        初始化文件存储管理器

        Args:
            base_dir: 存储根目录（默认使用 DEFAULT_BASE_DIR）
            config: 文件系统配置（可选）
        """
        # 加载配置
        self.config = config or FileStoreConfig()
        self.base_dir = base_dir or self.config.base_dir

        # 确保基础目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 初始化各个存储
        self._init_stores()

        logger.info(f"FileStore initialized at {self.base_dir}")

    def _init_stores(self) -> None:
        """初始化各个存储实例"""
        self.artifacts = ArtifactStore(self.base_dir / "artifacts")
        self.uploads = UploadStore(self.base_dir / "uploads")
        self.reports = ReportStore(self.base_dir / "reports")
        self.charts = ChartStore(self.base_dir / "charts")
        self.cache = CacheStore(self.base_dir / "cache")
        self.temp = TempStore(self.base_dir / "temp")
        self.memory = MemoryStore(self.base_dir / "memory")
        self.checkpoints = CheckpointStore(self.base_dir / "temp" / "checkpoints")
        self.code = CodeStore(self.base_dir / "code")

        # 存储映射表
        self._stores = {
            FileCategory.ARTIFACT: self.artifacts,
            FileCategory.UPLOAD: self.uploads,
            FileCategory.REPORT: self.reports,
            FileCategory.CHART: self.charts,
            FileCategory.CACHE: self.cache,
            FileCategory.TEMP: self.temp,
            FileCategory.MEMORY: self.memory,
            FileCategory.CODE: self.code,
        }

    def store_file(
        self,
        content: bytes,
        category: FileCategory,
        **metadata
    ) -> FileRef:
        """
        统一存储接口

        Args:
            content: 文件二进制内容
            category: 文件类别
            **metadata: 附加元数据

        Returns:
            FileRef: 文件引用对象

        Raises:
            ValueError: 无效的文件类别
            IOError: 存储失败

        示例:
            >>> file_ref = file_store.store_file(
            ...     content=b"data",
            ...     category=FileCategory.ARTIFACT,
            ...     session_id="session_123"
            ... )
        """
        store = self._stores.get(category)
        if not store:
            raise ValueError(f"Unknown file category: {category}")

        # 检查文件大小
        max_size = self.config.max_file_sizes.get(category.value)
        if max_size and len(content) > max_size:
            raise ValueError(
                f"File size ({len(content)} bytes) exceeds "
                f"maximum allowed size ({max_size} bytes) for {category.value}"
            )

        try:
            file_ref = store.store(content, **metadata)
            logger.debug(f"Stored file: {file_ref}")
            return file_ref
        except Exception as e:
            logger.error(f"Failed to store file: {e}")
            raise IOError(f"Failed to store file: {e}")

    def get_file(self, file_ref: FileRef) -> Optional[bytes]:
        """
        获取文件内容

        Args:
            file_ref: 文件引用

        Returns:
            文件二进制内容，如果文件不存在返回 None

        示例:
            >>> content = file_store.get_file(file_ref)
        """
        store = self._stores.get(file_ref.category)
        if not store:
            logger.error(f"Unknown file category: {file_ref.category}")
            return None

        try:
            content = store.retrieve(file_ref)
            return content
        except Exception as e:
            logger.error(f"Failed to retrieve file {file_ref}: {e}")
            return None

    def delete_file(self, file_ref: FileRef) -> bool:
        """
        删除文件

        Args:
            file_ref: 文件引用

        Returns:
            是否成功删除

        示例:
            >>> success = file_store.delete_file(file_ref)
        """
        store = self._stores.get(file_ref.category)
        if not store:
            logger.error(f"Unknown file category: {file_ref.category}")
            return False

        try:
            result = store.delete(file_ref)
            if result:
                logger.debug(f"Deleted file: {file_ref}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete file {file_ref}: {e}")
            return False

    def file_exists(self, file_ref: FileRef) -> bool:
        """
        检查文件是否存在

        Args:
            file_ref: 文件引用

        Returns:
            文件是否存在

        示例:
            >>> exists = file_store.file_exists(file_ref)
        """
        store = self._stores.get(file_ref.category)
        if not store:
            return False

        try:
            return store.exists(file_ref)
        except Exception as e:
            logger.error(f"Failed to check file existence {file_ref}: {e}")
            return False

    def list_files(
        self,
        category: Optional[FileCategory] = None,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
        **filters
    ) -> List[FileMetadata]:
        """
        列出文件

        Args:
            category: 文件类别（None 表示所有类别）
            session_id: 限定会话 ID
            limit: 返回数量限制
            **filters: 其他过滤条件

        Returns:
            文件元数据列表

        示例:
            >>> files = file_store.list_files(
            ...     category=FileCategory.UPLOAD,
            ...     session_id="session_123"
            ... )
        """
        if category:
            store = self._stores.get(category)
            if not store:
                return []
            return store.list_files(session_id=session_id, limit=limit, **filters)

        # 列出所有类别的文件
        results = []
        for store in self._stores.values():
            results.extend(store.list_files(session_id=session_id, limit=limit, **filters))

        # 按创建时间排序
        results.sort(key=lambda f: f.created_at, reverse=True)

        # 应用限制
        if limit and len(results) > limit:
            results = results[:limit]

        return results

    def get_store(self, category: FileCategory):
        """
        获取特定存储实例

        Args:
            category: 文件类别

        Returns:
            对应的 Store 实例

        示例:
            >>> upload_store = file_store.get_store(FileCategory.UPLOAD)
        """
        return self._stores.get(category)

    def get_storage_stats(self, category: Optional[FileCategory] = None) -> List[StorageStats]:
        """
        获取存储统计信息

        Args:
            category: 文件类别（None 表示所有类别）

        Returns:
            存储统计信息列表

        示例:
            >>> stats = file_store.get_storage_stats()
        """
        if category:
            store = self._stores.get(category)
            if not store:
                return []
            return [self._get_store_stats(category, store)]

        # 获取所有类别的统计
        stats_list = []
        for cat, store in self._stores.items():
            stats_list.append(self._get_store_stats(cat, store))

        return stats_list

    def _get_store_stats(self, category: FileCategory, store) -> StorageStats:
        """获取单个存储的统计信息"""
        files = store.list_files()
        total_size = sum(f.file_ref.size_bytes for f in files)

        return StorageStats(
            category=category,
            file_count=len(files),
            total_size_bytes=total_size,
            oldest_file_age_hours=None,
            newest_file_age_hours=None
        )

    def cleanup(self, max_age_hours: Optional[int] = None) -> CleanupStats:
        """
        清理过期文件

        Args:
            max_age_hours: 最大年龄（小时），None 使用配置的 TTL

        Returns:
            清理统计信息

        示例:
            >>> stats = file_store.cleanup(max_age_hours=24)
        """
        import time

        deleted_count = 0
        freed_space = 0
        category_stats = {}
        start_time = time.time()

        for category, store in self._stores.items():
            # 获取 TTL 配置
            if max_age_hours is None:
                ttl_hours = self.config.ttl_config.get(category.value, 0)
            else:
                ttl_hours = max_age_hours

            # 跳过不过期的类别
            if ttl_hours == 0:
                continue

            # 获取文件列表
            files = store.list_files()
            category_deleted = 0

            for file_meta in files:
                # 检查是否过期
                file_age_hours = (time.time() - file_meta.created_at.timestamp()) / 3600
                if file_age_hours > ttl_hours:
                    if store.delete(file_meta.file_ref):
                        deleted_count += 1
                        freed_space += file_meta.file_ref.size_bytes
                        category_deleted += 1

            if category_deleted > 0:
                category_stats[category.value] = category_deleted

        duration = time.time() - start_time

        stats = CleanupStats(
            deleted_count=deleted_count,
            freed_space_bytes=freed_space,
            category_stats=category_stats,
            duration_seconds=duration
        )

        logger.info(
            f"Cleanup completed: {deleted_count} files deleted, "
            f"{freed_space} bytes freed in {duration:.2f}s"
        )

        return stats

    def close(self) -> None:
        """
        关闭文件存储管理器

        释放资源（如关闭数据库连接等）
        """
        for store in self._stores.values():
            if hasattr(store, 'close'):
                store.close()

        logger.info("FileStore closed")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()


# 导出
__all__ = [
    "FileStore",
]
