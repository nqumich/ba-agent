"""
记忆索引系统测试
"""

import os
import sqlite3
import pytest
from pathlib import Path
from datetime import datetime

from backend.memory import (
    MemoryIndexer,
    MemoryWatcher,
    get_index_db_path,
    ensure_memory_index_schema,
    DEFAULT_INDEX_PATH
)


class TestSchema:
    """测试数据库 Schema"""

    def test_ensure_schema_creates_tables(self, tmp_path):
        """测试确保 schema 创建所有表"""
        db_path = tmp_path / "test_index.db"
        db = sqlite3.connect(db_path)

        result = ensure_memory_index_schema(db, fts_table="chunks_fts", fts_enabled=True)

        assert result["fts_available"] is True
        assert result["fts_error"] is None

        # 验证表已创建
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "meta" in tables
        assert "files" in tables
        assert "chunks" in tables
        assert "chunks_fts" in tables
        assert "embedding_cache" in tables

        db.close()

    def test_fts_disabled(self, tmp_path):
        """测试禁用 FTS 时的行为"""
        db_path = tmp_path / "test_index_no_fts.db"
        db = sqlite3.connect(db_path)

        result = ensure_memory_index_schema(db, fts_table="chunks_fts", fts_enabled=False)

        assert result["fts_available"] is False

        db.close()


class TestGetIndexPath:
    """测试数据库路径获取"""

    def test_default_path(self):
        """测试默认路径"""
        path = get_index_db_path()
        assert str(path) == DEFAULT_INDEX_PATH

    def test_custom_base_path(self, tmp_path):
        """测试自定义基础路径"""
        custom_path = tmp_path / "custom" / "index.db"
        path = get_index_db_path(base_path=custom_path)
        assert path == custom_path

    def test_agent_id_substitution(self):
        """测试 agent_id 替换"""
        path = get_index_db_path(agent_id="test-agent", base_path="memory/.index/{agentId}.sqlite")
        assert "test-agent" in str(path)
        assert ".sqlite" in str(path)


