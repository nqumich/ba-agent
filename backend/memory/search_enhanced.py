"""
Memory Search 文件引用增强

为 MemorySearch 添加文件引用存储和返回功能
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from backend.models.filestore import FileRef, FileCategory
from backend.memory.schema import open_index_db, get_index_db_path

logger = logging.getLogger(__name__)


class FileRefIndex:
    """
    文件引用索引管理器

    管理记忆块与文件引用的关联关系
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化文件引用索引

        Args:
            db_path: 数据库路径，默认使用记忆索引数据库
        """
        if db_path is None:
            db_path = get_index_db_path()

        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self):
        """确保数据库 schema 已创建"""
        db = open_index_db(self.db_path)
        try:
            # 创建文件引用表
            db.execute("""
                CREATE TABLE IF NOT EXISTS chunk_file_refs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    metadata TEXT,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
                    UNIQUE(chunk_id, file_id, category)
                );
            """)

            # 创建索引
            db.execute("CREATE INDEX IF NOT EXISTS idx_chunk_file_refs_chunk_id ON chunk_file_refs(chunk_id);")
            db.execute("CREATE INDEX IF NOT EXISTS idx_chunk_file_refs_file_id ON chunk_file_refs(file_id);")

            db.commit()
        finally:
            db.close()

    def add_file_refs_to_chunk(
        self,
        chunk_id: str,
        file_refs: List[FileRef]
    ) -> int:
        """
        为记忆块添加文件引用

        Args:
            chunk_id: 记忆块 ID
            file_refs: 文件引用列表

        Returns:
            添加的引用数量
        """
        if not file_refs:
            return 0

        db = open_index_db(self.db_path)
        try:
            import time
            now = int(time.time())

            count = 0
            for ref in file_refs:
                try:
                    db.execute("""
                        INSERT OR REPLACE INTO chunk_file_refs
                        (chunk_id, file_id, category, metadata, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        chunk_id,
                        ref.file_id,
                        ref.category.value,
                        json.dumps(ref.metadata or {}),
                        now
                    ))
                    count += 1
                except Exception as e:
                    logger.warning(f"添加文件引用失败: {e}")

            db.commit()
            return count
        finally:
            db.close()

    def get_file_refs_for_chunk(self, chunk_id: str) -> List[FileRef]:
        """
        获取记忆块的文件引用

        Args:
            chunk_id: 记忆块 ID

        Returns:
            FileRef 列表
        """
        db = open_index_db(self.db_path)
        try:
            cursor = db.execute("""
                SELECT file_id, category, metadata
                FROM chunk_file_refs
                WHERE chunk_id = ?
                ORDER BY created_at DESC
            """, (chunk_id,))

            refs = []
            for row in cursor.fetchall():
                file_id, category, metadata_json = row
                try:
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    refs.append(FileRef(
                        file_id=file_id,
                        category=FileCategory(category),
                        metadata=metadata
                    ))
                except Exception as e:
                    logger.warning(f"解析文件引用失败: {e}")

            return refs
        finally:
            db.close()

    def get_file_refs_for_chunks(self, chunk_ids: List[str]) -> Dict[str, List[FileRef]]:
        """
        批量获取记忆块的文件引用

        Args:
            chunk_ids: 记忆块 ID 列表

        Returns:
            字典: chunk_id -> FileRef 列表
        """
        if not chunk_ids:
            return {}

        db = open_index_db(self.db_path)
        try:
            placeholders = ','.join(['?' for _ in chunk_ids])
            cursor = db.execute(f"""
                SELECT chunk_id, file_id, category, metadata
                FROM chunk_file_refs
                WHERE chunk_id IN ({placeholders})
                ORDER BY chunk_id, created_at DESC
            """, chunk_ids)

            result = {chunk_id: [] for chunk_id in chunk_ids}

            for row in cursor.fetchall():
                chunk_id, file_id, category, metadata_json = row
                try:
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    ref = FileRef(
                        file_id=file_id,
                        category=FileCategory(category),
                        metadata=metadata
                    )
                    if chunk_id in result:
                        result[chunk_id].append(ref)
                except Exception as e:
                    logger.warning(f"解析文件引用失败: {e}")

            return result
        finally:
            db.close()

    def search_chunks_by_file_ref(
        self,
        file_id: str,
        category: Optional[FileCategory] = None
    ) -> List[str]:
        """
        搜索引用了特定文件的记忆块

        Args:
            file_id: 文件 ID
            category: 文件类别（可选）

        Returns:
            记忆块 ID 列表
        """
        db = open_index_db(self.db_path)
        try:
            if category:
                cursor = db.execute("""
                    SELECT DISTINCT chunk_id
                    FROM chunk_file_refs
                    WHERE file_id = ? AND category = ?
                """, (file_id, category.value))
            else:
                cursor = db.execute("""
                    SELECT DISTINCT chunk_id
                    FROM chunk_file_refs
                    WHERE file_id = ?
                """, (file_id,))

            return [row[0] for row in cursor.fetchall()]
        finally:
            db.close()

    def remove_file_refs_for_chunk(self, chunk_id: str) -> int:
        """
        删除记忆块的所有文件引用

        Args:
            chunk_id: 记忆块 ID

        Returns:
            删除的引用数量
        """
        db = open_index_db(self.db_path)
        try:
            cursor = db.execute("""
                DELETE FROM chunk_file_refs
                WHERE chunk_id = ?
            """, (chunk_id,))
            db.commit()
            return cursor.rowcount
        finally:
            db.close()


