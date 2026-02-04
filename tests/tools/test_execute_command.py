"""
命令行执行工具单元测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pydantic import ValidationError

from tools.execute_command import (
    ExecuteCommandInput,
    execute_command_impl,
    execute_command_tool,
)


class TestExecuteCommandInput:
    """测试 ExecuteCommandInput 模型"""

    def test_valid_command_in_whitelist(self):
        """测试白名单中的有效命令"""
        input_data = ExecuteCommandInput(command="ls -la")
        assert input_data.command == "ls -la"

    def test_valid_command_with_timeout(self):
        """测试带超时参数的有效命令"""
        input_data = ExecuteCommandInput(command="cat file.txt", timeout=60)
        assert input_data.command == "cat file.txt"
        assert input_data.timeout == 60

    def test_command_not_in_whitelist(self):
        """测试不在白名单中的命令"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCommandInput(command="rm -rf file.txt")

        assert "不在白名单中" in str(exc_info.value)

    def test_empty_command(self):
        """测试空命令"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCommandInput(command="")

        assert "不能为空" in str(exc_info.value)

    def test_timeout_below_minimum(self):
        """测试超时时间低于最小值"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCommandInput(command="ls", timeout=0)

        assert "greater than or equal to 1" in str(exc_info.value)

    def test_timeout_above_maximum(self):
        """测试超时时间高于最大值"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCommandInput(command="ls", timeout=301)

        assert "less than or equal to 300" in str(exc_info.value)

    def test_quoted_command(self):
        """测试带引号的命令"""
        input_data = ExecuteCommandInput(command="echo 'Hello World'")
        assert input_data.command == "echo 'Hello World'"

    def test_all_whitelist_commands(self):
        """测试所有白名单命令"""
        whitelist_commands = [
            "ls",
            "cat",
            "echo",
            "grep",
            "head",
            "tail",
            "wc",
        ]

        for cmd in whitelist_commands:
            input_data = ExecuteCommandInput(command=cmd)
            assert input_data.command == cmd


class TestExecuteCommandImpl:
    """测试 execute_command_impl 函数"""

    @patch('tools.execute_command.get_sandbox')
    @patch('tools.execute_command.get_config')
    def test_successful_execution(self, mock_get_config, mock_get_sandbox):
        """测试成功执行命令"""
        # Mock 配置
        mock_config = Mock()
        mock_config.docker.memory_limit = "128m"
        mock_config.docker.cpu_limit = "0.5"
        mock_config.docker.network_disabled = True
        mock_get_config.return_value = mock_config

        # Mock 沙盒
        mock_sandbox = Mock()
        mock_sandbox.execute_command.return_value = {
            'success': True,
            'stdout': 'file1.txt\nfile2.txt',
            'stderr': '',
            'exit_code': 0,
        }
        mock_get_sandbox.return_value = mock_sandbox

        # 执行
        result = execute_command_impl("ls -la", timeout=30)

        # 验证
        assert 'file1.txt' in result
        assert 'file2.txt' in result
        mock_sandbox.execute_command.assert_called_once_with(
            command="ls -la",
            timeout=30,
            memory_limit="128m",
            cpu_limit="0.5",
            network_disabled=True,
        )

    @patch('tools.execute_command.get_sandbox')
    @patch('tools.execute_command.get_config')
    def test_failed_execution(self, mock_get_config, mock_get_sandbox):
        """测试命令执行失败"""
        # Mock 配置
        mock_config = Mock()
        mock_config.docker.memory_limit = "128m"
        mock_config.docker.cpu_limit = "0.5"
        mock_config.docker.network_disabled = True
        mock_get_config.return_value = mock_config

        # Mock 沙盒
        mock_sandbox = Mock()
        mock_sandbox.execute_command.return_value = {
            'success': False,
            'stdout': '',
            'stderr': 'Command not found',
            'exit_code': 127,
        }
        mock_get_sandbox.return_value = mock_sandbox

        # 执行
        result = execute_command_impl("invalid_cmd", timeout=30)

        # 验证
        assert "命令执行失败" in result
        assert "Command not found" in result

    @patch('tools.execute_command.get_sandbox')
    @patch('tools.execute_command.get_config')
    def test_empty_output(self, mock_get_config, mock_get_sandbox):
        """测试空输出"""
        # Mock 配置
        mock_config = Mock()
        mock_config.docker.memory_limit = "128m"
        mock_config.docker.cpu_limit = "0.5"
        mock_config.docker.network_disabled = True
        mock_get_config.return_value = mock_config

        # Mock 沙盒
        mock_sandbox = Mock()
        mock_sandbox.execute_command.return_value = {
            'success': True,
            'stdout': '',
            'stderr': '',
            'exit_code': 0,
        }
        mock_get_sandbox.return_value = mock_sandbox

        # 执行
        result = execute_command_impl("true", timeout=30)

        # 验证
        assert result == "命令执行成功，无输出"


class TestExecuteCommandTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert execute_command_tool.name == "execute_command"
        assert "Docker 隔离" in execute_command_tool.description
        assert execute_command_tool.args_schema == ExecuteCommandInput

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(execute_command_tool, StructuredTool)

    def test_tool_invocation(self):
        """测试工具调用"""
        # Mock 内部实现
        with patch('tools.execute_command.get_sandbox') as mock_get_sandbox, \
             patch('tools.execute_command.get_config') as mock_get_config:

            # Mock 配置
            mock_config = Mock()
            mock_config.docker.memory_limit = "128m"
            mock_config.docker.cpu_limit = "0.5"
            mock_config.docker.network_disabled = True
            mock_config.security.command_whitelist = ["ls", "cat", "echo", "grep", "head", "tail", "wc"]
            mock_get_config.return_value = mock_config

            # Mock 沙盒
            mock_sandbox = Mock()
            mock_sandbox.execute_command.return_value = {
                'success': True,
                'stdout': 'test output',
                'stderr': '',
                'exit_code': 0,
            }
            mock_get_sandbox.return_value = mock_sandbox

            # 通过工具调用
            result = execute_command_tool.invoke({
                "command": "echo test",
                "timeout": 30
            })

            assert "test output" in result


class TestExecuteCommandIntegration:
    """集成测试（需要 Docker）"""

    @pytest.mark.slow
    @pytest.mark.docker
    def test_real_docker_execution(self):
        """真实 Docker 环境执行（慢速测试）"""
        # 注意：这需要在 CI 环境中跳过或标记为 slow
        result = execute_command_impl("echo 'Hello from Docker'", timeout=10)
        assert "Hello from Docker" in result

    @pytest.mark.slow
    @pytest.mark.docker
    def test_real_docker_with_complex_command(self):
        """测试复杂命令"""
        result = execute_command_impl("echo 'line1\nline2\nline3' | wc -l", timeout=10)
        assert "3" in result
