"""
记忆搜索工具 v2 - 混合搜索

使用 SQLite FTS5 + 向量搜索的混合搜索引擎
支持语义搜索、相关性评分、来源过滤等高级功能
"""

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator

from langchain_core.tools import StructuredTool

from backend.memory import (
    HybridSearchEngine,
    create_embedding_provider,
    ensure_memory_index_schema,
    open_index_db,
    get_index_db_path,
    DEFAULT_INDEX_PATH,
)


# 记忆目录路径
MEMORY_DIR = Path("memory")


class MemorySearchV2Input(BaseModel):
    """记忆搜索工具 v2 的输入参数"""

    query: str = Field(
        description="搜索查询（关键词或自然语言问题）"
    )
    max_results: int = Field(
        default=6,
        description="最大返回结果数（默认 6）"
    )
    min_score: float = Field(
        default=0.35,
        description="最小相关性分数（0-1），低于此值的结果会被过滤（默认 0.35）"
    )
    source: str = Field(
        default="memory",
        description="来源过滤: 'all', 'memory', 'sessions'"
    )
    use_hybrid: bool = Field(
        default=True,
        description="是否使用混合搜索（FTS + 向量），False 则仅使用 FTS"
    )
    vector_weight: float = Field(
        default=0.7,
        description="向量搜索权重（0-1），仅在混合搜索时生效（默认 0.7）"
    )
    text_weight: float = Field(
        default=0.3,
        description="文本搜索权重（0-1），仅在混合搜索时生效（默认 0.3）"
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
        # 限制查询长度
        if len(v) > 5000:
            raise ValueError("查询长度不能超过 5000 字符")
        return v

    @field_validator('min_score')
    @classmethod
    def validate_min_score(cls, v: float) -> float:
        """验证最小分数"""
        if v < 0 or v > 1:
            raise ValueError("min_score 必须在 0-1 之间")
        return v

    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str) -> str:
        """验证来源过滤"""
        valid_sources = ['all', 'memory', 'sessions']
        if v not in valid_sources:
            raise ValueError(f"source 必须是: {', '.join(valid_sources)}")
        return v

    @field_validator('vector_weight', 'text_weight')
    @classmethod
    def validate_weights(cls, v: float, info) -> float:
        """验证权重"""
        if v < 0 or v > 1:
            raise ValueError(f"{info.field_name} 必须在 0-1 之间")
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


def memory_search_v2(
    query: str,
    max_results: int = 6,
    min_score: float = 0.35,
    source: str = "memory",
    use_hybrid: bool = True,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    context_lines: int = 2
) -> str:
    """
    使用混合搜索引擎搜索用户记忆

    Args:
        query: 搜索查询（关键词或自然语言问题）
        max_results: 最大返回结果数
        min_score: 最小相关性分数
        source: 来源过滤: "all", "memory", "sessions"
        use_hybrid: 是否使用混合搜索
        vector_weight: 向量搜索权重
        text_weight: 文本搜索权重
        context_lines: 上下文行数

    Returns:
        搜索结果（Markdown 格式）

    Examples:
        >>> memory_search_v2("Python 装饰器")  # 语义搜索
        >>> memory_search_v2("今天的任务", min_score=0.5)  # 高相关性过滤
        >>> memory_search_v2("@架构", source="bank")  # 仅搜索 bank 目录
    """
    # 确保索引存在
    index_path = get_index_db_path()

    if not index_path.exists():
        return "❌ 搜索索引尚未创建。请先运行索引建立。"

    try:
        # 打开索引数据库
        db = open_index_db(index_path)

        # 检查是否已创建 schema
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
        )
        if cursor.fetchone() is None:
            return "❌ 搜索索引尚未建立。请先运行索引建立。"

        # 检查是否有向量表
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
        )
        has_vectors = cursor.fetchone() is not None

        # 创建 embedding provider
        try:
            provider = create_embedding_provider(provider="auto")
            embedding = provider.encode_batch([query])[0]
            embedding_dims = len(embedding)
        except Exception as e:
            # Embedding 失败，回退到 FTS only
            use_hybrid = False
            embedding_dims = 0

        if use_hybrid and has_vectors and embedding_dims > 0:
            # 使用混合搜索
            results = _search_hybrid(
                db,
                query,
                embedding,
                embedding_dims,
                max_results,
                min_score,
                source,
                vector_weight,
                text_weight
            )
        else:
            # 仅使用 FTS 搜索
            results = _search_fts(
                db,
                query,
                max_results,
                min_score,
                source
            )

        db.close()

        # 格式化结果
        return _format_results_v2(results, query, min_score, source, use_hybrid)

    except Exception as e:
        return f"❌ 搜索失败: {str(e)}"


