"""
Web 搜索工具集成测试

测试真实的 MCP 服务器集成
"""

import os
import subprocess
import json
import pytest

from tools.web_search import WebSearchInput, web_search_impl


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


class TestWebSearchIntegration:
    """集成测试（使用真实的 MCP 测试服务器）"""

    @pytest.mark.slow
    def test_real_mcp_search(self, mcp_server):
        """测试真实 MCP 搜索"""
        result = mcp_server.call_tool(
            "mcp__web-search-prime__webSearchPrime",
            {
                "query": "Python 数据分析",
                "max_results": 3
            }
        )

        assert result is not None
        assert "content" in result
        assert len(result["content"]) > 0
        assert result["isError"] == False

        # 验证返回的内容包含搜索结果
        content = result["content"][0]["text"]
        assert "Python 数据分析" in content
        assert "搜索结果" in content

    @pytest.mark.slow
    def test_real_mcp_search_with_recency(self, mcp_server):
        """测试带时间过滤的真实 MCP 搜索"""
        result = mcp_server.call_tool(
            "mcp__web-search-prime__webSearchPrime",
            {
                "query": "AI 新闻",
                "recency": "oneDay",
                "max_results": 5
            }
        )

        assert result is not None
        assert "content" in result
        assert result["isError"] == False

        content = result["content"][0]["text"]
        assert "oneDay" in content

    @pytest.mark.slow
    def test_real_mcp_search_with_domain_filter(self, mcp_server):
        """测试带域名过滤的真实 MCP 搜索"""
        result = mcp_server.call_tool(
            "mcp__web-search-prime__webSearchPrime",
            {
                "query": "Python 教程",
                "domain_filter": "wikipedia.org",
                "max_results": 5
            }
        )

        assert result is not None
        assert result["isError"] == False

    @pytest.mark.slow
    def test_real_mcp_search_max_results(self, mcp_server):
        """测试不同最大结果数"""
        for max_results in [1, 5, 10]:
            result = mcp_server.call_tool(
                "mcp__web-search-prime__webSearchPrime",
                {
                    "query": f"测试搜索 {max_results}",
                    "max_results": max_results
                }
            )

            assert result is not None
            assert result["isError"] == False
            content = result["content"][0]["text"]
            # 检查结果数量（去除 markdown 格式）
            assert f"{max_results}" in content
            assert "搜索结果" in content


# 保留原有的简单测试（用于快速验证）
class TestWebSearchSimple:
    """简单的 MCP 集成测试（快速验证）"""

    @pytest.mark.slow
    def test_mcp_search_basic(self):
        """基础 MCP 搜索测试（快速）"""
        if os.environ.get('MCP_AVAILABLE') != 'true':
            pytest.skip("需要 MCP 环境")

        # 测试工具函数不报错
        result = web_search_impl(
            query="Python",
            max_results=5
        )
        assert result is not None
        assert isinstance(result, str)
