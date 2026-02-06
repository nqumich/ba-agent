"""
命令行执行工具 (v2.1 - Pipeline Only)

使用 Docker 隔离环境安全执行命令行命令
支持命令白名单验证

v2.1 变更：
- 使用 ToolExecutionResult 返回
- 支持 OutputLevel (BRIEF/STANDARD/FULL)
- 添加 response_format 参数
"""

import shlex
import time
import uuid
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool

from config import get_config
from backend.docker.sandbox import get_sandbox

# Pipeline v2.1 模型
from backend.models.pipeline import (
    OutputLevel,
    ToolExecutionResult,
    ToolCachePolicy,
)


class ExecuteCommandInput(BaseModel):
    """命令行执行工具的输入参数"""

    command: str = Field(
        ...,
        description="要执行的命令行命令（仅支持白名单中的命令）"
    )
    timeout: Optional[int] = Field(
        default=30,
        ge=1,
        le=300,
        description="执行超时时间（秒），范围 1-300"
    )
    # 支持 OutputLevel 字符串
    response_format: Optional[str] = Field(
        default="standard",
        description="响应格式: brief, standard, full"
    )

    @field_validator('command')
    @classmethod
    def validate_command(cls, v: str) -> str:
        """验证命令是否在白名单中"""
        config = get_config()
        whitelist = config.security.command_whitelist

        # 解析命令名称（第一个词）
        try:
            parts = shlex.split(v.strip())
            if not parts:
                raise ValueError("命令不能为空")
            cmd_name = parts[0]
        except ValueError as e:
            raise ValueError(f"命令解析失败: {e}")

        # 检查白名单
        if cmd_name not in whitelist:
            allowed = ", ".join(whitelist)
            raise ValueError(
                f"命令 '{cmd_name}' 不在白名单中。"
                f"允许的命令: {allowed}"
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


def execute_command_impl(
    command: str,
    timeout: int = 30,
    response_format: str = "standard",
) -> ToolExecutionResult:
    """
    执行命令的实现函数 (v2.1 - Pipeline)

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒）
        response_format: 响应格式

    Returns:
        ToolExecutionResult
    """
    start_time = time.time()

    # 生成 tool_call_id
    tool_call_id = f"call_execute_command_{uuid.uuid4().hex[:12]}"

    # 解析输出级别
    output_level = _parse_output_level(response_format)

    try:
        sandbox = get_sandbox()
        config = get_config()

        # 执行命令
        result = sandbox.execute_command(
            command=command,
            timeout=timeout,
            memory_limit=config.docker.memory_limit,
            cpu_limit=config.docker.cpu_limit,
            network_disabled=config.docker.network_disabled,
        )

        duration_ms = (time.time() - start_time) * 1000

        # 格式化原始数据
        if result['success']:
            output = result['stdout']
            if not output:
                raw_data = {
                    "success": True,
                    "message": "命令执行成功，无输出",
                    "command": command,
                    "exit_code": result.get('exit_code', 0),
                }
            else:
                raw_data = {
                    "success": True,
                    "output": output,
                    "command": command,
                    "exit_code": result.get('exit_code', 0),
                }
        else:
            raw_data = {
                "success": False,
                "error": result['stderr'],
                "command": command,
                "exit_code": result.get('exit_code', -1),
            }

        # 创建 ToolExecutionResult
        return ToolExecutionResult.from_raw_data(
            tool_call_id=tool_call_id,
            raw_data=raw_data,
            output_level=output_level,
            tool_name="execute_command",
            cache_policy=ToolCachePolicy.NO_CACHE,
        ).with_duration(duration_ms)

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        # 创建错误结果
        return ToolExecutionResult.create_error(
            tool_call_id=tool_call_id,
            error_message=str(e),
            error_type=type(e).__name__,
            tool_name="execute_command",
        ).with_duration(duration_ms)


# 创建 LangChain 工具
execute_command_tool = StructuredTool.from_function(
    func=execute_command_impl,
    name="execute_command",
    description="""
执行安全的命令行命令（Docker 隔离环境）。

支持的白名单命令：
- ls: 列出文件
- cat: 查看文件内容
- echo: 输出文本
- grep: 搜索文本
- head: 查看文件开头
- tail: 查看文件结尾
- wc: 统计行数、字数等

使用示例：
- execute_command(command="ls -la")
- execute_command(command="cat file.txt")
- execute_command(command="grep 'pattern' file.txt")
    """.strip(),
    args_schema=ExecuteCommandInput,
)


# 导出
__all__ = [
    "ExecuteCommandInput",
    "execute_command_impl",
    "execute_command_tool",
]
