"""
数据库查询工具单元测试 (v3.0 - SQLite First)

测试 SQLite 数据库功能（默认，无需外部服务器）
"""

import pytest
import sqlite3
from pathlib import Path
from pydantic import ValidationError
from unittest.mock import patch, MagicMock

from tools.database import (
    DatabaseQueryInput,
    query_database_impl,
    query_database_tool,
    _get_sqlite_connection,
    _sqlite_connections,
    _DATA_DIR,
)

# Pipeline v2.1 模型
from backend.models.pipeline import ToolExecutionResult, OutputLevel


@pytest.fixture
def temp_db_dir():
    """临时数据库目录"""
    import tempfile
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # 清理
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def clear_sqlite_connections():
    """清理 SQLite 连接缓存"""
    _sqlite_connections.clear()
    yield
    _sqlite_connections.clear()


@pytest.fixture
def sample_sqlite_db(temp_db_dir):
    """创建示例 SQLite 数据库"""
    db_path = temp_db_dir / "sqlite.db"  # 改为 sqlite.db 以匹配默认连接名
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 创建测试表
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            product TEXT,
            amount REAL,
            date TEXT
        )
    """)

    # 插入测试数据
    cursor.execute("INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@example.com')")
    cursor.execute("INSERT INTO users (id, name, email) VALUES (2, 'Bob', 'bob@example.com')")
    cursor.execute("INSERT INTO users (id, name, email) VALUES (3, 'Charlie', 'charlie@example.com')")

    cursor.execute("INSERT INTO sales (id, product, amount, date) VALUES (1, 'Widget A', 100.50, '2024-01-01')")
    cursor.execute("INSERT INTO sales (id, product, amount, date) VALUES (2, 'Widget B', 250.00, '2024-01-02')")

    conn.commit()
    conn.close()

    return db_path


class TestDatabaseQueryInput:
    """测试 DatabaseQueryInput 模型"""

    def test_basic_query(self):
        """测试基本查询输入"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users"
        )
        assert input_data.query == "SELECT * FROM users"
        assert input_data.connection == "sqlite"
        assert input_data.max_rows == 1000

    def test_select_query(self):
        """测试 SELECT 查询"""
        input_data = DatabaseQueryInput(
            query="SELECT id, name, email FROM users WHERE active = true"
        )
        assert "SELECT" in input_data.query.upper()

    def test_with_query(self):
        """测试 WITH 查询"""
        input_data = DatabaseQueryInput(
            query="WITH ranked_users AS (SELECT * FROM users) SELECT * FROM ranked_users"
        )
        assert "WITH" in input_data.query.upper()

    def test_connection_name(self):
        """测试自定义连接名称"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM sales",
            connection="test_db"
        )
        assert input_data.connection == "test_db"

    def test_max_rows(self):
        """测试最大行数"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users",
            max_rows=100
        )
        assert input_data.max_rows == 100

    def test_response_format_brief(self):
        """测试简洁响应格式"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users",
            response_format="brief"
        )
        assert input_data.response_format == "brief"

    def test_response_format_full(self):
        """测试详细响应格式"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users",
            response_format="full"
        )
        assert input_data.response_format == "full"

    def test_invalid_query_type(self):
        """测试无效的查询类型"""
        with pytest.raises(ValidationError):
            DatabaseQueryInput(
                query="INSERT INTO users VALUES (1, 'Test')"
            )

    def test_invalid_response_format(self):
        """测试无效的响应格式"""
        with pytest.raises(ValidationError):
            DatabaseQueryInput(
                query="SELECT * FROM users",
                response_format="invalid"
            )


