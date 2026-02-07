"""
Code Store - 代码文件存储

支持存储模型生成的代码文件，支持代码管理和检索
"""

import uuid
import hashlib
import re
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


# 代码块检测正则表达式
CODE_BLOCK_PATTERN = re.compile(
    r'```(?:python|py)?\n(.*?)```',
    re.DOTALL
)

# 代码保存标识格式
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
    """

    CODE_PREFIX = "code_"

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

        # 保存为 .py 文件
        filename = f"{code_id}.py"
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
            metadata=metadata
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
    def generate_code_id() -> str:
        """
        生成唯一的代码标识

        Returns:
            代码标识，格式: code_YYYYMMDD_random
        """
        date_str = datetime.now().strftime("%Y%m%d")
        random_str = uuid.uuid4().hex[:8]
        return f"{CodeStore.CODE_PREFIX}{date_str}_{random_str}"

    @staticmethod
    def extract_code_blocks(text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取所有代码块

        Args:
            text: 文本内容

        Returns:
            代码块列表，每个元素包含 code, language, start, end
        """
        blocks = []

        for match in CODE_BLOCK_PATTERN.finditer(text):
            code = match.group(1).strip()
            blocks.append({
                "code": code,
                "language": "python",
                "start": match.start(),
                "end": match.end()
            })

        return blocks

    @staticmethod
    def has_code_blocks(text: str) -> bool:
        """
        检测文本是否包含代码块

        Args:
            text: 文本内容

        Returns:
            是否包含代码块
        """
        return CODE_BLOCK_PATTERN.search(text) is not None

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

    @staticmethod
    def replace_code_with_marker(
        text: str,
        code_block: str,
        code_id: str,
        description: Optional[str] = None
    ) -> str:
        """
        将代码块替换为保存标识

        Args:
            text: 原始文本
            code_block: 要替换的代码块（不包含反引号）
            code_id: 代码标识
            description: 代码描述

        Returns:
            替换后的文本
        """
        marker = CodeStore.create_code_saved_marker(code_id, description)
        # 使用更精确的替换，匹配 ```python 或 ```py 开头的代码块
        escaped_code = re.escape(code_block)
        pattern = r'```(?:python|py)?\s*' + escaped_code + r'\s*```'
        return re.sub(
            pattern,
            marker,
            text,
            flags=re.DOTALL
        )

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


__all__ = [
    "CodeStore",
]
