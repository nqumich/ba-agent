"""
Agent MemoryFlush 集成测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from backend.agents.agent import BAAgent


class TestMemoryFlushIntegration:
    """测试 MemoryFlush 与 Agent 的集成"""

    def test_memory_flush_initialized_when_enabled(self):
        """测试当配置启用时，MemoryFlush 被正确初始化"""
        with patch('backend.agents.agent.get_config') as mock_get_config:
            # 创建模拟配置
            mock_config = Mock()
            mock_config.memory.enabled = True
            mock_config.memory.flush.enabled = True
            mock_config.memory.flush.soft_threshold_tokens = 100
            mock_config.memory.flush.reserve_tokens_floor = 50
            mock_config.memory.flush.min_memory_count = 1
            mock_config.memory.flush.max_memory_age_hours = 24.0
            mock_config.memory.flush.llm_model = "glm-4.7-flash"
            mock_config.memory.flush.llm_timeout = 30
            mock_config.memory.memory_dir = "./memory"
            mock_config.llm.model = "claude-3-5-sonnet-20241022"
            mock_config.llm.temperature = 0.7
            mock_config.llm.max_tokens = 4096
            mock_config.llm.timeout = 120
            mock_config.llm.provider = "anthropic"
            mock_get_config.return_value = mock_config

            with patch('backend.agents.agent.os.environ.get', return_value="test-key"):
                agent = BAAgent()

                # 验证 MemoryFlush 被初始化
                assert agent.memory_flush is not None
                assert agent.memory_flush.config.soft_threshold == 100
                assert agent.session_tokens == 0
                assert agent.compaction_count == 0

    def test_memory_flush_disabled_when_config_disabled(self):
        """测试当配置禁用时，MemoryFlush 为 None"""
        with patch('backend.agents.agent.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.memory.enabled = False
            mock_config.llm.model = "claude-3-5-sonnet-20241022"
            mock_config.llm.temperature = 0.7
            mock_config.llm.max_tokens = 4096
            mock_config.llm.timeout = 120
            mock_config.llm.provider = "anthropic"
            mock_get_config.return_value = mock_config

            with patch('backend.agents.agent.os.environ.get', return_value="test-key"):
                agent = BAAgent()

                # 验证 MemoryFlush 为 None
                assert agent.memory_flush is None

    def test_get_total_tokens_from_response_metadata(self):
        """测试从响应中提取 token 数"""
        with patch('backend.agents.agent.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.memory.enabled = False
            mock_config.llm.model = "claude-3-5-sonnet-20241022"
            mock_config.llm.temperature = 0.7
            mock_config.llm.max_tokens = 4096
            mock_config.llm.timeout = 120
            mock_config.llm.provider = "anthropic"
            mock_get_config.return_value = mock_config

            with patch('backend.agents.agent.os.environ.get', return_value="test-key"):
                agent = BAAgent()

                # 模拟响应
                result = {
                    "response_metadata": {
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 50
                        }
                    }
                }

                tokens = agent._get_total_tokens(result)
                assert tokens == 150

    def test_get_total_tokens_from_message_metadata(self):
        """测试从消息 metadata 中提取 token 数"""
        with patch('backend.agents.agent.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.memory.enabled = False
            mock_config.llm.model = "claude-3-5-sonnet-20241022"
            mock_config.llm.temperature = 0.7
            mock_config.llm.max_tokens = 4096
            mock_config.llm.timeout = 120
            mock_config.llm.provider = "anthropic"
            mock_get_config.return_value = mock_config

            with patch('backend.agents.agent.os.environ.get', return_value="test-key"):
                agent = BAAgent()

                # 模拟带 metadata 的消息
                from langchain_core.messages import AIMessage

                msg = AIMessage(content="test")
                msg.usage_metadata = {"input_tokens": 200, "output_tokens": 100}

                result = {
                    "messages": [msg]
                }

                tokens = agent._get_total_tokens(result)
                assert tokens == 300

    def test_check_and_flush_returns_none_when_disabled(self):
        """测试当 MemoryFlush 禁用时，check_and_flush 返回 None"""
        with patch('backend.agents.agent.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.memory.enabled = False
            mock_config.llm.model = "claude-3-5-sonnet-20241022"
            mock_config.llm.temperature = 0.7
            mock_config.llm.max_tokens = 4096
            mock_config.llm.timeout = 120
            mock_config.llm.provider = "anthropic"
            mock_get_config.return_value = mock_config

            with patch('backend.agents.agent.os.environ.get', return_value="test-key"):
                agent = BAAgent()

                result = agent._check_and_flush("conv_123", [], 100)
                assert result is None

    def test_check_and_flush_adds_messages_to_buffer(self):
        """测试消息被添加到 buffer"""
        with patch('backend.agents.agent.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.memory.enabled = True
            mock_config.memory.flush.enabled = True
            mock_config.memory.flush.soft_threshold_tokens = 100
            mock_config.memory.flush.reserve_tokens_floor = 50
            mock_config.memory.flush.min_memory_count = 1
            mock_config.memory.flush.max_memory_age_hours = 24.0
            mock_config.memory.flush.llm_model = "glm-4.7-flash"
            mock_config.memory.flush.llm_timeout = 30
            mock_config.memory.memory_dir = "./memory"
            mock_config.llm.model = "claude-3-5-sonnet-20241022"
            mock_config.llm.temperature = 0.7
            mock_config.llm.max_tokens = 4096
            mock_config.llm.timeout = 120
            mock_config.llm.provider = "anthropic"
            mock_get_config.return_value = mock_config

            with patch('backend.agents.agent.os.environ.get', return_value="test-key"):
                agent = BAAgent()

                # 模拟消息
                from langchain_core.messages import HumanMessage, AIMessage

                messages = [
                    HumanMessage(content="用户消息"),
                    AIMessage(content="助手响应")
                ]

                # 检查并 flush（不会触发因为 token 数不足）
                agent._check_and_flush("conv_123", messages, 10)

                # 验证消息被添加到 buffer
                assert len(agent.memory_flush.message_buffer) == 2
                assert agent.memory_flush.message_buffer[0]["content"] == "用户消息"
                assert agent.memory_flush.message_buffer[1]["content"] == "助手响应"

    def test_session_tokens_incremented(self):
        """测试 session_tokens 正确累加"""
        with patch('backend.agents.agent.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.memory.enabled = False
            mock_config.llm.model = "claude-3-5-sonnet-20241022"
            mock_config.llm.temperature = 0.7
            mock_config.llm.max_tokens = 4096
            mock_config.llm.timeout = 120
            mock_config.llm.provider = "anthropic"
            mock_get_config.return_value = mock_config

            with patch('backend.agents.agent.os.environ.get', return_value="test-key"):
                agent = BAAgent()

                # 模拟第一次响应
                result1 = {
                    "response_metadata": {
                        "usage": {"input_tokens": 100, "output_tokens": 50}
                    }
                }
                tokens1 = agent._get_total_tokens(result1)
                agent.session_tokens += tokens1

                assert agent.session_tokens == 150

                # 模拟第二次响应
                result2 = {
                    "response_metadata": {
                        "usage": {"input_tokens": 200, "output_tokens": 100}
                    }
                }
                tokens2 = agent._get_total_tokens(result2)
                agent.session_tokens += tokens2

                assert agent.session_tokens == 450


class TestMemoryFlushConfigModel:
    """测试 MemoryFlush 配置模型"""

    def test_memory_flush_config_defaults(self):
        """测试 MemoryFlushConfig 默认值"""
        from config.config import MemoryFlushConfig

        config = MemoryFlushConfig()

        assert config.enabled is True
        assert config.soft_threshold_tokens == 4000
        assert config.reserve_tokens_floor == 2000
        assert config.min_memory_count == 3
        assert config.max_memory_age_hours == 24.0
        assert config.llm_model == "glm-4.7-flash"
        assert config.llm_timeout == 30

    def test_memory_config_with_flush(self):
        """测试 MemoryConfig 包含 flush 配置"""
        from config.config import MemoryConfig

        config = MemoryConfig()

        assert hasattr(config, "flush")
        assert config.flush.enabled is True
        assert config.flush.soft_threshold_tokens == 4000

    def test_memory_config_from_dict(self):
        """测试从字典创建配置"""
        from config.config import MemoryConfig

        data = {
            "enabled": True,
            "memory_dir": "./memory",
            "daily_log_format": "%Y-%m-%d",
            "max_context_tokens": 8000,
            "flush": {
                "enabled": True,
                "soft_threshold_tokens": 3000,
                "reserve_tokens_floor": 1500,
            }
        }

        config = MemoryConfig(**data)

        assert config.flush.soft_threshold_tokens == 3000
        assert config.flush.reserve_tokens_floor == 1500
