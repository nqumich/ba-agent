"""
Docker 沙盒执行器单元测试

US-005: Docker 隔离环境配置
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# 跳过所有测试如果 Docker 不可用
docker_sdk = pytest.importorskip("docker", reason="Docker Python SDK not installed")

from backend.docker.sandbox import (
    DockerSandbox,
    get_sandbox,
    execute_python_safely,
)


# 检查 Docker daemon 是否可用
DOCKER_AVAILABLE = os.environ.get("DOCKER_AVAILABLE", "false").lower() == "true"

# 尝试连接 Docker daemon
try:
    from docker import from_env
    client = from_env()
    client.ping()
    DOCKER_AVAILABLE = True
    client.close()
except Exception:
    DOCKER_AVAILABLE = False


@pytest.mark.skipif(
    not DOCKER_AVAILABLE,
    reason="Docker daemon not available"
)
class TestDockerSandbox:
    """测试 DockerSandbox 类（需要 Docker 运行）"""

    def test_init_sandbox(self):
        """测试初始化沙盒"""
        sandbox = DockerSandbox()
        assert sandbox.client is not None
        assert sandbox.config is not None
        sandbox.close()

    def test_execute_python_simple(self):
        """测试执行简单 Python 代码"""
        sandbox = DockerSandbox()

        code = """
print("Hello, World!")
result = 2 + 2
print(f"2 + 2 = {result}")
"""

        result = sandbox.execute_python(code, timeout=10)

        assert result is not None
        assert 'success' in result
        assert 'stdout' in result
        assert 'exit_code' in result

        sandbox.close()

    def test_execute_python_with_error(self):
        """测试执行有错误的 Python 代码"""
        sandbox = DockerSandbox()

        code = """
# 这段代码会抛出异常
raise ValueError("Test error")
"""

        result = sandbox.execute_python(code, timeout=10)

        assert result is not None
        assert result['exit_code'] != 0

        sandbox.close()

    def test_execute_command_simple(self):
        """测试执行简单命令"""
        sandbox = DockerSandbox()

        result = sandbox.execute_command("echo 'Hello from Docker'", timeout=10)

        assert result is not None
        assert 'success' in result
        assert 'Hello from Docker' in result['stdout']

        sandbox.close()

    def test_execute_python_timeout(self):
        """测试执行超时"""
        sandbox = DockerSandbox()

        code = """
import time
time.sleep(100)  # 超过超时时间
"""

        result = sandbox.execute_python(code, timeout=2)

        assert result is not None
        # 应该超时或被终止
        assert not result.get('success', True)

        sandbox.close()

    def test_resource_limits(self):
        """测试资源限制"""
        sandbox = DockerSandbox()

        code = """
# 尝试分配大量内存
large_list = [0] * 1000000  # 1 million integers
print(f"Created list with {len(large_list)} elements")
"""

        result = sandbox.execute_python(
            code,
            timeout=10,
            memory_limit="64m",  # 限制内存
        )

        assert result is not None

        sandbox.close()


class TestSandboxSingleton:
    """测试沙盒单例"""

    def test_get_sandbox_returns_instance(self):
        """测试 get_sandbox 返回实例"""
        # 使用 mock 避免 Docker 连接
        with patch('backend.docker.sandbox.docker.from_env') as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            sandbox = get_sandbox()
            assert isinstance(sandbox, DockerSandbox)

    def test_get_sandbox_singleton(self):
        """测试 get_sandbox 返回单例"""
        # 使用 mock
        with patch('backend.docker.sandbox.docker.from_env') as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            from backend.docker import sandbox as sandbox_module
            sandbox_module._sandbox = None  # 重置单例

            sandbox1 = get_sandbox()
            sandbox2 = get_sandbox()
            # 应该是同一个实例
            assert sandbox1 is sandbox2


class TestExecutePythonSafely:
    """测试 execute_python_safely 便捷函数"""

    def test_execute_python_safely_simple(self):
        """测试执行简单 Python 代码"""
        # Mock sandbox
        mock_result = {
            'success': True,
            'stdout': '42',
            'stderr': '',
            'exit_code': 0,
        }

        mock_sandbox = MagicMock()
        mock_sandbox.execute_python.return_value = mock_result

        with patch('backend.docker.sandbox.get_sandbox', return_value=mock_sandbox):
            result = execute_python_safely("print(42)")

            assert result['success'] is True
            assert '42' in result['stdout']

    def test_execute_python_safely_with_config(self):
        """测试使用配置执行"""
        mock_sandbox = MagicMock()
        mock_sandbox.execute_python.return_value = {
            'success': True,
            'stdout': 'done',
            'stderr': '',
            'exit_code': 0,
        }

        with patch('backend.docker.sandbox.get_sandbox', return_value=mock_sandbox):
            # 调用便捷函数
            result = execute_python_safely("print('done')", timeout=60)

            # 验证使用了配置中的值
            mock_sandbox.execute_python.assert_called_once()
            call_args = mock_sandbox.execute_python.call_args
            assert call_args[1]['timeout'] == 60


class TestDockerSandboxUnit:
    """使用 mock 测试 Docker 沙盒"""

    def test_init_creates_docker_client(self):
        """测试初始化创建 Docker 客户端"""
        with patch('backend.docker.sandbox.docker.from_env') as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            sandbox = DockerSandbox()

            mock_docker.assert_called_once()
            assert sandbox.client == mock_client

    def test_execute_python_creates_container(self):
        """测试执行 Python 创建容器"""
        mock_container = MagicMock()
        mock_container.wait.return_value = {'StatusCode': 0}
        mock_container.logs.return_value = b'output'

        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container

        with patch('backend.docker.sandbox.docker.from_env', return_value=mock_client):
            sandbox = DockerSandbox()
            result = sandbox.execute_python('print("test")')

            # 验证容器被创建和启动
            mock_client.containers.create.assert_called_once()
            mock_container.start.assert_called_once()
            mock_container.wait.assert_called_once()
            call_args = mock_client.containers.create.call_args
            assert 'python' in call_args[1]['command']

    def test_execute_command_creates_container(self):
        """测试执行命令创建容器"""
        mock_container = MagicMock()
        mock_container.wait.return_value = {'StatusCode': 0}
        mock_container.logs.return_value = b'command output'

        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container

        with patch('backend.docker.sandbox.docker.from_env', return_value=mock_client):
            sandbox = DockerSandbox()
            result = sandbox.execute_command('echo test')

            # 验证容器被创建
            mock_client.containers.run.assert_called_once()
            call_args = mock_client.containers.run.call_args
            assert call_args[1]['command'] == 'echo test'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
