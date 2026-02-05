"""
记忆搜索工具

搜索用户记忆文件，支持关键词、实体、时间范围过滤
"""

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator

from langchain_core.tools import StructuredTool


# 记忆目录路径
MEMORY_DIR = Path("memory")


class MemorySearchInput(BaseModel):
    """记忆搜索工具的输入参数"""

    query: str = Field(
        description="搜索查询（关键词或正则表达式）"
    )
    entities: Optional[List[str]] = Field(
        default=None,
        description="实体过滤（如 ['@Python', '@架构']），匹配 @entity 标记"
    )
    since_days: Optional[int] = Field(
        default=None,
        description="时间范围（最近 N 天），None 表示搜索全部"
    )
    memory_type: str = Field(
        default="all",
        description="记忆类型过滤: 'all', 'long_term', 'daily', 'bank'"
    )
    max_results: int = Field(
        default=10,
        description="最大返回结果数"
    )
    context_lines: int = Field(
        default=2,
        description="匹配行上下文行数（前后各几行）"
    )

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """验证查询"""
        v = v.strip()
        if not v:
            raise ValueError("查询不能为空")
        # 尝试编译正则表达式，如果失败则作为字面字符串
        try:
            re.compile(v)
        except re.error:
            # 如果不是有效的正则，转义特殊字符
            v = re.escape(v)
        return v

    @field_validator('memory_type')
    @classmethod
    def validate_memory_type(cls, v: str) -> str:
        """验证记忆类型"""
        valid_types = ['all', 'long_term', 'daily', 'bank']
        if v not in valid_types:
            raise ValueError(f"memory_type 必须是: {', '.join(valid_types)}")
        return v

    @field_validator('max_results')
    @classmethod
    def validate_max_results(cls, v: int) -> int:
        """验证最大结果数"""
        if v < 1:
            raise ValueError("max_results 必须 >= 1")
        if v > 100:
            raise ValueError("max_results 不能超过 100")
        return v

    @field_validator('context_lines')
    @classmethod
    def validate_context_lines(cls, v: int) -> int:
        """验证上下文行数"""
        if v < 0:
            raise ValueError("context_lines 必须 >= 0")
        if v > 10:
            raise ValueError("context_lines 不能超过 10")
        return v


def memory_search(
    query: str,
    entities: Optional[List[str]] = None,
    since_days: Optional[int] = None,
    memory_type: str = "all",
    max_results: int = 10,
    context_lines: int = 2
) -> str:
    """
    搜索用户记忆文件

    Args:
        query: 搜索查询（关键词或正则表达式）
        entities: 实体过滤（如 ['@Python', '@架构']）
        since_days: 时间范围（最近 N 天）
        memory_type: 记忆类型过滤
        max_results: 最大返回结果数
        context_lines: 匹配行上下文行数

    Returns:
        搜索结果（Markdown 格式）

    Examples:
        >>> memory_search("Python")  # 搜索包含 Python 的内容
        >>> memory_search("@Python", memory_type="bank")  # 搜索 bank 中 @Python 标记
        >>> memory_search("decorator", since_days=7)  # 搜索最近7天
    """
    results = []

    # 确定要搜索的文件列表
    files_to_search = _get_files_to_search(memory_type, since_days)

    # 编译查询正则
    try:
        query_pattern = re.compile(query, re.IGNORECASE | re.MULTILINE)
    except re.error as e:
        return f"❌ 查询语法错误: {e}"

    # 编译实体过滤
    entity_patterns = None
    if entities:
        entity_patterns = [re.compile(re.escape(e), re.IGNORECASE) for e in entities]

    # 搜索每个文件
    for file_path in files_to_search:
        file_results = _search_file(
            file_path,
            query_pattern,
            entity_patterns,
            context_lines
        )
        results.extend(file_results)

        # 早期终止
        if len(results) >= max_results:
            break

    # 限制结果数量
    results = results[:max_results]

    # 格式化输出
    return _format_results(results, query, entities, memory_type)


