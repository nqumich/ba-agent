"""
Chart Store - 图表文件存储

支持存储生成的图表（ECharts HTML、JSON 配置等）
支持图表按会话隔离、TTL 自动清理
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


class ChartStore(IndexableStore, WriteableStore):
    """
    图表文件存储

    特性:
    - 支持多种图表格式（html、json、png）
    - 按会话隔离
    - 图表配置索引
    - SQLite 索引
    - TTL 自动清理
    """

    def __init__(self, storage_dir: Path):
        """
        初始化 ChartStore

        Args:
            storage_dir: 存储目录
        """
        IndexableStore.__init__(self, storage_dir, storage_dir / "charts_index.db")

        # 创建会话目录
        self.sessions_dir = storage_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        content: bytes,
        filename: str,
        session_id: str,
        chart_type: str = "line",
        chart_config: Optional[Dict[str, Any]] = None,
        **metadata
    ) -> FileRef:
        """
        存储图表文件

        Args:
            content: 图表内容
            filename: 文件名
            session_id: 会话 ID
            chart_type: 图表类型（line/bar/pie/scatter/heatmap）
            chart_config: ECharts 配置（可选）
            **metadata: 附加元数据

        Returns:
            FileRef: 文件引用
        """
        # 生成 file_id
        file_id = f"chart_{uuid.uuid4().hex[:12]}"
        content_hash = hashlib.md5(content).hexdigest()

        # 创建会话目录
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件
        file_path = session_dir / f"{file_id}_{filename}"
        self._write_file(file_path, content)

        # 检测 MIME 类型
        mime_type = self._detect_mime_type(filename)

        # 添加图表特定元数据
        chart_metadata = {
            "chart_type": chart_type,
            "created_at": datetime.now().isoformat(),
        }
        if chart_config:
            chart_metadata["chart_config"] = chart_config
        metadata.update(chart_metadata)

        # 计算图表 TTL（7天）
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
            category=FileCategory.CHART,
            session_id=session_id,
            size_bytes=len(content),
            hash=content_hash,
            mime_type=mime_type,
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """
        检索图表

        Args:
            file_ref: 文件引用

        Returns:
            图表内容，如果不存在返回 None
        """
        index_data = self._index_get(file_ref.file_id)
        if not index_data:
            return None

        file_path = Path(index_data["file_path"])
        return self._read_file(file_path)

    def delete(self, file_ref: FileRef) -> bool:
        """
        删除图表

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
        检查图表是否存在

        Args:
            file_ref: 文件引用

        Returns:
            图表是否存在
        """
        return self._index_exists(file_ref.file_id)

    def list_files(
        self,
        session_id: Optional[str] = None,
        chart_type: Optional[str] = None,
        limit: Optional[int] = None,
        **filters
    ) -> List[FileMetadata]:
        """
        列出图表

        Args:
            session_id: 限定会话 ID
            chart_type: 图表类型过滤
            limit: 返回数量限制
            **filters: 其他过滤条件

        Returns:
            图表元数据列表
        """
        index_list = self._index_list(session_id=session_id, limit=limit)

        results = []
        for item in index_list:
            # 按图表类型过滤
            item_metadata = item.get("metadata", {})
            if chart_type and item_metadata.get("chart_type") != chart_type:
                continue

            results.append(FileMetadata(
                file_ref=FileRef(
                    file_id=item["file_id"],
                    category=FileCategory.CHART,
                    session_id=item["session_id"],
                    size_bytes=item["size_bytes"],
                    hash=item["hash"],
                    mime_type=item["mime_type"],
                    metadata=item_metadata
                ),
                filename=item["filename"],
                created_at=datetime.fromtimestamp(item["created_at"])
            ))

        return results

    def get_charts_by_type(
        self,
        chart_type: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[FileMetadata]:
        """
        按图表类型获取图表

        Args:
            chart_type: 图表类型（line/bar/pie/scatter/heatmap）
            session_id: 限定会话 ID
            limit: 返回数量限制

        Returns:
            图表元数据列表
        """
        return self.list_files(
            session_id=session_id,
            chart_type=chart_type,
            limit=limit
        )

    def cleanup_expired(self) -> int:
        """
        清理过期图表

        Returns:
            清理的图表数量
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
            '.html': 'text/html',
            '.htm': 'text/html',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.svg': 'image/svg+xml',
        }
        return mime_map.get(ext, 'application/octet-stream')


__all__ = [
    "ChartStore",
]
