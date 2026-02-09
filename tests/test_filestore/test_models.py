"""
文件系统模型测试

测试 FileRef, FileCategory 等核心模型
"""

import pytest
from datetime import datetime

from backend.models.filestore import (
    FileCategory,
    FileRef,
    FileContent,
    FileMetadata,
    MemoryLayer,
    MemoryRef,
    MemoryContent,
    CheckpointRef,
    StorageStats,
    CleanupStats,
    FileStoreConfig,
)


class TestFileCategory:
    """FileCategory 枚举测试"""

    def test_all_categories(self):
        """测试所有类别存在"""
        assert FileCategory.ARTIFACT == "artifact"
        assert FileCategory.UPLOAD == "upload"
        assert FileCategory.REPORT == "report"
        assert FileCategory.CHART == "chart"
        assert FileCategory.CACHE == "cache"
        assert FileCategory.TEMP == "temp"
        assert FileCategory.MEMORY == "memory"


class TestFileRef:
    """FileRef 模型测试"""

    def test_create_file_ref(self):
        """测试创建文件引用"""
        ref = FileRef(
            file_id="test_123",
            category=FileCategory.ARTIFACT,
            size_bytes=1024
        )

        assert ref.file_id == "test_123"
        assert ref.category == FileCategory.ARTIFACT
        assert ref.size_bytes == 1024
        assert ref.session_id is None

    def test_file_ref_with_session(self):
        """测试带会话的文件引用"""
        ref = FileRef(
            file_id="upload_abc",
            category=FileCategory.UPLOAD,
            session_id="session_123",
            size_bytes=2048
        )

        assert ref.session_id == "session_123"
        assert ref.category == FileCategory.UPLOAD

    def test_file_ref_str_representation(self):
        """测试字符串表示"""
        ref = FileRef(
            file_id="test_123",
            category=FileCategory.ARTIFACT
        )

        assert str(ref) == "artifact:test_123"

    def test_file_ref_validation(self):
        """测试字段验证"""
        # size_bytes 必须 >= 0
        with pytest.raises(ValueError):
            FileRef(
                file_id="test",
                category=FileCategory.ARTIFACT,
                size_bytes=-1
            )

        # file_id 不能为空
        with pytest.raises(ValueError):
            FileRef(
                file_id="",
                category=FileCategory.ARTIFACT
            )


class TestFileContent:
    """FileContent 模型测试"""

    def test_create_file_content(self):
        """测试创建文件内容"""
        content = FileContent(
            data=b"test data",
            mime_type="text/plain",
            size_bytes=9,
            hash="abc123"
        )

        assert content.data == b"test data"
        assert content.mime_type == "text/plain"
        assert content.size_bytes == 9


class TestFileMetadata:
    """FileMetadata 模型测试"""

    def test_create_file_metadata(self):
        """测试创建文件元数据"""
        file_ref = FileRef(
            file_id="test",
            category=FileCategory.ARTIFACT
        )

        metadata = FileMetadata(
            file_ref=file_ref,
            filename="test.json",
            access_count=5
        )

        assert metadata.file_ref == file_ref
        assert metadata.filename == "test.json"
        assert metadata.access_count == 5


class TestMemoryLayer:
    """MemoryLayer 枚举测试"""

    def test_all_layers(self):
        """测试所有层级"""
        assert MemoryLayer.DAILY == "daily"
        assert MemoryLayer.CONTEXT == "context"
        assert MemoryLayer.KNOWLEDGE == "knowledge"


class TestMemoryRef:
    """MemoryRef 模型测试"""

    def test_create_memory_ref(self):
        """测试创建记忆引用"""
        from pathlib import Path

        ref = MemoryRef(
            file_id="2026-02-07",
            layer=MemoryLayer.DAILY,
            path=Path("/memory/daily/2026-02-07.md"),
            created_at=1707200000.0
        )

        assert ref.file_id == "2026-02-07"
        assert ref.layer == MemoryLayer.DAILY
        assert len(ref.file_refs) == 0

    def test_memory_ref_with_file_refs(self):
        """测试带文件引用的记忆"""
        from pathlib import Path

        file_refs = [
            FileRef(file_id="artifact_1", category=FileCategory.ARTIFACT),
            FileRef(file_id="chart_1", category=FileCategory.CHART)
        ]

        ref = MemoryRef(
            file_id="test",
            layer=MemoryLayer.CONTEXT,
            path=Path("/memory/context/test.md"),
            created_at=1707200000.0,
            file_refs=file_refs
        )

        assert len(ref.file_refs) == 2
        assert ref.file_refs[0].category == FileCategory.ARTIFACT


class TestMemoryContent:
    """MemoryContent 模型测试"""

    def test_create_memory_content(self):
        """测试创建记忆内容"""
        content = MemoryContent(
            content="# Test Memory\n\nThis is a test.",
            file_refs=[],
            metadata={"key": "value"}
        )

        assert content.content == "# Test Memory\n\nThis is a test."
        assert content.metadata["key"] == "value"


class TestCheckpointRef:
    """CheckpointRef 模型测试"""

    def test_create_checkpoint_ref(self):
        """测试创建检查点引用"""
        ref = CheckpointRef(
            checkpoint_id="checkpoint_session_123_step1",
            session_id="session_123",
            name="step1",
            variables=["x", "y", "df"],
            created_at=1707200000.0
        )

        assert ref.session_id == "session_123"
        assert ref.name == "step1"
        assert "x" in ref.variables


class TestStorageStats:
    """StorageStats 模型测试"""

    def test_create_storage_stats(self):
        """测试创建存储统计"""
        stats = StorageStats(
            category=FileCategory.ARTIFACT,
            file_count=10,
            total_size_bytes=1024000
        )

        assert stats.category == FileCategory.ARTIFACT
        assert stats.file_count == 10
        assert stats.total_size_bytes == 1024000


class TestCleanupStats:
    """CleanupStats 模型测试"""

    def test_create_cleanup_stats(self):
        """测试创建清理统计"""
        stats = CleanupStats(
            deleted_count=5,
            freed_space_bytes=512000,
            category_stats={"artifact": 3, "upload": 2},
            duration_seconds=1.5
        )

        assert stats.deleted_count == 5
        assert stats.freed_space_bytes == 512000
        assert stats.category_stats["artifact"] == 3


class TestFileStoreConfig:
    """FileStoreConfig 模型测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = FileStoreConfig()

        assert config.base_dir.name == "ba-agent"
        assert config.max_total_size_gb == 10
        assert config.cleanup_interval_hours == 1
        assert len(config.ttl_config) > 0

    def test_custom_config(self):
        """测试自定义配置"""
        from pathlib import Path

        config = FileStoreConfig(
            base_dir=Path("/custom/path"),
            max_total_size_gb=20,
            cleanup_interval_hours=2
        )

        assert config.base_dir == Path("/custom/path")
        assert config.max_total_size_gb == 20
        assert config.cleanup_interval_hours == 2
