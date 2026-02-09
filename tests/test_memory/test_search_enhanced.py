"""
Enhanced Memory Search 测试

测试文件引用索引和增强的搜索功能
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from backend.memory.search_enhanced import (
    FileRefIndex,
    FileRefSearchResult,
    FileRefMemorySearcher,
    enhance_search_results_with_file_refs,
    format_search_results_with_file_refs,
    get_file_ref_index,
    create_file_ref_searcher
)
from backend.models.filestore import FileRef, FileCategory


@pytest.fixture
def temp_db_path(tmp_path):
    """临时数据库路径"""
    return tmp_path / "test_memory.db"


@pytest.fixture
def file_ref_index(temp_db_path):
    """文件引用索引夹具"""
    return FileRefIndex(temp_db_path)


@pytest.fixture
def sample_file_refs():
    """示例文件引用"""
    return [
        FileRef(
            file_id="artifact_123",
            category=FileCategory.ARTIFACT,
            size_bytes=1024,
            metadata={"summary": "查询结果"}
        ),
        FileRef(
            file_id="chart_456",
            category=FileCategory.CHART,
            metadata={"title": "可视化图表"}
        )
    ]


class TestFileRefIndex:
    """测试文件引用索引"""

    def test_init_creates_schema(self, temp_db_path):
        """测试初始化创建 schema"""
        index = FileRefIndex(temp_db_path)

        # 验证表已创建
        import sqlite3
        db = sqlite3.connect(temp_db_path)
        cursor = db.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='chunk_file_refs'
        """)
        result = cursor.fetchone()
        db.close()

        assert result is not None

    def test_add_file_refs_to_chunk(self, file_ref_index, sample_file_refs):
        """测试为记忆块添加文件引用"""
        chunk_id = "chunk_123"
        count = file_ref_index.add_file_refs_to_chunk(chunk_id, sample_file_refs)

        assert count == 2

    def test_add_empty_file_refs(self, file_ref_index):
        """测试添加空文件引用列表"""
        count = file_ref_index.add_file_refs_to_chunk("chunk_123", [])
        assert count == 0

    def test_get_file_refs_for_chunk(self, file_ref_index, sample_file_refs):
        """测试获取记忆块的文件引用"""
        chunk_id = "chunk_123"
        file_ref_index.add_file_refs_to_chunk(chunk_id, sample_file_refs)

        refs = file_ref_index.get_file_refs_for_chunk(chunk_id)

        assert len(refs) == 2
        assert refs[0].file_id == "artifact_123"
        assert refs[1].file_id == "chart_456"

    def test_get_file_refs_for_empty_chunk(self, file_ref_index):
        """测试获取不存在记忆块的文件引用"""
        refs = file_ref_index.get_file_refs_for_chunk("nonexistent")
        assert refs == []

    def test_get_file_refs_for_chunks(self, file_ref_index):
        """测试批量获取文件引用"""
        refs1 = [FileRef(file_id="artifact_1", category=FileCategory.ARTIFACT)]
        refs2 = [FileRef(file_id="chart_2", category=FileCategory.CHART)]

        file_ref_index.add_file_refs_to_chunk("chunk_1", refs1)
        file_ref_index.add_file_refs_to_chunk("chunk_2", refs2)

        result = file_ref_index.get_file_refs_for_chunks(["chunk_1", "chunk_2", "chunk_3"])

        assert len(result["chunk_1"]) == 1
        assert len(result["chunk_2"]) == 1
        assert len(result["chunk_3"]) == 0

    def test_search_chunks_by_file_ref(self, file_ref_index):
        """测试通过文件引用搜索记忆块"""
        refs = [FileRef(file_id="artifact_123", category=FileCategory.ARTIFACT)]

        file_ref_index.add_file_refs_to_chunk("chunk_1", refs)
        file_ref_index.add_file_refs_to_chunk("chunk_2", refs)

        chunk_ids = file_ref_index.search_chunks_by_file_ref("artifact_123")

        assert len(chunk_ids) == 2
        assert "chunk_1" in chunk_ids
        assert "chunk_2" in chunk_ids

    def test_search_chunks_by_file_ref_with_category(self, file_ref_index):
        """测试通过文件引用和类别搜索记忆块"""
        refs = [FileRef(file_id="artifact_123", category=FileCategory.ARTIFACT)]

        file_ref_index.add_file_refs_to_chunk("chunk_1", refs)

        chunk_ids = file_ref_index.search_chunks_by_file_ref(
            "artifact_123",
            FileCategory.ARTIFACT
        )

        assert len(chunk_ids) == 1

    def test_remove_file_refs_for_chunk(self, file_ref_index, sample_file_refs):
        """测试删除记忆块的文件引用"""
        chunk_id = "chunk_123"
        file_ref_index.add_file_refs_to_chunk(chunk_id, sample_file_refs)

        count = file_ref_index.remove_file_refs_for_chunk(chunk_id)

        assert count == 2

        refs = file_ref_index.get_file_refs_for_chunk(chunk_id)
        assert len(refs) == 0

    def test_duplicate_file_refs_handled(self, file_ref_index):
        """测试重复文件引用的处理"""
        chunk_id = "chunk_123"
        refs = [FileRef(file_id="artifact_123", category=FileCategory.ARTIFACT)]

        # 添加两次相同的引用
        file_ref_index.add_file_refs_to_chunk(chunk_id, refs)
        file_ref_index.add_file_refs_to_chunk(chunk_id, refs)

        # 应该只有一个引用（由于 UNIQUE 约束）
        result_refs = file_ref_index.get_file_refs_for_chunk(chunk_id)
        assert len(result_refs) == 1


