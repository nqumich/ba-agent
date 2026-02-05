"""
记忆读取工具

读取用户记忆文件的内容，支持行号范围、最近文件等过滤
"""

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, model_validator

from langchain_core.tools import StructuredTool


# 记忆目录路径
MEMORY_DIR = Path("memory")


class MemoryGetInput(BaseModel):
    """记忆读取工具的输入参数"""

    file_path: str = Field(
        default="",
        description="记忆文件路径（如 'MEMORY.md' 或 'AGENTS.md'），为空时使用 recent_days"
    )
    line_start: Optional[int] = Field(
        default=None,
        description="起始行号（从1开始，包含），None 表示从头开始"
    )
    line_end: Optional[int] = Field(
        default=None,
        description="结束行号（包含），None 表示到文件末尾"
    )
    recent_days: Optional[int] = Field(
        default=None,
        description="读取最近 N 天的日志文件（仅对 daily logs 有效）"
    )
    max_length: Optional[int] = Field(
        default=5000,
        description="最大返回字符数（防止返回过长内容），None 表示不限制"
    )

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """验证文件路径"""
        v = v.strip()

        # 如果为空且使用 recent_days，允许
        # 实际验证会在函数中进行
        if not v:
            return v

        # 检查路径遍历攻击
        if ".." in v:
            raise ValueError("路径中不能包含 '..'（安全限制）")

        # 构建完整路径
        full_path = MEMORY_DIR / v

        # 检查是否在 memory 目录内
        try:
            full_path = full_path.resolve()
            memory_dir = MEMORY_DIR.resolve()
            if not str(full_path).startswith(str(memory_dir)):
                raise ValueError("只能读取 memory/ 目录下的文件")
        except Exception as e:
            raise ValueError(f"路径解析失败: {e}")

        return v

    @field_validator('line_start')
    @classmethod
    def validate_line_start(cls, v: Optional[int]) -> Optional[int]:
        """验证起始行号"""
        if v is not None and v < 1:
            raise ValueError("起始行号必须 >= 1")
        return v

    @field_validator('line_end')
    @classmethod
    def validate_line_end(cls, v: Optional[int]) -> Optional[int]:
        """验证结束行号"""
        if v is not None and v < 1:
            raise ValueError("结束行号必须 >= 1")
        return v

    @model_validator(mode='after')
    def validate_line_range(self) -> 'MemoryGetInput':
        """验证行号范围"""
        if self.line_start is not None and self.line_end is not None:
            if self.line_start > self.line_end:
                raise ValueError("起始行号不能大于结束行号")
        return self


def memory_get(
    file_path: str = "",
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    recent_days: Optional[int] = None,
    max_length: Optional[int] = 5000
) -> str:
    """
    读取用户记忆文件的内容

    Args:
        file_path: 记忆文件路径（如 'MEMORY.md'），为空时必须提供 recent_days
        line_start: 起始行号（从1开始）
        line_end: 结束行号
        recent_days: 读取最近 N 天的日志
        max_length: 最大返回字符数

    Returns:
        文件内容（Markdown 格式）

    Examples:
        >>> memory_get("MEMORY.md")  # 读取全部内容
        >>> memory_get("MEMORY.md", line_start=1, line_end=10)  # 读取前10行
        >>> memory_get("MEMORY.md", line_start=100, line_end=150)  # 读取100-150行
        >>> memory_get(recent_days=7)  # 读取最近7天的所有日志
    """
    # 处理 recent_days 参数（读取最近的日志文件）
    if recent_days is not None:
        return _get_recent_logs(recent_days, max_length)

    # 如果 file_path 为空，返回提示
    if not file_path:
        return f"❌ 请指定 file_path 或 recent_days 参数\n\n{_list_memory_files()}"

    # 构建完整路径
    full_path = MEMORY_DIR / file_path

    # 检查文件是否存在
    if not full_path.exists():
        # 尝试常用文件的默认路径
        if file_path == "MEMORY.md":
            full_path = MEMORY_DIR / "MEMORY.md"
        elif file_path == "AGENTS.md":
            full_path = MEMORY_DIR / "AGENTS.md"
        elif file_path == "CLAUDE.md":
            full_path = MEMORY_DIR / "CLAUDE.md"
        elif file_path == "USER.md":
            full_path = MEMORY_DIR / "USER.md"
        elif file_path == "SOUL.md":
            full_path = MEMORY_DIR / "SOUL.md"
        else:
            # 尝试 bank/ 目录
            full_path = MEMORY_DIR / "bank" / file_path

    if not full_path.exists():
        return f"❌ 文件不存在: {file_path}\n\n可用的记忆文件:\n{_list_memory_files()}"

    # 读取文件内容
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return f"❌ 读取文件失败: {e}"

    # 处理行号范围
    if line_start is not None or line_end is not None:
        start = (line_start or 1) - 1  # 转换为索引（从0开始）
        end = line_end or len(lines)
        lines = lines[start:end]

    # 合并内容
    content = ''.join(lines)

    # 处理最大长度限制
    if max_length and len(content) > max_length:
        content = content[:max_length]
        content += f"\n\n... (内容已截断，共 {len(content)} 字符)"

    return content


