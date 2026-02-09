"""
Memory Search v2 测试
"""

import sqlite3
import pytest
from pathlib import Path
import tempfile

from backend.memory.tools.memory_search_v2 import (
    memory_search_v2,
    MemorySearchV2Input,
    _search_fts,
    _get_context_from_text,
)


class TestMemorySearchV2Input:
    """测试 MemorySearchV2Input 输入验证"""

    def test_valid_input(self):
        """测试有效输入"""
        input_data = MemorySearchV2Input(
            query="Python 装饰器",
            max_results=10,
            min_score=0.5,
            source="memory"
        )
        assert input_data.query == "Python 装饰器"
        assert input_data.max_results == 10
        assert input_data.min_score == 0.5
        assert input_data.source == "memory"

    def test_default_values(self):
        """测试默认值"""
        input_data = MemorySearchV2Input(query="test")
        assert input_data.max_results == 6
        assert input_data.min_score == 0.35
        assert input_data.source == "memory"
        assert input_data.use_hybrid is True
        assert input_data.vector_weight == 0.7
        assert input_data.text_weight == 0.3

    def test_query_validation_empty(self):
        """测试空查询验证"""
        with pytest.raises(ValueError, match="查询不能为空"):
            MemorySearchV2Input(query="   ")

    def test_min_score_validation(self):
        """测试最小分数验证"""
        with pytest.raises(ValueError, match="min_score 必须在 0-1 之间"):
            MemorySearchV2Input(query="test", min_score=1.5)

        with pytest.raises(ValueError, match="min_score 必须在 0-1 之间"):
            MemorySearchV2Input(query="test", min_score=-0.1)

    def test_source_validation(self):
        """测试来源验证"""
        with pytest.raises(ValueError, match="source 必须是"):
            MemorySearchV2Input(query="test", source="invalid")

    def test_weight_validation(self):
        """测试权重验证"""
        with pytest.raises(ValueError, match="vector_weight 必须在 0-1 之间"):
            MemorySearchV2Input(query="test", vector_weight=1.5)

        with pytest.raises(ValueError, match="text_weight 必须在 0-1 之间"):
            MemorySearchV2Input(query="test", text_weight=-0.1)

    def test_max_results_validation(self):
        """测试最大结果数验证"""
        with pytest.raises(ValueError, match="max_results 必须 >= 1"):
            MemorySearchV2Input(query="test", max_results=0)

        with pytest.raises(ValueError, match="max_results 不能超过 100"):
            MemorySearchV2Input(query="test", max_results=101)


class TestGetContextFromText:
    """测试上下文提取"""

    def test_simple_text(self):
        """测试简单文本"""
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        context = _get_context_from_text(text, 2, 1)
        assert context == "Line 2\nLine 3\nLine 4"

    def test_short_text(self):
        """测试短文本"""
        text = "Line 1\nLine 2"
        context = _get_context_from_text(text, 0, 2)
        assert context == text

    def test_single_line(self):
        """测试单行文本"""
        text = "Single line"
        context = _get_context_from_text(text, 0, 2)
        assert context == text


class TestSearchFTS:
    """测试 FTS 搜索"""

    def test_search_fts_basic(self, tmp_path):
        """测试基本 FTS 搜索"""
        # 创建测试数据库
        db_path = tmp_path / "test.db"
        db = sqlite3.connect(db_path)

        # 创建表
        db.execute("""
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'memory',
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL
            );
        """)

        # 插入测试数据
        db.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
            ("chunk1", "memory/test.md", "memory", 1, 3, "hello world test")
        )
        db.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
            ("chunk2", "memory/test2.md", "memory", 4, 6, "python programming")
        )

        db.commit()

        # 执行搜索
        results = _search_fts(db, "python", 10, 0.0, "all")

        assert len(results) == 1
        assert results[0]["id"] == "chunk2"
        assert "python" in results[0]["text"]

    def test_search_fts_min_score_filter(self, tmp_path):
        """测试最小分数过滤"""
        db_path = tmp_path / "test.db"
        db = sqlite3.connect(db_path)

        db.execute("""
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'memory',
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL
            );
        """)

        db.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
            ("chunk1", "test.md", "memory", 1, 1, "python python python")
        )

        db.commit()

        # 设置很高的 min_score，应该能过滤掉
        results = _search_fts(db, "python", 10, 1.0, "all")
        # match_count = 3, score = 3/10 = 0.3 < 1.0
        assert len(results) == 0

    def test_search_fts_source_filter(self, tmp_path):
        """测试来源过滤"""
        db_path = tmp_path / "test.db"
        db = sqlite3.connect(db_path)

        db.execute("""
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'memory',
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL
            );
        """)

        db.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
            ("chunk1", "test.md", "memory", 1, 1, "test content")
        )
        db.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
            ("chunk2", "test2.md", "sessions", 1, 1, "test content")
        )

        db.commit()

        # 只搜索 memory
        results = _search_fts(db, "test", 10, 0.0, "memory")
        assert len(results) == 1
        assert results[0]["id"] == "chunk1"


