"""
文件存储基础接口

定义所有存储实现的抽象基类
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from backend.models.filestore import (
    FileRef,
    FileCategory,
    FileMetadata,
)


class BaseStore(ABC):
    """
    存储基类

    所有具体存储实现（ArtifactStore, UploadStore 等）的抽象基类
    定义统一的存储接口规范
    """

    def __init__(self, storage_dir: Path):
        """
        初始化存储

        Args:
            storage_dir: 存储目录路径
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def store(self, content: bytes, **metadata) -> FileRef:
        """
        存储文件

        Args:
            content: 文件二进制内容
            **metadata: 附加元数据（如 filename, session_id, user_id 等）

        Returns:
            FileRef: 文件引用对象

        Raises:
            ValueError: 文件内容无效
            IOError: 存储失败
        """
        pass

    @abstractmethod
    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """
        检索文件

        Args:
            file_ref: 文件引用

        Returns:
            文件二进制内容，如果文件不存在返回 None

        Raises:
            PermissionError: 无访问权限
        """
        pass

    @abstractmethod
    def delete(self, file_ref: FileRef) -> bool:
        """
        删除文件

        Args:
            file_ref: 文件引用

        Returns:
            是否成功删除

        Raises:
            PermissionError: 无删除权限
        """
        pass

    @abstractmethod
    def exists(self, file_ref: FileRef) -> bool:
        """
        检查文件是否存在

        Args:
            file_ref: 文件引用

        Returns:
            文件是否存在
        """
        pass

    @abstractmethod
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
        pass

    def get_file_path(self, file_ref: FileRef) -> Path:
        """
        获取文件的物理路径（子类可覆盖以自定义路径结构）

        Args:
            file_ref: 文件引用

        Returns:
            文件物理路径

        Raises:
            ValueError: file_id 格式无效
        """
        # 验证 file_id 格式
        if not self._validate_file_id(file_ref.file_id):
            raise ValueError(f"Invalid file_id format: {file_ref.file_id}")

        # 构建路径
        file_path = self.storage_dir / file_ref.file_id

        # 安全检查
        try:
            resolved = file_path.resolve()
            storage_resolved = self.storage_dir.resolve()

            if not str(resolved).startswith(str(storage_resolved)):
                raise ValueError(f"Security violation: path outside sandbox")

            return resolved
        except Exception as e:
            raise ValueError(f"Path resolution failed: {e}")

    def _validate_file_id(self, file_id: str) -> bool:
        """
        验证 file_id 格式

        Args:
            file_id: 文件 ID

        Returns:
            是否有效
        """
        # 禁止路径分隔符
        if "/" in file_id or "\\" in file_id:
            return False

        # 禁止路径遍历
        if ".." in file_id:
            return False

        # 禁止空字符串
        if not file_id:
            return False

        return True

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息

        Returns:
            存储统计信息字典
        """
        files = self.list_files()
        total_size = sum(f.file_ref.size_bytes for f in files)

        return {
            "storage_dir": str(self.storage_dir),
            "file_count": len(files),
            "total_size_bytes": total_size,
            "category": self.__class__.__name__
        }


class WriteableStore(BaseStore):
    """
    可写存储基类

    提供常见的写入操作实现
    """

    def _write_file(
        self,
        file_path: Path,
        content: bytes,
        create_parent_dirs: bool = True
    ) -> None:
        """
        写入文件到磁盘

        Args:
            file_path: 目标文件路径
            content: 文件内容
            create_parent_dirs: 是否创建父目录

        Raises:
            IOError: 写入失败
        """
        try:
            if create_parent_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'wb') as f:
                f.write(content)
        except Exception as e:
            raise IOError(f"Failed to write file: {e}")

    def _read_file(self, file_path: Path) -> Optional[bytes]:
        """
        从磁盘读取文件

        Args:
            file_path: 文件路径

        Returns:
            文件内容，如果文件不存在返回 None
        """
        try:
            if not file_path.exists():
                return None

            with open(file_path, 'rb') as f:
                return f.read()
        except Exception:
            return None

    def _delete_file(self, file_path: Path) -> bool:
        """
        从磁盘删除文件

        Args:
            file_path: 文件路径

        Returns:
            是否成功删除
        """
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False


class IndexableStore(BaseStore):
    """
    可索引存储基类

    提供基于索引的文件管理
    """

    def __init__(self, storage_dir: Path, index_path: Optional[Path] = None):
        """
        初始化可索引存储

        Args:
            storage_dir: 存储目录
            index_path: 索引文件路径（默认使用 storage_dir/index.db）
        """
        super().__init__(storage_dir)
        self.index_path = index_path or (storage_dir / "index.db")
        self._init_index()

    def _init_index(self) -> None:
        """初始化索引数据库"""
        import sqlite3

        self.conn = sqlite3.connect(str(self.index_path))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_index (
                file_id TEXT PRIMARY KEY,
                filename TEXT,
                file_path TEXT,
                size_bytes INTEGER,
                hash TEXT,
                mime_type TEXT,
                session_id TEXT,
                created_at REAL,
                metadata TEXT,
                expires_at REAL
            )
        """)

        # 创建索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_id
            ON file_index(session_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at
            ON file_index(created_at)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at
            ON file_index(expires_at)
        """)

        self.conn.commit()

    def _index_add(
        self,
        file_id: str,
        filename: str,
        file_path: str,
        size_bytes: int,
        hash: str,
        mime_type: str,
        session_id: Optional[str],
        metadata: Dict[str, Any],
        expires_at: Optional[float]
    ) -> None:
        """添加文件到索引"""
        import json
        import time

        self.conn.execute("""
            INSERT INTO file_index
            (file_id, filename, file_path, size_bytes, hash, mime_type,
             session_id, created_at, metadata, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_id,
            filename,
            file_path,
            size_bytes,
            hash,
            mime_type,
            session_id,
            time.time(),
            json.dumps(metadata),
            expires_at
        ))
        self.conn.commit()

    def _index_get(self, file_id: str) -> Optional[Dict[str, Any]]:
        """从索引获取文件信息"""
        import json

        cursor = self.conn.execute("""
            SELECT * FROM file_index WHERE file_id = ?
        """, (file_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "file_id": row[0],
            "filename": row[1],
            "file_path": row[2],
            "size_bytes": row[3],
            "hash": row[4],
            "mime_type": row[5],
            "session_id": row[6],
            "created_at": row[7],
            "metadata": json.loads(row[8]) if row[8] else {},
            "expires_at": row[9]
        }

    def _index_delete(self, file_id: str) -> bool:
        """从索引删除文件"""
        cursor = self.conn.execute("""
            DELETE FROM file_index WHERE file_id = ?
        """, (file_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def _index_exists(self, file_id: str) -> bool:
        """检查索引中是否存在文件"""
        cursor = self.conn.execute("""
            SELECT 1 FROM file_index WHERE file_id = ?
        """, (file_id,))
        return cursor.fetchone() is not None

    def _index_list(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """列出索引中的文件"""
        import json

        query = "SELECT * FROM file_index"
        params = []

        conditions = []
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)

        results = []
        for row in cursor.fetchall():
            results.append({
                "file_id": row[0],
                "filename": row[1],
                "file_path": row[2],
                "size_bytes": row[3],
                "hash": row[4],
                "mime_type": row[5],
                "session_id": row[6],
                "created_at": row[7],
                "metadata": json.loads(row[8]) if row[8] else {},
                "expires_at": row[9]
            })

        return results

    def close(self) -> None:
        """关闭索引连接"""
        if hasattr(self, 'conn'):
            self.conn.close()


# 导出
__all__ = [
    "BaseStore",
    "WriteableStore",
    "IndexableStore",
]
