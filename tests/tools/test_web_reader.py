"""
Web Reader 工具单元测试
"""

import os
import pytest
from pydantic import ValidationError

from tools.web_reader import (
    WebReaderInput,
    web_reader_impl,
    web_reader_tool,
)


class TestWebReaderInput:
    """测试 WebReaderInput 模型"""

    def test_valid_url(self):
        """测试有效的 URL"""
        input_data = WebReaderInput(url="https://example.com")
        assert input_data.url == "https://example.com"
        assert input_data.timeout == 20
        assert input_data.return_format == "markdown"
        assert input_data.retain_images is False

    def test_http_url(self):
        """测试 http:// URL"""
        input_data = WebReaderInput(url="http://example.com")
        assert input_data.url == "http://example.com"

    def test_custom_timeout(self):
        """测试自定义超时"""
        input_data = WebReaderInput(
            url="https://example.com",
            timeout=60
        )
        assert input_data.timeout == 60

    def test_return_format_text(self):
        """测试 text 返回格式"""
        input_data = WebReaderInput(
            url="https://example.com",
            return_format="text"
        )
        assert input_data.return_format == "text"

    def test_retain_images_true(self):
        """测试保留图片"""
        input_data = WebReaderInput(
            url="https://example.com",
            retain_images=True
        )
        assert input_data.retain_images is True

    def test_all_parameters(self):
        """测试所有参数"""
        input_data = WebReaderInput(
            url="https://docs.python.org/",
            timeout=45,
            return_format="markdown",
            retain_images=True
        )
        assert input_data.url == "https://docs.python.org/"
        assert input_data.timeout == 45
        assert input_data.return_format == "markdown"
        assert input_data.retain_images is True

    def test_empty_url(self):
        """测试空 URL"""
        with pytest.raises(ValidationError) as exc_info:
            WebReaderInput(url="   ")
        assert "URL" in str(exc_info.value).lower() or "url" in str(exc_info.value).lower()

    def test_url_without_protocol(self):
        """测试没有协议的 URL"""
        with pytest.raises(ValidationError) as exc_info:
            WebReaderInput(url="example.com")
        assert "http" in str(exc_info.value).lower() or "url" in str(exc_info.value).lower()

    def test_url_invalid_format(self):
        """测试无效的 URL 格式"""
        with pytest.raises(ValidationError) as exc_info:
            WebReaderInput(url="not-a-url")
        assert "url" in str(exc_info.value).lower() or "域名" in str(exc_info.value).lower()

    def test_timeout_below_minimum(self):
        """测试超时时间低于最小值"""
        with pytest.raises(ValidationError) as exc_info:
            WebReaderInput(
                url="https://example.com",
                timeout=4
            )
        assert "greater than or equal to 5" in str(exc_info.value)

    def test_timeout_above_maximum(self):
        """测试超时时间高于最大值"""
        with pytest.raises(ValidationError) as exc_info:
            WebReaderInput(
                url="https://example.com",
                timeout=121
            )
        assert "less than or equal to 120" in str(exc_info.value)

    def test_invalid_return_format(self):
        """测试无效的返回格式"""
        with pytest.raises(ValidationError) as exc_info:
            WebReaderInput(
                url="https://example.com",
                return_format="html"
            )
        assert "return_format" in str(exc_info.value).lower()

    def test_return_format_defaults_to_markdown(self):
        """测试返回格式默认为 markdown"""
        input_data = WebReaderInput(
            url="https://example.com",
            return_format=None
        )
        assert input_data.return_format == "markdown"

    def test_https_urls(self):
        """测试各种 HTTPS URL"""
        urls = [
            "https://example.com",
            "https://www.example.com",
            "https://docs.python.org/3/library/",
            "https://github.com/user/repo",
        ]

        for url in urls:
            input_data = WebReaderInput(url=url)
            assert input_data.url == url


class TestWebReaderImpl:
    """测试 web_reader_impl 函数"""

    def test_basic_read(self):
        """测试基本读取"""
        result = web_reader_impl(url="https://example.com")
        assert "example.com" in result
        assert "模拟网页内容" in result

    def test_with_custom_timeout(self):
        """测试自定义超时"""
        result = web_reader_impl(
            url="https://example.com",
            timeout=60
        )
        assert result is not None

    def test_with_text_format(self):
        """测试 text 返回格式"""
        result = web_reader_impl(
            url="https://example.com",
            return_format="text"
        )
        assert result is not None

    def test_with_retain_images(self):
        """测试保留图片"""
        result = web_reader_impl(
            url="https://example.com",
            retain_images=True
        )
        assert result is not None

    def test_content_contains_url(self):
        """测试返回内容包含 URL"""
        result = web_reader_impl(url="https://docs.python.org/")
        assert "docs.python.org" in result


class TestWebReaderTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert web_reader_tool.name == "web_reader"
        assert "Web Reader" in web_reader_tool.description or "web_reader" in web_reader_tool.description
        assert "web_reader_tool" in str(web_reader_tool.args_schema) or "WebReaderInput" in str(web_reader_tool.args_schema)

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(web_reader_tool, StructuredTool)

    def test_tool_invocation(self):
        """测试工具调用"""
        result = web_reader_tool.invoke({
            "url": "https://example.com",
            "timeout": 30,
            "return_format": "markdown",
            "retain_images": False,
        })
        assert result is not None


# 集成测试已移至 test_web_reader_integration.py

class TestWebReaderParams:
    """测试参数组合"""

    def test_minimal_parameters(self):
        """测试最小参数（只有 url）"""
        input_data = WebReaderInput(url="https://example.com")
        assert input_data.url == "https://example.com"
        assert input_data.timeout == 20  # 默认值
        assert input_data.return_format == "markdown"  # 默认值
        assert input_data.retain_images is False  # 默认值

    def test_chinese_url(self):
        """测试中文网站 URL"""
        input_data = WebReaderInput(url="https://baidu.com")
        assert input_data.url == "https://baidu.com"

    def test_long_url(self):
        """测试长 URL"""
        long_url = "https://example.com/path/to/article?param1=value1&param2=value2#section"
        input_data = WebReaderInput(url=long_url)
        assert input_data.url == long_url

    def test_timeout_boundary_values(self):
        """测试超时边界值"""
        # 最小值
        input_min = WebReaderInput(
            url="https://example.com",
            timeout=5
        )
        assert input_min.timeout == 5

        # 最大值
        input_max = WebReaderInput(
            url="https://example.com",
            timeout=120
        )
        assert input_max.timeout == 120

    def test_all_return_formats(self):
        """测试所有返回格式"""
        formats = ["markdown", "text"]

        for fmt in formats:
            input_data = WebReaderInput(
                url="https://example.com",
                return_format=fmt
            )
            assert input_data.return_format == fmt
