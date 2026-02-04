"""
命令行执行工具

使用 Docker 隔离环境安全执行命令行命令
支持命令白名单验证
"""

import shlex
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool

from config import get_config
from backend.docker.sandbox import get_sandbox


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


def execute_command_impl(command: str, timeout: int = 30) -> str:
    """
    执行命令的实现函数

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒）

    Returns:
        执行结果字符串
    """
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

    # 格式化返回结果
    if result['success']:
        output = result['stdout']
        if not output:
            return "命令执行成功，无输出"
        return output
    else:
        return f"命令执行失败: {result['stderr']}"


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
