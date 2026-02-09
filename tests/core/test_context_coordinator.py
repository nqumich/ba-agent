"""
Context Coordinator Tests

测试上下文协调器的消息准备和清理功能
"""

import pytest
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from backend.core.context_coordinator import ContextCoordinator, create_context_coordinator
from backend.core.context_manager import ContextManager


class TestContextCoordinator:
    """测试 ContextCoordinator 基本功能"""

    def test_init(self):
        """测试初始化"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        assert coordinator.context_manager == context_manager

    def test_create_context_coordinator(self):
        """测试便捷创建函数"""
        context_manager = ContextManager()
        coordinator = create_context_coordinator(context_manager)

        assert isinstance(coordinator, ContextCoordinator)
        assert coordinator.context_manager == context_manager


class TestPrepareMessages:
    """测试 prepare_messages 方法"""

    def test_prepare_messages_empty(self):
        """测试空消息列表"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        result = coordinator.prepare_messages([])

        assert result == []

    def test_prepare_messages_simple(self):
        """测试简单消息列表（无需清理）"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there")
        ]

        result = coordinator.prepare_messages(messages)

        assert len(result) == 2
        assert result[0].content == "Hello"
        assert result[1].content == "Hi there"

    def test_prepare_messages_with_large_content(self):
        """测试包含大文件内容的消息清理"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        # 创建包含大内容的消息
        large_content = "A" * 3000
        messages = [
            HumanMessage(content="User message"),
            AIMessage(content=large_content)
        ]

        result = coordinator.prepare_messages(messages)

        assert len(result) == 2
        assert result[0].content == "User message"
        # 大内容应该被清理
        assert "[大文件内容已清理" in result[1].content
        assert "原始 3000 字符" in result[1].content
        assert "预览:" in result[1].content

    def test_prepare_messages_with_system_prompt(self):
        """测试包含系统提示词的消息列表"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        system_prompt = "You are a helpful assistant."
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Hello")
        ]

        result = coordinator.prepare_messages(messages)

        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == system_prompt

    def test_prepare_messages_preserves_message_types(self):
        """测试保留消息类型"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="Human"),
            AIMessage(content="AI"),
        ]

        result = coordinator.prepare_messages(messages)

        assert isinstance(result[0], SystemMessage)
        assert isinstance(result[1], HumanMessage)
        assert isinstance(result[2], AIMessage)

    def test_prepare_messages_with_session_id(self):
        """测试传递 session_id"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        messages = [HumanMessage(content="Test")]

        result = coordinator.prepare_messages(messages, session_id="test_session")

        assert len(result) == 1
        # session_id 暂时未使用，但应该不会报错


class TestPrepareMessagesWithSystemPrompt:
    """测试 prepare_messages_with_system_prompt 方法"""

    def test_with_system_prompt_adds_missing(self):
        """测试添加缺失的系统提示词"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        messages = [
            HumanMessage(content="Hello")
        ]
        system_prompt = "You are a helpful assistant."

        result = coordinator.prepare_messages_with_system_prompt(
            messages, system_prompt
        )

        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == system_prompt
        assert result[1].content == "Hello"

    def test_with_system_prompt_replaces_existing(self):
        """测试替换现有的系统提示词"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        messages = [
            SystemMessage(content="Old prompt"),
            HumanMessage(content="Hello")
        ]
        new_prompt = "You are a helpful assistant."

        result = coordinator.prepare_messages_with_system_prompt(
            messages, new_prompt
        )

        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == new_prompt
        assert result[1].content == "Hello"

    def test_with_system_prompt_preserves_correct(self):
        """测试保留正确的系统提示词"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        prompt = "You are a helpful assistant."
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Hello")
        ]

        result = coordinator.prepare_messages_with_system_prompt(
            messages, prompt
        )

        assert len(result) == 2
        assert result[0].content == prompt

    def test_with_system_prompt_with_large_content(self):
        """测试系统提示词 + 大内容清理"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        prompt = "You are a helpful assistant."
        large_content = "B" * 3000
        messages = [
            HumanMessage(content="User"),
            AIMessage(content=large_content)
        ]

        result = coordinator.prepare_messages_with_system_prompt(
            messages, prompt
        )

        assert len(result) == 3
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == prompt
        assert "[大文件内容已清理" in result[2].content


class TestContextCoordinatorIntegration:
    """集成测试"""

    def test_full_message_flow(self):
        """测试完整的消息处理流程"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        # 模拟一个完整的对话场景，使用更大的内容以确保超过阈值
        large_file_content = "def process_sales():\n" + "    # " * 100 + "\n" + "    pass" * 200 + "\n" + "    return" * 200
        messages = [
            HumanMessage(content="请读取 sales_analysis.py 文件"),
            AIMessage(content="I'll read the file for you."),
            ToolMessage(
                content=large_file_content,
                tool_call_id="call_read_file_123",
                name="read_file"
            ),
        ]

        result = coordinator.prepare_messages(messages)

        assert len(result) == 3
        # ToolMessage 的大内容应该被清理
        assert "[大文件内容已清理" in result[2].content

    def test_multiple_large_messages(self):
        """测试多个大消息的清理"""
        context_manager = ContextManager()
        coordinator = ContextCoordinator(context_manager)

        messages = [
            HumanMessage(content="User message"),
            AIMessage(content="A" * 3000),
            AIMessage(content="B" * 4000),
        ]

        result = coordinator.prepare_messages(messages)

        assert len(result) == 3
        assert result[0].content == "User message"
        assert "[大文件内容已清理" in result[1].content
        assert "原始 3000 字符" in result[1].content
        assert "[大文件内容已清理" in result[2].content
        assert "原始 4000 字符" in result[2].content