class TestMemoryIndexer:
    """测试 MemoryIndexer"""

    def test_indexer_initialization(self, tmp_path):
        """测试索引器初始化"""
        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        assert indexer.db is not None
        assert indexer.db_path == db_path
        assert indexer.fts_available is True

        indexer.close()

    def test_index_file(self, tmp_path):
        """测试索引单个文件"""
        # 创建测试文件
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "test.md"
        test_file.write_text("# 第一行\n第二行\n第三行\n")

        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        result = indexer.index_file(test_file)

        assert result["success"] is True
        assert result["updated"] is True
        assert result["chunks_added"] == 1

        # 验证数据库内容
        cursor = indexer.db.execute("SELECT COUNT(*) FROM chunks WHERE path = ?", (str(test_file),))
        count = cursor.fetchone()[0]
        assert count == 1

        indexer.close()

    def test_index_same_file_twice(self, tmp_path):
        """测试重复索引相同文件（应该跳过）"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "test.md"
        test_file.write_text("内容")

        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        # 第一次索引
        result1 = indexer.index_file(test_file)
        assert result1["success"] is True
        assert result1["updated"] is True
        assert result1["chunks_added"] == 1

        # 第二次索引（应该检测到 hash 相同，跳过）
        result2 = indexer.index_file(test_file)
        assert result2["success"] is True
        assert result2["updated"] is False
        assert result2["chunks_added"] == 0

        indexer.close()

    def test_search_with_fts(self, tmp_path):
        """测试 FTS5 搜索"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "search_test.md"
        test_file.write_text("Python 装饰器是强大的功能\n")

        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        # 索引文件
        indexer.index_file(test_file)

        # 搜索
        results = indexer.search("装饰器")

        assert len(results) > 0
        assert "装饰器" in results[0]["text"]

        indexer.close()

    def test_search_without_fts(self, tmp_path):
        """测试禁用 FTS 时的搜索"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "search_test.md"
        test_file.write_text("Python 装饰器\n")

        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path, fts_enabled=False)

        # 索引文件
        indexer.index_file(test_file)

        # 搜索
        results = indexer.search("装饰器")

        assert len(results) > 0

        indexer.close()

    def test_empty_query_returns_empty(self, tmp_path):
        """测试空查询返回空结果"""
        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        results = indexer.search("")
        assert results == []

        results = indexer.search("   ")
        assert results == []

        indexer.close()

    def test_get_status(self, tmp_path):
        """测试获取索引状态"""
        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        status = indexer.get_status()

        assert "db_path" in status
        assert "file_count" in status
        assert "chunk_count" in status
        assert "fts_available" in status

        indexer.close()

    def test_context_manager(self, tmp_path):
        """测试上下文管理器"""
        db_path = tmp_path / "test.db"

        with MemoryIndexer(db_path=db_path) as indexer:
            assert indexer.db is not None

        # 连接应该已关闭
        # 注意：sqlite3.Connection 在 __exit__ 时不一定是 None，所以这里不检查


class TestChunking:
    """测试文本分块"""

    def test_chunk_content(self):
        """测试内容分块"""
        db_path = ":memory:"  # 内存数据库
        indexer = MemoryIndexer(db_path=db_path, chunk_size=10, chunk_overlap=2)

        content = "\n".join([f"行{i}" for i in range(100)])
        chunks = indexer._chunk_content(content, "test.md")

        # 应该有多个块
        assert len(chunks) > 1

        # 验证块的基本属性
        for chunk in chunks:
            assert "id" in chunk
            assert "path" in chunk
            assert "text" in chunk
            assert "start_line" in chunk
            assert "end_line" in chunk
            assert chunk["start_line"] >= 1
            assert chunk["end_line"] <= 100

        # 验证块不重叠
        for i in range(len(chunks) - 1):
            # 当前块的结束行应该大于或等于下一块开始行减去重叠
            # （因为 start_line 是 1-based，end_line 是包含的）
            assert chunks[i]["end_line"] >= chunks[i+1]["start_line"]

    def test_small_file_single_chunk(self):
        """测试小文件只生成一个块"""
        db_path = ":memory:"
        indexer = MemoryIndexer(db_path=db_path, chunk_size=100)

        content = "只有几行\n第二行\n第三行\n"
        chunks = indexer._chunk_content(content, "test.md")

        # 小文件应该只有一个块
        assert len(chunks) == 1

        # 块应该包含所有内容
        assert chunks[0]["text"] == content

    def test_chunk_has_correct_line_numbers(self):
        """测试块有正确的行号"""
        db_path = ":memory:"
        indexer = MemoryIndexer(db_path=db_path, chunk_size=10, chunk_overlap=2)

        content = "\n".join([f"行{i}" for i in range(1, 31)])  # 30 行
        chunks = indexer._chunk_content(content, "test.md")

        # 验证行号 - 实际产生 4 个块
        assert len(chunks) == 4

        # 第一块: 1-10
        assert chunks[0]["start_line"] == 1
        assert chunks[0]["end_line"] == 10

        # 第二块: 9-18 (10 - 2 = 8, 8 + 10 = 18)
        assert chunks[1]["start_line"] == 9
        assert chunks[1]["end_line"] == 18

        # 第三块: 17-26 (18 - 2 = 16, 16 + 10 = 26)
        assert chunks[2]["start_line"] == 17
        assert chunks[2]["end_line"] == 26

        # 第四块: 25-30 (26 - 2 = 24, 剩余 6 行)
        assert chunks[3]["start_line"] == 25
        assert chunks[3]["end_line"] == 30


class TestMemoryWatcher:
    """测试文件监听器"""

    def test_watcher_initialization(self, tmp_path):
        """测试监听器初始化"""
        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        watcher = MemoryWatcher(
            indexer=indexer,
            watch_paths=[memory_dir],
            debounce_seconds=1.0
        )

        assert watcher.indexer is indexer
        assert len(watcher.watch_paths) == 1
        assert watcher.debounce_seconds == 1.0

    def test_is_watch_path(self, tmp_path):
        """测试路径判断"""
        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        watcher = MemoryWatcher(
            indexer=indexer,
            watch_paths=[memory_dir],
            debounce_seconds=1.0
        )

        # 监听路径内的文件
        assert watcher._is_watch_path(memory_dir / "test.md")

        # 监听路径的子目录
        subdir = memory_dir / "subdir"
        subdir.mkdir()
        assert watcher._is_watch_path(subdir / "test.md")

        # 监听路径外的文件
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        assert not watcher._is_watch_path(outside_dir / "test.md")

    def test_on_file_changed(self, tmp_path):
        """测试文件变更回调"""
        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        watcher = MemoryWatcher(
            indexer=indexer,
            watch_paths=[memory_dir],
            debounce_seconds=1.0
        )

        # 触发文件变更
        test_file = memory_dir / "test.md"
        watcher.on_file_changed(test_file)

        assert test_file in watcher._dirty_files

        # 触发非监听路径的文件变更
        outside_file = tmp_path / "outside.md"
        watcher.on_file_changed(outside_file)

        assert outside_file not in watcher._dirty_files

    def test_process_changes(self, tmp_path):
        """测试处理变更"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "test.md"
        test_file.write_text("测试内容")

        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        watcher = MemoryWatcher(
            indexer=indexer,
            watch_paths=[memory_dir],
            debounce_seconds=1.0
        )

        # 添加到脏文件列表
        watcher.on_file_changed(test_file)

        # 处理变更
        results = watcher.process_changes()

        assert results["processed"] == 1
        assert results["failed"] == 0
        assert len(results["files"]) == 1
        assert results["files"][0]["success"] is True

        # 脏文件列表应该被清空
        assert len(watcher._dirty_files) == 0


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, tmp_path):
        """测试完整工作流"""
        # 设置
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        # 创建测试文件
        test_file = memory_dir / "integration_test.md"
        test_content = """# Python 学习笔记

## 装饰器
Python 装饰器是强大的功能，可以在不修改原函数的情况下扩展功能。

## 实例
```python
@decorator
def func():
    pass
```
"""
        test_file.write_text(test_content)

        # 索引文件
        result = indexer.index_file(test_file)
        assert result["success"] is True

        # 搜索测试
        results = indexer.search("装饰器")
        assert len(results) > 0
        assert "装饰器" in results[0]["text"]

        # 搜索不存在的关键词
        results = indexer.search("不存在的内容xyz123")
        assert len(results) == 0

        # 获取状态
        status = indexer.get_status()
        assert status["file_count"] == 1
        assert status["chunk_count"] > 0

        indexer.close()


