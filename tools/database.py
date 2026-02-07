"""
数据库查询工具 (v3.0 - SQLite First, PostgreSQL Optional)

使用 SQLite 作为默认数据库（嵌入式，无需外部服务器）
可选支持 PostgreSQL 和 ClickHouse（用于企业级部署）

v3.0 变更 (2026-02-07)：
- ✅ 默认使用 SQLite（无需外部服务器）
- ✅ 自动创建数据目录
- ✅ 支持向量搜索（可选）
- ✅ PostgreSQL 作为可选配置
- ✅ 保持与 v2.x API 兼容

依赖要求：
- Python 内置 sqlite3 模块（无需安装）
- psycopg2-binary (PostgreSQL 支持，可选)
"""

import os
import re
import time
from pathlib import Path
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

# SQLite 是 Python 内置的，总是可用
import sqlite3

# 尝试导入 SQLAlchemy（用于 PostgreSQL 支持）
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    from sqlalchemy.pool import QueuePool
    from sqlalchemy.exc import SQLAlchemyError
    import threading

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    threading = None

# 类型提示（仅在类型检查时使用）
if TYPE_CHECKING:
    from sqlalchemy.engine import Engine as EngineType


# 全局连接管理
_sqlite_connections: Dict[str, sqlite3.Connection] = {}
_engines: Dict[str, Any] = {}  # Store Engine objects when available
_engines_lock = threading.Lock() if SQLALCHEMY_AVAILABLE else None
_SQLITE_LOCK = threading.Lock() if SQLALCHEMY_AVAILABLE else None

# 数据目录
_DATA_DIR = Path("./data")
_DATA_DIR.mkdir(exist_ok=True)


class DatabaseQueryInput(BaseModel):
    """数据库查询输入参数"""

    query: str = Field(
        ...,
        description="SQL 查询语句（仅支持 SELECT, WITH 等只读查询）"
    )

    connection: str = Field(
        default="sqlite",
        description="连接名称（sqlite 为默认，使用内置 SQLite）"
    )

    max_rows: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="最大返回行数"
    )

    response_format: str = Field(
        default="standard",
        pattern="^(brief|standard|full)$",
        description="响应格式（brief: 仅行数, standard: 结果+行数, full: 完整信息）"
    )

    @field_validator('query')
    @classmethod
    def validate_read_only_query(cls, v: str) -> str:
        """验证查询是只读的（SELECT 或 WITH）"""
        query_upper = v.strip().upper()
        if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH")):
            raise ValueError("仅支持 SELECT 和 WITH 只读查询，不允许 INSERT、UPDATE、DELETE 等修改操作")
        return v


def _get_sqlite_connection(connection_name: str = "sqlite", db_path: str = None) -> sqlite3.Connection:
    """
    获取或创建 SQLite 连接

    Args:
        connection_name: 连接名称
        db_path: 数据库文件路径（可选，默认为 ./data/ba_agent.db）

    Returns:
        SQLite 连接对象
    """
    global _sqlite_connections

    # 使用锁确保线程安全
    if _SQLITE_LOCK:
        with _SQLITE_LOCK:
            if connection_name not in _sqlite_connections:
                # 确定数据库路径
                if db_path is None:
                    db_path = _DATA_DIR / f"{connection_name}.db"
                else:
                    db_path = Path(db_path)

                # 确保目录存在
                db_path.parent.mkdir(parents=True, exist_ok=True)

                # 创建连接
                conn = sqlite3.connect(str(db_path), check_same_thread=False)
                conn.row_factory = sqlite3.Row  # 返回字典式行
                _sqlite_connections[connection_name] = conn

            return _sqlite_connections[connection_name]
    else:
        # 没有锁的情况（单线程）
        if connection_name not in _sqlite_connections:
            if db_path is None:
                db_path = _DATA_DIR / f"{connection_name}.db"
            else:
                db_path = Path(db_path)

            db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            _sqlite_connections[connection_name] = conn

        return _sqlite_connections[connection_name]


def _get_engine(connection_name: str, db_config: Dict[str, Any]) -> Optional[Any]:
    """
    获取或创建 PostgreSQL/ClickHouse 数据库引擎（可选）

    仅在配置了非 SQLite 数据库时使用

    Args:
        connection_name: 连接名称
        db_config: 数据库配置

    Returns:
        SQLAlchemy Engine 或 None（如果 SQLAlchemy 不可用或配置为 SQLite）
    """
    if not SQLALCHEMY_AVAILABLE:
        return None

    db_type = getattr(db_config, "type", "sqlite")
    if db_type == "sqlite":
        return None

    with _engines_lock:
        if connection_name in _engines:
            return _engines[connection_name]

        host = getattr(db_config, "host", "localhost")
        port = getattr(db_config, "port", 5432)
        username = getattr(db_config, "username", "postgres")
        password = getattr(db_config, "password", "")
        database = getattr(db_config, "database", "postgres")

        if db_type == "clickhouse" or port == 8123:
            url = f"clickhouse+native://{username}:{password}@{host}:{port}/{database}"
        else:  # postgresql
            url = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"

        pool_size = getattr(db_config, "pool_size", 5)
        max_overflow = getattr(db_config, "max_overflow", 10)
        pool_timeout = getattr(db_config, "pool_timeout", 30)

        engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
            echo=False,
        )

        _engines[connection_name] = engine
        return engine