class TestFileRefSearchResult:
    """测试文件引用搜索结果"""

    def test_init_minimal(self):
        """测试最小初始化"""
        result = FileRefSearchResult(
            id="chunk_1",
            path="/test/path",
            source="memory",
            start_line=1,
            end_line=5,
            text="测试内容"
        )

        assert result.id == "chunk_1"
        assert result.score == 0.0
        assert len(result.file_refs) == 0

    def test_init_with_file_refs(self, sample_file_refs):
        """测试带文件引用的初始化"""
        result = FileRefSearchResult(
            id="chunk_1",
            path="/test/path",
            source="memory",
            start_line=1,
            end_line=5,
            text="测试内容",
            file_refs=sample_file_refs
        )

        assert len(result.file_refs) == 2

    def test_to_dict(self, sample_file_refs):
        """测试转换为字典"""
        result = FileRefSearchResult(
            id="chunk_1",
            path="/test/path",
            source="memory",
            start_line=1,
            end_line=5,
            text="测试内容",
            score=0.85,
            file_refs=sample_file_refs
        )

        d = result.to_dict()

        assert d["id"] == "chunk_1"
        assert d["score"] == 0.85
        assert len(d["file_refs"]) == 2

    def test_has_file_refs(self):
        """测试是否有文件引用"""
        result_without = FileRefSearchResult(
            id="chunk_1",
            path="/test",
            source="memory",
            start_line=1,
            end_line=5,
            text="测试"
        )

        result_with = FileRefSearchResult(
            id="chunk_1",
            path="/test",
            source="memory",
            start_line=1,
            end_line=5,
            text="测试",
            file_refs=[FileRef(file_id="test", category=FileCategory.ARTIFACT)]
        )

        assert result_without.has_file_refs() is False
        assert result_with.has_file_refs() is True

    def test_get_file_refs_summary(self, sample_file_refs):
        """测试获取文件引用摘要"""
        result = FileRefSearchResult(
            id="chunk_1",
            path="/test",
            source="memory",
            start_line=1,
            end_line=5,
            text="测试",
            file_refs=sample_file_refs
        )

        summary = result.get_file_refs_summary()

        assert "关联文件" in summary
        assert "artifact:artifact_123" in summary
        assert "chart:chart_456" in summary


class TestEnhanceSearchResults:
    """测试增强搜索结果"""

    def test_enhance_empty_results(self, temp_db_path):
        """测试增强空结果列表"""
        enhanced = enhance_search_results_with_file_refs([], temp_db_path)
        assert enhanced == []

    def test_enhance_results_without_file_refs(self, temp_db_path):
        """测试增强没有文件引用的结果"""
        results = [
            {
                "id": "chunk_1",
                "path": "/test/path",
                "source": "memory",
                "start_line": 1,
                "end_line": 5,
                "text": "测试内容",
                "score": 0.8
            }
        ]

        enhanced = enhance_search_results_with_file_refs(results, temp_db_path)

        assert len(enhanced) == 1
        assert isinstance(enhanced[0], FileRefSearchResult)
        assert enhanced[0].id == "chunk_1"
        assert len(enhanced[0].file_refs) == 0

    def test_enhance_results_with_file_refs(self, temp_db_path):
        """测试增强有文件引用的结果"""
        # 先添加文件引用
        index = FileRefIndex(temp_db_path)
        refs = [FileRef(file_id="artifact_123", category=FileCategory.ARTIFACT)]
        index.add_file_refs_to_chunk("chunk_1", refs)

        results = [
            {
                "id": "chunk_1",
                "path": "/test/path",
                "source": "memory",
                "start_line": 1,
                "end_line": 5,
                "text": "测试内容",
                "score": 0.8
            }
        ]

        enhanced = enhance_search_results_with_file_refs(results, temp_db_path)

        assert len(enhanced) == 1
        assert len(enhanced[0].file_refs) == 1
        assert enhanced[0].file_refs[0].file_id == "artifact_123"

    def test_enhance_results_preserves_extra_fields(self, temp_db_path):
        """测试增强结果保留额外字段"""
        results = [
            {
                "id": "chunk_1",
                "path": "/test",
                "source": "memory",
                "start_line": 1,
                "end_line": 5,
                "text": "测试",
                "score": 0.8,
                "fts_score": 0.5,
                "vec_score": 0.9
            }
        ]

        enhanced = enhance_search_results_with_file_refs(results, temp_db_path)

        assert enhanced[0].extra.get("fts_score") == 0.5
        assert enhanced[0].extra.get("vec_score") == 0.9