class TestEdgeCases:
    """边界情况测试"""

    def test_index_nonexistent_file(self, tmp_path):
        """测试索引不存在的文件"""
        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        result = indexer.index_file(Path("不存在的文件.md"))

        assert result["success"] is False
        assert "文件不存在" in result["error"]

        indexer.close()

    def test_search_with_source_filter(self, tmp_path):
        """测试来源过滤"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        # 创建测试文件
        test_file = memory_dir / "test.md"
        test_file.write_text("Python 内容\n")

        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        indexer.index_file(test_file)

        # 搜索（匹配的来源）
        results = indexer.search("Python", source_filter=["memory"])
        assert len(results) > 0

        # 搜索（不匹配的来源）
        results = indexer.search("Python", source_filter=["sessions"])
        assert len(results) == 0

        indexer.close()

    def test_unicode_content(self, tmp_path):
        """测试 Unicode 内容"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "unicode.md"
        test_file.write_text("中文内容\nEmoji 😊\n特殊符号: αβγ\n")

        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        result = indexer.index_file(test_file)
        assert result["success"] is True

        # 搜索中文
        results = indexer.search("中文")
        assert len(results) > 0

        indexer.close()

    def test_empty_file(self, tmp_path):
        """测试空文件"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "empty.md"
        test_file.write_text("")

        db_path = tmp_path / "test.db"
        indexer = MemoryIndexer(db_path=db_path)

        result = indexer.index_file(test_file)
        assert result["success"] is True
        # 空文件不应该生成 chunks
        assert result["chunks_added"] == 0

        indexer.close()