class TestMemorySearchV2:
    """测试 memory_search_v2 函数"""

    def test_no_index_directory(self, monkeypatch):
        """测试索引目录不存在"""
        # Mock get_index_db_path 返回不存在的路径
        # 需要patch原始位置，因为memory_search_v2导入了这个函数
        def mock_get_index_db_path():
            return Path("/nonexistent/path/memory.db")

        monkeypatch.setattr("backend.memory.index.get_index_db_path", mock_get_index_db_path)

        result = memory_search_v2("test query")
        # 当索引不存在时，搜索会返回空结果
        assert "未找到" in result or "no results" in result.lower()

    def test_empty_query(self):
        """测试空查询"""
        # 测试模型验证
        with pytest.raises(ValueError):
            MemorySearchV2Input(query="")

    def test_format_results_with_no_results(self):
        """测试格式化空结果"""
        from backend.memory.tools.memory_search_v2 import _format_results_v2

        result = _format_results_v2([], "test query", 0.5, "memory", True)
        assert "未找到" in result
        assert "test query" in result

    def test_format_results_with_results(self):
        """测试格式化有结果"""
        from backend.memory.tools.memory_search_v2 import _format_results_v2

        results = [
            {
                "id": "chunk1",
                "path": "memory/test.md",
                "start_line": 10,
                "score": 0.85,
                "context": "Test content here"
            }
        ]

        result = _format_results_v2(results, "test", 0.5, "memory", True)
        assert "混合搜索" in result
        assert "test.md" in result
        assert "0.85" in result
        assert "Test content" in result


class TestEdgeCases:
    """边界情况测试"""

    def test_unicode_query(self):
        """测试 Unicode 查询"""
        input_data = MemorySearchV2Input(query="中文测试 🎉")
        assert input_data.query == "中文测试 🎉"

    def test_very_long_query(self):
        """测试非常长的查询"""
        long_query = "test " * 1001  # 超过 5000 字符限制
        with pytest.raises(ValueError):
            MemorySearchV2Input(query=long_query)

    def test_min_score_zero(self):
        """测试 min_score = 0"""
        input_data = MemorySearchV2Input(query="test", min_score=0.0)
        assert input_data.min_score == 0.0

    def test_min_score_one(self):
        """测试 min_score = 1"""
        input_data = MemorySearchV2Input(query="test", min_score=1.0)
        assert input_data.min_score == 1.0

    def test_weight_sum_exceeds_one(self):
        """测试权重和超过 1（应该被归一化）"""
        input_data = MemorySearchV2Input(
            query="test",
            vector_weight=0.8,
            text_weight=0.5  # 和为 1.3
        )
        # 输入验证允许，但在使用时会被归一化
        assert input_data.vector_weight == 0.8
        assert input_data.text_weight == 0.5


