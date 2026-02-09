"""
文件写入工具 (v2.1 - Pipeline Only)

让 Agent 可以写入任意文件

v2.1 变更：
- 使用 ToolExecutionResult 返回
- 支持 OutputLevel (BRIEF/STANDARD/FULL)
- 添加 response_format 参数
"""

import os
import time
import uuid
from pathlib import Path
from typing import Optional, Literal

from pydantic import BaseModel, Field, field_validator

from langchain_core.tools import StructuredTool

# Pipeline v2.1 模型
from backend.models.pipeline import (
    OutputLevel,
    ToolExecutionResult,
    ToolCachePolicy,
)


# 工作目录限制
ALLOWED_DIRS = [
    Path(".").resolve(),  # 项目根目录
    Path("memory").resolve(),  # 记忆目录
    Path("data").resolve(),  # 数据目录
    Path("docs").resolve(),  # 文档目录
]


class FileWriteInput(BaseModel):
    """文件写入工具的输入参数"""

    content: str = Field(
        description="要写入的内容（支持文本和 Markdown 格式）"
    )
    file_path: str = Field(
        description="目标文件相对路径（如 'data/output.md'）"
    )
    mode: Literal["append", "overwrite", "prepend"] = Field(
        default="append",
        description="写入模式：append=追加到末尾, overwrite=覆盖文件, prepend=插入到开头"
    )
    create_dirs: bool = Field(
        default=True,
        description="是否自动创建不存在的目录"
    )
    separator: str = Field(
        default="\n\n---\n\n",
        description="追加/前置模式下的分隔符"
    )
    # 支持 OutputLevel 字符串
    response_format: Optional[str] = Field(
        default="standard",
        description="响应格式: brief, standard, full"
    )

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证内容"""
        if v is None:
            raise ValueError("内容不能为 None")
        return v

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """验证文件路径"""
        v = v.strip()

        # 检查路径遍历攻击
        if ".." in v:
            raise ValueError("路径中不能包含 '..'（安全限制）")

        # 解析目标路径
        target_path = Path(".").resolve() / v

        # 检查是否在允许的目录内
        allowed = False
        for allowed_dir in ALLOWED_DIRS:
            try:
                target_path.relative_to(allowed_dir)
                allowed = True
                break
            except ValueError:
                continue

        if not allowed:
            allowed_dirs_str = ", ".join([str(d) for d in ALLOWED_DIRS])
            raise ValueError(
                f"只能写入以下目录及其子目录: {allowed_dirs_str}"
            )

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


def file_write(
    content: str,
    file_path: str,
    mode: Literal["append", "overwrite", "prepend"] = "append",
    create_dirs: bool = True,
    separator: str = "\n\n---\n\n",
    response_format: str = "standard",
) -> ToolExecutionResult:
    """
    写入文件 (v2.1 - Pipeline)

    Args:
        content: 要写入的内容
        file_path: 目标文件相对路径
        mode: 写入模式
        create_dirs: 是否自动创建目录
        separator: 分隔符（用于 append/prepend）
        response_format: 响应格式

    Returns:
        ToolExecutionResult

    Examples:
        >>> file_write("Hello World", "data/greeting.md")
        >>> file_write("# 新笔记\\n内容", "memory/notes.md", mode="append")
    """
    start_time = time.time()

    # 生成 tool_call_id
    tool_call_id = f"call_file_write_{uuid.uuid4().hex[:12]}"

    # 解析输出级别
    output_level = _parse_output_level(response_format)

    try:
        # 解析目标路径
        target_path = Path(".").resolve() / file_path

        # 确保目录存在
        if create_dirs:
            target_path.parent.mkdir(parents=True, exist_ok=True)

        if mode == "overwrite":
            # 覆盖模式
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            action = "覆盖写入"

        elif mode == "append":
            # 追加模式
            if target_path.exists():
                with open(target_path, 'a', encoding='utf-8') as f:
                    f.write(separator)
                    f.write(content)
            else:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            action = "追加到"

        elif mode == "prepend":
            # 前置模式
            if target_path.exists():
                existing_content = target_path.read_text(encoding='utf-8')
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    f.write(separator)
                    f.write(existing_content)
            else:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            action = "前置到"

        else:
            raw_data = {
                "success": False,
                "error": f"不支持的写入模式: {mode}",
                "file_path": file_path,
            }
            duration_ms = (time.time() - start_time) * 1000
            return ToolExecutionResult.from_raw_data(
                tool_call_id=tool_call_id,
                raw_data=raw_data,
                output_level=output_level,
                tool_name="file_write",
                cache_policy=ToolCachePolicy.NO_CACHE,
            ).with_duration(duration_ms)

        # 统计信息
        char_count = len(content)
        line_count = len(content.split('\n'))

        raw_data = {
            "success": True,
            "action": action,
            "file_path": file_path,
            "full_path": str(target_path),
            "char_count": char_count,
            "line_count": line_count,
            "mode": mode,
            "content_preview": content[:100] + ('...' if len(content) > 100 else ''),
        }

        duration_ms = (time.time() - start_time) * 1000

        # 创建 ToolExecutionResult
        return ToolExecutionResult.from_raw_data(
            tool_call_id=tool_call_id,
            raw_data=raw_data,
            output_level=output_level,
            tool_name="file_write",
            cache_policy=ToolCachePolicy.NO_CACHE,
        ).with_duration(duration_ms)

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        # 创建错误结果
        return ToolExecutionResult.create_error(
            tool_call_id=tool_call_id,
            error_message=str(e),
            error_type=type(e).__name__,
            tool_name="file_write",
        ).with_duration(duration_ms)


# 创建工具
file_write_tool = StructuredTool.from_function(
    func=file_write,
    name="file_write",
    description="""
写入文件到指定路径。

**支持的目录**:
- 项目根目录 (./)
- memory/ (记忆文件)
- data/ (数据文件)
- docs/ (文档文件)

**参数**:
- content: 要写入的内容（必需）
- file_path: 目标文件相对路径（必需，如 'data/output.md'）
- mode: 写入模式（默认 append）
  - append: 追加到文件末尾
  - overwrite: 覆盖整个文件
  - prepend: 插入到文件开头
- create_dirs: 是否自动创建目录（默认 True）
- separator: 追加/前置模式下的分隔符（默认 "\\n\\n---\\n\\n"）

**示例**:
- 写入数据: file_write("结果数据", "data/results.md")
- 追加笔记: file_write("新笔记", "memory/notes.md", mode="append")
- 覆盖配置: file_write("配置内容", "config.yaml", mode="overwrite")
""",
    args_schema=FileWriteInput
)


# 导出
__all__ = ["file_write", "file_write_tool", "FileWriteInput"]
