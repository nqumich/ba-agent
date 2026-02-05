"""
记忆写入工具

智能写入用户记忆文件，自动选择合适的层级
"""

import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Literal

from pydantic import BaseModel, Field, field_validator

from langchain_core.tools import StructuredTool


# 记忆目录路径
MEMORY_DIR = Path("memory")


class MemoryWriteInput(BaseModel):
    """记忆写入工具的输入参数"""

    content: str = Field(
        description="要写入的内容（支持 Markdown 格式）"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="目标文件路径（如 'MEMORY.md'），为空时自动选择"
    )
    layer: Literal["daily", "longterm", "context", "bank", "auto"] = Field(
        default="auto",
        description="记忆层级：daily=每日日志, longterm=长期记忆, context=上下文引导, bank=知识库, auto=自动判断"
    )
    category: Optional[Literal["world", "experience", "opinions"]] = Field(
        default=None,
        description="bank 层级的分类（仅当 layer='bank' 时有效）"
    )
    append: bool = Field(
        default=True,
        description="是否追加到文件末尾（False 则覆盖文件）"
    )
    timestamp: bool = Field(
        default=True,
        description="是否在内容前添加时间戳"
    )

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证内容"""
        if not v or not v.strip():
            raise ValueError("内容不能为空")
        return v.strip()

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: Optional[str]) -> Optional[str]:
        """验证文件路径"""
        if v is None:
            return v

        v = v.strip()

        # 检查路径遍历攻击
        if ".." in v:
            raise ValueError("路径中不能包含 '..'（安全限制）")

        # 检查是否在 memory 目录内
        full_path = MEMORY_DIR / v
        try:
            full_path = full_path.resolve()
            memory_dir = MEMORY_DIR.resolve()
            if not str(full_path).startswith(str(memory_dir)):
                raise ValueError("只能写入 memory/ 目录下的文件")
        except Exception as e:
            raise ValueError(f"路径解析失败: {e}")

        return v

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: Optional[str], info) -> Optional[str]:
        """验证 category 参数"""
        if v is not None and info.data.get('layer') != 'bank':
            raise ValueError("category 参数仅在 layer='bank' 时有效")
        return v


def memory_write(
    content: str,
    file_path: Optional[str] = None,
    layer: Literal["daily", "longterm", "context", "bank", "auto"] = "auto",
    category: Optional[Literal["world", "experience", "opinions"]] = None,
    append: bool = True,
    timestamp: bool = True
) -> str:
    """
    智能写入用户记忆文件

    Args:
        content: 要写入的内容
        file_path: 目标文件路径，为空时根据 layer 自动选择
        layer: 记忆层级
        category: bank 层级的分类
        append: 是否追加（默认 True）
        timestamp: 是否添加时间戳（默认 True）

    Returns:
        操作结果消息

    Examples:
        >>> memory_write("今天学习了 Python 装饰器", layer="daily")
        >>> memory_write("# 用户偏好\\n\\n喜欢简洁的代码", layer="longterm", file_path="MEMORY.md")
        >>> memory_write("Python 装饰器可以在不修改原函数的情况下扩展功能", layer="bank", category="experience")
    """
    # 自动判断层级
    if layer == "auto":
        layer = _auto_detect_layer(content, file_path)

    # 确定目标文件
    target_file = _resolve_target_file(layer, file_path, category)
    if not target_file:
        return f"❌ 无法确定目标文件\\n\\nlayer={layer}, file_path={file_path}, category={category}"

    # 确保目录存在
    target_file.parent.mkdir(parents=True, exist_ok=True)

    # 准备写入内容
    write_content = content

    if timestamp:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_content = f"## {now}\\n\\n{content}"

    # 添加分隔符（追加模式）
    if append and target_file.exists():
        write_content = f"\\n\\n---\\n\\n{write_content}"

    # 写入文件
    try:
        mode = 'a' if append else 'w'
        with open(target_file, mode, encoding='utf-8') as f:
            f.write(write_content)

        # 返回成功消息
        relative_path = target_file.relative_to(MEMORY_DIR.parent)
        action = "追加到" if append else "写入"
        return f"✅ 成功{action} {relative_path}\\n\\n内容预览:\\n{content[:100]}{'...' if len(content) > 100 else ''}"

    except Exception as e:
        return f"❌ 写入文件失败: {e}\\n\\n目标文件: {target_file}"


def _auto_detect_layer(content: str, file_path: Optional[str]) -> str:
    """
    自动检测应该写入哪个层级

    判断逻辑：
    1. 如果指定了 file_path，根据路径判断
    2. 内容包含日期格式 → daily
    3. 内容包含结构化标记（W @/B @/O(c=)/S @）→ bank
    4. 内容较短且像笔记 → daily
    5. 内容较长且有结构 → longterm
    """
    if file_path:
        # 根据文件路径判断
        if file_path.startswith("bank/"):
            return "bank"
        # 提取文件名（不含扩展名）
        file_name = Path(file_path).stem.upper()
        if file_name in ["MEMORY", "USER"]:
            return "longterm"
        if file_name in ["CLAUDE", "AGENTS", "SOUL"]:
            return "context"
        # 日期格式文件 (YYYY-MM-DD.md)
        if len(file_path) == 14 and file_path.count("-") == 2 and file_path.endswith(".md"):
            return "daily"

    # 根据内容判断
    content_lower = content.lower()

    # 检查 Retain 格式标记
    retain_markers = ["w @", "b @", "o(c=", "s @"]
    if any(marker in content_lower for marker in retain_markers):
        return "bank"

    # 检查是否是今日笔记
    daily_keywords = ["今天", "今日", "完成了", "学习了", "会议", "待办"]
    if len(content) < 500 and any(kw in content for kw in daily_keywords):
        return "daily"

    # 默认写入每日日志
    return "daily"


def _resolve_target_file(
    layer: str,
    file_path: Optional[str],
    category: Optional[str]
) -> Optional[Path]:
    """解析目标文件路径"""
    # 如果明确指定了文件路径
    if file_path:
        return MEMORY_DIR / file_path

    # 根据层级自动选择文件
    if layer == "daily":
        # 今日日志
        today = date.today().strftime("%Y-%m-%d")
        return MEMORY_DIR / f"{today}.md"

    elif layer == "longterm":
        # 长期记忆
        return MEMORY_DIR / "MEMORY.md"

    elif layer == "context":
        # 上下文引导层（默认不自动写入，需要指定文件）
        return None  # 需要明确指定文件

    elif layer == "bank":
        # 知识库
        if category:
            return MEMORY_DIR / "bank" / f"{category}.md"
        return MEMORY_DIR / "bank" / "experience.md"  # 默认写入 experience

    return None


# 创建工具
memory_write_tool = StructuredTool.from_function(
    func=memory_write,
    name="memory_write",
    description="""
