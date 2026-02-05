"""
向量搜索测试
"""

import sqlite3
import pytest
import math
from pathlib import Path

from backend.memory.vector_search import (
    cosine_similarity,
    normalize_scores,
    combine_scores,
    VectorSearchEngine,
    HybridSearchEngine,
    HAS_NUMPY,
    HAS_SQLITE_VEC
)


class TestCosineSimilarity:
    """测试余弦相似度"""

    def test_identical_vectors(self):
        """测试相同向量"""
        a = [1.0, 2.0, 3.0]
        b = [1.0, 2.0, 3.0]
        result = cosine_similarity(a, b)
        assert result == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """测试正交向量"""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        result = cosine_similarity(a, b)
        assert result == pytest.approx(0.0)

    def test_opposite_vectors(self):
        """测试相反向量"""
        a = [1.0, 2.0, 3.0]
        b = [-1.0, -2.0, -3.0]
        result = cosine_similarity(a, b)
        assert result == pytest.approx(-1.0)

    def test_dimension_mismatch(self):
        """测试维度不匹配"""
        a = [1.0, 2.0]
        b = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="dimension mismatch"):
            cosine_similarity(a, b)

    def test_empty_vectors(self):
        """测试空向量"""
        result = cosine_similarity([], [])
        assert result == 0.0


class TestNormalizeScores:
    """测试分数归一化"""

    def test_minmax_normalization(self):
        """测试 Min-max 归一化"""
        scores = [0.5, 1.0, 0.0, 0.75]
        result = normalize_scores(scores, method="minmax")

        assert len(result) == 4
        assert min(result) == 0.0
        assert max(result) == 1.0

    def test_minmax_identical_scores(self):
        """测试相同分数"""
        scores = [0.5, 0.5, 0.5]
        result = normalize_scores(scores, method="minmax")
        assert all(s == 1.0 for s in result)

    def test_sigmoid_normalization(self):
        """测试 Sigmoid 归一化"""
        scores = [-2.0, 0.0, 2.0]
        result = normalize_scores(scores, method="sigmoid")

        assert len(result) == 3
        # sigmoid(0) = 0.5
        assert result[1] == pytest.approx(0.5, abs=0.01)

    def test_softmax_normalization(self):
        """测试 Softmax 归一化"""
        scores = [1.0, 2.0, 3.0]
        result = normalize_scores(scores, method="softmax")

        assert len(result) == 3
        assert abs(sum(result) - 1.0) < 0.001  # 和为 1

    def test_empty_scores(self):
        """测试空分数列表"""
        result = normalize_scores([], method="minmax")
        assert result == []

    def test_unknown_method(self):
        """测试未知归一化方法"""
        with pytest.raises(ValueError, match="Unknown normalization"):
            normalize_scores([1.0, 2.0], method="unknown")


class TestCombineScores:
    """测试分数融合"""

    def test_equal_weights(self):
        """测试等权重融合"""
        fts = [0.8, 0.6, 0.4]
        vec = [0.2, 0.4, 0.6]
        result = combine_scores(fts, vec, fts_weight=0.5, vec_weight=0.5)

        assert result == [0.5, 0.5, 0.5]

    def test_custom_weights(self):
        """测试自定义权重"""
        fts = [1.0, 0.0]
        vec = [0.0, 1.0]
        result = combine_scores(fts, vec, fts_weight=0.7, vec_weight=0.3)

        assert result[0] == pytest.approx(0.7)
        assert result[1] == pytest.approx(0.3)

    def test_weight_normalization(self):
        """测试权重归一化"""
        fts = [1.0, 0.0]
        vec = [0.0, 1.0]
        # 权重和不为 1，应该自动归一化
        result = combine_scores(fts, vec, fts_weight=0.8, vec_weight=0.4)

        # 0.8 / (0.8 + 0.4) = 2/3
        # 0.4 / (0.8 + 0.4) = 1/3
        assert result[0] == pytest.approx(2/3)
        assert result[1] == pytest.approx(1/3)

    def test_length_mismatch(self):
        """测试长度不匹配"""
        fts = [0.5, 0.5]
        vec = [0.5]
        with pytest.raises(ValueError, match="count mismatch"):
            combine_scores(fts, vec)


