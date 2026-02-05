"""
记忆索引管理器

提供文件监听、文本分块、增量索引更新等功能
"""

import hashlib
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from .schema import (
    ensure_memory_index_schema,
    get_index_db_path,
    open_index_db,
    DEFAULT_INDEX_PATH
)


# 默认配置
DEFAULT_CHUNK_SIZE = 400  # chunk_tokens
DEFAULT_CHUNK_OVERLAP = 80  # overlap
DEFAULT_FTS_TABLE = "chunks_fts"


class MemoryIndexer:
    """
    记忆索引管理器

    功能:
    - 文件监听和变更检测
    - 文本分块和索引
    - 增量更新
    - FTS5 全文搜索
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        fts_enabled: bool = True,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    ):
        """
        初始化索引管理器

        Args:
            db_path: 数据库文件路径
            fts_enabled: 是否启用 FTS5
            chunk_size: 分块大小（行数）
            chunk_overlap: 分块重叠（行数）
        """
        self.db_path = db_path or get_index_db_path()
        self.fts_enabled = fts_enabled
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 线程锁（用于并发控制）
        self._lock = threading.Lock()

        # 打开数据库连接
        self.db = self._open_db()

        # 确保 schema 已创建
        schema_result = ensure_memory_index_schema(
            self.db,
            fts_table=DEFAULT_FTS_TABLE,
            fts_enabled=fts_enabled
        )

        self.fts_available = schema_result["fts_available"]
        self.fts_error = schema_result.get("fts_error")

    def _open_db(self) -> sqlite3.Connection:
        """打开数据库连接"""
        return open_index_db(self.db_path)

    def index_file(self, file_path: Path) -> Dict[str, Any]:
        """
        索引单个文件

        Args:
            file_path: 要索引的文件路径

        Returns:
            dict: 索引结果统计
        """
        if not file_path.exists():
            return {
                "success": False,
                "error": "文件不存在",
                "chunks_added": 0
            }

        # 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "chunks_added": 0
            }

        # 计算文件 hash
        file_hash = self._compute_hash(content)
        file_stat = file_path.stat()
        mtime = int(file_stat.st_mtime)
        size = file_stat.st_size

        # 检查是否需要更新
        existing = self._get_file_record(str(file_path))
        if existing and existing["hash"] == file_hash:
            return {
                "success": True,
                "updated": False,
                "chunks_added": 0
            }

        # 分块
        chunks = self._chunk_content(content, str(file_path))
        chunks_added = 0

        with self._lock:
            # 更新文件记录
            self._upsert_file_record(
                path=str(file_path),
                source="memory",
                hash=file_hash,
                mtime=mtime,
                size=size
            )

            # 删除旧的 chunks
            self._delete_chunks(str(file_path))

            # 添加新的 chunks
            for chunk in chunks:
                self._add_chunk(chunk)
                chunks_added += 1

        return {
            "success": True,
            "updated": True,
            "chunks_added": chunks_added
        }

    def search(
        self,
        query: str,
        max_results: int = 10,
        source_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆内容

        Args:
            query: 搜索查询
            max_results: 最大结果数
            source_filter: 来源过滤

        Returns:
            list: 搜索结果列表
        """
        if not query or not query.strip():
            return []

        query = query.strip()

        # 如果 FTS 不可用，使用简单的 LIKE 搜索
        if not self.fts_available:
            return self._search_like(query, max_results, source_filter)

        # 使用 FTS5 搜索
        results = self._search_fts(query, max_results, source_filter)

        # 如果 FTS 搜索没有结果（比如中文文本），回退到 LIKE 搜索
        if not results:
            results = self._search_like(query, max_results, source_filter)

        return results

    def _compute_hash(self, content: str) -> str:
        """计算内容的 hash 值"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _chunk_content(
        self,
        content: str,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """
        将内容分块

        Args:
            content: 文件内容
            file_path: 文件路径

        Returns:
            list: 分块列表
        """
        # 空内容返回空列表
        if not content or not content.strip():
            return []

        lines = content.split('\n')
        # 过滤掉空列表情况（比如空字符串 split 后是 ['']）
        if not lines or (len(lines) == 1 and not lines[0]):
            return []

        chunks = []

        start_line = 0
        chunk_size = self.chunk_size
        overlap = self.chunk_overlap

        while start_line < len(lines):
            end_line = min(start_line + chunk_size, len(lines))

            # 提取文本块
            chunk_lines = lines[start_line:end_line]
            chunk_text = '\n'.join(chunk_lines)

            # 跳过空块
            if not chunk_text or not chunk_text.strip():
                start_line = end_line - overlap if end_line < len(lines) else len(lines)
                continue

            # 计算块的 hash
            chunk_hash = self._compute_hash(chunk_text)

            # 生成唯一 ID
            chunk_id = f"{file_path}:{start_line+1}:{end_line}:{chunk_hash}"

            chunks.append({
                "id": chunk_id,
                "path": file_path,
                "source": "memory",
                "start_line": start_line + 1,  # 转换为 1-based
                "end_line": end_line,
                "hash": chunk_hash,
                "text": chunk_text,
                "updated_at": int(datetime.now().timestamp())
            })

            # 移动到下一个块（带重叠）
            start_line = end_line - overlap if end_line < len(lines) else len(lines)

        return chunks

    def _get_file_record(self, path: str) -> Optional[Dict[str, Any]]:
        """获取文件记录"""
        cursor = self.db.execute(
            "SELECT path, source, hash, mtime, size FROM files WHERE path = ?",
            (path,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "path": row[0],
                "source": row[1],
                "hash": row[2],
                "mtime": row[3],
                "size": row[4]
            }
        return None

    def _upsert_file_record(
        self,
        path: str,
        source: str,
        hash: str,
        mtime: int,
        size: int
    ) -> None:
        """插入或更新文件记录"""
        self.db.execute("""
            INSERT INTO files (path, source, hash, mtime, size)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                source=excluded.source,
                hash=excluded.hash,
                mtime=excluded.mtime,
                size=excluded.size
        """, (path, source, hash, mtime, size))

    def _delete_chunks(self, path: str) -> None:
        """删除文件的所有 chunks"""
        # 删除 FTS 表中的记录
        if self.fts_available:
            self.db.execute(
                f"DELETE FROM {DEFAULT_FTS_TABLE} WHERE path = ?",
                (path,)
            )

        # 删除 chunks 表中的记录
        self.db.execute("DELETE FROM chunks WHERE path = ?", (path,))

    def _add_chunk(self, chunk: Dict[str, Any]) -> None:
        """添加一个文本块"""
        # 添加到 chunks 表
        self.db.execute("""
            INSERT INTO chunks (id, path, source, start_line, end_line, hash, text, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chunk["id"],
            chunk["path"],
            chunk["source"],
            chunk["start_line"],
            chunk["end_line"],
            chunk["hash"],
            chunk["text"],
            chunk["updated_at"]
        ))

        # 添加到 FTS 表
        if self.fts_available:
            self.db.execute(f"""
                INSERT INTO {DEFAULT_FTS_TABLE} (rowid, text, id, path, source, start_line, end_line)
                VALUES (
                    (SELECT rowid FROM chunks WHERE id = ?),
                    ?, ?, ?, ?, ?, ?
                )
            """, (
                chunk["id"],
                chunk["text"],
                chunk["id"],
                chunk["path"],
                chunk["source"],
                chunk["start_line"],
                chunk["end_line"]
            ))

    def _search_like(
        self,
        query: str,
        max_results: int,
        source_filter: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """使用 LIKE 搜索"""
        # 构建查询
        sql = "SELECT id, path, source, start_line, end_line, text FROM chunks WHERE text LIKE ?"
        params = [f"%{query}%"]

        if source_filter:
            placeholders = ', '.join(['?'] * len(source_filter))
            sql += f" AND source IN ({placeholders})"
            params.extend(source_filter)

        sql += " LIMIT ?"
        params.append(max_results)

        cursor = self.db.execute(sql, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "path": row[1],
                "source": row[2],
                "start_line": row[3],
                "end_line": row[4],
                "text": row[5],
                "score": 1.0  # LIKE 搜索没有分数
            })

        return results

    def _search_fts(
        self,
        query: str,
        max_results: int,
        source_filter: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """使用 FTS5 搜索"""
        # 构建查询 - 使用 format 避免与 SQL 占位符冲突
        sql = """
            SELECT chunks.id, chunks.path, chunks.source, chunks.start_line, chunks.end_line, chunks.text
            FROM {fts_table}
            JOIN chunks ON chunks.rowid = {fts_table}.rowid
            WHERE {fts_table} MATCH ?
        """.format(fts_table=DEFAULT_FTS_TABLE)
        params = [query]

        if source_filter:
            placeholders = ', '.join(['?'] * len(source_filter))
            sql += " AND chunks.source IN ({})".format(placeholders)
            params.extend(source_filter)

        sql += " ORDER BY bm25({}) LIMIT ?".format(DEFAULT_FTS_TABLE)
        params.append(max_results)

        cursor = self.db.execute(sql, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "path": row[1],
                "source": row[2],
                "start_line": row[3],
                "end_line": row[4],
                "text": row[5],
                "score": 1.0  # BM25 分数可以后续添加
            })

        return results

    def get_status(self) -> Dict[str, Any]:
        """获取索引状态"""
        # 获取文件统计
        cursor = self.db.execute("SELECT COUNT(*) as c FROM files")
        file_count = cursor.fetchone()[0]

        # 获取块统计
        cursor = self.db.execute("SELECT COUNT(*) as c FROM chunks")
        chunk_count = cursor.fetchone()[0]

        # 获取 FTS 状态
        cursor = self.db.execute(f"SELECT COUNT(*) as c FROM {DEFAULT_FTS_TABLE}")
        fts_count = cursor.fetchone()[0] if self.fts_available else 0

        return {
            "db_path": str(self.db_path),
            "file_count": file_count,
            "chunk_count": chunk_count,
            "fts_available": self.fts_available,
            "fts_count": fts_count,
            "fts_error": self.fts_error
        }

    def close(self) -> None:
        """关闭数据库连接"""
        if hasattr(self, 'db') and self.db:
            self.db.close()

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()