智能写入用户记忆文件，自动选择合适的记忆层级。

**记忆层级**:
- daily: 每日日志（默认）
- longterm: 长期记忆 (MEMORY.md)
- context: 上下文引导 (CLAUDE.md, AGENTS.md, SOUL.md)
- bank: 知识库 (world/experience/opinions)
- auto: 自动判断（推荐）

**参数**:
- content: 要写入的内容（必需）
- file_path: 目标文件路径（可选，layer 优先）
- layer: 记忆层级（默认 auto）
- category: bank 层级的分类（world/experience/opinions）
- append: 是否追加（默认 True）
- timestamp: 是否添加时间戳（默认 True）

**Retain 格式** (推荐用于 bank 层):
- W @主题: 内容 - 新知识
- B @主题: 内容 - 基础事实
- O(c=置信度) @主题: 内容 - 判断和观点
- S @主题: 内容 - 技能

**示例**:
- 写入今日日志: memory_write("今天学习了 Python 装饰器")
- 写入长期记忆: memory_write("# 用户偏好\\n\\n喜欢简洁的代码", layer="longterm")
- 写入知识库: memory_write("W @Python: 装饰器可以在不修改原函数的情况下扩展功能", layer="bank", category="experience")
""",
    args_schema=MemoryWriteInput
)