class TestFormatSearchResults:
    """测试格式化搜索结果"""

    def test_format_empty_results(self):
        """测试格式化空结果"""
        formatted = format_search_results_with_file_refs(
            [],
            query="测试查询",
            min_score=0.5,
            source="memory"
        )

        assert "未找到匹配" in formatted
        assert "测试查询" in formatted

    def test_format_results_without_file_refs(self):
        """测试格式化没有文件引用的结果"""
        results = [
            FileRefSearchResult(
                id="chunk_1",
                path="/test/path",
                source="memory",
                start_line=1,
                end_line=5,
                text="测试内容",
                score=0.8
            )
        ]

        formatted = format_search_results_with_file_refs(
            results,
            query="测试查询",
            min_score=0.5,
            source="memory"
        )

        assert "测试查询" in formatted
        assert "1 个匹配" in formatted
        assert "0.80" in formatted

    def test_format_results_with_file_refs(self, sample_file_refs):
        """测试格式化有文件引用的结果"""
        results = [
            FileRefSearchResult(
                id="chunk_1",
                path="/test/path",
                source="memory",
                start_line=1,
                end_line=5,
                text="测试内容",
                score=0.8,
                file_refs=sample_file_refs
            )
        ]

        formatted = format_search_results_with_file_refs(
            results,
            query="测试查询",
            min_score=0.5,
            source="memory"
        )

        assert "2 个文件引用" in formatted
        assert "artifact:artifact_123" in formatted

    def test_format_limits_context_length(self):
        """测试格式化限制上下文长度"""
        long_text = "word " * 1000  # 超过 500 字符
        results = [
            FileRefSearchResult(
                id="chunk_1",
                path="/test/path",
                source="memory",
                start_line=1,
                end_line=5,
                text=long_text,
                score=0.8,
                context=long_text
            )
        ]

        formatted = format_search_results_with_file_refs(
            results,
            query="测试",
            min_score=0.0,
            source="all"
        )

        # 应该有省略号
        assert "..." in formatted


class TestFileRefMemorySearcher:
    """测试文件引用记忆搜索器"""

    def test_init(self, temp_db_path):
        """测试初始化"""
        searcher = FileRefMemorySearcher(db_path=temp_db_path)

        assert searcher.db_path == temp_db_path
        assert searcher.file_ref_index is not None

    def test_init_with_custom_index(self, temp_db_path):
        """测试使用自定义索引初始化"""
        custom_index = FileRefIndex(temp_db_path)
        searcher = FileRefMemorySearcher(index=custom_index)

        assert searcher.file_ref_index == custom_index

    def test_format_results(self, temp_db_path):
        """测试格式化结果"""
        searcher = FileRefMemorySearcher(db_path=temp_db_path)

        results = [
            FileRefSearchResult(
                id="chunk_1",
                path="/test",
                source="memory",
                start_line=1,
                end_line=5,
                text="测试",
                score=0.8
            )
        ]

        formatted = searcher.format_results(
            results,
            query="测试查询",
            min_score=0.5,
            source="memory"
        )

        assert "测试查询" in formatted


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_get_file_ref_index(self, temp_db_path):
        """测试获取文件引用索引"""
        index = get_file_ref_index(temp_db_path)

        assert isinstance(index, FileRefIndex)
        assert index.db_path == temp_db_path

    def test_create_file_ref_searcher(self, temp_db_path):
        """测试创建文件引用搜索器"""
        searcher = create_file_ref_searcher(temp_db_path)

        assert isinstance(searcher, FileRefMemorySearcher)
        assert searcher.db_path == temp_db_path
