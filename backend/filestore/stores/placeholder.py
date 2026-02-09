"""
Placeholder Store - 占位符存储基类

用于未完全实现的存储类型
"""

from typing import List, Optional
from pathlib import Path
from backend.models.filestore import FileRef, FileMetadata
from backend.filestore.base import BaseStore


class PlaceholderStore(BaseStore):
    """
    占位符存储基类

    为未完全实现的存储类型提供通用占位符实现
    """

    def __init__(self, base_dir: Optional[Path] = None, category: str = "placeholder"):
        """
        初始化占位符存储

        Args:
            base_dir: 存储目录（占位符实现中忽略）
            category: 存储类别名称
        """
        self.base_dir = base_dir
        self.category = category

    def store(self, content: bytes, **metadata) -> FileRef:
        """存储文件（占位符实现）"""
        import uuid
        file_id = f"{self.category}_{uuid.uuid4().hex[:12]}"
        return FileRef(
            file_id=file_id,
            category=self.category,
            session_id=metadata.get("session_id"),
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """检索文件（占位符实现）"""
        return None

    def delete(self, file_ref: FileRef) -> bool:
        """删除文件（占位符实现）"""
        return False

    def exists(self, file_ref: FileRef) -> bool:
        """检查文件是否存在（占位符实现）"""
        return False

    def list_files(self, **filters) -> List[FileMetadata]:
        """列出文件（占位符实现）"""
        return []


__all__ = ["PlaceholderStore"]
