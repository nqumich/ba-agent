"""
Web Reader 工具 (v2.1 - Pipeline Only)

使用 MCP Web Reader 工具读取网页内容

v2.1 变更：
- 使用 ToolExecutionResult 返回
- 支持 OutputLevel (BRIEF/STANDARD/FULL)
- 添加 response_format 参数
"""

import os
import time
import uuid
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool

# Pipeline v2.1 模型
from backend.models.pipeline import (
    OutputLevel,
    ToolExecutionResult,
    ToolCachePolicy,
)


class WebReaderInput(BaseModel):
    """Web Reader 工具的输入参数"""

    url: str = Field(
        ...,
        description="要读取的网页 URL"
    )
    timeout: Optional[int] = Field(
        default=20,
        ge=5,
        le=120,
        description="请求超时时间（秒），范围 5-120"
    )
    return_format: Optional[str] = Field(
        default="markdown",
        description="返回格式: markdown 或 text"
    )
    retain_images: Optional[bool] = Field(
        default=False,
        description="是否保留图片信息"
    )
    # 支持 OutputLevel 字符串
    response_format: Optional[str] = Field(
        default="standard",
        description="响应格式: brief, standard, full"
    )

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """验证 URL 格式"""
        v = v.strip()
        if not v:
            raise ValueError("URL 不能为空")

        # 简单的 URL 格式验证
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("URL 必须以 http:// 或 https:// 开头")

        # 验证域名部分
        try:
            from urllib.parse import urlparse
            parsed = urlparse(v)
            if not parsed.netloc:
                raise ValueError("URL 格式无效，缺少域名")
        except Exception:
            raise ValueError("URL 格式无效")

        return v

    @field_validator('return_format')
    @classmethod
    def validate_return_format(cls, v: Optional[str]) -> Optional[str]:
        """验证返回格式"""
        if v is None:
            return "markdown"
        allowed = ["markdown", "text"]
        if v not in allowed:
            raise ValueError(f"return_format 必须是以下之一: {', '.join(allowed)}")
        return v


def _parse_output_level(format_str: str) -> OutputLevel:
    """
    解析输出格式字符串为 OutputLevel

    支持的格式：
    - brief/concise → OutputLevel.BRIEF
    - standard → OutputLevel.STANDARD
    - full/detailed → OutputLevel.FULL
    """
    format_lower = format_str.lower()

    if format_lower in ("brief", "concise"):
        return OutputLevel.BRIEF
    elif format_lower in ("full", "detailed"):
        return OutputLevel.FULL
    else:
        return OutputLevel.STANDARD


def web_reader_impl(
    url: str,
    timeout: int = 20,
    return_format: str = "markdown",
    retain_images: bool = False,
    response_format: str = "standard",
) -> ToolExecutionResult:
    """
    Web Reader 的实现函数 (v2.1 - Pipeline)

    注意：此函数是 MCP 工具的包装器。
    实际网页读取通过 MCP 服务执行，这里提供模拟实现用于测试。

    Args:
        url: 网页 URL
        timeout: 超时时间
        return_format: 返回格式 (markdown 或 text)
        retain_images: 是否保留图片
        response_format: 响应格式 (OutputLevel)

    Returns:
        ToolExecutionResult
    """
    start_time = time.time()

    # 生成 tool_call_id
    tool_call_id = f"call_web_reader_{uuid.uuid4().hex[:12]}"

    # 解析输出级别
    output_level = _parse_output_level(response_format)

    try:
        # 检查是否在真实的 MCP 环境中
        is_real_mcp = os.environ.get('MCP_REAL_MODE', 'false').lower() == 'true'

        if is_real_mcp:
            # 真实 MCP 模式：返回提示
            raw_data = {
                "message": "[MCP MODE] 请使用 mcp__web_reader__webReader 工具读取网页",
                "url": url,
                "timeout": timeout,
                "return_format": return_format,
            }
        else:
            # 模拟网页内容（默认，用于测试）
            raw_data = {
                "url": url,
                "timeout": timeout,
                "return_format": return_format,
                "retain_images": retain_images,
                "content": f"""# 网页内容

来源: {url}

## 模拟网页内容

这是从 {url} 读取的模拟内容。
在实际环境中，此工具会通过 MCP (Model Context Protocol) 服务
读取真实的网页内容。

## 支持的功能

- 读取网页并转换为 Markdown 格式
- 保留网页结构和链接
- 提取主要内容
- 支持多种返回格式（markdown/text）

---
*注意：完整功能需要 MCP 服务支持。*
"""
            }

        duration_ms = (time.time() - start_time) * 1000

        # 创建 ToolExecutionResult
        return ToolExecutionResult.from_raw_data(
            tool_call_id=tool_call_id,
            raw_data=raw_data,
            output_level=output_level,
            tool_name="web_reader",
            cache_policy=ToolCachePolicy.TTL_SHORT,  # 网页内容可以短时间缓存
        ).with_duration(duration_ms)

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        # 创建错误结果
        return ToolExecutionResult.create_error(
            tool_call_id=tool_call_id,
            error_message=str(e),
            error_type=type(e).__name__,
            tool_name="web_reader",
        ).with_duration(duration_ms)


# 创建 LangChain 工具
web_reader_tool = StructuredTool.from_function(
    func=web_reader_impl,
    name="web_reader",
    description="""
读取网页内容，提取文本信息。

使用场景：
- 读取技术文档和博客文章
- 获取新闻和资讯内容
- 提取网页中的有用信息
- 分析竞争对手网站

支持的功能：
- 自动将网页转换为 Markdown 格式
- 保留链接和标题结构
- 提取主要内容
- 移除广告和无关元素

参数：
- url: 网页 URL（必须以 http:// 或 https:// 开头）
- timeout: 请求超时时间（秒），范围 5-120
- return_format: 返回格式（markdown 或 text）
- retain_images: 是否保留图片信息

使用示例：
- web_reader(url="https://example.com/article")
- web_reader(url="https://docs.python.org/", return_format="markdown")
- web_reader(url="https://news.example.com/news/123", timeout=30)

注意：
- 此工具通过 MCP (Model Context Protocol) 服务读取网页
- 需要 MCP 服务支持才能正常工作
- 某些网站可能阻止访问或加载缓慢
    """.strip(),
    args_schema=WebReaderInput,
)


# 导出
__all__ = [
    "WebReaderInput",
    "web_reader_impl",
    "web_reader_tool",
]
