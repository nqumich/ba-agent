"""
FileStore 与 Pipeline 集成测试

测试工具执行结果与 FileStore 的集成功能
"""

import pytest
import json
import tempfile
from pathlib import Path

from backend.models.pipeline import ToolExecutionResult, OutputLevel
from backend.filestore import FileStore, get_file_store
from backend.pipeline.filestore_integration import FileStorePipelineIntegration


class TestFileStorePipelineIntegration:
    """FileStore Pipeline 集成测试"""

    @pytest.fixture
    def integration(self, temp_dir):
        """集成管理器夹具"""
        fs = FileStore(base_dir=temp_dir)
        return FileStorePipelineIntegration(fs)

    def test_store_tool_result_with_artifact(self, integration):
        """测试存储带 artifact_id 的结果"""
        result = ToolExecutionResult(
            tool_call_id="test_123",
            tool_name="test_tool",
            observation="Test observation",
            artifact_id="artifact_abc123",
            data_size_bytes=1024,
            data_hash="abc123"
        )

        file_ref = integration.store_tool_result(result, session_id="session_1")

        assert file_ref is not None
        assert file_ref.file_id == "artifact_abc123"
        assert file_ref.category.value == "artifact"

    def test_result_with_file_ref(self, integration):
        """测试为结果添加 FileRef"""
        result = ToolExecutionResult(
            tool_call_id="test_123",
            tool_name="test_tool",
            observation="Test observation"
        )

        from backend.models.filestore import FileRef, FileCategory

        file_ref = FileRef(
            file_id="upload_xyz",
            category=FileCategory.UPLOAD,
            session_id="session_1"
        )

        updated_result = integration.result_with_file_ref(result, file_ref)

        assert 'file_ref' in updated_result.metadata
        assert updated_result.metadata['file_ref']['file_id'] == "upload_xyz"
        assert updated_result.artifact_id == "upload_xyz"

    def test_create_result_with_storage_small_data(self, integration, temp_dir):
        """测试创建结果并存储（小数据）"""
        raw_data = {"result": "success", "count": 5}

        result, file_ref = FileStorePipelineIntegration.create_result_with_storage(
            tool_call_id="test_123",
            raw_data=raw_data,
            output_level=OutputLevel.STANDARD,
            tool_name="test_tool",
            file_store=integration.file_store,
            session_id="session_1"
        )

        assert result is not None
        assert result.tool_name == "test_tool"
        # 小数据不会存储到 FileStore
        assert file_ref is None

    def test_create_result_with_storage_large_data(self, integration):
        """测试创建结果并存储（大数据）"""
        # 创建大于 1MB 的数据
        large_data = {"data": "x" * 1_200_000}

        result, file_ref = FileStorePipelineIntegration.create_result_with_storage(
            tool_call_id="test_123",
            raw_data=large_data,
            output_level=OutputLevel.FULL,
            tool_name="test_tool",
            file_store=integration.file_store,
            session_id="session_1"
        )

        assert result is not None
        # 大数据应该存储到 FileStore
        assert file_ref is not None
        assert "artifact_" in file_ref.file_id
        assert result.artifact_id == file_ref.file_id
        assert "stored as artifact" in result.observation

    def test_extract_file_refs_from_context(self, integration):
        """测试从上下文提取文件引用"""
        context = {
            'artifact_id': 'artifact_abc',
            'session_id': 'session_123'
        }

        refs = integration.extract_file_refs_from_context(context)

        assert len(refs) == 1
        assert refs[0].file_id == "artifact_abc"


class TestFileStoreFactory:
    """FileStore 工厂函数测试"""

    def test_get_file_store(self, temp_dir):
        """测试获取 FileStore 实例"""
        fs = get_file_store(base_dir=temp_dir, force_new=True)

        assert fs is not None
        assert fs.base_dir == temp_dir

    def test_get_file_store_singleton(self, temp_dir):
        """测试单例模式"""
        fs1 = get_file_store(base_dir=temp_dir, force_new=True)
        fs2 = get_file_store(base_dir=temp_dir, force_new=False)

        # 不强制新建时应该返回同一个实例
        assert fs1 is fs2

    def test_reset_file_store(self, temp_dir):
        """测试重置 FileStore"""
        from backend.filestore.factory import reset_file_store

        fs1 = get_file_store(base_dir=temp_dir, force_new=True)
        reset_file_store()

        fs2 = get_file_store(base_dir=temp_dir, force_new=True)

        # 重置后应该是新实例
        assert fs1 is not fs2