def _search_hybrid(
    db: sqlite3.Connection,
    query: str,
    query_embedding: List[float],
    dims: int,
    max_results: int,
    min_score: float,
    source: str,
    vector_weight: float,
    text_weight: float
) -> List[Dict[str, Any]]:
    """
    使用混合搜索引擎

    Args:
        db: 数据库连接
        query: 查询文本
        query_embedding: 查询向量
        dims: 向量维度
        max_results: 最大结果数
        min_score: 最小分数
        source: 来源过滤
        vector_weight: 向量权重
        text_weight: 文本权重

    Returns:
        搜索结果列表
    """
    # 创建混合搜索引擎
    engine = HybridSearchEngine(
        db,
        dims=dims,
        fts_weight=text_weight,
        vec_weight=vector_weight,
        use_sqlite_vec=False  # 使用 JSON 存储回退
    )

    # 确保向量表存在
    engine.ensure_vector_tables()

    # 插入查询向量（临时）
    query_id = "__query__"
    engine.insert_vector(query_id, query_embedding)

    try:
        # 执行混合搜索
        source_filter = None if source == "all" else [source]
        results = engine.search(
            query=query,
            query_embedding=query_embedding,
            limit=max_results * 4,  # 获取更多候选结果
            source_filter=source_filter
        )

        # 过滤低分结果
        filtered_results = [
            r for r in results
            if r.get("score", 0) >= min_score
        ][:max_results]

        # 为每个结果添加上下文
        for result in filtered_results:
            chunk_id = result.get("id")
            if chunk_id:
                context = _get_chunk_context(db, chunk_id, context_lines)
                result["context"] = context

        return filtered_results

    finally:
        # 清理查询向量
        try:
            engine.delete_by_path("")  # 删除临时向量
        except:
            pass


def _search_fts(
    db: sqlite3.Connection,
    query: str,
    max_results: int,
    min_score: float,
    source: str
) -> List[Dict[str, Any]]:
    """
    使用 FTS 搜索（回退方案）

    Args:
        db: 数据库连接
        query: 查询文本
        max_results: 最大结果数
        min_score: 最小分数
        source: 来源过滤

    Returns:
        搜索结果列表
    """
    # 使用 LIKE 搜索（支持中文）
    like_query = f"%{query}%"

    # 构建基础 SQL
    sql = """
        SELECT
            c.id,
            c.path,
            c.source,
            c.start_line,
            c.end_line,
            c.text
        FROM chunks c
        WHERE c.text LIKE ?
    """

    params = [like_query]

    # 添加来源过滤
    if source != "all":
        sql += " AND c.source = ?"
        params.append(source)

    # 限制结果数
    sql += f" LIMIT {max_results * 2}"

    cursor = db.execute(sql, params)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        chunk_id, path, source, start_line, end_line, text = row

        # 简单的相关性评分（基于匹配次数）
        match_count = text.lower().count(query.lower())
        score = min(1.0, match_count / 10.0)

        if score >= min_score:
            results.append({
                "id": chunk_id,
                "path": path,
                "source": source,
                "start_line": start_line,
                "end_line": end_line,
                "text": text,
                "score": score,
                "context": _get_context_from_text(text, start_line, 2)
            })

    return results[:max_results]


