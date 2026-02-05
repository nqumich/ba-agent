"""
向量搜索模块

提供向量相似度计算和混合搜索功能
"""

import math
import sqlite3
import time
from typing import List, Dict, Any, Optional, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import sqlite_vec
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    计算余弦相似度

    Args:
        a: 向量 A
        b: 向量 B

    Returns:
        余弦相似度 (-1 到 1，通常 0 到 1)
    """
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} != {len(b)}")

    if not a or not b:
        return 0.0

    # 点积
    dot_product = sum(x * y for x, y in zip(a, b))

    # 模的乘积
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def normalize_scores(scores: List[float], method: str = "minmax") -> List[float]:
    """
    归一化分数到 [0, 1] 区间

    Args:
        scores: 分数列表
        method: 归一化方法 (minmax, sigmoid, softmax)

    Returns:
        归一化后的分数列表
    """
    if not scores:
        return []

    if method == "minmax":
        # Min-max 归一化
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [1.0] * len(scores)

        return [(s - min_score) / (max_score - min_score) for s in scores]

    elif method == "sigmoid":
        # Sigmoid 归一化 (适合 BM25 分数)
        return [1 / (1 + math.exp(-s)) for s in scores]

    elif method == "softmax":
        # Softmax 归一化
        exp_scores = [math.exp(s) for s in scores]
        sum_exp = sum(exp_scores)
        return [e / sum_exp for e in exp_scores]

    else:
        raise ValueError(f"Unknown normalization method: {method}")


def combine_scores(
    fts_scores: List[float],
    vec_scores: List[float],
    fts_weight: float = 0.5,
    vec_weight: float = 0.5
) -> List[float]:
    """
    融合 FTS 和向量分数

    Args:
        fts_scores: FTS 分数列表 (BM25)
        vec_scores: 向量分数列表 (余弦相似度)
        fts_weight: FTS 权重
        vec_weight: 向量权重

    Returns:
        融合后的分数列表
    """
    if len(fts_scores) != len(vec_scores):
        raise ValueError(f"Score count mismatch: {len(fts_scores)} != {len(vec_scores)}")

    if fts_weight + vec_weight != 1.0:
        # 归一化权重
        total = fts_weight + vec_weight
        fts_weight /= total
        vec_weight /= total

    return [
        fts * fts_weight + vec * vec_weight
        for fts, vec in zip(fts_scores, vec_scores)
    ]


class VectorSearchEngine:
    """
    向量搜索引擎

    支持纯 Python 实现和 sqlite-vec 加速
    """

    def __init__(
        self,
        db: sqlite3.Connection,
        dims: int,
        use_sqlite_vec: bool = True
    ):
        """
        初始化向量搜索引擎

        Args:
            db: SQLite 数据库连接
            dims: 向量维度
            use_sqlite_vec: 是否尝试使用 sqlite-vec
        """
        self.db = db
        self.dims = dims
        self.use_sqlite_vec = use_sqlite_vec and HAS_SQLITE_VEC

        # 尝试加载 sqlite-vec
        self._vec_loaded = False
        if self.use_sqlite_vec:
            try:
                # 加载 sqlite-vec 扩展
                db.enable_load_extension(True)
                sqlite_vec.load(db)
                self._vec_loaded = True
            except Exception as e:
                # 加载失败，回退到纯 Python
                self._vec_loaded = False

    def ensure_vector_tables(self) -> None:
        """确保向量表已创建"""
        if self._vec_loaded:
            self._ensure_vec_table()
        else:
            self._ensure_json_table()

    def _ensure_vec_table(self) -> None:
        """创建 sqlite-vec 表"""
        # 使用 sqlite-vec 虚拟表
        self.db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vectors USING vec0(
                chunk_id TEXT PRIMARY KEY,
                embedding FLOAT[{dims}]
            );
        """.format(dims=self.dims))

    def _ensure_json_table(self) -> None:
        """创建 JSON 存储表（回退方案）"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS chunk_vectors (
                chunk_id TEXT PRIMARY KEY,
                embedding TEXT NOT NULL,
                dims INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
            );
        """)

        # 创建索引
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_chunk_vectors_updated ON chunk_vectors(updated_at);")

    def insert_vector(self, chunk_id: str, embedding: List[float]) -> None:
        """
        插入向量

        Args:
            chunk_id: 块 ID
            embedding: 嵌入向量
        """
        if len(embedding) != self.dims:
            raise ValueError(f"Embedding dimension mismatch: {len(embedding)} != {self.dims}")

        if self._vec_loaded:
            self._insert_vec(chunk_id, embedding)
        else:
            self._insert_json(chunk_id, embedding)

    def _insert_vec(self, chunk_id: str, embedding: List[float]) -> None:
        """使用 sqlite-vec 插入"""
        # sqlite-vec 使用特殊的插入语法
        self.db.execute(
            "INSERT OR REPLACE INTO chunk_vectors(chunk_id, embedding) VALUES (?, vec(?))",
            (chunk_id, embedding)
        )

    def _insert_json(self, chunk_id: str, embedding: List[float]) -> None:
        """使用 JSON 插入"""
        embedding_str = ",".join(str(x) for x in embedding)
        now = int(time.time())

        self.db.execute("""
            INSERT OR REPLACE INTO chunk_vectors (chunk_id, embedding, dims, updated_at)
            VALUES (?, ?, ?, ?)
        """, (chunk_id, embedding_str, self.dims, now))

    def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        source_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量搜索

        Args:
            query_embedding: 查询向量
            limit: 返回结果数量
            source_filter: 来源过滤

        Returns:
            搜索结果列表
        """
        if len(query_embedding) != self.dims:
            raise ValueError(f"Query dimension mismatch: {len(query_embedding)} != {self.dims}")

        if self._vec_loaded:
            return self._search_vec(query_embedding, limit, source_filter)
        else:
            return self._search_json(query_embedding, limit, source_filter)

    def _search_vec(
        self,
        query_embedding: List[float],
        limit: int,
        source_filter: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """使用 sqlite-vec 搜索"""
        # 构建查询
        sql = """
            SELECT
                cv.chunk_id,
                c.path,
                c.source,
                c.start_line,
                c.end_line,
                c.text,
                distance
            FROM chunk_vectors cv
            JOIN chunks c ON c.id = cv.chunk_id
            WHERE chunk_vectors MATCH ? AND k = ?
        """
        params = [f"vec_array({query_embedding})", limit]

        if source_filter:
            sql += " AND c.source IN ({})".format(
                ', '.join(['?'] * len(source_filter))
            )
            params.extend(source_filter)

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
                "distance": row[6],
                "score": 1.0 - row[6]  # 转换距离为相似度
            })

        return results

    def _search_json(
        self,
        query_embedding: List[float],
        limit: int,
        source_filter: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """使用纯 Python 搜索"""
        # 获取所有向量
        sql = """
            SELECT
                cv.chunk_id,
                c.path,
                c.source,
                c.start_line,
                c.end_line,
                c.text,
                cv.embedding
            FROM chunk_vectors cv
            JOIN chunks c ON c.id = cv.chunk_id
        """
        params = []

        if source_filter:
            sql += " WHERE c.source IN ({})".format(
                ', '.join(['?'] * len(source_filter))
            )
            params.extend(source_filter)

        cursor = self.db.execute(sql, params)

        # 计算相似度
        results = []
        for row in cursor.fetchall():
            chunk_id, path, source, start_line, end_line, text, embedding_str = row

            # 解析向量
            embedding = [float(x) for x in embedding_str.split(',')]

            # 计算余弦相似度
            similarity = cosine_similarity(query_embedding, embedding)

            results.append({
                "id": chunk_id,
                "path": path,
                "source": source,
                "start_line": start_line,
                "end_line": end_line,
                "text": text,
                "score": similarity,
                "distance": 1.0 - similarity  # 添加距离字段保持一致性
            })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:limit]

    def delete_by_path(self, path: str) -> None:
        """删除路径的所有向量"""
        if self._vec_loaded:
            self.db.execute("""
                DELETE FROM chunk_vectors
                WHERE chunk_id IN (SELECT id FROM chunks WHERE path = ?)
            """, (path,))
        else:
            self.db.execute("""
                DELETE FROM chunk_vectors
                WHERE chunk_id IN (SELECT id FROM chunks WHERE path = ?)
            """, (path,))


class HybridSearchEngine:
    """
    混合搜索引擎

    结合 FTS (BM25) 和向量搜索 (Cosine)
    """

    def __init__(
        self,
        db: sqlite3.Connection,
        dims: int,
        fts_table: str = "chunks_fts",
        fts_weight: float = 0.3,
        vec_weight: float = 0.7,
        normalize_method: str = "minmax",
        use_sqlite_vec: bool = True
    ):
        """
        初始化混合搜索引擎

        Args:
            db: SQLite 数据库连接
            dims: 向量维度
            fts_table: FTS 表名
            fts_weight: FTS 权重
            vec_weight: 向量权重
            normalize_method: 归一化方法
            use_sqlite_vec: 是否尝试使用 sqlite-vec
        """
        self.db = db
        self.dims = dims
        self.fts_table = fts_table
        self.fts_weight = fts_weight
        self.vec_weight = vec_weight
        self.normalize_method = normalize_method

        # 创建向量搜索引擎
        self.vec_engine = VectorSearchEngine(db, dims=dims, use_sqlite_vec=use_sqlite_vec)

    def search(
        self,
        query: str,
        query_embedding: List[float],
        limit: int = 10,
        source_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        混合搜索

        Args:
            query: 文本查询 (用于 FTS)
            query_embedding: 查询向量 (用于向量搜索)
            limit: 返回结果数量
            source_filter: 来源过滤

        Returns:
            搜索结果列表
        """
        # FTS 搜索
        fts_results = self._search_fts(query, limit * 2, source_filter)

        # 向量搜索
        vec_results = self.vec_engine.search(query_embedding, limit * 2, source_filter)

        # 合并结果
        combined = self._combine_results(fts_results, vec_results, limit)

        return combined

    def _search_fts(
        self,
        query: str,
        limit: int,
        source_filter: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """FTS 搜索"""
        sql = """
            SELECT chunks.id, chunks.path, chunks.source,
                   chunks.start_line, chunks.end_line, chunks.text
            FROM {fts_table}
            JOIN chunks ON chunks.rowid = {fts_table}.rowid
            WHERE {fts_table} MATCH ?
        """.format(fts_table=self.fts_table)
        params = [query]

        if source_filter:
            placeholders = ', '.join(['?'] * len(source_filter))
            sql += " AND chunks.source IN ({})".format(placeholders)
            params.extend(source_filter)

        sql += " LIMIT ?"
        params.append(limit)

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
                "fts_score": 0.0,  # 稍后填充
                "vec_score": 0.0
            })

        return results

    def _combine_results(
        self,
        fts_results: List[Dict[str, Any]],
        vec_results: List[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        合并 FTS 和向量结果

        使用 Reciprocal Rank Fusion (RRF) 算法
        """
        # 创建结果映射
        result_map = {}

        # 处理 FTS 结果
        for rank, result in enumerate(fts_results):
            chunk_id = result["id"]
            if chunk_id not in result_map:
                result_map[chunk_id] = result.copy()
                result_map[chunk_id]["fts_score"] = 0.0
                result_map[chunk_id]["vec_score"] = 0.0

            # RRF 分数: 1 / (k + rank)，k 通常为 60
            k = 60
            result_map[chunk_id]["fts_score"] = 1.0 / (k + rank + 1)

        # 处理向量结果
        for rank, result in enumerate(vec_results):
            chunk_id = result["id"]
            if chunk_id not in result_map:
                result_map[chunk_id] = {
                    "id": result["id"],
                    "path": result["path"],
                    "source": result["source"],
                    "start_line": result["start_line"],
                    "end_line": result["end_line"],
                    "text": result["text"],
                    "fts_score": 0.0,
                    "vec_score": 0.0
                }

            # 向量分数使用余弦相似度 + RRF
            k = 60
            vec_rrf = 1.0 / (k + rank + 1)
            result_map[chunk_id]["vec_score"] = vec_rrf

        # 归一化分数
        fts_scores = [r["fts_score"] for r in result_map.values()]
        vec_scores = [r["vec_score"] for r in result_map.values()]

        if fts_scores:
            fts_normalized = normalize_scores(fts_scores, method=self.normalize_method)
        else:
            fts_normalized = []

        if vec_scores:
            vec_normalized = normalize_scores(vec_scores, method=self.normalize_method)
        else:
            vec_normalized = []

        # 组合分数
        results = list(result_map.values())
        for i, result in enumerate(results):
            result["combined_score"] = (
                result["fts_score"] * self.fts_weight +
                result["vec_score"] * self.vec_weight
            )
            result["score"] = result["combined_score"]  # 主要分数

        # 排序并限制结果
        results.sort(key=lambda x: x["combined_score"], reverse=True)
        return results[:limit]

    def ensure_vector_tables(self) -> None:
        """确保向量表已创建"""
        self.vec_engine.ensure_vector_tables()

    def insert_vector(self, chunk_id: str, embedding: List[float]) -> None:
        """插入向量"""
        self.vec_engine.insert_vector(chunk_id, embedding)

    def delete_by_path(self, path: str) -> None:
        """删除路径的所有向量"""
        self.vec_engine.delete_by_path(path)
