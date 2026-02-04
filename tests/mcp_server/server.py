#!/usr/bin/env python3
"""
Test MCP Server for BA-Agent Integration Testing

This server implements the Model Context Protocol (MCP) to provide
web-search-prime and web-reader tools for integration testing.

Usage:
    python server.py

The server communicates via stdio using JSON-RPC protocol.
"""

import json
import sys
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


class MCPServer:
    """Test MCP Server implementation"""

    def __init__(self):
        self.tools = self._register_tools()

    def _register_tools(self) -> Dict[str, Dict[str, Any]]:
        """Register available MCP tools"""
        return {
            "mcp__web-search-prime__webSearchPrime": {
                "name": "mcp__web-search-prime__webSearchPrime",
                "description": "执行 Web 搜索，获取网页信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询内容",
                            "minLength": 1,
                            "maxLength": 200
                        },
                        "recency": {
                            "type": "string",
                            "description": "时间过滤: oneDay, oneWeek, oneMonth, oneYear, noLimit",
                            "enum": ["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"],
                            "default": "noLimit"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最大返回结果数量 (1-20)",
                            "minimum": 1,
                            "maximum": 20,
                            "default": 10
                        },
                        "domain_filter": {
                            "type": "string",
                            "description": "限制搜索域 (例如: wikipedia.org)"
                        }
                    },
                    "required": ["query"]
                }
            },
            "mcp__web_reader__webReader": {
                "name": "mcp__web_reader__webReader",
                "description": "读取网页内容，提取文本信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "要读取的网页 URL"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "请求超时时间（秒），范围 5-120",
                            "minimum": 5,
                            "maximum": 120,
                            "default": 20
                        },
                        "return_format": {
                            "type": "string",
                            "description": "返回格式: markdown 或 text",
                            "enum": ["markdown", "text"],
                            "default": "markdown"
                        },
                        "retain_images": {
                            "type": "boolean",
                            "description": "是否保留图片信息",
                            "default": False
                        }
                    },
                    "required": ["url"]
                }
            }
        }

    def handle_list_tools(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Handle tools/list request"""
        return {
            "tools": [
                {
                    "name": name,
                    "description": tool["description"],
                    "inputSchema": tool["inputSchema"]
                }
                for name, tool in self.tools.items()
            ]
        }

    def handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request"""
        name = params.get("name")
        arguments = params.get("arguments", {})

        if name == "mcp__web-search-prime__webSearchPrime":
            return self._web_search(arguments)
        elif name == "mcp__web_reader__webReader":
            return self._web_reader(arguments)
        else:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True
            }

    def _web_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle web search tool call"""
        query = args.get("query", "")
        recency = args.get("recency", "noLimit")
        max_results = args.get("max_results", 10)

        # Generate mock search results
        results = []
        for i in range(min(max_results, 5)):
            results.append({
                "title": f"关于 '{query}' 的搜索结果 {i+1}",
                "url": f"https://example.com/search-result-{i+1}",
                "snippet": f"这是关于 '{query}' 的搜索结果摘要...搜索结果内容...",
                "publishedDate": datetime.now().strftime("%Y-%m-%d")
            })

        content = f"""# Web 搜索结果

**查询**: {query}
**时间过滤**: {recency}
**结果数量**: {len(results)}

## 搜索结果

"""
        for i, result in enumerate(results, 1):
            content += f"{i}. **{result['title']}**\n"
            content += f"   URL: {result['url']}\n"
            content += f"   摘要: {result['snippet']}\n"
            content += f"   发布日期: {result['publishedDate']}\n\n"

        return {
            "content": [{"type": "text", "text": content}],
            "isError": False
        }

    def _web_reader(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle web reader tool call"""
        url = args.get("url", "")
        return_format = args.get("return_format", "markdown")

        # Generate mock webpage content
        content = f"""# 网页内容

**来源**: {url}
**读取时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**格式**: {return_format}

## 网页标题

这是一个从 {url} 读取的模拟网页内容。在实际的 MCP 环境中，
这里会返回真实的网页内容。

## 主要内容

### 第一部分
这是网页的第一部分内容，包含了关于该主题的重要信息。

### 第二部分
这是网页的第二部分内容，提供了更多详细信息。

### 链接
- [相关链接 1](https://example.com/link1)
- [相关链接 2](https://example.com/link2)

## 总结

这个网页内容是由测试 MCP 服务器生成的模拟数据。
在实际使用中，会通过 Z.ai 的 MCP 服务读取真实的网页内容。

---

*测试 MCP 服务器 - BA-Agent 集成测试*
"""

        return {
            "content": [{"type": "text", "text": content}],
            "isError": False
        }

    def run(self):
        """Run the MCP server (stdio communication)"""
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                self._handle_request(request)
            except json.JSONDecodeError:
                # Ignore non-JSON lines
                continue
            except Exception as e:
                self._send_error(str(e))

    def _handle_request(self, request: Dict[str, Any]):
        """Handle incoming MCP request"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        response = {
            "jsonrpc": "2.0",
            "id": request_id
        }

        try:
            if method == "tools/list":
                response["result"] = self.handle_list_tools(params)
            elif method == "tools/call":
                response["result"] = self.handle_call_tool(params)
            elif method == "initialize":
                response["result"] = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "ba-agent-test-mcp-server",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            else:
                response["error"] = {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
        except Exception as e:
            response["error"] = {
                "code": -32603,
                "message": str(e)
            }

        self._send_response(response)

    def _send_response(self, response: Dict[str, Any]):
        """Send JSON response to stdout"""
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

    def _send_error(self, message: str):
        """Send error response"""
        self._send_response({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": message
            }
        })


def main():
    """Main entry point"""
    server = MCPServer()
    server.run()


if __name__ == "__main__":
    main()