class TestMemorySearchV2EnhancedFeatures:
    """测试 memory_search_v2 增强功能（从旧版迁移）"""

    def test_entities_filter_validation_valid(self):
        """测试实体过滤验证（有效输入）"""
        input_data = MemorySearchV2Input(
            query="test",
            entities=["@Python", "@架构"]
        )
        assert input_data.entities == ["@Python", "@架构"]

    def test_entities_filter_validation_invalid(self):
        """测试实体过滤验证（无效格式）"""
        with pytest.raises(ValueError, match="实体必须以 @ 开头"):
            MemorySearchV2Input(
                query="test",
                entities=["Python"]  # 缺少 @
            )

    def test_since_days_validation_valid(self):
        """测试时间范围验证（有效输入）"""
        input_data = MemorySearchV2Input(
            query="test",
            since_days=7
        )
        assert input_data.since_days == 7

    def test_since_days_validation_invalid(self):
        """测试时间范围验证（无效值）"""
        with pytest.raises(ValueError, match="since_days 必须 >= 1"):
            MemorySearchV2Input(
                query="test",
                since_days=0
            )

    def test_entities_filter_default(self):
        """测试实体过滤默认为 None"""
        input_data = MemorySearchV2Input(query="test")
        assert input_data.entities is None

    def test_since_days_default(self):
        """测试时间范围默认为 None"""
        input_data = MemorySearchV2Input(query="test")
        assert input_data.since_days is None

    def test_apply_filters_with_entities(self):
        """测试应用实体过滤器"""
        from backend.memory.tools.memory_search_v2 import _apply_filters

        results = [
            {
                "id": "1",
                "text": "This is about @Python and @Architecture",
                "context": "Content with @Python decorator"
            },
            {
                "id": "2",
                "text": "This is about @Java only",
                "context": "Content with @Java"
            },
            {
                "id": "3",
                "text": "No entities here",
                "context": "Plain text"
            }
        ]

        # 过滤包含 @Python 的结果
        filtered = _apply_filters(results, entities=["@Python"])
        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

    def test_apply_filters_with_multiple_entities(self):
        """测试应用多个实体过滤器（AND 逻辑）"""
        from backend.memory.tools.memory_search_v2 import _apply_filters

        results = [
            {
                "id": "1",
                "text": "Has @Python and @Architecture",
                "context": "Content @Python @Architecture"
            },
            {
                "id": "2",
                "text": "Has @Python only",
                "context": "Content @Python"
            },
            {
                "id": "3",
                "text": "Has @Architecture only",
                "context": "Content @Architecture"
            }
        ]

        # 必须同时包含两个实体
        filtered = _apply_filters(results, entities=["@Python", "@Architecture"])
        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

    def test_apply_filters_with_since_days(self):
        """测试应用时间范围过滤器"""
        from backend.memory.tools.memory_search_v2 import _apply_filters, _is_result_recent

        results = [
            {
                "id": "1",
                "path": "memory/2026-02-01.md",
                "text": "Recent content"
            },
            {
                "id": "2",
                "path": "memory/2026-01-01.md",
                "text": "Old content"
            },
            {
                "id": "3",
                "path": "memory/unknown.md",
                "text": "Unknown date"
            }
        ]

        # 过滤最近 7 天 (假设今天是 2026-02-07，截止日期 2026-01-31)
        filtered = _apply_filters(results, since_days=7)
        # 应该只包含 2026-02-01 和 unknown.md 的结果
        assert len(filtered) >= 1
        # 确保旧日期被过滤
        assert not any(r["id"] == "2" for r in filtered)

    def test_is_result_recent_valid_format(self):
        """测试日期检查 - 有效格式"""
        from backend.memory.tools.memory_search_v2 import _is_result_recent

        result = {"path": "memory/2026-02-05.md"}
        assert _is_result_recent(result, "2026-02-01") is True  # 2/5 > 2/1
        assert _is_result_recent(result, "2026-02-10") is False  # 2/5 < 2/10

    def test_is_result_recent_invalid_format(self):
        """测试日期检查 - 无效格式"""
        from backend.memory.tools.memory_search_v2 import _is_result_recent

        result = {"path": "memory/unknown.md"}
        # 无法解析日期时默认返回 True（保留结果）
        assert _is_result_recent(result, "2026-02-01") is True

    def test_apply_filters_with_max_results(self):
        """测试限制结果数量"""
        from backend.memory.tools.memory_search_v2 import _apply_filters

        results = [{"id": str(i), "text": f"Content {i}"} for i in range(20)]

        # 限制为 5 个结果
        filtered = _apply_filters(results, max_results=5)
        assert len(filtered) == 5

    def test_apply_filters_combined(self):
        """测试组合过滤器"""
        from backend.memory.tools.memory_search_v2 import _apply_filters

        results = [
            {
                "id": "1",
                "text": "Recent @Python content",
                "path": "memory/2026-02-05.md",
                "context": "Has @Python"
            },
            {
                "id": "2",
                "text": "Recent @Java content",
                "path": "memory/2026-02-05.md",
                "context": "Has @Java"
            },
            {
                "id": "3",
                "text": "Old @Python content",
                "path": "memory/2026-01-01.md",
                "context": "Has @Python"
            }
        ]

        # 组合：@Python + 最近7天 + 最多1个结果
        filtered = _apply_filters(
            results,
            entities=["@Python"],
            since_days=30,
            max_results=1
        )
        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