def _execute_sqlite_query(
    query: str,
    connection_name: str = "sqlite",
    max_rows: int = 1000
) -> ToolExecutionResult:
    """
    在 SQLite 上执行查询

    Args:
        query: SQL 查询语句
        connection_name: 连接名称
        max_rows: 最大返回行数

    Returns:
        ToolExecutionResult
    """
    tool_call_id = f"call_query_database_{int(time.time() * 1000)}"
    start_time = time.time()

    try:
        conn = _get_sqlite_connection(connection_name)
        cursor = conn.cursor()

        # 安全检查：只允许 SELECT 和 WITH 语句
        query_upper = query.strip().upper()
        if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH")):
            return ToolExecutionResult(
                tool_call_id=tool_call_id,
                tool_name="query_database",
                observation=f"错误: 仅支持 SELECT 和 WITH 查询，不允许修改数据的操作",
                output_level=OutputLevel.STANDARD,
                success=False,
                error_type="SecurityError",
                error_message="仅允许只读查询",
                duration_ms=int((time.time() - start_time) * 1000),
                cache_policy=ToolCachePolicy.NO_CACHE,
            )

        # 执行查询
        cursor.execute(query)

        # 获取结果
        rows = cursor.fetchmany(max_rows)
        row_count = len(rows)

        # 获取列名
        if rows:
            columns = list(rows[0].keys())
        else:
            columns = []
            # 尝试从 cursor.description 获取列名
            if cursor.description:
                columns = [col[0] for col in cursor.description]

        # 格式化结果
        formatted_rows = []
        for row in rows:
            formatted_rows.append([str(v) if v is not None else "" for v in row])

        # 构建观察结果
        observation = f"查询成功，返回 {row_count} 行"

        if row_count > 0:
            observation += f"\n\n列: {', '.join(columns)}\n\n"
            for i, row in enumerate(formatted_rows[:10]):  # 最多显示 10 行
                observation += f"第 {i+1} 行: {row}\n"
            if row_count > 10:
                observation += f"\n... 还有 {row_count - 10} 行"

        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name="query_database",
            observation=observation,
            output_level=OutputLevel.STANDARD,
            success=True,
            data={
                "rows": formatted_rows,
                "columns": columns,
                "row_count": row_count
            },
            duration_ms=int((time.time() - start_time) * 1000),
            cache_policy=ToolCachePolicy.NO_CACHE,
        )

    except sqlite3.Error as e:
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name="query_database",
            observation=f"数据库查询失败: {str(e)}",
            output_level=OutputLevel.STANDARD,
            success=False,
            error_type="DatabaseError",
            error_message=str(e),
            duration_ms=int((time.time() - start_time) * 1000),
            cache_policy=ToolCachePolicy.NO_CACHE,
        )
    except Exception as e:
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name="query_database",
            observation=f"查询执行失败: {str(e)}",
            output_level=OutputLevel.STANDARD,
            success=False,
            error_type=type(e).__name__,
            error_message=str(e),
            duration_ms=int((time.time() - start_time) * 1000),
            cache_policy=ToolCachePolicy.NO_CACHE,
        )