class TestVectorSearchEngine:
    """测试向量搜索引擎"""

    def test_init(self):
        """测试初始化"""
        db = sqlite3.connect(":memory:")
        engine = VectorSearchEngine(db, dims=3, use_sqlite_vec=False)

        assert engine.dims == 3
        assert engine._vec_loaded is False

    def test_ensure_vector_tables_json(self):
        """测试创建 JSON 表"""
        db = sqlite3.connect(":memory:")
        engine = VectorSearchEngine(db, dims=3, use_sqlite_vec=False)

        engine.ensure_vector_tables()

        # 验证表已创建
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "chunk_vectors" in tables

    def test_insert_vector_json(self):
        """测试插入向量 (JSON)"""
        db = sqlite3.connect(":memory:")
        engine = VectorSearchEngine(db, dims=3, use_sqlite_vec=False)

        engine.ensure_vector_tables()
        engine.insert_vector("chunk1", [0.1, 0.2, 0.3])

        # 验证插入
        cursor = db.execute("SELECT embedding, dims FROM chunk_vectors WHERE chunk_id = ?", ("chunk1",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "0.1,0.2,0.3"
        assert row[1] == 3

    def test_insert_vector_dimension_mismatch(self):
        """测试插入维度不匹配的向量"""
        db = sqlite3.connect(":memory:")
        engine = VectorSearchEngine(db, dims=3, use_sqlite_vec=False)

        engine.ensure_vector_tables()

        with pytest.raises(ValueError, match="dimension mismatch"):
            engine.insert_vector("chunk1", [0.1, 0.2])

    def test_search_json(self, tmp_path):
        """测试向量搜索 (JSON)"""
        db_path = tmp_path / "test.db"
        db = sqlite3.connect(db_path)

        # 创建必要的表
        db.execute("""
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                source TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL
            );
        """)

        engine = VectorSearchEngine(db, dims=3, use_sqlite_vec=False)
        engine.ensure_vector_tables()

        # 插入测试数据
        db.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                   ("chunk1", "/test.md", "memory", 1, 3, "hello world test"))
        db.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                   ("chunk2", "/test2.md", "memory", 4, 6, "different content"))

        engine.insert_vector("chunk1", [1.0, 0.0, 0.0])
        engine.insert_vector("chunk2", [0.0, 1.0, 0.0])

        # 搜索
        results = engine.search([1.0, 0.0, 0.0], limit=10)

        assert len(results) == 2
        # 第一个结果应该是最相似的
        assert results[0]["id"] == "chunk1"
        assert results[0]["score"] == pytest.approx(1.0)

    def test_search_with_source_filter(self, tmp_path):
        """测试来源过滤"""
        db_path = tmp_path / "test.db"
        db = sqlite3.connect(db_path)

        db.execute("""
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                source TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL
            );
        """)

        engine = VectorSearchEngine(db, dims=2, use_sqlite_vec=False)
        engine.ensure_vector_tables()

        # 插入不同来源的数据
        db.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                   ("chunk1", "/test.md", "memory", 1, 2, "test"))
        db.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                   ("chunk2", "/test2.md", "sessions", 1, 2, "test"))

        engine.insert_vector("chunk1", [1.0, 0.0])
        engine.insert_vector("chunk2", [1.0, 0.0])

        # 只搜索 memory 来源
        results = engine.search([1.0, 0.0], limit=10, source_filter=["memory"])

        assert len(results) == 1
        assert results[0]["id"] == "chunk1"

    def test_delete_by_path(self, tmp_path):
        """测试删除路径"""
        db_path = tmp_path / "test.db"
        db = sqlite3.connect(db_path)

        db.execute("""
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                source TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL
            );
        """)

        engine = VectorSearchEngine(db, dims=2, use_sqlite_vec=False)
        engine.ensure_vector_tables()

        db.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                   ("chunk1", "/test.md", "memory", 1, 2, "test"))
        engine.insert_vector("chunk1", [1.0, 0.0])

        # 删除
        engine.delete_by_path("/test.md")

        # 验证删除
        cursor = db.execute("SELECT COUNT(*) FROM chunk_vectors")
        count = cursor.fetchone()[0]
        assert count == 0


