"""
Web Reader 工具集成测试 (v2.1 - Pipeline Only)

测试真实的 MCP 服务器集成
"""

import os
import subprocess
import json
import pytest

from tools.web_reader import WebReaderInput, web_reader_impl

# Pipeline v2.1 模型
from backend.models.pipeline import ToolExecutionResult, OutputLevel


class MCPServerManager:
    """MCP 测试服务器管理器"""

    def __init__(self):
        self.server_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "mcp_server",
            "server.py"
        )
        self.process = None

    def start(self):
        """启动 MCP 测试服务器"""
        self.process = subprocess.Popen(
            ["python", self.server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # 等待服务器启动
        import time
        time.sleep(0.5)

    def stop(self):
        """停止 MCP 测试服务器"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用 MCP 工具"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()

        # 读取响应
        response_line = self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("No response from MCP server")

        response = json.loads(response_line.strip())

        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")

        return response.get("result", {})

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


@pytest.fixture(scope="module")
def mcp_server():
    """MCP 服务器 fixture"""
    if os.environ.get('MCP_AVAILABLE') != 'true':
        pytest.skip("需要 MCP 环境 (设置 MCP_AVAILABLE=true)")

    server = MCPServerManager()
    server.start()
    yield server
    server.stop()


class TestWebReaderIntegration:
    """集成测试（使用真实的 MCP 测试服务器）"""

    @pytest.mark.slow
    def test_real_mcp_read(self, mcp_server):
        """测试真实 MCP 读取"""
        result = mcp_server.call_tool(
            "mcp__web_reader__webReader",
            {
                "url": "https://example.com/article",
                "timeout": 20
            }
        )

        assert result is not None
        assert "content" in result
        assert len(result["content"]) > 0
        assert result["isError"] == False

        # 验证返回的内容包含网页信息
        content = result["content"][0]["text"]
        assert "https://example.com/article" in content
        assert "网页内容" in content

    @pytest.mark.slow
    def test_real_mcp_read_with_timeout(self, mcp_server):
        """测试带超时的真实 MCP 读取"""
        result = mcp_server.call_tool(
            "mcp__web_reader__webReader",
            {
                "url": "https://example.com/article",
                "timeout": 60
            }
        )

        assert result is not None
        assert "content" in result
        assert result["isError"] == False

        content = result["content"][0]["text"]
        assert "60" in content or "超时时间" in content

    @pytest.mark.slow
    def test_real_mcp_read_with_format(self, mcp_server):
        """测试不同返回格式"""
        for return_format in ["markdown", "text"]:
            result = mcp_server.call_tool(
                "mcp__web_reader__webReader",
                {
                    "url": f"https://example.com/page-{return_format}",
                    "return_format": return_format
                }
            )

            assert result is not None
            assert result["isError"] == False
            content = result["content"][0]["text"]
            assert return_format in content

    @pytest.mark.slow
    def test_real_mcp_read_retain_images(self, mcp_server):
        """测试保留图片选项"""
        result = mcp_server.call_tool(
            "mcp__web_reader__webReader",
            {
                "url": "https://example.com/images",
                "retain_images": True
            }
        )

        assert result is not None
        assert result["isError"] == False


# 保留原有的简单测试（用于快速验证）
class TestWebReaderSimple:
    """简单的 MCP 集成测试（快速验证）"""

    @pytest.mark.slow
    def test_mcp_read_basic(self):
        """基础 MCP 读取测试（快速）"""
        if os.environ.get('MCP_AVAILABLE') != 'true':
            pytest.skip("需要 MCP 环境")

        # 测试工具函数不报错
        result = web_reader_impl(
            url="https://example.com",
            timeout=20
        )
        assert result is not None
        # v2.1: result 是 ToolExecutionResult
        assert isinstance(result, ToolExecutionResult)
        assert result.success
