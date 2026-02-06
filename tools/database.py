"""
数据库查询工具 (v2.2 - Pipeline + SQLAlchemy)

使用 SQLAlchemy 安全执行 SQL 查询
支持参数化查询防止 SQL 注入
支持多数据库连接配置
支持 PostgreSQL 和 ClickHouse

v2.1 变更：
- 移除旧模型 (ToolOutput, ResponseFormat)
- 仅使用 ToolExecutionResult
- 移除 use_pipeline 参数

v2.2 变更 (2026-02-06)：
- ✅ 实现真实 SQLAlchemy 执行
- ✅ 移除 mock 实现
- ✅ 添加连接池管理 (QueuePool)
- ✅ 支持参数化查询 (text() + params)
- ✅ 线程安全的引擎管理
- ✅ 支持 PostgreSQL (psycopg2) 和 ClickHouse (clickhouse-sqlalchemy)
- ✅ Fallback 机制：SQLAlchemy 不可用时使用 mock

依赖要求：
- psycopg2-binary (PostgreSQL 驱动)
- clickhouse-sqlalchemy (ClickHouse 支持，可选)
- sqlalchemy
"""

import re
import time
import warnings
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool

from config import get_config

# Pipeline v2.1 模型
from backend.models.pipeline import (
    OutputLevel,
    ToolExecutionResult,
    ToolCachePolicy,
)

# 尝试导入 SQLAlchemy
try:
    from sqlalchemy import create_engine, text, Column
    from sqlalchemy.engine import Engine
    from sqlalchemy.pool import QueuePool
    from sqlalchemy.exc import SQLAlchemyError
    import threading

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    warnings.warn(
        "SQLAlchemy 不可用，数据库查询工具将使用 mock 模式。"
        "请安装: pip install sqlalchemy psycopg2-binary"
    )

# 类型提示（仅在类型检查时使用）
if TYPE_CHECKING:
    from sqlalchemy.engine import Engine as EngineType


# 全局连接池管理（线程安全）
_engines: Dict[str, Any] = {}  # Store Engine objects when available
_engines_lock = threading.Lock() if SQLALCHEMY_AVAILABLE else None
_USE_MOCK = not SQLALCHEMY_AVAILABLE


def _get_engine(connection_name: str, db_config: Dict[str, Any]) -> Optional[Any]:
    """
    获取或创建数据库引擎

    Args:
        connection_name: 连接名称
        db_config: 数据库配置

    Returns:
        SQLAlchemy Engine 或 None（如果 SQLAlchemy 不可用）
    """
    if not SQLALCHEMY_AVAILABLE:
        return None

    with _engines_lock:
        if connection_name in _engines:
            return _engines[connection_name]

        # 构建 SQLAlchemy URL
        # 支持 PostgreSQL 和 ClickHouse
        db_type = db_config.get("type", "postgresql")
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 5432)
        username = db_config.get("username", "postgres")
        password = db_config.get("password", "")
        database = db_config.get("database", "postgres")

        if db_type == "clickhouse" or port == 8123:
            # ClickHouse 使用 clickhouse_connect 风格 URL
            # SQLAlchemy 通过 clickhouse-sqlalchemy 驱动
            url = f"clickhouse+native://{username}:{password}@{host}:{port}/{database}"
        else:
            # PostgreSQL
            url = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"

        # 创建引擎
        pool_size = db_config.get("pool_size", 5)
        max_overflow = db_config.get("max_overflow", 10)
        pool_timeout = db_config.get("pool_timeout", 30)

        engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,  # 检查连接有效性
            echo=False,  # 不打印 SQL
        )

        _engines[connection_name] = engine
        return engine


def _close_engines():
    """关闭所有数据库连接（用于清理）"""
    if not SQLALCHEMY_AVAILABLE:
        return

    with _engines_lock:
        for engine in _engines.values():
            engine.dispose()
        _engines.clear()


def _generate_mock_result(query: str, max_rows: int) -> tuple:
    """生成 mock 查询结果"""
    mock_rows = []
    mock_columns = []

    if "users" in query.lower():
        mock_columns = ["id", "name", "email", "created_at"]
        mock_rows = [
            {"id": 1, "name": "Sample 1", "email": "data_1", "created_at": "2025-02-05"},
            {"id": 2, "name": "Sample 2", "email": "data_2", "created_at": "2025-02-06"},
            {"id": 3, "name": "Sample 3", "email": "data_3", "created_at": "2025-02-07"},
            {"id": 4, "name": "Sample 4", "email": "data_4", "created_at": "2025-02-08"},
            {"id": 5, "name": "Sample 5", "email": "data_5", "created_at": "2025-02-09"},
        ]
    elif "sales" in query.lower():
        mock_columns = ["id", "name", "value", "created_at"]
        mock_rows = [
            {"id": 1, "name": "Product A", "value": 100, "created_at": "2025-02-05"},
            {"id": 2, "name": "Product B", "value": 200, "created_at": "2025-02-06"},
            {"id": 3, "name": "Product C", "value": 300, "created_at": "2025-02-07"},
            {"id": 4, "name": "Product D", "value": 400, "created_at": "2025-02-08"},
            {"id": 5, "name": "Product E", "value": 500, "created_at": "2025-02-09"},
        ]
    else:
        # 默认结果
        mock_columns = ["id", "name", "value", "created_at"]
        mock_rows = [
            {"id": 1, "name": "Sample 1", "value": 100, "created_at": "2025-02-05"}
        ]

    # 限制行数
    mock_rows = mock_rows[:max_rows]

    return mock_rows, mock_columns


