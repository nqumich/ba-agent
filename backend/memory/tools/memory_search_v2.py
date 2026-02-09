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
    # 从旧版 memory_search 迁移的功能
    entities: Optional[List[str]] = Field(
        default=None,
        description="实体过滤（如 ['@Python', '@架构']），仅匹配包含这些实体的结果"
    )
    since_days: Optional[int] = Field(
        default=None,
        description="时间范围（最近 N 天），None 表示搜索全部时间范围"
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

    @field_validator('since_days')
    @classmethod
    def validate_since_days(cls, v: Optional[int]) -> Optional[int]:
        """验证时间范围"""
        if v is not None and v < 1:
            raise ValueError("since_days 必须 >= 1")
        return v

    @field_validator('entities')
    @classmethod
    def validate_entities(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """验证实体列表"""
        if v is not None:
            for entity in v:
                if not entity.startswith('@'):
                    raise ValueError(f"实体必须以 @ 开头， got: {entity}")
        return v


def memory_search_v2(
    query: str,
    max_results: int = 6,
    min_score: float = 0.35,
    source: str = "memory",
    use_hybrid: bool = True,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    context_lines: int = 2,
    entities: Optional[List[str]] = None,
    since_days: Optional[int] = None
) -> str:
    """
    使用混合搜索引擎搜索用户记忆

    支持多索引文件搜索：当索引文件轮换时，会自动搜索所有索引文件

    Args:
        query: 搜索查询（关键词或自然语言问题）
        max_results: 最大返回结果数
        min_score: 最小相关性分数
        source: 来源过滤: "all", "memory", "sessions"
        use_hybrid: 是否使用混合搜索
        vector_weight: 向量搜索权重
        text_weight: 文本搜索权重
        context_lines: 上下文行数
        entities: 实体过滤（如 ['@Python', '@架构']）
        since_days: 时间范围（最近 N 天）

    Returns:
        搜索结果（Markdown 格式）

    Examples:
        >>> memory_search_v2("Python 装饰器")  # 语义搜索
        >>> memory_search_v2("今天的任务", min_score=0.5)  # 高相关性过滤
        >>> memory_search_v2("架构", entities=["@Python"])  # 实体过滤
        >>> memory_search_v2("任务", since_days=7)  # 最近7天
    """
    # 获取所有索引文件路径
    try:
        from backend.memory.index_rotation import get_all_index_paths
        index_paths = get_all_index_paths()
    except Exception:
        # 回退到单索引模式
        index_paths = [get_index_db_path()]

    # 检查索引是否存在
    if not any(p.exists() for p in index_paths):
        return "❌ 搜索索引尚未创建。请先运行索引建立。"

    all_results = []
    has_vectors = False
    embedding_dims = 0
    query_embedding = None

    # 创建 embedding provider（只需一次）
    if use_hybrid:
        try:
            provider = create_embedding_provider(provider="auto")
            query_embedding = provider.encode_batch([query])[0]
            embedding_dims = len(query_embedding)
        except Exception as e:
            # Embedding 失败，回退到 FTS only
            use_hybrid = False
            embedding_dims = 0

    # 遍历所有索引文件进行搜索
    for index_path in index_paths:
        if not index_path.exists():
            continue

        try:
            # 打开索引数据库
            db = open_index_db(index_path)

            # 检查是否已创建 schema
            cursor = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
            )
            if cursor.fetchone() is None:
                db.close()
                continue

            # 检查是否有向量表
            if not has_vectors:
                cursor = db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
                )
                has_vectors = cursor.fetchone() is not None

            if use_hybrid and has_vectors and embedding_dims > 0:
                # 使用混合搜索
                results = _search_hybrid(
                    db,
                    query,
                    query_embedding,
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

            # 标记结果来源索引
            for result in results:
                result["_index_file"] = index_path.name

            all_results.extend(results)
            db.close()

        except Exception as e:
            logger.warning(f"搜索索引 {index_path.name} 失败: {e}")
            continue

    if not all_results:
        return "❌ 未找到相关结果。"

    # 按分数排序并去重（按 id）
    seen_ids = set()
    unique_results = []
    for r in sorted(all_results, key=lambda x: x.get("score", 0), reverse=True):
        chunk_id = r.get("id")
        if chunk_id and chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            unique_results.append(r)

    # 限制结果数量
    results = unique_results[:max_results * 2]

    # 应用后处理过滤器
    results = _apply_filters(
        results,
        entities=entities,
        since_days=since_days,
        max_results=max_results
    )

    # 格式化结果
    return _format_results_v2(results, query, min_score, source, use_hybrid, entities, since_days)


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


def _apply_filters(
    results: List[Dict[str, Any]],
    entities: Optional[List[str]] = None,
    since_days: Optional[int] = None,
    max_results: int = 100
) -> List[Dict[str, Any]]:
    """
    应用后处理过滤器

    Args:
        results: 搜索结果列表
        entities: 实体过滤列表
        since_days: 时间范围过滤
        max_results: 最大结果数

    Returns:
        过滤后的结果列表
    """
    filtered = results

    # 实体过滤：只保留上下文中包含所有指定实体的结果
    if entities:
        filtered = [
            r for r in filtered
            if all(entity in r.get("context", r.get("text", "")) for entity in entities)
        ]

    # 时间过滤：只保留最近 N 天的结果
    if since_days:
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")

        filtered = [
            r for r in filtered
            if _is_result_recent(r, cutoff_date)
        ]

    # 限制结果数量
    return filtered[:max_results]


def _is_result_recent(result: Dict[str, Any], cutoff_date: str) -> bool:
    """
    检查结果是否在指定日期之后

    Args:
        result: 搜索结果
        cutoff_date: 截止日期 (YYYY-MM-DD 格式)

    Returns:
        是否在截止日期之后
    """
    path = result.get("path", "")

    # 从文件路径中提取日期 (格式: memory/YYYY-MM-DD.md)
    import re
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', path)

    if date_match:
        result_date = date_match.group(1)
        return result_date >= cutoff_date

    return True  # 如果无法解析日期，默认保留


def _format_results_v2(
    results: List[Dict[str, Any]],
    query: str,
    min_score: float,
    source: str,
    use_hybrid: bool,
    entities: Optional[List[str]] = None,
    since_days: Optional[int] = None
) -> str:
    """
    格式化搜索结果（v2 版本）

    Args:
        results: 搜索结果列表
        query: 查询文本
        min_score: 最小分数
        source: 来源过滤
        use_hybrid: 是否使用混合搜索
        entities: 实体过滤
        since_days: 时间范围

    Returns:
        格式化的 Markdown 输出
    """
    if not results:
        filters = []
        if source != "all":
            filters.append(f"来源={source}")
        if min_score > 0:
            filters.append(f"最小分数={min_score}")
        if entities:
            filters.append(f"实体={', '.join(entities)}")
        if since_days:
            filters.append(f"最近{since_days}天")
        filter_str = f" (过滤: {', '.join(filters)})" if filters else ""
        return f"❌ 未找到匹配 \"{query}\" 的结果{filter_str}"

    # 构建输出
    output = [f"## 搜索结果: \"{query}\"\n"]
    output.append(f"**搜索模式**: {'混合搜索 (FTS + 向量)' if use_hybrid else 'FTS 关键词搜索'}")
    output.append(f"**找到 {len(results)} 个匹配** (最低分数: {min_score:.2f})")

    # 显示过滤器
    active_filters = []
    if source != "all":
        active_filters.append(f"来源={source}")
    if entities:
        active_filters.append(f"实体={', '.join(entities)}")
    if since_days:
        active_filters.append(f"最近{since_days}天")
    if active_filters:
        output.append(f"**过滤条件**: {', '.join(active_filters)}")

    output.append("")

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
- 实体过滤: 按实体标记过滤 (如 @Python, @架构)
- 时间过滤: 按时间范围过滤 (最近 N 天)

**参数**:
- query: 搜索查询（必需）
- max_results: 最大结果数（默认 6）
- min_score: 最小相关性分数（默认 0.35）
- source: 来源过滤 (all/memory/sessions，默认 memory)
- use_hybrid: 是否使用混合搜索（默认 true）
- vector_weight: 向量权重（默认 0.7）
- text_weight: 文本权重（默认 0.3）
- context_lines: 上下文行数（默认 2）
- entities: 实体过滤列表（如 ['@Python', '@架构']）
- since_days: 时间范围（最近 N 天）

**示例**:
- 语义搜索: memory_search_v2("Python 装饰器的用法")
- 高相关性: memory_search_v2("架构设计", min_score=0.7)
- 实体过滤: memory_search_v2("架构", entities=["@Python"])
- 时间过滤: memory_search_v2("任务", since_days=7)
- 组合过滤: memory_search_v2("代码", entities=["@Python"], since_days=30)

**返回**: 匹配的内容片段，包含文件路径、行号、相关性分数
""",
    args_schema=MemorySearchV2Input
)
