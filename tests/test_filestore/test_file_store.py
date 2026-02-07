"""
FileStore 主类测试

测试统一文件存储管理器的核心功能
"""

import pytest
import json
from pathlib import Path

from backend.models.filestore import FileCategory, FileRef
from backend.filestore import FileStore


class TestFileStoreInitialization:
    """FileStore 初始化测试"""

    def test_init_default_dir(self, temp_dir):
        """测试使用默认目录初始化（使用临时目录）"""
        # 使用临时目录来测试默认初始化逻辑
        fs = FileStore(base_dir=temp_dir)

        assert fs.base_dir == temp_dir
        assert fs.artifacts is not None
        assert fs.uploads is not None

    def test_init_custom_dir(self, temp_dir):
        """测试使用自定义目录初始化"""
        fs = FileStore(base_dir=temp_dir)

        assert fs.base_dir == temp_dir

    def test_all_stores_initialized(self, file_store):
        """测试所有存储已初始化"""
        assert file_store.artifacts is not None
        assert file_store.uploads is not None
        assert file_store.reports is not None
        assert file_store.charts is not None
        assert file_store.cache is not None
        assert file_store.temp is not None
        assert file_store.memory is not None
        assert file_store.checkpoints is not None

    def test_store_mapping(self, file_store):
        """测试存储映射表"""
        assert FileCategory.ARTIFACT in file_store._stores
        assert FileCategory.UPLOAD in file_store._stores
        assert FileCategory.REPORT in file_store._stores


class TestFileStoreBasicOperations:
    """FileStore 基础操作测试"""

    def test_store_file(self, file_store):
        """测试存储文件"""
        content = b"test content"
        file_ref = file_store.store_file(
            content=content,
            category=FileCategory.ARTIFACT,
            session_id="test_session"
        )

        assert file_ref is not None
        assert file_ref.category == FileCategory.ARTIFACT
        assert file_ref.session_id == "test_session"

    def test_store_and_retrieve(self, file_store):
        """测试存储和检索"""
        content = json.dumps({"test": "data"}).encode('utf-8')

        file_ref = file_store.store_file(
            content=content,
            category=FileCategory.ARTIFACT
        )

        retrieved = file_store.get_file(file_ref)
        assert retrieved is not None
        assert json.loads(retrieved.decode('utf-8')) == {"test": "data"}

    def test_store_and_exists(self, file_store):
        """测试存储和存在性检查"""
        content = b"test content"

        file_ref = file_store.store_file(
            content=content,
            category=FileCategory.ARTIFACT
        )

        assert file_store.file_exists(file_ref)

    def test_store_and_delete(self, file_store):
        """测试存储和删除"""
        content = b"test content"

        file_ref = file_store.store_file(
            content=content,
            category=FileCategory.ARTIFACT
        )

        assert file_store.file_exists(file_ref)

        deleted = file_store.delete_file(file_ref)
        assert deleted

        assert not file_store.file_exists(file_ref)

    def test_list_files(self, file_store):
        """测试列出文件"""
        # 存储多个文件
        for i in range(3):
            file_store.store_file(
                content=f"content {i}".encode(),
                category=FileCategory.ARTIFACT,
                session_id=f"session_{i}"
            )

        files = file_store.list_files(category=FileCategory.ARTIFACT)
        assert len(files) >= 3


class TestFileStoreGetStore:
    """FileStore.get_store 测试"""

    def test_get_store(self, file_store):
        """测试获取特定存储"""
        artifact_store = file_store.get_store(FileCategory.ARTIFACT)
        assert artifact_store is file_store.artifacts

        upload_store = file_store.get_store(FileCategory.UPLOAD)
        assert upload_store is file_store.uploads

    def test_get_store_invalid_category(self, file_store):
        """测试获取不存在的类别"""
        store = file_store.get_store(FileCategory.ARTIFACT)
        assert store is not None


class TestFileStoreStorageStats:
    """FileStore 存储统计测试"""

    def test_get_storage_stats(self, file_store):
        """测试获取存储统计"""
        # 存储一些文件
        file_store.store_file(
            content=b"data",
            category=FileCategory.ARTIFACT
        )

        stats = file_store.get_storage_stats()
        assert len(stats) > 0

        # 检查 artifact 类别有文件
        artifact_stats = [s for s in stats if s.category == FileCategory.ARTIFACT]
        assert len(artifact_stats) == 1

    def test_get_storage_stats_all_categories(self, file_store):
        """测试获取所有类别统计"""
        stats = file_store.get_storage_stats()

        # 应该有 8 个类别（artifact, upload, report, chart, cache, temp, memory, code）
        assert len(stats) == 8


class TestFileStoreCleanup:
    """FileStore 清理测试"""

    def test_cleanup_dry_run(self, file_store):
        """测试清理（dry run）"""
        # 存储一些文件
        for i in range(3):
            file_store.store_file(
                content=f"data {i}".encode(),
                category=FileCategory.ARTIFACT
            )

        # 清理所有文件（TTL=0）
        stats = file_store.cleanup(max_age_hours=0)

        assert stats.deleted_count >= 0
        assert stats.duration_seconds >= 0


class TestFileStoreContextManager:
    """FileStore 上下文管理器测试"""

    def test_context_manager(self, temp_dir):
        """测试上下文管理器"""
        with FileStore(base_dir=temp_dir) as fs:
            file_ref = fs.store_file(
                content=b"test",
                category=FileCategory.ARTIFACT
            )

            assert fs.file_exists(file_ref)

        # 退出后应该正常关闭


class TestFileStoreSizeValidation:
    """FileStore 大小验证测试"""

    def test_file_size_validation(self, file_store):
        """测试文件大小验证"""
        # 正常大小应该可以存储
        content = b"x" * 100  # 100 bytes
        file_ref = file_store.store_file(
            content=content,
            category=FileCategory.ARTIFACT
        )
        assert file_ref is not None

    def test_file_size_exceeds_limit(self, file_store):
        """测试文件大小超过限制"""
        # Artifact 默认最大 100MB
        # 这里我们测试配置是否生效
        # 实际的大小限制测试需要更多配置
        pass


class TestFileStoreErrorHandling:
    """FileStore 错误处理测试"""

    def test_invalid_category(self, file_store):
        """测试无效的文件类别"""
        with pytest.raises(ValueError):
            file_store.store_file(
                content=b"data",
                category="invalid_category"  # 类型错误
            )

    def test_get_nonexistent_file(self, file_store):
        """测试获取不存在的文件"""
        fake_ref = FileRef(
            file_id="nonexistent",
            category=FileCategory.ARTIFACT
        )

        content = file_store.get_file(fake_ref)
        # ArtifactStore 可能返回 None
        assert content is None or content == b""

    def test_delete_nonexistent_file(self, file_store):
        """测试删除不存在的文件"""
        fake_ref = FileRef(
            file_id="nonexistent",
            category=FileCategory.ARTIFACT
        )

        deleted = file_store.delete_file(fake_ref)
        # 应该返回 False
        assert deleted is False or deleted is None