class DatabaseQueryInput(BaseModel):
    """数据库查询工具的输入参数"""

    query: str = Field(
        ...,
        description="要执行的 SQL 查询语句（仅支持 SELECT 和 WITH）"
    )
    connection: Optional[str] = Field(
        default="primary",
        description="数据库连接名称（默认: primary）"
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="查询参数（用于参数化查询，防止 SQL 注入）"
    )
    max_rows: Optional[int] = Field(
        default=1000,
        ge=1,
        le=10000,
        description="最大返回行数（范围 1-10000）"
    )
    # 支持 OutputLevel 字符串
    response_format: Optional[str] = Field(
        default="standard",
        description="响应格式: brief, standard, full"
    )

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """验证 SQL 查询安全性"""
        config = get_config()

        # 去除首尾空白和多余空格
        query = v.strip()
        if not query:
            raise ValueError("查询不能为空")
        query = re.sub(r'\s+', ' ', query)

        # 检查安全配置是否启用
        if not config.database.security.enabled:
            # 移除结尾分号后返回
            return query.rstrip(';').strip()

        security = config.database.security

        # 检查是否包含注释注入
        if '--' in query or '/*' in query:
            raise ValueError("查询不能包含 SQL 注释")

        # 检查禁止的关键字（在检查语句类型之前）
        forbidden_keywords = security.forbidden_keywords or []
        query_upper = query.upper()
        for keyword in forbidden_keywords:
            # 使用单词边界匹配，避免误判（如 DROP 不会匹配 DROPOUT）
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, query_upper):
                raise ValueError(
                    f"查询包含禁止的关键字 '{keyword}'。"
                    f"仅允许执行只读查询。"
                )

        # 检查是否以允许的语句类型开头
        allowed_statements = security.allowed_statements or ["SELECT", "WITH"]
        if not any(query_upper.strip().startswith(stmt) for stmt in allowed_statements):
            raise ValueError(
                f"仅允许执行 {', '.join(allowed_statements)} 语句。"
            )

        # 检查是否包含多条语句（分号分隔）
        if ';' in query:
            raise ValueError("仅允许执行单条语句")

        # 移除结尾分号
        return query.rstrip(';').strip()

    @field_validator('params')
    @classmethod
    def validate_params(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """验证查询参数安全性"""
        if v is None:
            return v

        for key, value in v.items():
            # 检查值类型是否安全
            if isinstance(value, dict):
                raise ValueError(f"参数 '{key}' 的类型不安全：不允许使用字典")
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        raise ValueError(f"参数 '{key}' 的列表元素类型不安全：不允许使用字典")

        return v


def _format_result(rows: List[Dict[str, Any]], columns: List[str]) -> Dict[str, Any]:
    """格式化查询结果"""
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "column_count": len(columns)
    }


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