def _get_chunk_context(
    db: sqlite3.Connection,
    chunk_id: str,
    context_lines: int
) -> str:
    """
    获取 chunk 的上下文

    Args:
        db: 数据库连接
        chunk_id: chunk ID
        context_lines: 上下文行数

    Returns:
        上下文文本
    """
    cursor = db.execute(
        "SELECT start_line, end_line, text FROM chunks WHERE id = ?",
        (chunk_id,)
    )
    row = cursor.fetchone()

    if row is None:
        return ""

    start_line, end_line, text = row
    lines = text.split('\n')

    # 简单的上下文提取（取前 context_lines 和后 context_lines 行）
    context_start = max(0, context_lines)
    context_end = min(len(lines), len(lines) - context_lines)

    if context_start >= context_end:
        return text

    context_lines_list = lines[context_start:context_end]
    return '\n'.join(context_lines_list)


def _get_context_from_text(text: str, start_line: int, context_lines: int) -> str:
    """
    从文本中获取上下文（简化版）

    Args:
        text: 文本内容
        start_line: 起始行号
        context_lines: 上下文行数

    Returns:
        上下文文本
    """
    lines = text.split('\n')
    total_lines = len(lines)

    # 计算实际可取的上下文范围
    context_start = max(0, context_lines)
    context_end = min(total_lines, total_lines - context_lines)

    if context_start >= context_end:
        return text

    return '\n'.join(lines[context_start:context_end])


def _format_results_v2(
    results: List[Dict[str, Any]],
    query: str,
    min_score: float,
    source: str,
    use_hybrid: bool
) -> str:
    """
    格式化搜索结果（v2 版本）

    Args:
        results: 搜索结果列表
        query: 查询文本
        min_score: 最小分数
        source: 来源过滤
        use_hybrid: 是否使用混合搜索

    Returns:
        格式化的 Markdown 输出
    """
    if not results:
        filters = []
        if source != "all":
            filters.append(f"来源={source}")
        if min_score > 0:
            filters.append(f"最小分数={min_score}")
        filter_str = f" (过滤: {', '.join(filters)})" if filters else ""
        return f"❌ 未找到匹配 \"{query}\" 的结果{filter_str}"

    # 构建输出
    output = [f"## 搜索结果: \"{query}\"\n"]
    output.append(f"**搜索模式**: {'混合搜索 (FTS + 向量)' if use_hybrid else 'FTS 关键词搜索'}")
    output.append(f"**找到 {len(results)} 个匹配** (最低分数: {min_score:.2f})\n")

    for i, result in enumerate(results, 1):
        score = result.get("score", 0)
        path = result.get("path", "")
        line = result.get("start_line", 0)

        # 获取上下文
        context = result.get("context", result.get("text", ""))

        output.append(f"### {i}. {path}:{line}")
        output.append(f"**相关性**: {score:.2f}\n")
        output.append("```")
        output.append(context[:500])  # 限制上下文长度
        if len(context) > 500:
            output.append("...")
        output.append("```\n")

    return '\n'.join(output)


# 创建工具
memory_search_v2_tool = StructuredTool.from_function(
    func=memory_search_v2,
    name="memory_search_v2",
    description="""
使用混合搜索引擎（全文搜索 + 向量搜索）搜索用户记忆。

**能力**:
- 语义搜索: 理解查询意图，找到语义相关的内容
- 相关性评分: 返回每个结果的相关性分数 (0-1)
- 混合算法: 结合 BM25 (文本) 和 Cosine (向量) 分数
- 来源过滤: 可按 memory/sessions 过滤

**参数**:
- query: 搜索查询（必需）
- max_results: 最大结果数（默认 6）
- min_score: 最小相关性分数（默认 0.35）
- source: 来源过滤 (all/memory/sessions，默认 memory)
- use_hybrid: 是否使用混合搜索（默认 true）
- vector_weight: 向量权重（默认 0.7）
- text_weight: 文本权重（默认 0.3）
- context_lines: 上下文行数（默认 2）

**示例**:
- 语义搜索: memory_search_v2("Python 装饰器的用法")
- 高相关性: memory_search_v2("架构设计", min_score=0.7)
- 仅搜索 bank: memory_search_v2("@实体", source="memory")

**返回**: 匹配的内容片段，包含文件路径、行号、相关性分数
""",
    args_schema=MemorySearchV2Input
)