class FileRefSearchResult:
    """
    带文件引用的搜索结果

    扩展搜索结果以包含文件引用信息
    """

    def __init__(
        self,
        id: str,
        path: str,
        source: str,
        start_line: int,
        end_line: int,
        text: str,
        score: float = 0.0,
        file_refs: Optional[List[FileRef]] = None,
        context: Optional[str] = None,
        **kwargs
    ):
        """
        初始化搜索结果

        Args:
            id: 记忆块 ID
            path: 文件路径
            source: 来源
            start_line: 起始行
            end_line: 结束行
            text: 文本内容
            score: 相关性分数
            file_refs: 文件引用列表
            context: 上下文
            **kwargs: 其他字段
        """
        self.id = id
        self.path = path
        self.source = source
        self.start_line = start_line
        self.end_line = end_line
        self.text = text
        self.score = score
        self.file_refs = file_refs or []
        self.context = context or text
        self.extra = kwargs

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "path": self.path,
            "source": self.source,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "text": self.text,
            "score": self.score,
            "file_refs": [
                {
                    "file_id": ref.file_id,
                    "category": ref.category.value,
                    "session_id": ref.session_id,
                    "metadata": ref.metadata
                }
                for ref in self.file_refs
            ],
            "context": self.context,
            **self.extra
        }

    def has_file_refs(self) -> bool:
        """是否有文件引用"""
        return len(self.file_refs) > 0

    def get_file_refs_summary(self) -> str:
        """获取文件引用摘要"""
        if not self.file_refs:
            return ""

        summary_parts = []
        for ref in self.file_refs:
            summary_parts.append(f"`{ref.category.value}:{ref.file_id}`")

        return "关联文件: " + ", ".join(summary_parts)


def enhance_search_results_with_file_refs(
    results: List[Dict[str, Any]],
    db_path: Optional[Path] = None
) -> List[FileRefSearchResult]:
    """
    为搜索结果添加文件引用信息

    Args:
        results: 搜索结果列表
        db_path: 数据库路径

    Returns:
        增强的搜索结果列表
    """
    if not results:
        return []

    # 获取所有 chunk_id
    chunk_ids = [r.get("id") for r in results if r.get("id")]

    if not chunk_ids:
        # 没有有效的 chunk_id，返回普通结果
        return [
            FileRefSearchResult(
                id=r.get("id", ""),
                path=r.get("path", ""),
                source=r.get("source", ""),
                start_line=r.get("start_line", 0),
                end_line=r.get("end_line", 0),
                text=r.get("text", ""),
                score=r.get("score", 0.0),
                context=r.get("context", r.get("text", "")),
                **{k: v for k, v in r.items() if k not in ["id", "path", "source", "start_line", "end_line", "text", "score", "context"]}
            )
            for r in results
        ]

    # 批量获取文件引用
    index = FileRefIndex(db_path)
    file_refs_map = index.get_file_refs_for_chunks(chunk_ids)

    # 构建增强结果
    enhanced_results = []
    for result in results:
        chunk_id = result.get("id", "")
        file_refs = file_refs_map.get(chunk_id, [])

        enhanced_result = FileRefSearchResult(
            id=chunk_id,
            path=result.get("path", ""),
            source=result.get("source", ""),
            start_line=result.get("start_line", 0),
            end_line=result.get("end_line", 0),
            text=result.get("text", ""),
            score=result.get("score", 0.0),
            file_refs=file_refs,
            context=result.get("context", result.get("text", "")),
            **{k: v for k, v in result.items() if k not in ["id", "path", "source", "start_line", "end_line", "text", "score", "context"]}
        )
        enhanced_results.append(enhanced_result)

    return enhanced_results