def _get_files_to_search(memory_type: str, since_days: Optional[int]) -> List[Path]:
    """获取要搜索的文件列表"""
    files = []
    memory_dir = MEMORY_DIR

    if not memory_dir.exists():
        return files

    # 根据类型确定文件
    if memory_type in ["all", "long_term"]:
        # 长期记忆文件
        long_term_files = [
            "MEMORY.md",
            "AGENTS.md",
            "CLAUDE.md",
            "USER.md",
            "SOUL.md"
        ]
        for filename in long_term_files:
            file_path = memory_dir / filename
            if file_path.exists():
                files.append(file_path)

    if memory_type in ["all", "bank"]:
        # bank 目录
        bank_dir = memory_dir / "bank"
        if bank_dir.exists():
            for item in bank_dir.rglob("*.md"):
                if item.is_file():
                    files.append(item)

    if memory_type in ["all", "daily"]:
        # 每日日志
        if since_days is not None:
            today = date.today()
            for i in range(since_days):
                log_date = today - timedelta(days=i)
                log_file = memory_dir / log_date.strftime("%Y-%m-%d.md")
                if log_file.exists():
                    files.append(log_file)
        else:
            # 搜索所有日期格式的文件
            for item in memory_dir.glob("*.md"):
                if item.is_file() and re.match(r"\d{4}-\d{2}-\d{2}\.md", item.name):
                    files.append(item)

    return files


def _search_file(
    file_path: Path,
    query_pattern: re.Pattern,
    entity_patterns: Optional[List[re.Pattern]],
    context_lines: int
) -> List[Dict[str, Any]]:
    """搜索单个文件"""
    results = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return results

    # 搜索匹配行
    for line_num, line in enumerate(lines, start=1):
        # 检查查询匹配
        if not query_pattern.search(line):
            continue

        # 检查实体过滤
        if entity_patterns:
            line_has_entity = False
            for pattern in entity_patterns:
                if pattern.search(line):
                    line_has_entity = True
                    break
            if not line_has_entity:
                continue

        # 提取上下文
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        context_lines_list = lines[start:end]

        # 清理上下文
        context = ''.join(context_lines_list).strip()

        results.append({
            "content": context,
            "path": str(file_path.relative_to(MEMORY_DIR)),
            "line_number": line_num,
            "score": 1.0  # v1 版本简单评分，都为 1.0
        })

    return results


def _format_results(
    results: List[Dict[str, Any]],
    query: str,
    entities: Optional[List[str]],
    memory_type: str
) -> str:
    """格式化搜索结果"""
    if not results:
        filters = []
        if entities:
            filters.append(f"实体={entities}")
        if memory_type != "all":
            filters.append(f"类型={memory_type}")

        filter_str = f" (过滤: {', '.join(filters)})" if filters else ""
        return f"❌ 未找到匹配 \"{query}\" 的结果{filter_str}"

    # 构建输出
    output = [f"## 搜索结果: \"{query}\"\n"]
    output.append(f"找到 {len(results)} 个匹配:\n")

    for i, result in enumerate(results, 1):
        output.append(f"### {i}. {result['path']}:{result['line_number']}")
        output.append(f"**相关性**: {result['score']:.1f}\n")
        output.append("```")
        output.append(result['content'])
        output.append("```\n")

    return '\n'.join(output)


# 创建工具
memory_search_tool = StructuredTool.from_function(
    func=memory_search,
    name="memory_search",
    description="""
搜索用户记忆文件，支持关键词、实体、时间范围过滤。

**搜索类型**:
- 关键词搜索: 直接输入关键词
- 正则表达式: 支持正则语法
- 实体过滤: 通过 entities 参数过滤 @entity 标记
- 时间范围: 通过 since_days 限制搜索最近 N 天
- 类型过滤: 通过 memory_type 选择 long_term/daily/bank

**参数**:
- query: 搜索查询（必需）
- entities: 实体过滤列表（可选）
- since_days: 时间范围（可选）
- memory_type: 记忆类型 (all/long_term/daily/bank，默认 all)
- max_results: 最大结果数（默认 10）
- context_lines: 匹配行上下文行数（默认 2）

**示例**:
- 搜索关键词: memory_search("Python")
- 搜索实体: memory_search("@Python", memory_type="bank")
- 最近7天: memory_search("架构", since_days=7)
- 正则搜索: memory_search("decorator.*function")

**返回**: 匹配的内容片段，包含文件路径和行号
""",
    args_schema=MemorySearchInput
)