class TestSQLiteConnection:
    """测试 SQLite 连接管理"""

    def test_get_sqlite_connection(self, temp_db_dir, clear_sqlite_connections):
        """测试获取 SQLite 连接"""
        test_db_path = temp_db_dir / "test.db"

        conn = _get_sqlite_connection("test", str(test_db_path))

        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)

        # 验证文件被创建
        assert test_db_path.exists()

    def test_connection_reuse(self, temp_db_dir, clear_sqlite_connections):
        """测试连接复用"""
        test_db_path = temp_db_dir / "test.db"

        conn1 = _get_sqlite_connection("test", str(test_db_path))
        conn2 = _get_sqlite_connection("test", str(test_db_path))

        # 应该返回同一个连接
        assert conn1 is conn2

    def test_row_factory(self, temp_db_dir, clear_sqlite_connections):
        """测试行工厂（返回字典式行）"""
        test_db_path = temp_db_dir / "test.db"

        # 创建一个表来测试
        conn = sqlite3.connect(str(test_db_path))
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'Alice')")
        conn.commit()
        conn.close()

        conn = _get_sqlite_connection("test", str(test_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM test")
        row = cursor.fetchone()

        # 应该是字典式行
        assert isinstance(row, sqlite3.Row)
        assert row["id"] == 1
        assert row["name"] == "Alice"


class TestQueryDatabaseImpl:
    """测试查询实现函数"""

    def test_basic_query_execution(self, sample_sqlite_db, clear_sqlite_connections):
        """测试基本查询执行"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_impl(query="SELECT * FROM users")

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            assert len(result.observation) > 0
            assert "3 行" in result.observation

    def test_query_with_specific_columns(self, sample_sqlite_db, clear_sqlite_connections):
        """测试指定列的查询"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_impl(query="SELECT id, name FROM users")

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            assert "3 行" in result.observation

    def test_query_with_wildcard(self, sample_sqlite_db, clear_sqlite_connections):
        """测试通配符查询"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_impl(query="SELECT * FROM sales")

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            assert "2 行" in result.observation

    def test_max_rows_limit(self, sample_sqlite_db, clear_sqlite_connections):
        """测试最大行数限制"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_impl(
                query="SELECT * FROM users",
                max_rows=2
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            # 应该只返回 2 行
            assert "2 行" in result.observation

    def test_brief_response_format(self, sample_sqlite_db, clear_sqlite_connections):
        """测试简洁响应格式"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_impl(
                query="SELECT * FROM users",
                response_format="brief"
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            assert result.output_level == OutputLevel.STANDARD

    def test_standard_response_format(self, sample_sqlite_db, clear_sqlite_connections):
        """测试标准响应格式"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_impl(
                query="SELECT * FROM users",
                response_format="standard"
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            assert result.output_level == OutputLevel.STANDARD

    def test_full_response_format(self, sample_sqlite_db, clear_sqlite_connections):
        """测试详细响应格式"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_impl(
                query="SELECT * FROM users",
                response_format="full"
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            assert result.output_level == OutputLevel.STANDARD

    def test_with_query_execution(self, sample_sqlite_db, clear_sqlite_connections):
        """测试 WITH 查询执行"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_impl(
                query="WITH ranked AS (SELECT * FROM users) SELECT * FROM ranked"
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success

    def test_invalid_query_type(self, sample_sqlite_db, clear_sqlite_connections):
        """测试无效的查询类型（安全检查）"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_impl(query="INSERT INTO users VALUES (1, 'Test')")

            assert isinstance(result, ToolExecutionResult)
            assert not result.success
            assert "SecurityError" in result.error_type

    def test_invalid_connection(self, clear_sqlite_connections):
        """测试无效的连接"""
        with patch('tools.database._get_sqlite_connection') as mock_get:
            mock_get.side_effect = sqlite3.Error("Unable to open database")

            result = query_database_impl(
                query="SELECT * FROM users",
                connection="nonexistent"
            )

            assert isinstance(result, ToolExecutionResult)
            assert not result.success


class TestQueryDatabaseTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert query_database_tool.name == "query_database"
        assert "SQLite" in query_database_tool.description or "SQL" in query_database_tool.description

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(query_database_tool, StructuredTool)

    def test_tool_args_schema(self):
        """测试工具参数模式"""
        assert query_database_tool.args_schema == DatabaseQueryInput

    def test_tool_invocation(self, sample_sqlite_db, clear_sqlite_connections):
        """测试工具调用"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_tool.invoke({
                "query": "SELECT id, name FROM users"
            })

            assert isinstance(result, ToolExecutionResult)
            assert result.success

    def test_tool_with_max_rows(self, sample_sqlite_db, clear_sqlite_connections):
        """测试工具带最大行数参数"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_tool.invoke({
                "query": "SELECT * FROM users",
                "max_rows": 2
            })

            assert isinstance(result, ToolExecutionResult)
            assert result.success

    def test_tool_with_connection(self, sample_sqlite_db, clear_sqlite_connections):
        """测试工具带连接参数"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_tool.invoke({
                "query": "SELECT * FROM sales",
                "connection": "sqlite"
            })

            assert isinstance(result, ToolExecutionResult)
            assert result.tool_name == "query_database"


class TestQueryDatabaseIntegration:
    """数据库查询工具集成测试"""

    def test_full_query_workflow(self, sample_sqlite_db, clear_sqlite_connections):
        """测试完整查询工作流"""
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            # 1. 创建输入
            input_data = DatabaseQueryInput(
                query="SELECT id, name, email FROM users",
                max_rows=100
            )

            # 2. 执行查询
            result = query_database_impl(
                query=input_data.query,
                max_rows=input_data.max_rows
            )

            # 3. 验证结果
            assert isinstance(result, ToolExecutionResult)
            assert result.success
            assert result.tool_name == "query_database"

    def test_tool_chain_with_structured_tool(self, sample_sqlite_db, clear_sqlite_connections):
        """测试与 LangChain StructuredTool 的集成"""
        from langchain_core.tools import StructuredTool

        # 确保工具是 StructuredTool
        assert isinstance(query_database_tool, StructuredTool)

        # 调用工具 - 需要 patch 数据目录
        with patch('tools.database._DATA_DIR', sample_sqlite_db.parent):
            result = query_database_tool.invoke({
                "query": "SELECT COUNT(*) as total FROM users"
            })

            # 验证结果
            assert isinstance(result, ToolExecutionResult)
            assert result.success


class TestDatabaseConfig:
    """测试数据库配置"""

    def test_default_config_is_sqlite(self):
        """测试默认配置是 SQLite"""
        from config import get_config

        config = get_config()
        if hasattr(config, 'database'):
            db_config = config.database
            # 默认应该是 SQLite
            assert getattr(db_config, 'type', 'sqlite') == 'sqlite'

    def test_data_directory_created(self):
        """测试数据目录自动创建"""
        assert _DATA_DIR.exists()
        assert _DATA_DIR.is_dir()
