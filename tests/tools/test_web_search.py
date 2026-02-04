"""
Web 搜索工具单元测试
"""

import os
import pytest
from unittest.mock import patch, Mock
from pydantic import ValidationError

from tools.web_search import (
    WebSearchInput,
    web_search_impl,
    web_search_tool,
)


class TestWebSearchInput:
    """测试 WebSearchInput 模型"""

    def test_valid_search_input(self):
        """测试有效的搜索输入"""
        input_data = WebSearchInput(query="Python 数据分析")
        assert input_data.query == "Python 数据分析"
        assert input_data.recency == "noLimit"
        assert input_data.max_results == 10

    def test_custom_recency(self):
        """测试自定义时间过滤"""
        input_data = WebSearchInput(
            query="测试",
            recency="oneWeek"
        )
        assert input_data.recency == "oneWeek"

    def test_custom_max_results(self):
        """测试自定义最大结果数"""
        input_data = WebSearchInput(
            query="测试",
            max_results=15
        )
        assert input_data.max_results == 15

    def test_domain_filter(self):
        """测试域名过滤"""
        input_data = WebSearchInput(
            query="测试",
            domain_filter="wikipedia.org"
        )
        assert input_data.domain_filter == "wikipedia.org"

    def test_empty_query(self):
        """测试空查询"""
        with pytest.raises(ValidationError) as exc_info:
            WebSearchInput(query="")
        assert "query" in str(exc_info.value).lower()

    def test_query_too_long(self):
        """测试查询过长"""
        long_query = "a" * 201
        with pytest.raises(ValidationError) as exc_info:
            WebSearchInput(query=long_query)
        assert "query" in str(exc_info.value).lower()

    def test_invalid_recency(self):
        """测试无效的时间过滤"""
        with pytest.raises(ValidationError) as exc_info:
            WebSearchInput(
                query="测试",
                recency="invalid"
            )
        assert "recency" in str(exc_info.value).lower()

    def test_max_results_below_minimum(self):
        """测试最大结果数低于最小值"""
        with pytest.raises(ValidationError) as exc_info:
            WebSearchInput(
                query="测试",
                max_results=0
            )
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_max_results_above_maximum(self):
        """测试最大结果数高于最大值"""
        with pytest.raises(ValidationError) as exc_info:
            WebSearchInput(
                query="测试",
                max_results=21
            )
        assert "less than or equal to 20" in str(exc_info.value)

    def test_invalid_domain_filter(self):
        """测试无效的域名过滤"""
        with pytest.raises(ValidationError) as exc_info:
            WebSearchInput(
                query="测试",
                domain_filter="invalid"
            )
        assert "domain_filter" in str(exc_info.value).lower()

    def test_all_recency_options(self):
        """测试所有时间过滤选项"""
        recency_options = [
            "oneDay",
            "oneWeek",
            "oneMonth",
            "oneYear",
            "noLimit",
        ]

        for recency in recency_options:
            input_data = WebSearchInput(
                query="测试",
                recency=recency
            )
            assert input_data.recency == recency

    def test_recency_defaults_to_no_limit(self):
        """测试时间过滤默认为 noLimit"""
        input_data = WebSearchInput(query="测试", recency=None)
        assert input_data.recency == "noLimit"


class TestWebSearchImpl:
    """测试 web_search_impl 函数"""

    def test_basic_search(self):
        """测试基本搜索"""
        result = web_search_impl(query="Python 数据分析")
        assert "Python 数据分析" in result
        assert "搜索结果" in result

    def test_search_with_custom_max_results(self):
        """测试自定义最大结果数"""
        result = web_search_impl(
            query="测试",
            max_results=5
        )
        # 应该只返回较少的结果
        lines = result.strip().split('\n')
        assert len(lines) <= 5

    def test_search_with_domain_filter(self):
        """测试带域名过滤的搜索"""
        result = web_search_impl(
            query="测试",
            domain_filter="wikipedia.org"
        )
        assert result is not None


class TestWebSearchTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert web_search_tool.name == "web_search"
        assert "Web 搜索" in web_search_tool.description
        assert web_search_tool.args_schema == WebSearchInput

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(web_search_tool, StructuredTool)

    def test_tool_invocation(self):
        """测试工具调用"""
        result = web_search_tool.invoke({
            "query": "测试搜索",
            "recency": "oneWeek",
            "max_results": 5,
        })
        assert "测试搜索" in result


# 集成测试已移至 test_web_search_integration.py

class TestWebSearchParams:
    """测试搜索参数组合"""

    def test_all_parameters(self):
        """测试所有参数"""
        input_data = WebSearchInput(
            query="跨境电商",
            recency="oneMonth",
            max_results=15,
            domain_filter="wikipedia.org"
        )
        assert input_data.query == "跨境电商"
        assert input_data.recency == "oneMonth"
        assert input_data.max_results == 15
        assert input_data.domain_filter == "wikipedia.org"

    def test_minimal_parameters(self):
        """测试最小参数（只有 query）"""
        input_data = WebSearchInput(query="简单查询")
        assert input_data.query == "简单查询"
        assert input_data.recency == "noLimit"  # 默认值
        assert input_data.max_results == 10   # 默认值
        assert input_data.domain_filter is None  # 默认值

    def test_chinese_search_query(self):
        """测试中文搜索查询"""
        input_data = WebSearchInput(query="中国电商平台 GMV 增长")
        assert "中国电商平台 GMV 增长" in input_data.query

    def test_english_search_query(self):
        """测试英文搜索查询"""
        input_data = WebSearchInput(query="machine learning best practices")
        assert "machine learning best practices" in input_data.query
