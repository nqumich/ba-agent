"""
Cache Store - 缓存文件存储

支持缓存计算结果、API 响应等
支持基于键的快速查找、TTL 自动过期
"""

import uuid
import hashlib
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from backend.models.filestore import (
    FileRef,
    FileCategory,
    FileMetadata,
)
from backend.filestore.base import IndexableStore, WriteableStore


class CacheStore(IndexableStore, WriteableStore):
    """
    缓存文件存储

    特性:
    - 基于键的快速查找
    - TTL 自动过期（默认 1 小时）
    - 按会话隔离
    - 命中率统计
    - SQLite 索引
    """

    def __init__(self, storage_dir: Path, default_ttl_hours: float = 1.0):
        """
        初始化 CacheStore

        Args:
            storage_dir: 存储目录
            default_ttl_hours: 默认 TTL（小时）
        """
        IndexableStore.__init__(self, storage_dir, storage_dir / "cache_index.db")
        self.default_ttl_seconds = default_ttl_hours * 3600

        # 创建缓存目录
        self.cache_dir = storage_dir / "data"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 缓存统计
        self._hits = 0
        self._misses = 0

    def store(
        self,
        content: bytes,
        cache_key: str,
        session_id: Optional[str] = None,
        ttl_hours: Optional[float] = None,
        **metadata
    ) -> FileRef:
        """
        存储缓存内容

        Args:
            content: 缓存内容
            cache_key: 缓存键
            session_id: 会话 ID
            ttl_hours: TTL（小时），None 使用默认值
            **metadata: 附加元数据

        Returns:
            FileRef: 文件引用
        """
        # 使用缓存键作为 file_id 的一部分
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        file_id = f"cache_{key_hash[:12]}"
        content_hash = hashlib.md5(content).hexdigest()

        # 保存文件
        file_path = self.cache_dir / f"{file_id}"
        self._write_file(file_path, content)

        # 计算 TTL
        ttl_seconds = int(ttl_hours * 3600) if ttl_hours else self.default_ttl_seconds
        expires_at = time.time() + ttl_seconds

        # 添加缓存特定元数据
        cache_metadata = {
            "cache_key": cache_key,
            "ttl_seconds": ttl_seconds,
            "created_at": datetime.now().isoformat(),
        }
        metadata.update(cache_metadata)

        # 保存到索引
        self._index_add(
            file_id=file_id,
            filename=file_id,
            file_path=str(file_path),
            size_bytes=len(content),
            hash=content_hash,
            mime_type="application/octet-stream",
            session_id=session_id,
            metadata=metadata,
            expires_at=expires_at
        )

        return FileRef(
            file_id=file_id,
            category=FileCategory.CACHE,
            session_id=session_id,
            size_bytes=len(content),
            hash=content_hash,
            mime_type="application/octet-stream",
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """
        检索缓存内容

        Args:
            file_ref: 文件引用

        Returns:
            缓存内容，如果不存在或已过期返回 None
        """
        index_data = self._index_get(file_ref.file_id)
        if not index_data:
            self._misses += 1
            return None

        # 检查是否过期
        if "expires_at" in index_data:
            expires_at = index_data["expires_at"]
            if time.time() > expires_at:
                # 删除过期缓存
                self.delete(file_ref)
                self._misses += 1
                return None

        file_path = Path(index_data["file_path"])
        content = self._read_file(file_path)
        if content:
            self._hits += 1
        return content

    def get_by_key(self, cache_key: str) -> Optional[bytes]:
        """
        通过缓存键获取内容

        Args:
            cache_key: 缓存键

        Returns:
            缓存内容，如果不存在或已过期返回 None
        """
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        file_id = f"cache_{key_hash[:12]}"

        # 从索引查找
        index_data = self._index_get(file_id)
        if not index_data:
            self._misses += 1
            return None

        # 检查是否过期
        if "expires_at" in index_data:
            expires_at = index_data["expires_at"]
            if time.time() > expires_at:
                # 删除过期缓存
                self._index_delete(file_id)
                self._misses += 1
                return None

        file_path = Path(index_data["file_path"])
        content = self._read_file(file_path)
        if content:
            self._hits += 1
        return content

    def delete(self, file_ref: FileRef) -> bool:
        """
        删除缓存

        Args:
            file_ref: 文件引用

        Returns:
            是否成功删除
        """
        index_data = self._index_get(file_ref.file_id)
        if not index_data:
            return False

        file_path = Path(index_data["file_path"])
        deleted = self._delete_file(file_path)

        if deleted:
            self._index_delete(file_ref.file_id)

        return deleted

    def exists(self, file_ref: FileRef) -> bool:
        """
        检查缓存是否存在

        Args:
            file_ref: 文件引用

        Returns:
            缓存是否存在（未过期）
        """
        index_data = self._index_get(file_ref.file_id)
        if not index_data:
            return False

        # 检查是否过期
        if "expires_at" in index_data:
            expires_at = index_data["expires_at"]
            if time.time() > expires_at:
                return False

        return True

    def list_files(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
        **filters
    ) -> List[FileMetadata]:
        """
        列出缓存

        Args:
            session_id: 限定会话 ID
            limit: 返回数量限制
            **filters: 其他过滤条件

        Returns:
            缓存元数据列表
        """
        index_list = self._index_list(session_id=session_id, limit=limit)

        results = []
        for item in index_list:
            # 过滤已过期的缓存
            if "expires_at" in item:
                if time.time() > item["expires_at"]:
                    continue

            results.append(FileMetadata(
                file_ref=FileRef(
                    file_id=item["file_id"],
                    category=FileCategory.CACHE,
                    session_id=item["session_id"],
                    size_bytes=item["size_bytes"],
                    hash=item["hash"],
                    mime_type=item["mime_type"],
                    metadata=item["metadata"]
                ),
                filename=item["filename"],
                created_at=datetime.fromtimestamp(item["created_at"])
            ))

        return results

    def cleanup_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            清理的缓存数量
        """
        current_time = time.time()
        index_list = self._index_list()
        count = 0

        for item in index_list:
            expires_at = item.get("expires_at")
            if expires_at and expires_at < current_time:
                file_path = Path(item["file_path"])
                if self._delete_file(file_path):
                    self._index_delete(item["file_id"])
                    count += 1

        return count

    def clear_session(self, session_id: str) -> int:
        """
        清理会话的所有缓存

        Args:
            session_id: 会话 ID

        Returns:
            清理的缓存数量
        """
        index_list = self._index_list(session_id=session_id)
        count = 0

        for item in index_list:
            file_path = Path(item["file_path"])
            if self._delete_file(file_path):
                self._index_delete(item["file_id"])
                count += 1

        return count

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息字典
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        index_list = self._index_list()
        total_size = sum(item["size_bytes"] for item in index_list)

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "total_items": len(index_list),
            "total_size_bytes": total_size,
        }

    def reset_stats(self) -> None:
        """重置缓存统计"""
        self._hits = 0
        self._misses = 0


__all__ = [
    "CacheStore",
]
