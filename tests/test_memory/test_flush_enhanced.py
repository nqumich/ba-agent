"""
Enhanced Memory Flush 测试

测试文件引用检测和增强的 MemoryFlush 功能
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from langchain_core.messages import HumanMessage, AIMessage

from backend.memory.flush_enhanced import (
    FileRefDetector,
    EnhancedMemoryFlush,
    create_enhanced_memory_flush
)
from backend.models.filestore import FileRef, FileCategory
from backend.filestore import FileStore


@pytest.fixture
def mock_file_store():
    """模拟 FileStore"""
    fs = Mock(spec=FileStore)
    fs.memory = Mock()
    fs.memory.write_daily_memory = Mock()
    return fs


@pytest.fixture
def temp_dir(tmp_path):
    """临时目录夹具"""
    return tmp_path


class TestFileRefDetector:
    """测试文件引用检测器"""

    def test_detect_from_tool_call_with_artifact_id(self):
        """测试从工具调用检测 artifact_id"""
        tool_output = {
            "artifact_id": "artifact_abc123",
            "data_size_bytes": 1024,
            "summary": "测试结果"
        }

        refs = FileRefDetector.detect_from_tool_call(
            tool_name="test_tool",
            tool_input={},
            tool_output=tool_output
        )

        assert len(refs) == 1
        assert refs[0].file_id == "artifact_abc123"
        assert refs[0].category == FileCategory.ARTIFACT
        assert refs[0].size_bytes == 1024

    def test_detect_from_tool_call_with_file_ref(self):
        """测试从工具调用检测 file_ref"""
        tool_output = {
            "file_ref": {
                "file_id": "upload_xyz",
                "category": "upload",
                "session_id": "session_123",
                "size_bytes": 2048
            }
        }

        refs = FileRefDetector.detect_from_tool_call(
            tool_name="test_tool",
            tool_input={},
            tool_output=tool_output
        )

        assert len(refs) == 1
        assert refs[0].file_id == "upload_xyz"
        assert refs[0].category == FileCategory.UPLOAD
        assert refs[0].session_id == "session_123"

    def test_detect_from_tool_call_with_colon_format(self):
        """测试从工具输入检测冒号格式的文件引用"""
        tool_input = {
            "file_id": "artifact:abc123",
            "other_param": "value"
        }

        refs = FileRefDetector.detect_from_tool_call(
            tool_name="query_database",
            tool_input=tool_input,
            tool_output={}
        )

        assert len(refs) == 1
        assert refs[0].file_id == "abc123"
        assert refs[0].category == FileCategory.ARTIFACT

    def test_detect_from_tool_call_invalid_category(self):
        """测试无效的类别格式"""
        tool_input = {
            "file_id": "invalid:abc123"
        }

        refs = FileRefDetector.detect_from_tool_call(
            tool_name="test_tool",
            tool_input=tool_input,
            tool_output={}
        )

        # 无效类别应该被忽略
        assert len(refs) == 0

    def test_detect_from_messages_with_context(self):
        """测试从消息和上下文检测文件引用"""
        context = {
            "artifacts": ["artifact_1", "artifact_2"]
        }

        refs = FileRefDetector.detect_from_messages(
            messages=[],
            context=context
        )

        assert len(refs) == 2
        assert refs[0].file_id == "artifact_1"
        assert refs[0].category == FileCategory.ARTIFACT

    def test_extract_all_file_refs_deduplication(self):
        """测试文件引用去重"""
        tool_history = [
            {
                "name": "test_tool",
                "input": {"file_id": "artifact:abc123"},
                "output": {"artifact_id": "abc123"}
            },
            {
                "name": "another_tool",
                "input": {},
                "output": {"artifact_id": "abc123"}  # 重复
            }
        ]

        refs = FileRefDetector.extract_all_file_refs(
            messages=[],
            context={},
            tool_history=tool_history
        )

        # 应该去重
        assert len(refs) == 1
        assert refs[0].file_id == "abc123"

    def test_tool_file_categories_mapping(self):
        """测试工具到文件类别的映射"""
        # 验证预定义的工具映射
        assert "run_python" in FileRefDetector.TOOL_FILE_CATEGORIES
        assert FileRefDetector.TOOL_FILE_CATEGORIES["run_python"] == FileCategory.TEMP
        assert FileRefDetector.TOOL_FILE_CATEGORIES["chart"] == FileCategory.CHART


class TestEnhancedMemoryFlush:
    """测试增强的 MemoryFlush"""

    def test_init_with_file_store(self, mock_file_store):
        """测试使用 FileStore 初始化"""
        flush = EnhancedMemoryFlush(file_store=mock_file_store)

        assert flush.file_store == mock_file_store
        assert flush.file_ref_detector is not None

    def test_init_without_file_store(self):
        """测试不使用 FileStore 初始化"""
        flush = EnhancedMemoryFlush()

        assert flush.file_store is None
        assert flush.file_ref_detector is not None

    def test_add_message_with_context(self, mock_file_store):
        """测试添加带上下文的消息"""
        flush = EnhancedMemoryFlush(file_store=mock_file_store)

        tool_calls = [
            {
                "name": "test_tool",
                "input": {},
                "output": {"artifact_id": "artifact_123"}
            }
        ]

        flush.add_message_with_context(
            role="user",
            content="测试消息",
            tool_calls=tool_calls,
            context={"session_id": "session_1"}
        )

        assert len(flush.message_buffer) == 1
        assert hasattr(flush, "_contexts")
        assert len(flush._contexts) == 1

    def test_detect_file_refs_from_session(self, mock_file_store):
        """测试从会话检测文件引用"""
        flush = EnhancedMemoryFlush(file_store=mock_file_store)

        # 添加带工具调用的消息
        tool_calls = [
            {
                "name": "test_tool",
                "input": {},
                "output": {"artifact_id": "artifact_123"}
            },
            {
                "name": "another_tool",
                "input": {},
                "output": {"artifact_id": "artifact_456"}
            }
        ]

        flush.add_message_with_context(
            role="assistant",
            content="响应",
            tool_calls=tool_calls,
            context={}
        )

        refs = flush._detect_file_refs_from_session("session_1")

        assert len(refs) == 2

    def test_flush_with_file_refs(self, temp_dir, mock_file_store):
        """测试带文件引用的 flush"""
        flush = EnhancedMemoryFlush(
            memory_path=temp_dir,
            file_store=mock_file_store
        )

        # 添加一些消息
        flush.add_message("user", "记住：这是一条测试消息")

        # 模拟文件引用
        flush._contexts = [{
            "tool_calls": [
                {
                    "name": "test_tool",
                    "input": {},
                    "output": {"artifact_id": "artifact_123"}
                }
            ],
            "context": {},
            "role": "assistant",
            "content": "",
            "timestamp": 0
        }]

        # 模拟 LangChain 消息
        messages = [HumanMessage(content="测试")]

        result = flush.flush_with_file_refs(
            messages=messages,
            context={},
            session_id="session_1"
        )

        # 由于 extractor 可能不会提取到记忆，我们检查结果结构
        assert "flushed" in result
        assert "memories_extracted" in result
        assert "file_refs_count" in result

    def test_flush_without_file_refs_fallback(self, temp_dir):
        """测试没有文件引用时回退到原有逻辑"""
        flush = EnhancedMemoryFlush(memory_path=temp_dir)

        # 添加消息但不添加文件引用
        flush.add_message("user", "记住：测试消息")

        messages = [HumanMessage(content="测试")]
        context = {}

        result = flush.flush_with_file_refs(
            messages=messages,
            context=context,
            session_id="session_1"
        )

        # 应该使用原有逻辑
        assert "flushed" in result

    def test_convert_messages_to_dict(self):
        """测试消息格式转换"""
        flush = EnhancedMemoryFlush()

        messages = [
            HumanMessage(content="用户消息"),
            AIMessage(content="助手消息")
        ]

        dict_messages = flush._convert_messages_to_dict(messages)

        assert len(dict_messages) == 2
        assert dict_messages[0]["role"] == "user"
        assert dict_messages[0]["content"] == "用户消息"
        assert dict_messages[1]["role"] == "assistant"
        assert dict_messages[1]["content"] == "助手消息"

    def test_write_to_file(self, temp_dir):
        """测试写入文件"""
        flush = EnhancedMemoryFlush(memory_path=temp_dir)

        success = flush._write_to_file("测试记忆内容")

        assert success is True

        # 验证文件已创建
        files = list(temp_dir.glob("*.md"))
        assert len(files) > 0


class TestCreateEnhancedMemoryFlush:
    """测试便捷工厂函数"""

    def test_create_enhanced_memory_flush_with_file_store(self, mock_file_store):
        """测试创建带 FileStore 的实例"""
        flush = create_enhanced_memory_flush(file_store=mock_file_store)

        assert isinstance(flush, EnhancedMemoryFlush)
        assert flush.file_store == mock_file_store

    def test_create_enhanced_memory_flush_without_file_store(self):
        """测试创建不带 FileStore 的实例"""
        flush = create_enhanced_memory_flush()

        assert isinstance(flush, EnhancedMemoryFlush)
        assert flush.file_store is None

    def test_create_enhanced_memory_flush_with_config(self):
        """测试创建带自定义配置的实例"""
        from backend.memory.flush import MemoryFlushConfig

        config = MemoryFlushConfig(soft_threshold=1000)
        flush = create_enhanced_memory_flush(config=config)

        assert flush.config == config


class TestIntegration:
    """集成测试"""

    def test_full_workflow_with_file_refs(self, temp_dir):
        """测试完整的工作流：添加消息、检测文件引用、flush"""
        # 创建真实的 FileStore
        fs = FileStore(base_dir=temp_dir)

        flush = EnhancedMemoryFlush(
            memory_path=temp_dir / "memory",
            file_store=fs
        )

        # 模拟工具调用
        tool_calls = [
            {
                "name": "query_database",
                "input": {},
                "output": {
                    "artifact_id": "query_result_123",
                    "data_size_bytes": 512
                }
            }
        ]

        # 添加带上下文的消息
        flush.add_message_with_context(
            role="user",
            content="查询数据库",
            tool_calls=tool_calls,
            context={"session_id": "session_1"}
        )

        # 检测文件引用
        refs = flush._detect_file_refs_from_session("session_1")

        assert len(refs) == 1
        assert refs[0].file_id == "query_result_123"

    def test_multiple_file_refs_deduplication(self, temp_dir):
        """测试多个文件引用的去重"""
        fs = FileStore(base_dir=temp_dir)
        flush = EnhancedMemoryFlush(file_store=fs)

        # 添加多个包含相同文件引用的工具调用
        tool_calls = [
            {
                "name": "tool1",
                "input": {},
                "output": {"artifact_id": "shared_artifact"}
            },
            {
                "name": "tool2",
                "input": {},
                "output": {"artifact_id": "shared_artifact"}
            },
            {
                "name": "tool3",
                "input": {},
                "output": {"artifact_id": "unique_artifact"}
            }
        ]

        flush.add_message_with_context(
            role="assistant",
            content="测试",
            tool_calls=tool_calls,
            context={}
        )

        refs = flush._detect_file_refs_from_session("session_1")

        # 应该去重，只有 2 个唯一的文件引用
        assert len(refs) == 2

    def test_file_refs_from_different_sources(self, temp_dir):
        """测试从不同来源检测文件引用"""
        fs = FileStore(base_dir=temp_dir)
        flush = EnhancedMemoryFlush(file_store=fs)

        # 从工具输出检测
        tool_calls_from_output = [
            {
                "name": "chart_tool",
                "input": {},
                "output": {"artifact_id": "chart_123"}
            }
        ]

        # 从工具输入检测
        tool_calls_from_input = [
            {
                "name": "query_database",
                "input": {"file_id": "artifact:existing_data"},
                "output": {}
            }
        ]

        flush.add_message_with_context(
            role="assistant",
            content="响应",
            tool_calls=tool_calls_from_output + tool_calls_from_input,
            context={}
        )

        refs = flush._detect_file_refs_from_session("session_1")

        # 应该检测到 2 个文件引用
        assert len(refs) == 2
        file_ids = {ref.file_id for ref in refs}
        assert "chart_123" in file_ids
        assert "existing_data" in file_ids
