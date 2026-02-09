"""
Artifact Store - 工具执行结果存储

扩展现有 DataStorage 功能，实现 BaseStore 接口
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from backend.models.filestore import (
    FileRef,
    FileCategory,
    FileMetadata,
)
from backend.filestore.base import WriteableStore
from backend.pipeline.storage import DataStorage, ArtifactMetadata


class ArtifactStore(WriteableStore):
    """
    工具执行结果存储

    扩展现有 DataStorage 功能:
    - 实现 BaseStore 接口
    - 支持 FileRef 转换
    - 增加元数据管理
    """

    # Artifact ID 格式
    ARTIFACT_PREFIX = "artifact_"
    ARTIFACT_HASH_LENGTH = 16

    def __init__(self, storage_dir: Path):
        """
        初始化 ArtifactStore

        Args:
            storage_dir: 存储目录
        """
        super().__init__(storage_dir)

        # 复用现有 DataStorage
        self._data_storage = DataStorage(
            storage_dir=str(storage_dir),
            max_age_hours=24,
            max_size_mb=1000
        )

        # 创建 artifacts 子目录
        self.artifacts_dir = storage_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def store(self, content: bytes, **metadata) -> FileRef:
        """
        存储数据

        Args:
            content: 文件二进制内容
            **metadata: 附加元数据

        Returns:
            FileRef: 文件引用
        """
        # 反序列化 JSON
        try:
            data = json.loads(content.decode('utf-8'))
        except Exception:
            # 如果不是 JSON，作为文本存储
            data = content.decode('utf-8', errors='ignore')

        # 计算哈希
        content_hash = hashlib.md5(content).hexdigest()

        # 生成 artifact_id
        data_str = json.dumps(data, sort_keys=True, default=str)
        data_hash = hashlib.md5(data_str.encode()).hexdigest()
        artifact_id = f"{self.ARTIFACT_PREFIX}{data_hash[:self.ARTIFACT_HASH_LENGTH]}"

        # 使用现有 DataStorage 存储
        stored_id, observation, artifact_meta = self._data_storage.store(
            data=data,
            tool_name=metadata.get('tool_name', ''),
            summary=metadata.get('summary')
        )

        # 转换为 FileRef
        return FileRef(
            file_id=stored_id,
            category=FileCategory.ARTIFACT,
            session_id=metadata.get('session_id'),
            size_bytes=len(content),
            hash=content_hash,
            mime_type=metadata.get('mime_type', 'application/json'),
            metadata={
                **metadata,
                'artifact_metadata': artifact_meta.model_dump(),
                'observation': observation
            }
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """
        检索文件

        Args:
            file_ref: 文件引用

        Returns:
            文件内容，如果不存在返回 None
        """
        data = self._data_storage.retrieve(file_ref.file_id)
        if data is None:
            return None

        return json.dumps(data).encode('utf-8')

    def delete(self, file_ref: FileRef) -> bool:
        """
        删除文件

        Args:
            file_ref: 文件引用

        Returns:
            是否成功删除
        """
        return self._data_storage.delete(file_ref.file_id)

    def exists(self, file_ref: FileRef) -> bool:
        """
        检查文件是否存在

        Args:
            file_ref: 文件引用

        Returns:
            文件是否存在
        """
        return file_ref.file_id in self._data_storage._metadata

    def list_files(
        self,
        tool_name: Optional[str] = None,
        limit: Optional[int] = None,
        **filters
    ) -> List[FileMetadata]:
        """
        列出文件

        Args:
            tool_name: 限定工具名称
            limit: 返回数量限制
            **filters: 其他过滤条件

        Returns:
            文件元数据列表
        """
        # 获取所有 artifacts
        all_metadata = list(self._data_storage._metadata.values())

        # 过滤
        if tool_name:
            all_metadata = [m for m in all_metadata if m.tool_name == tool_name]

        # 转换为 FileMetadata
        results = []
        for art in all_metadata[:limit] if limit else all_metadata:
            results.append(FileMetadata(
                file_ref=FileRef(
                    file_id=art.artifact_id,
                    category=FileCategory.ARTIFACT,
                    size_bytes=art.size_bytes,
                    hash=art.hash,
                    metadata={
                        'tool_name': art.tool_name,
                        'summary': art.summary
                    }
                ),
                filename=art.filename,
                created_at=datetime.fromtimestamp(art.created_at)
            ))

        return results

    def cleanup(self, max_age_hours: int = 24) -> int:
        """
        清理过期文件

        Args:
            max_age_hours: 最大年龄（小时）

        Returns:
            删除的文件数量
        """
        deleted = 0
        cutoff_time = time.time() - (max_age_hours * 3600)

        # 获取所有 artifacts
        all_metadata = list(self._data_storage._metadata.items())

        for artifact_id, meta in all_metadata:
            if meta.created_at < cutoff_time:
                if self._data_storage.delete(artifact_id):
                    deleted += 1

        return deleted

    def get_artifact_metadata(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        """
        获取 artifact 元数据

        Args:
            artifact_id: Artifact ID

        Returns:
            Artifact 元数据，如果不存在返回 None
        """
        return self._data_storage._metadata.get(artifact_id)

    def list_artifacts(
        self,
        tool_name: Optional[str] = None
    ) -> List[ArtifactMetadata]:
        """
        列出 artifacts

        Args:
            tool_name: 限定工具名称

        Returns:
            Artifact 元数据列表
        """
        all_metadata = list(self._data_storage._metadata.values())

        if tool_name:
            all_metadata = [m for m in all_metadata if m.tool_name == tool_name]

        return sorted(all_metadata, key=lambda m: m.created_at, reverse=True)


__all__ = [
    "ArtifactStore",
]
