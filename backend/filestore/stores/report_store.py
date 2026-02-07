"""
Report Store - 报告文件存储

支持存储生成的报告（markdown、html、json 格式）
支持报告版本管理、按会话隔离、TTL 自动清理
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


class ReportStore(IndexableStore, WriteableStore):
    """
    报告文件存储

    特性:
    - 支持多种报告格式（markdown、html、json）
    - 按会话隔离
    - 报告版本管理
    - SQLite 索引
    - TTL 自动清理
    """

    def __init__(self, storage_dir: Path):
        """
        初始化 ReportStore

        Args:
            storage_dir: 存储目录
        """
        IndexableStore.__init__(self, storage_dir, storage_dir / "reports_index.db")

        # 创建会话目录
        self.sessions_dir = storage_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        content: bytes,
        filename: str,
        session_id: str,
        report_type: str = "custom",
        format_type: str = "markdown",
        **metadata
    ) -> FileRef:
        """
        存储报告文件

        Args:
            content: 报告内容
            filename: 文件名
            session_id: 会话 ID
            report_type: 报告类型（daily/weekly/monthly/custom）
            format_type: 格式类型（markdown/html/json）
            **metadata: 附加元数据

        Returns:
            FileRef: 文件引用
        """
        # 生成 file_id
        file_id = f"report_{uuid.uuid4().hex[:12]}"
        content_hash = hashlib.md5(content).hexdigest()

        # 创建会话目录
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件
        file_path = session_dir / f"{file_id}_{filename}"
        self._write_file(file_path, content)

        # 检测 MIME 类型
        mime_type = self._detect_mime_type(format_type)

        # 添加报告特定元数据
        report_metadata = {
            "report_type": report_type,
            "format_type": format_type,
            "created_at": datetime.now().isoformat(),
        }
        metadata.update(report_metadata)

        # 计算报告 TTL（7天）
        ttl_seconds = 7 * 24 * 3600
        expires_at = time.time() + ttl_seconds

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
            category=FileCategory.REPORT,
            session_id=session_id,
            size_bytes=len(content),
            hash=content_hash,
            mime_type=mime_type,
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """
        检索报告

        Args:
            file_ref: 文件引用

        Returns:
            报告内容，如果不存在返回 None
        """
        index_data = self._index_get(file_ref.file_id)
        if not index_data:
            return None

        file_path = Path(index_data["file_path"])
        return self._read_file(file_path)

    def delete(self, file_ref: FileRef) -> bool:
        """
        删除报告

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
        检查报告是否存在

        Args:
            file_ref: 文件引用

        Returns:
            报告是否存在
        """
        return self._index_exists(file_ref.file_id)

    def list_files(
        self,
        session_id: Optional[str] = None,
        report_type: Optional[str] = None,
        limit: Optional[int] = None,
        **filters
    ) -> List[FileMetadata]:
        """
        列出报告

        Args:
            session_id: 限定会话 ID
            report_type: 报告类型过滤
            limit: 返回数量限制
            **filters: 其他过滤条件

        Returns:
            报告元数据列表
        """
        index_list = self._index_list(session_id=session_id, limit=limit)

        results = []
        for item in index_list:
            # 按报告类型过滤
            metadata = item.get("metadata", {})
            if report_type and metadata.get("report_type") != report_type:
                continue

            results.append(FileMetadata(
                file_ref=FileRef(
                    file_id=item["file_id"],
                    category=FileCategory.REPORT,
                    session_id=item["session_id"],
                    size_bytes=item["size_bytes"],
                    hash=item["hash"],
                    mime_type=item["mime_type"],
                    metadata=metadata
                ),
                filename=item["filename"],
                created_at=datetime.fromtimestamp(item["created_at"])
            ))

        return results

    def get_reports_by_type(
        self,
        report_type: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[FileMetadata]:
        """
        按报告类型获取报告

        Args:
            report_type: 报告类型（daily/weekly/monthly/custom）
            session_id: 限定会话 ID
            limit: 返回数量限制

        Returns:
            报告元数据列表
        """
        return self.list_files(
            session_id=session_id,
            report_type=report_type,
            limit=limit
        )

    def cleanup_expired(self) -> int:
        """
        清理过期报告

        Returns:
            清理的报告数量
        """
        import time
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

    def _detect_mime_type(self, format_type: str) -> str:
        """
        检测 MIME 类型

        Args:
            format_type: 格式类型

        Returns:
            MIME 类型字符串
        """
        mime_map = {
            "markdown": "text/markdown",
            "md": "text/markdown",
            "html": "text/html",
            "json": "application/json",
        }
        return mime_map.get(format_type.lower(), "text/plain")


__all__ = [
    "ReportStore",
]
