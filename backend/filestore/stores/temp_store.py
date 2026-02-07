"""
Temp Store - 临时文件存储

支持存储临时文件、中间结果等
支持短 TTL（默认 1 天）、自动清理
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


class TempStore(IndexableStore, WriteableStore):
    """
    临时文件存储

    特性:
    - 短 TTL（默认 24 小时）
    - 按会话隔离
    - 自动清理过期文件
    - SQLite 索引
    """

    def __init__(self, storage_dir: Path, default_ttl_hours: float = 24.0):
        """
        初始化 TempStore

        Args:
            storage_dir: 存储目录
            default_ttl_hours: 默认 TTL（小时）
        """
        IndexableStore.__init__(self, storage_dir, storage_dir / "temp_index.db")
        self.default_ttl_seconds = default_ttl_hours * 3600

        # 创建临时目录
        self.temp_dir = storage_dir / "data"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        content: bytes,
        filename: str,
        session_id: Optional[str] = None,
        ttl_hours: Optional[float] = None,
        **metadata
    ) -> FileRef:
        """
        存储临时文件

        Args:
            content: 文件内容
            filename: 文件名
            session_id: 会话 ID
            ttl_hours: TTL（小时），None 使用默认值
            **metadata: 附加元数据

        Returns:
            FileRef: 文件引用
        """
        # 生成 file_id
        file_id = f"temp_{uuid.uuid4().hex[:12]}"
        content_hash = hashlib.md5(content).hexdigest()

        # 保存文件
        file_path = self.temp_dir / f"{file_id}_{filename}"
        self._write_file(file_path, content)

        # 检测 MIME 类型
        mime_type = self._detect_mime_type(filename)

        # 计算 TTL
        ttl_seconds = int(ttl_hours * 3600) if ttl_hours else self.default_ttl_seconds
        expires_at = time.time() + ttl_seconds

        # 添加临时文件特定元数据
        temp_metadata = {
            "temp_filename": filename,
            "ttl_seconds": ttl_seconds,
            "created_at": datetime.now().isoformat(),
        }
        metadata.update(temp_metadata)

        # 保存到索引
        self._index_add(
            file_id=file_id,
            filename=filename,
            file_path=str(file_path),
            size_bytes=len(content),
            hash=content_hash,
            mime_type=mime_type,
            session_id=session_id,
            metadata=metadata,
            expires_at=expires_at
        )

        return FileRef(
            file_id=file_id,
            category=FileCategory.TEMP,
            session_id=session_id,
            size_bytes=len(content),
            hash=content_hash,
            mime_type=mime_type,
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """
        检索临时文件

        Args:
            file_ref: 文件引用

        Returns:
            文件内容，如果不存在或已过期返回 None
        """
        index_data = self._index_get(file_ref.file_id)
        if not index_data:
            return None

        # 检查是否过期
        if "expires_at" in index_data:
            expires_at = index_data["expires_at"]
            if time.time() > expires_at:
                # 删除过期文件
                self.delete(file_ref)
                return None

        file_path = Path(index_data["file_path"])
        return self._read_file(file_path)

    def delete(self, file_ref: FileRef) -> bool:
        """
        删除临时文件

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
        检查临时文件是否存在

        Args:
            file_ref: 文件引用

        Returns:
            文件是否存在（未过期）
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
        列出临时文件

        Args:
            session_id: 限定会话 ID
            limit: 返回数量限制
            **filters: 其他过滤条件

        Returns:
            文件元数据列表
        """
        index_list = self._index_list(session_id=session_id, limit=limit)

        results = []
        for item in index_list:
            # 过滤已过期的文件
            if "expires_at" in item:
                if time.time() > item["expires_at"]:
                    continue

            results.append(FileMetadata(
                file_ref=FileRef(
                    file_id=item["file_id"],
                    category=FileCategory.TEMP,
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
        清理过期临时文件

        Returns:
            清理的文件数量
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
        清理会话的所有临时文件

        Args:
            session_id: 会话 ID

        Returns:
            清理的文件数量
        """
        index_list = self._index_list(session_id=session_id)
        count = 0

        for item in index_list:
            file_path = Path(item["file_path"])
            if self._delete_file(file_path):
                self._index_delete(item["file_id"])
                count += 1

        return count

    def _detect_mime_type(self, filename: str) -> str:
        """
        检测 MIME 类型

        Args:
            filename: 文件名

        Returns:
            MIME 类型字符串
        """
        ext = Path(filename).suffix.lower()
        mime_map = {
            '.txt': 'text/plain',
            '.csv': 'text/csv',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.html': 'text/html',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.pdf': 'application/pdf',
        }
        return mime_map.get(ext, 'application/octet-stream')


__all__ = [
    "TempStore",
]
