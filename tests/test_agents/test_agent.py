"""
BA-Agent 单元测试

US-004: LangGraph Agent 基础框架
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.tools import tool

from backend.agents.agent import (
    BAAgent,
    AgentState,
    create_agent,
)


class TestBAAgent:
    """测试 BAAgent 类"""

    def test_init_without_api_key_raises_error(self, monkeypatch):
        """测试没有 API 密钥时抛出错误"""
        # 确保没有 API 密钥
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("BA_ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not found"):
            BAAgent()

    def test_init_with_api_key(self, monkeypatch):
        """测试使用 API 密钥初始化"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        agent = BAAgent()
        assert agent.config.name == "BA-Agent"
        assert agent.config.model == "claude-3-5-sonnet-20241022"
        assert agent.llm is not None
        assert isinstance(agent.tools, list)

    def test_default_system_prompt(self, monkeypatch):
        """测试默认系统提示词"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        agent = BAAgent()
        prompt = agent.system_prompt

        assert "BA-Agent" in prompt
        assert "异动检测" in prompt
        assert "归因分析" in prompt
        assert "报告生成" in prompt

    def test_custom_system_prompt(self, monkeypatch):
        """测试自定义系统提示词"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        custom_prompt = "你是一个测试助手"
        agent = BAAgent(system_prompt=custom_prompt)

        assert agent.system_prompt == custom_prompt

    def test_add_tool(self, monkeypatch):
        """测试添加工具"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        agent = BAAgent()

        # 获取初始工具数量（可能包含 skill_tool）
        initial_count = len(agent.tools)

        # 创建测试工具
        @tool
        def test_tool(query: str) -> str:
            """测试工具"""
            return f"结果: {query}"

        agent.add_tool(test_tool)

        assert len(agent.tools) == initial_count + 1
        assert agent.tools[-1].name == "test_tool"

    def test_add_tools(self, monkeypatch):
        """测试批量添加工具"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        agent = BAAgent()

        # 获取初始工具数量（可能包含 skill_tool）
        initial_count = len(agent.tools)

        # 创建测试工具
        @tool
        def tool1(query: str) -> str:
            """工具1"""
            return f"结果1: {query}"

        @tool
        def tool2(query: str) -> str:
            """工具2"""
            return f"结果2: {query}"

        agent.add_tools([tool1, tool2])

        assert len(agent.tools) == initial_count + 2

    @patch("backend.agents.agent.ChatAnthropic")
    def test_invoke_without_mock_llm(self, mock_chat_anthropic, monkeypatch):
        """测试 invoke 方法（不实际调用 LLM）"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        # Mock LLM 响应
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="测试响应")
        mock_chat_anthropic.return_value = mock_llm

        agent = BAAgent()

        # Mock agent
        agent.agent = MagicMock()
        agent.agent.invoke.return_value = {
            "messages": [AIMessage(content="测试响应")]
        }

        result = agent.invoke("你好")

        assert result["success"] is True
        assert result["response"] == "测试响应"
        assert "conversation_id" in result

    def test_extract_response_from_ai_message(self, monkeypatch):
        """测试从 AI 消息中提取响应"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        agent = BAAgent()

        # 测试字符串内容
        result1 = agent._extract_response({
            "messages": [AIMessage(content="测试响应")]
        })
        assert result1 == "测试响应"

        # 测试列表内容（多模态）
        result2 = agent._extract_response({
            "messages": [
                AIMessage(content=[
                    {"type": "text", "text": "第一部分"},
                    {"type": "text", "text": "第二部分"},
                ])
            ]
        })
        assert result2 == "第一部分\n第二部分"

    def test_extract_response_empty(self, monkeypatch):
        """测试提取空响应"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        agent = BAAgent()

        result = agent._extract_response({})
        assert result == ""

        result = agent._extract_response({"messages": []})
        assert result == ""


class TestCreateAgent:
    """测试 create_agent 便捷函数"""

    def test_create_agent_without_tools(self, monkeypatch):
        """测试不使用工具创建 Agent"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        agent = create_agent()

        assert isinstance(agent, BAAgent)
        # Agent may have skill_tool if skills directory exists
        # The key is that we didn't explicitly add any tools
        # Check that any tool present is the skill_tool
        for tool in agent.tools:
            assert tool.name in ["activate_skill", ""]

    def test_create_agent_with_tools(self, monkeypatch):
        """测试使用工具创建 Agent"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        @tool
        def test_tool(query: str) -> str:
            """测试工具"""
            return query

        agent = create_agent(tools=[test_tool])

        assert isinstance(agent, BAAgent)
        # Agent should have at least our test_tool
        # May also have skill_tool if skills directory exists
        tool_names = [t.name for t in agent.tools]
        assert "test_tool" in tool_names

    def test_create_agent_with_custom_prompt(self, monkeypatch):
        """测试使用自定义提示词创建 Agent"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        custom_prompt = "你是一个测试助手"
        agent = create_agent(system_prompt=custom_prompt)

        assert agent.system_prompt == custom_prompt


class TestAgentIntegration:
    """集成测试（需要 API 密钥）"""

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="需要 ANTHROPIC_API_KEY 环境变量"
    )
    def test_real_agent_invoke(self):
        """测试真实的 Agent 调用（需要 API 密钥）"""
        # 这个测试只在有 API 密钥时运行
        agent = create_agent()

        result = agent.invoke("你好，请介绍一下你自己")

        assert result["success"] is True
        assert result["response"] is not None
        assert len(result["response"]) > 0

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="需要 ANTHROPIC_API_KEY 环境变量"
    )
    def test_real_agent_with_tool(self):
        """测试带工具的真实 Agent 调用"""
        @tool
        def get_current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
            """获取当前时间"""
            from datetime import datetime
            return datetime.now().strftime(format)

        agent = create_agent(tools=[get_current_time])

        result = agent.invoke("现在几点了？")

        assert result["success"] is True
        # 响应应该包含时间信息
        assert result["response"] is not None


class TestAgentState:
    """测试 AgentState 类型定义"""

    def test_agent_state_structure(self):
        """测试 AgentState 结构"""
        state: AgentState = {
            "messages": [HumanMessage(content="测试")],
            "conversation_id": "conv-001",
            "user_id": "user-001",
            "metadata": {"key": "value"},
        }

        assert len(state["messages"]) == 1
        assert state["conversation_id"] == "conv-001"
        assert state["user_id"] == "user-001"
        assert state["metadata"]["key"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