def _execute_postgresql_query(
    query: str,
    connection_name: str = "primary",
    max_rows: int = 1000,
    db_config: Dict[str, Any] = None
) -> ToolExecutionResult:
    """
    在 PostgreSQL/ClickHouse 上执行查询（可选功能）

    Args:
        query: SQL 查询语句
        connection_name: 连接名称
        max_rows: 最大返回行数
        db_config: 数据库配置

    Returns:
        ToolExecutionResult
    """
    tool_call_id = f"call_query_database_{int(time.time() * 1000)}"
    start_time = time.time()

    try:
        if not SQLALCHEMY_AVAILABLE:
            return ToolExecutionResult(
                tool_call_id=tool_call_id,
                tool_name="query_database",
                observation="错误: PostgreSQL 支持需要安装 sqlalchemy 和 psycopg2-binary",
                output_level=OutputLevel.STANDARD,
                success=False,
                error_type="DependencyError",
                error_message="缺少依赖包",
                duration_ms=int((time.time() - start_time) * 1000),
                cache_policy=ToolCachePolicy.NO_CACHE,
            )

        engine = _get_engine(connection_name, db_config or {})
        if engine is None:
            return ToolExecutionResult(
                tool_call_id=tool_call_id,
                tool_name="query_database",
                observation=f"错误: 无法连接到数据库 '{connection_name}'",
                output_level=OutputLevel.STANDARD,
                success=False,
                error_type="ConnectionError",
                error_message=f"数据库连接 '{connection_name}' 不可用",
                duration_ms=int((time.time() - start_time) * 1000),
                cache_policy=ToolCachePolicy.NO_CACHE,
            )

        with engine.connect() as conn:
            result = conn.execute(text(query))

            # 获取所有结果
            rows = result.fetchmany(max_rows)
            row_count = len(rows)

            # 获取列名
            if rows:
                columns = list(rows[0]._fields)
            else:
                columns = []

            # 格式化结果
            formatted_rows = []
            for row in rows:
                formatted_rows.append([str(v) if v is not None else "" for v in row])

            # 构建观察结果
            observation = f"查询成功，返回 {row_count} 行"

            if row_count > 0:
                observation += f"\n\n列: {', '.join(columns)}\n\n"
                for i, row in enumerate(formatted_rows[:10]):
                    observation += f"第 {i+1} 行: {row}\n"
                if row_count > 10:
                    observation += f"\n... 还有 {row_count - 10} 行"

            return ToolExecutionResult(
                tool_call_id=tool_call_id,
                tool_name="query_database",
                observation=observation,
                output_level=OutputLevel.STANDARD,
                success=True,
                data={
                    "rows": formatted_rows,
                    "columns": columns,
                    "row_count": row_count
                },
                duration_ms=int((time.time() - start_time) * 1000),
                cache_policy=ToolCachePolicy.NO_CACHE,
            )

    except SQLAlchemyError as e:
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name="query_database",
            observation=f"数据库查询失败: {str(e)}",
            output_level=OutputLevel.STANDARD,
            success=False,
            error_type="DatabaseError",
            error_message=str(e),
            duration_ms=int((time.time() - start_time) * 1000),
            cache_policy=ToolCachePolicy.NO_CACHE,
        )
    except Exception as e:
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name="query_database",
            observation=f"查询执行失败: {str(e)}",
            output_level=OutputLevel.STANDARD,
            success=False,
            error_type=type(e).__name__,
            error_message=str(e),
            duration_ms=int((time.time() - start_time) * 1000),
            cache_policy=ToolCachePolicy.NO_CACHE,
        )


def query_database_impl(
    query: str,
    connection: str = "sqlite",
    max_rows: int = 1000,
    response_format: str = "standard"
) -> ToolExecutionResult:
    """
    执行数据库查询

    默认使用 SQLite（无需外部服务器）
    可配置使用 PostgreSQL 或 ClickHouse

    Args:
        query: SQL 查询语句
        connection: 连接名称（sqlite 为默认，使用内置 SQLite）
        max_rows: 最大返回行数
        response_format: 响应格式

    Returns:
        ToolExecutionResult
    """
    # 获取数据库配置
    config = get_config()
    db_config = config.database if hasattr(config, 'database') else {}

    # 判断使用哪种数据库
    if connection == "sqlite" or getattr(db_config, "type", "sqlite") == "sqlite":
        return _execute_sqlite_query(query, connection, max_rows)
    else:
        # 使用 PostgreSQL 或 ClickHouse
        return _execute_postgresql_query(query, connection, max_rows, db_config)


# 创建 LangChain 工具
query_database_tool = StructuredTool.from_function(
    name="query_database",
    func=query_database_impl,
    description="""执行 SQL 数据库查询（SELECT, WITH 等）

**默认使用 SQLite**（无需外部服务器，自动创建数据库文件）
支持配置 PostgreSQL 或 ClickHouse 用于企业部署

**查询示例**:
- SELECT * FROM users LIMIT 10
- SELECT COUNT(*) as total FROM sales
- WITH ranked AS (SELECT * FROM products) SELECT * FROM ranked

**注意事项**:
- 仅支持只读查询（SELECT, WITH）
- 不允许修改数据的操作（INSERT, UPDATE, DELETE 等）
- max_rows 限制返回行数（默认 1000）
""",
    args_schema=DatabaseQueryInput,
)


def _close_connections():
    """关闭所有数据库连接"""
    global _sqlite_connections, _engines

    # 关闭 SQLite 连接
    for conn in _sqlite_connections.values():
        try:
            conn.close()
        except Exception:
            pass
    _sqlite_connections.clear()

    # 关闭 SQLAlchemy 引擎
    if _engines:
        for engine in _engines.values():
            try:
                engine.dispose()
            except Exception:
                pass
        _engines.clear()
