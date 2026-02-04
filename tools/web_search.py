"""
Web 搜索工具

使用 MCP Web 搜索工具进行网络搜索
"""

import os
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool


class WebSearchInput(BaseModel):
    """Web 搜索工具的输入参数"""

    query: str = Field(
        ...,
        description="搜索查询内容",
        min_length=1,
        max_length=200,
    )
    recency: Optional[str] = Field(
        default="noLimit",
        description="时间过滤: oneDay, oneWeek, oneMonth, oneYear, noLimit"
    )
    max_results: Optional[int] = Field(
        default=10,
        ge=1,
        le=20,
        description="最大返回结果数量 (1-20)"
    )
    domain_filter: Optional[str] = Field(
        default=None,
        description="限制搜索域 (例如: wikipedia.org)"
    )

    @field_validator('recency')
    @classmethod
    def validate_recency(cls, v: Optional[str]) -> Optional[str]:
        """验证时间过滤参数"""
        if v is None:
            return "noLimit"
        allowed_values = ["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"]
        if v not in allowed_values:
            raise ValueError(f"recency 必须是以下之一: {', '.join(allowed_values)}")
        return v

    @field_validator('domain_filter')
    @classmethod
    def validate_domain_filter(cls, v: Optional[str]) -> Optional[str]:
        """验证域名过滤"""
        if v is None:
            return None
        # 简单的域名格式验证
        if not v or '.' not in v:
            raise ValueError("domain_filter 必须是有效的域名 (例如: wikipedia.org)")
        return v


def web_search_impl(
    query: str,
    recency: str = "noLimit",
    max_results: int = 10,
    domain_filter: Optional[str] = None,
) -> str:
    """
    Web 搜索的实现函数

    注意：此函数是 MCP 工具的包装器。
    实际搜索通过 MCP 服务执行，这里提供模拟实现用于测试。

    Args:
        query: 搜索查询
        recency: 时间过滤
        max_results: 最大结果数
        domain_filter: 域名过滤

    Returns:
        搜索结果字符串
    """
    # 检查是否在真实的 MCP 环境中（通过检查是否在 Claude Code 环境中运行）
    # 注意：仅当实际在 Claude Code 中调用 MCP 工具时才使用此分支
    # 单元测试和集成测试应使用 mock 实现
    is_real_mcp = os.environ.get('MCP_REAL_MODE', 'false').lower() == 'true'

    if is_real_mcp:
        # 真实 MCP 模式：返回提示，让 Claude Code 调用 MCP 工具
        return f"[MCP MODE] 请使用 mcp__web-search-prime__webSearchPrime 工具执行搜索: query={query}, recency={recency}, max_results={max_results}"

    # 模拟搜索结果（默认，用于测试）
    mock_results = [
        f"1. 标题: 关于 '{query}' 的搜索结果 1",
        f"   URL: https://example.com/result1",
        f"   摘要: 这是 '{query}' 的相关内容...",
    ]

    if max_results > 1:
        mock_results.append(
            f"2. 标题: 关于 '{query}' 的搜索结果 2"
        )

    return "\n".join(mock_results)


# 创建 LangChain 工具
web_search_tool = StructuredTool.from_function(
    func=web_search_impl,
    name="web_search",
    description="""
执行 Web 搜索，获取网页信息。

使用场景：
- 搜索最新的行业新闻和动态
- 查找技术文档和解决方案
- 获取竞争对手信息
- 搜索市场数据和报告

支持的时间过滤：
- oneDay: 最近一天
- oneWeek: 最近一周
- oneMonth: 最近一个月
- oneYear: 最近一年
- noLimit: 不限制时间（默认）

使用示例：
- web_search(query="Python 数据分析最佳实践")
- web_search(query="跨境电商 2024 趋势", recency="oneMonth")
- web_search(query="GMV 同比增长", domain_filter="wikipedia.org")

注意：完整功能需要 MCP (Model Context Protocol) 服务支持。
    """.strip(),
    args_schema=WebSearchInput,
)


# 导出
__all__ = [
    "WebSearchInput",
    "web_search_impl",
    "web_search_tool",
]