def _get_recent_logs(days: int, max_length: Optional[int]) -> str:
    """获取最近几天的日志文件内容"""
    today = date.today()
    logs = []
    total_chars = 0

    for i in range(days):
        log_date = today - timedelta(days=i)
        log_file = MEMORY_DIR / log_date.strftime("%Y-%m-%d.md")

        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                    # 添加文件头
                    header = f"\n## {log_date.strftime('%Y-%m-%d')}\n\n"
                    full_content = header + content

                    # 检查长度限制
                    if max_length and total_chars + len(full_content) > max_length:
                        remaining = max_length - total_chars
                        if remaining > 0:
                            logs.append(header + content[:remaining] + "\n... (已截断)")
                        break

                    logs.append(full_content)
                    total_chars += len(full_content)

            except Exception as e:
                logs.append(f"\n## {log_date.strftime('%Y-%m-%d')}\n\n❌ 读取失败: {e}")

    if not logs:
        return f"❌ 最近 {days} 天没有找到日志文件\n\n{_list_memory_files()}"

    return ''.join(logs)


def _list_memory_files() -> str:
    """列出可用的记忆文件"""
    files = []

    # 列出 memory/ 目录下的文件
    if MEMORY_DIR.exists():
        for item in MEMORY_DIR.iterdir():
            if item.is_file():
                files.append(f"- {item.name}")

        # 列出 bank/ 目录
        bank_dir = MEMORY_DIR / "bank"
        if bank_dir.exists():
            files.append("\n**bank/**:")
            for item in bank_dir.iterdir():
                if item.is_file():
                    files.append(f"  - bank/{item.name}")
                elif item.is_dir() and item.name != "entities":
                    # 列出子目录
                    for sub_item in item.iterdir():
                        if sub_item.is_file():
                            files.append(f"  - bank/{item.name}/{sub_item.name}")

    if not files:
        return "(无文件)"

    return '\n'.join(files)


# 创建工具
memory_get_tool = StructuredTool.from_function(
    func=memory_get,
    name="memory_get",
    description="""
读取用户记忆文件的内容。支持读取以下类型的记忆：

**常用文件**:
- MEMORY.md - 长期用户知识
- SOUL.md - Agent 身份定义
- CLAUDE.md - 项目架构（用户视角）
- AGENTS.md - Agent 行为指令
- USER.md - 用户档案
- bank/world.md - 客观事实
- bank/experience.md - Agent 经历
- bank/opinions.md - 判断和偏好

**参数**:
- file_path: 文件路径（如 'MEMORY.md'）
- line_start: 起始行号（可选，从1开始）
- line_end: 结束行号（可选）
- recent_days: 读取最近 N 天的日志（可选）
- max_length: 最大返回字符数（默认5000）

**示例**:
- 读取 MEMORY.md 全部: memory_get("MEMORY.md")
- 读取前10行: memory_get("MEMORY.md", line_end=10)
- 读取100-120行: memory_get("MEMORY.md", line_start=100, line_end=120)
- 读取最近7天日志: memory_get(recent_days=7)
""",
    args_schema=MemoryGetInput
)
