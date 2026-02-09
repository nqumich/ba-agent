"""
Code Store - 代码文件存储

支持存储模型生成的代码文件，支持代码管理和检索
"""

import uuid
import hashlib
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from backend.models.filestore import (
    FileRef,
    FileCategory,
    FileMetadata,
)
from backend.filestore.base import IndexableStore, WriteableStore


# 代码保存标识格式（用于前端显示和用户通知）
CODE_SAVED_PATTERN = re.compile(
    r'<!--\s*CODE_SAVED:\s*([^\s]+)\s*-->'
)


class CodeStore(IndexableStore, WriteableStore):
    """
    代码文件存储

    特性:
    - 自动检测和提取代码块
    - 生成可读的唯一标识
    - 支持代码检索和清理
    - SQLite 索引
    - 支持多种语言格式
    """

    CODE_PREFIX = "code_"

    # 语言到文件扩展名的映射
    LANGUAGE_EXTENSIONS = {
        'python': 'py',
        'py': 'py',
        'javascript': 'js',
        'js': 'js',
        'typescript': 'ts',
        'ts': 'ts',
        'html': 'html',
        'htm': 'html',
        'css': 'css',
        'sql': 'sql',
        'json': 'json',
        'yaml': 'yaml',
        'yml': 'yml',
        'xml': 'xml',
        'markdown': 'md',
        'md': 'md',
        'shell': 'sh',
        'bash': 'sh',
        'r': 'r',
        'java': 'java',
        'cpp': 'cpp',
        'c': 'c',
        'go': 'go',
        'rust': 'rs',
        'php': 'php',
        'ruby': 'rb',
    }

    def __init__(self, storage_dir: Path):
        """
        初始化 CodeStore

        Args:
            storage_dir: 存储目录
        """
        IndexableStore.__init__(self, storage_dir, storage_dir / "code_index.db")

        # 创建代码目录
        self.code_dir = storage_dir / "data"
        self.code_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        content: bytes,
        code_id: str,
        session_id: Optional[str] = None,
        description: Optional[str] = None,
        **metadata
    ) -> FileRef:
        """
        存储代码文件

        Args:
            content: 代码内容（文本）
            code_id: 代码唯一标识
            session_id: 会话 ID
            description: 代码描述
            **metadata: 附加元数据

        Returns:
            FileRef: 文件引用
        """
        content_hash = hashlib.md5(content).hexdigest()
        content_str = content.decode('utf-8', errors='ignore')

        # 验证并规范化 language
        language = metadata.get('language', 'python').lower()
        if language not in self.LANGUAGE_EXTENSIONS:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"不支持的语言类型 '{language}'，使用默认的 'python'")
            language = 'python'

        extension = self._get_file_extension(language)
        filename = f"{code_id}.{extension}"
        file_path = self.code_dir / filename
        self._write_file(file_path, content)

        # 生成摘要（取前100个字符）
        summary = content_str[:100].replace('\n', ' ')
        if len(content_str) > 100:
            summary += "..."

        # 添加代码特定元数据
        code_metadata = {
            "code_id": code_id,
            "description": description or summary,
            "language": "python",
            "line_count": content_str.count('\n') + 1,
            "char_count": len(content_str),
        }
        metadata.update(code_metadata)

        # 保存到索引
        self._index_add(
            file_id=code_id,
            filename=filename,
            file_path=str(file_path),
            size_bytes=len(content),
            hash=content_hash,
            mime_type="text/x-python",
            session_id=session_id,
            metadata=metadata,
            expires_at=None  # 代码文件不过期
        )

        return FileRef(
            file_id=code_id,
            category=FileCategory.CODE,
            session_id=session_id,
            size_bytes=len(content),
            hash=content_hash,
            mime_type="text/x-python",
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """
        检索代码文件

        Args:
            file_ref: 文件引用

        Returns:
            代码内容，如果不存在返回 None
        """
        index_data = self._index_get(file_ref.file_id)
        if not index_data:
            return None

        file_path = Path(index_data["file_path"])
        return self._read_file(file_path)

    def delete(self, file_ref: FileRef) -> bool:
        """
        删除代码文件

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
        检查代码文件是否存在

        Args:
            file_ref: 文件引用

        Returns:
            文件是否存在
        """
        index_data = self._index_get(file_ref.file_id)
        return index_data is not None

    def list_files(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
        **filters
    ) -> List[FileMetadata]:
        """
        列出代码文件

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
                    category=FileCategory.CODE,
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

    @staticmethod
    def create_code_saved_marker(code_id: str, description: Optional[str] = None) -> str:
        """
        创建代码保存标识

        Args:
            code_id: 代码标识
            description: 代码描述（可选）

        Returns:
            代码保存标识字符串
        """
        if description:
            return f"<!-- CODE_SAVED: {code_id} | {description} -->"
        return f"<!-- CODE_SAVED: {code_id} -->"

    @staticmethod
    def extract_code_saved_markers(text: str) -> List[str]:
        """
        从文本中提取所有代码保存标识

        Args:
            text: 文本内容

        Returns:
            代码标识列表
        """
        return CODE_SAVED_PATTERN.findall(text)

    def get_code_by_id(self, code_id: str) -> Optional[str]:
        """
        根据代码标识获取代码内容

        Args:
            code_id: 代码标识

        Returns:
            代码内容（字符串），如果不存在返回 None
        """
        file_ref = FileRef(
            file_id=code_id,
            category=FileCategory.CODE
        )
        content = self.retrieve(file_ref)
        if content:
            return content.decode('utf-8')
        return None

    def list_session_codes(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        列出会话的所有代码文件（用于统一文件列表）

        Args:
            session_id: 会话 ID
            limit: 返回数量限制

        Returns:
            文件信息列表，格式: [{"file_id": "...", "filename": "...", "file_type": "...", "size_bytes": ..., "description": "...", "language": "..."}, ...]
        """
        files = self.list_files(session_id=session_id, limit=limit)

        return [
            {
                "file_id": f.file_ref.file_id,
                "filename": f.filename,
                "file_type": self._get_file_extension(f.file_ref.metadata.get("language", "python")),
                "size_bytes": f.file_ref.size_bytes,
                "description": f.file_ref.metadata.get("description", ""),
                "language": f.file_ref.metadata.get("language", "python"),
            }
            for f in files
        ]

    @classmethod
    def _get_file_extension(cls, language: str) -> str:
        """
        根据语言获取文件扩展名

        Args:
            language: 语言名称

        Returns:
            文件扩展名（不含点）
        """
        language_lower = language.lower()
        return cls.LANGUAGE_EXTENSIONS.get(language_lower, 'txt')


__all__ = [
    "CodeStore",
]