class MemoryWatcher:
    """
    记忆文件监听器

    监控 memory/ 目录的文件变更，自动触发索引更新
    """

    def __init__(
        self,
        indexer: MemoryIndexer,
        watch_paths: List[Path],
        debounce_seconds: float = 1.5
    ):
        """
        初始化监听器

        Args:
            indexer: 索引管理器实例
            watch_paths: 要监听的路径列表
            debounce_seconds: 防抖秒数
        """
        self.indexer = indexer
        self.watch_paths = watch_paths
        self.debounce_seconds = debounce_seconds
        self._dirty_files = set()
        self._running = False
        self._thread = None

    def _is_watch_path(self, path: Path) -> bool:
        """检查路径是否在监听范围内"""
        for watch_path in self.watch_paths:
            try:
                path.resolve().relative_to(watch_path.resolve())
                return True
            except ValueError:
                continue
        return False

    def on_file_changed(self, path: Path) -> None:
        """文件变更回调"""
        if self._is_watch_path(path):
            self._dirty_files.add(path)

    def process_changes(self) -> Dict[str, Any]:
        """处理所有变更"""
        results = {
            "processed": 0,
            "failed": 0,
            "files": []
        }

        if not self._dirty_files:
            return results

        for file_path in list(self._dirty_files):
            try:
                result = self.indexer.index_file(file_path)
                if result["success"]:
                    results["processed"] += 1
                else:
                    results["failed"] += 1

                results["files"].append({
                    "path": str(file_path),
                    "success": result["success"],
                    "chunks_added": result.get("chunks_added", 0),
                    "error": result.get("error")
                })

                # 已处理，从集合中移除
                self._dirty_files.discard(file_path)

            except Exception as e:
                results["failed"] += 1
                results["files"].append({
                    "path": str(file_path),
                    "success": False,
                    "error": str(e)
                })

        return results

    def start(self) -> None:
        """启动监听（需要外部触发 process_changes）"""
        self._running = True

    def stop(self) -> None:
        """停止监听"""
        self._running = False
        self._dirty_files.clear()