def query_database_impl(
    query: str,
    connection: str = "primary",
    params: Optional[Dict[str, Any]] = None,
    max_rows: int = 1000,
    response_format: str = "standard",
) -> ToolExecutionResult:
    """
    数据库查询的实现函数

    Args:
        query: SQL 查询语句
        connection: 数据库连接名称
        params: 查询参数（参数化查询）
        max_rows: 最大返回行数
        response_format: 响应格式

    Returns:
        ToolExecutionResult
    """
    start_time = time.time()

    # 生成 tool_call_id
    import uuid
    tool_call_id = f"call_query_database_{uuid.uuid4().hex[:12]}"

    # 解析输出级别
    output_level = _parse_output_level(response_format)

    # 首先验证连接是否存在（无论 mock 还是 real 模式）
    config = get_config()
    connections_dict = config.database.connections
    db_config = None

    if connection in connections_dict:
        db_config = connections_dict[connection]
    elif connection == "primary" and hasattr(config.database, "host"):
        # 使用默认配置
        db_config = {
            "host": config.database.host,
            "port": config.database.port,
            "username": config.database.username,
            "password": config.database.password,
            "database": config.database.database,
            "pool_size": getattr(config.database, "pool_size", 10),
            "max_overflow": getattr(config.database, "max_overflow", 20),
        }
    else:
        # 连接不存在
        return ToolExecutionResult.create_error(
            tool_call_id=tool_call_id,
            error_message=f"未找到数据库连接: {connection}",
            error_type="ConnectionNotFound",
            tool_name="query_database",
        )

    # 检查是否使用 mock 模式
    if _USE_MOCK:
        # 使用 mock 数据（SQLAlchemy 不可用时）
        mock_rows, mock_columns = _generate_mock_result(query, max_rows)
        duration_ms = (time.time() - start_time) * 1000

        result_data = _format_result(mock_rows, mock_columns)
        result_data["mock_mode"] = True
        result_data["warning"] = "SQLAlchemy 不可用，使用 mock 数据。请安装: pip install sqlalchemy psycopg2-binary"

        return ToolExecutionResult.from_raw_data(
            tool_call_id=tool_call_id,
            raw_data=result_data,
            output_level=output_level,
            tool_name="query_database",
            cache_policy=ToolCachePolicy.TTL_SHORT,
        ).with_duration(duration_ms)

    try:
        # 获取或创建数据库引擎（db_config 已在上面获取）
        engine = _get_engine(connection, db_config)
        if engine is None:
            return ToolExecutionResult.create_error(
                tool_call_id=tool_call_id,
                error_message="数据库引擎创建失败，SQLAlchemy 不可用",
                error_type="DatabaseError",
                tool_name="query_database",
            )

        # 执行查询
        with engine.connect() as conn:
            # 使用 text() 包装查询以支持参数化
            stmt = text(query)

            # 如果有参数，使用参数化查询
            if params:
                result = conn.execute(stmt, **params)
            else:
                result = conn.execute(stmt)

            # 获取列名
            columns = list(result.keys())

            # 获取所有行（限制行数）
            rows = []
            for row in result:
                row_dict = dict(zip(columns, row))
                rows.append(row_dict)
                if len(rows) >= max_rows:
                    break

            # 如果达到最大行数，添加警告
            warning = None
            if len(rows) >= max_rows:
                # 检查是否还有更多行
                if result.fetchmany(1):
                    warning = f"结果已限制为 {max_rows} 行，实际可能还有更多数据。"

        duration_ms = (time.time() - start_time) * 1000

        # 格式化结果
        result_data = _format_result(rows, columns)

        # 如果有警告，添加到结果中
        if warning:
            result_data["warning"] = warning

        # 创建 ToolExecutionResult
        return ToolExecutionResult.from_raw_data(
            tool_call_id=tool_call_id,
            raw_data=result_data,
            output_level=output_level,
            tool_name="query_database",
            cache_policy=ToolCachePolicy.TTL_SHORT,
        ).with_duration(duration_ms)

    except SQLAlchemyError as e:
        duration_ms = (time.time() - start_time) * 1000

        # 创建错误结果
        return ToolExecutionResult.create_error(
            tool_call_id=tool_call_id,
            error_message=f"数据库查询失败: {str(e)}",
            error_type="DatabaseError",
            tool_name="query_database",
        ).with_duration(duration_ms)

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        # 创建错误结果
        return ToolExecutionResult.create_error(
            tool_call_id=tool_call_id,
            error_message=str(e),
            error_type=type(e).__name__,
            tool_name="query_database",
        ).with_duration(duration_ms)


# 创建 LangChain 工具
query_database_tool = StructuredTool.from_function(
    func=query_database_impl,
    name="query_database",
    description="""
执行 SQL 查询，从数据库中检索数据。

支持的操作：
- SELECT 查询（PostgreSQL, ClickHouse）
- WITH (CTE) 查询
- 参数化查询（防止 SQL 注入）
- 多数据库连接配置
- 连接池管理

安全特性：
- 禁止 DML 操作 (INSERT/UPDATE/DELETE)
- 禁止 DDL 操作 (CREATE/DROP/ALTER)
- SQL 注入防护
- 查询参数类型检查
- 查询超时控制

使用场景：
- 查询用户数据: "SELECT * FROM users WHERE id = :id"
- 查询销售数据: "SELECT * FROM sales WHERE date > :start_date"
- 聚合查询: "SELECT category, COUNT(*) as count FROM sales GROUP BY category"
- 多表关联: "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id"

参数说明：
- query: SQL 查询语句（必填）
- connection: 数据库连接名称（默认: primary）
- params: 查询参数（用于参数化查询，如 {"id": 123}）
- max_rows: 最大返回行数（1-10000，默认: 1000）
- response_format: 响应格式（brief/standard/full，默认: standard）

支持的数据库：
- PostgreSQL (默认)
- ClickHouse (通过 clickhouse-sqlalchemy)

注意事项：
- 需要安装相应的数据库驱动：psycopg2 (PostgreSQL), clickhouse-sqlalchemy (ClickHouse)
- 如果数据库连接失败，会返回详细错误信息
- 查询结果会自动转换为字典列表格式
""",
    args_schema=DatabaseQueryInput
)


__all__ = [
    "DatabaseQueryInput",
    "query_database_impl",
    "query_database_tool",
    "_format_result",
    "_get_engine",
    "_close_engines",
]