def format_search_results_with_file_refs(
    results: List[FileRefSearchResult],
    query: str,
    min_score: float = 0.0,
    source: str = "all",
    use_hybrid: bool = True
) -> str:
    """
    格式化带文件引用的搜索结果

    Args:
        results: 增强的搜索结果列表
        query: 查询文本
        min_score: 最小分数
        source: 来源过滤
        use_hybrid: 是否使用混合搜索

    Returns:
        格式化的 Markdown 输出
    """
    if not results:
        filters = []
        if source != "all":
            filters.append(f"来源={source}")
        if min_score > 0:
            filters.append(f"最小分数={min_score}")
        filter_str = f" (过滤: {', '.join(filters)})" if filters else ""
        return f"❌ 未找到匹配 \"{query}\" 的结果{filter_str}"

    # 构建输出
    output = [f"## 搜索结果: \"{query}\"\n"]
    output.append(f"**搜索模式**: {'混合搜索 (FTS + 向量)' if use_hybrid else 'FTS 关键词搜索'}")
    output.append(f"**找到 {len(results)} 个匹配** (最低分数: {min_score:.2f})\n")

    # 统计文件引用
    total_refs = sum(len(r.file_refs) for r in results)
    if total_refs > 0:
        output.append(f"**关联文件**: {total_refs} 个文件引用\n")

    for i, result in enumerate(results, 1):
        score = result.score
        path = result.path
        line = result.start_line

        output.append(f"### {i}. {path}:{line}")
        output.append(f"**相关性**: {score:.2f}")

        # 添加文件引用信息
        if result.has_file_refs():
            output.append(f"**{result.get_file_refs_summary()}**")

        output.append("```")
        context = result.context[:500]
        output.append(context)
        if len(result.context) > 500:
            output.append("...")
        output.append("```\n")

    return '\n'.join(output)


class FileRefMemorySearcher:
    """
    带文件引用的记忆搜索器

    整合文件引用索引和搜索功能
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        index: Optional[FileRefIndex] = None
    ):
        """
        初始化搜索器

        Args:
            db_path: 数据库路径
            index: 文件引用索引实例
        """
        self.db_path = db_path or get_index_db_path()
        self.file_ref_index = index or FileRefIndex(self.db_path)

    def search_with_file_refs(
        self,
        query: str,
        max_results: int = 6,
        min_score: float = 0.35,
        source: str = "memory",
        **kwargs
    ) -> List[FileRefSearchResult]:
        """
        搜索并返回带文件引用的结果

        Args:
            query: 查询文本
            max_results: 最大结果数
            min_score: 最小分数
            source: 来源过滤
            **kwargs: 其他搜索参数

        Returns:
            带文件引用的搜索结果列表
        """
        # 导入搜索函数（避免循环导入）
        from backend.memory.tools.memory_search_v2 import (
            _search_hybrid, _search_fts
        )
        from backend.memory import create_embedding_provider

        # 打开数据库
        db = open_index_db(self.db_path)

        try:
            # 尝试使用混合搜索
            try:
                provider = create_embedding_provider(provider="auto")
                embedding = provider.encode_batch([query])[0]
                embedding_dims = len(embedding)

                results = _search_hybrid(
                    db,
                    query,
                    embedding,
                    embedding_dims,
                    max_results,
                    min_score,
                    source,
                    kwargs.get("vector_weight", 0.7),
                    kwargs.get("text_weight", 0.3)
                )
                use_hybrid = True
            except Exception:
                # 回退到 FTS 搜索
                results = _search_fts(
                    db,
                    query,
                    max_results,
                    min_score,
                    source
                )
                use_hybrid = False

            # 增强结果，添加文件引用
            enhanced_results = enhance_search_results_with_file_refs(
                results,
                self.db_path
            )

            return enhanced_results

        finally:
            db.close()

    def format_results(
        self,
        results: List[FileRefSearchResult],
        query: str,
        min_score: float = 0.0,
        source: str = "all",
        use_hybrid: bool = True
    ) -> str:
        """
        格式化搜索结果

        Args:
            results: 搜索结果列表
            query: 查询文本
            min_score: 最小分数
            source: 来源过滤
            use_hybrid: 是否使用混合搜索

        Returns:
            格式化的输出
        """
        return format_search_results_with_file_refs(
            results,
            query,
            min_score,
            source,
            use_hybrid
        )


# 便捷函数
def get_file_ref_index(db_path: Optional[Path] = None) -> FileRefIndex:
    """获取文件引用索引实例"""
    return FileRefIndex(db_path)


def create_file_ref_searcher(db_path: Optional[Path] = None) -> FileRefMemorySearcher:
    """创建带文件引用的记忆搜索器"""
    return FileRefMemorySearcher(db_path)


__all__ = [
    "FileRefIndex",
    "FileRefSearchResult",
    "FileRefMemorySearcher",
    "enhance_search_results_with_file_refs",
    "format_search_results_with_file_refs",
    "get_file_ref_index",
    "create_file_ref_searcher",
]
