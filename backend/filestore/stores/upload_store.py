"""
Upload Store - 用户上传文件存储

支持会话隔离、自动元数据提取、Excel/CSV 解析
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


class UploadStore(IndexableStore, WriteableStore):
    """
    用户上传文件存储

    特性:
    - 按会话隔离
    - 自动提取元数据
    - 支持 Excel/CSV 解析
    - SQLite 索引
    """

    def __init__(self, storage_dir: Path):
        """
        初始化 UploadStore

        Args:
            storage_dir: 存储目录
        """
        # 初始化基类（IndexableStore 会创建索引数据库）
        IndexableStore.__init__(self, storage_dir, storage_dir / "uploads_index.db")

        # 创建会话目录
        self.sessions_dir = storage_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        content: bytes,
        filename: str,
        session_id: str,
        user_id: str,
        **metadata
    ) -> FileRef:
        """
        存储上传文件

        Args:
            content: 文件二进制内容
            filename: 原始文件名
            session_id: 会话 ID
            user_id: 用户 ID
            **metadata: 附加元数据

        Returns:
            FileRef: 文件引用
        """
        # 生成 file_id
        file_id = f"upload_{uuid.uuid4().hex[:12]}"
        content_hash = hashlib.md5(content).hexdigest()

        # 创建会话目录
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件
        file_path = session_dir / f"{file_id}_{filename}"
        self._write_file(file_path, content)

        # 检测 MIME 类型
        mime_type = self._detect_mime_type(filename)

        # 解析元数据（如果是 Excel/CSV）
        extra_metadata = self._extract_metadata(content, filename, mime_type)
        metadata.update(extra_metadata)

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
            expires_at=None
        )

        return FileRef(
            file_id=file_id,
            category=FileCategory.UPLOAD,
            session_id=session_id,
            size_bytes=len(content),
            hash=content_hash,
            mime_type=mime_type,
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """
        检索文件

        Args:
            file_ref: 文件引用

        Returns:
            文件内容，如果不存在返回 None
        """
        # 从索引获取文件路径
        index_data = self._index_get(file_ref.file_id)
        if not index_data:
            return None

        file_path = Path(index_data["file_path"])
        return self._read_file(file_path)

    def delete(self, file_ref: FileRef) -> bool:
        """
        删除文件

        Args:
            file_ref: 文件引用

        Returns:
            是否成功删除
        """
        # 从索引获取文件路径
        index_data = self._index_get(file_ref.file_id)
        if not index_data:
            return False

        file_path = Path(index_data["file_path"])

        # 删除文件
        deleted = self._delete_file(file_path)

        # 从索引删除
        if deleted:
            self._index_delete(file_ref.file_id)

        return deleted

    def exists(self, file_ref: FileRef) -> bool:
        """
        检查文件是否存在

        Args:
            file_ref: 文件引用

        Returns:
            文件是否存在
        """
        return self._index_exists(file_ref.file_id)

    def list_files(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
        **filters
    ) -> List[FileMetadata]:
        """
        列出文件

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
            results.append(FileMetadata(
                file_ref=FileRef(
                    file_id=item["file_id"],
                    category=FileCategory.UPLOAD,
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

    def delete_session_files(self, session_id: str) -> int:
        """
        删除会话的所有文件

        Args:
            session_id: 会话 ID

        Returns:
            删除的文件数量
        """
        index_list = self._index_list(session_id=session_id)
        count = 0

        for item in index_list:
            file_path = Path(item["file_path"])
            if self._delete_file(file_path):
                self._index_delete(item["file_id"])
                count += 1

        return count

    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文件元数据

        Args:
            file_id: 文件 ID

        Returns:
            文件元数据，如果不存在返回 None
        """
        return self._index_get(file_id)

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
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.csv': 'text/csv',
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.txt': 'text/plain',
            '.json': 'application/json',
        }
        return mime_map.get(ext, 'application/octet-stream')

    def _extract_metadata(
        self,
        content: bytes,
        filename: str,
        mime_type: str
    ) -> Dict[str, Any]:
        """
        提取文件元数据

        Args:
            content: 文件内容
            filename: 文件名
            mime_type: MIME 类型

        Returns:
            提取的元数据
        """
        metadata = {}

        # 如果是 Excel/CSV，尝试解析
        if 'excel' in mime_type or 'spreadsheet' in mime_type:
            metadata.update(self._parse_excel_metadata(content))
        elif mime_type == 'text/csv':
            metadata.update(self._parse_csv_metadata(content))
        elif mime_type == 'application/json':
            try:
                data = json.loads(content.decode('utf-8'))
                metadata.update({
                    'json_keys': list(data.keys()) if isinstance(data, dict) else [],
                    'json_type': type(data).__name__
                })
            except Exception:
                pass

        return metadata

    def _parse_excel_metadata(self, content: bytes) -> Dict[str, Any]:
        """
        解析 Excel 元数据

        Args:
            content: Excel 文件内容

        Returns:
            解析的元数据
        """
        metadata = {}
        try:
            import pandas as pd
            import io

            df = pd.read_excel(io.BytesIO(content), nrows=100)
            metadata.update({
                'rows': len(df),
                'columns': list(df.columns),
                'preview': df.head(10).to_dict(orient='records'),
                'data_types': {col: str(dtype) for col, dtype in df.dtypes.items()}
            })
        except Exception as e:
            metadata['parse_error'] = str(e)

        return metadata

    def _parse_csv_metadata(self, content: bytes) -> Dict[str, Any]:
        """
        解析 CSV 元数据

        Args:
            content: CSV 文件内容

        Returns:
            解析的元数据
        """
        metadata = {}
        try:
            import pandas as pd
            import io

            df = pd.read_csv(io.BytesIO(content), nrows=100)
            metadata.update({
                'rows': len(df),
                'columns': list(df.columns),
                'preview': df.head(10).to_dict(orient='records'),
                'data_types': {col: str(dtype) for col, dtype in df.dtypes.items()}
            })
        except Exception as e:
            metadata['parse_error'] = str(e)

        return metadata


__all__ = [
    "UploadStore",
]