class TestHybridSearchEngine:
    """测试混合搜索引擎"""

    def test_init(self):
        """测试初始化"""
        db = sqlite3.connect(":memory:")
        engine = HybridSearchEngine(db, dims=3, use_sqlite_vec=False)

        assert engine.dims == 3
        assert engine.fts_weight == 0.3
        assert engine.vec_weight == 0.7

    def test_custom_weights(self):
        """测试自定义权重"""
        db = sqlite3.connect(":memory:")
        engine = HybridSearchEngine(
            db,
            dims=3,
            fts_weight=0.6,
            vec_weight=0.4,
            use_sqlite_vec=False
        )

        assert engine.fts_weight == 0.6
        assert engine.vec_weight == 0.4

    def test_ensure_vector_tables(self):
        """测试创建向量表"""
        db = sqlite3.connect(":memory:")
        engine = HybridSearchEngine(db, dims=3, use_sqlite_vec=False)

        engine.ensure_vector_tables()

        # 验证表已创建
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "chunk_vectors" in tables

    def test_insert_vector(self):
        """测试插入向量"""
        db = sqlite3.connect(":memory:")
        engine = HybridSearchEngine(db, dims=3, use_sqlite_vec=False)

        engine.ensure_vector_tables()
        engine.insert_vector("chunk1", [0.1, 0.2, 0.3])

        # 验证插入
        cursor = db.execute("SELECT COUNT(*) FROM chunk_vectors WHERE chunk_id = ?", ("chunk1",))
        count = cursor.fetchone()[0]
        assert count == 1

    def test_search_hybrid(self, tmp_path):
        """测试混合搜索"""
        db_path = tmp_path / "test.db"
        db = sqlite3.connect(db_path)

        # 创建必要的表
        db.execute("""
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                source TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL
            );
        """)

        # 创建 FTS 表
        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                text,
                id UNINDEXED,
                path UNINDEXED,
                source UNINDEXED,
                start_line UNINDEXED,
                end_line UNINDEXED
            );
        """)

        engine = HybridSearchEngine(db, dims=2, use_sqlite_vec=False)
        engine.ensure_vector_tables()

        # 插入测试数据
        chunks = [
            ("chunk1", "/test.md", "memory", 1, 2, "python programming"),
            ("chunk2", "/test2.md", "memory", 3, 4, "javascript code"),
            ("chunk3", "/test3.md", "memory", 5, 6, "python tutorial"),
        ]

        for chunk in chunks:
            db.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)", chunk)

        # 插入 FTS 数据
        db.execute("""
            INSERT INTO chunks_fts (rowid, text, id, path, source, start_line, end_line)
            SELECT rowid, text, id, path, source, start_line, end_line FROM chunks
        """)

        # 插入向量
        engine.insert_vector("chunk1", [1.0, 0.0])  # python
        engine.insert_vector("chunk2", [0.0, 1.0])  # javascript
        engine.insert_vector("chunk3", [0.9, 0.1])  # python (相似)

        # 搜索
        results = engine.search(
            query="python",
            query_embedding=[1.0, 0.0],
            limit=10
        )

        assert len(results) > 0
        # python 相关的应该排在前面
        python_chunks = [r for r in results if "python" in r["text"].lower()]
        assert len(python_chunks) >= 1


class TestEdgeCases:
    """边界情况测试"""

    def test_zero_vector(self):
        """测试零向量"""
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        result = cosine_similarity(a, b)
        assert result == 0.0

    def test_negative_scores_normalization(self):
        """测试负分数归一化"""
        scores = [-1.0, 0.0, 1.0]
        result = normalize_scores(scores, method="minmax")

        assert min(result) == 0.0
        assert max(result) == 1.0

    def test_single_result(self):
        """测试单个结果"""
        fts = [0.5]
        vec = [0.7]
        result = combine_scores(fts, vec, fts_weight=0.5, vec_weight=0.5)

        assert len(result) == 1
        assert result[0] == 0.6
