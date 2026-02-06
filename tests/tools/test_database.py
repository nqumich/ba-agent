"""
数据库查询工具单元测试 (v2.1 - Pipeline Only)
"""

import pytest
from pydantic import ValidationError

from tools.database import (
    DatabaseQueryInput,
    query_database_impl,
    query_database_tool,
    _format_result,
)

# Pipeline v2.1 模型
from backend.models.pipeline import ToolExecutionResult, OutputLevel


class TestDatabaseQueryInput:
    """测试 DatabaseQueryInput 模型"""

    def test_basic_query(self):
        """测试基本查询输入"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users"
        )
        assert input_data.query == "SELECT * FROM users"
        assert input_data.connection == "primary"
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
            connection="clickhouse"
        )
        assert input_data.connection == "clickhouse"

    def test_params_dict(self):
        """测试参数化查询参数"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users WHERE category = :category",
            params={"category": "premium"}
        )
        assert input_data.params == {"category": "premium"}

    def test_params_with_list(self):
        """测试列表参数（用于 IN 子句）"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users WHERE id IN :ids",
            params={"ids": [1, 2, 3]}
        )
        assert input_data.params == {"ids": [1, 2, 3]}

    def test_max_rows_custom(self):
        """测试自定义最大行数"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users",
            max_rows=500
        )
        assert input_data.max_rows == 500

    def test_max_rows_boundary(self):
        """测试最大行数边界值"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users",
            max_rows=10000
        )
        assert input_data.max_rows == 10000

    def test_response_format_brief(self):
        """测试简洁响应格式"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users",
            response_format="brief"
        )
        assert input_data.response_format == "brief"

    def test_response_format_standard(self):
        """测试标准响应格式"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users",
            response_format="standard"
        )
        assert input_data.response_format == "standard"

    def test_query_normalization(self):
        """测试查询标准化（多余空格）"""
        input_data = DatabaseQueryInput(
            query="SELECT   *    FROM     users"
        )
        assert input_data.query == "SELECT * FROM users"

    def test_invalid_query_delete(self):
        """测试禁止的 DELETE 语句"""
        with pytest.raises(ValidationError, match="禁止的关键字"):
            DatabaseQueryInput(query="SELECT * FROM (SELECT DELETE FROM temp) AS subquery")

    def test_invalid_query_drop(self):
        """测试禁止的 DROP 语句"""
        with pytest.raises(ValidationError, match="禁止的关键字"):
            DatabaseQueryInput(query="SELECT * FROM (SELECT DROP FROM temp) AS subquery")

    def test_invalid_query_update(self):
        """测试禁止的 UPDATE 语句"""
        with pytest.raises(ValidationError, match="禁止的关键字"):
            DatabaseQueryInput(query="SELECT * FROM (SELECT UPDATE FROM temp) AS subquery")

    def test_invalid_query_insert(self):
        """测试禁止的 INSERT 语句"""
        with pytest.raises(ValidationError, match="禁止的关键字"):
            DatabaseQueryInput(query="SELECT * FROM (SELECT INSERT FROM temp) AS subquery")

    def test_invalid_query_alter(self):
        """测试禁止的 ALTER 语句"""
        with pytest.raises(ValidationError, match="禁止的关键字"):
            DatabaseQueryInput(query="SELECT * FROM (SELECT ALTER FROM temp) AS subquery")

    def test_delete_statement_blocked(self):
        """测试 DELETE 语句被阻止"""
        with pytest.raises(ValidationError, match="仅允许执行"):
            DatabaseQueryInput(query="DELETE FROM users")

    def test_drop_statement_blocked(self):
        """测试 DROP 语句被阻止"""
        with pytest.raises(ValidationError, match="仅允许执行"):
            DatabaseQueryInput(query="DROP TABLE users")

    def test_update_statement_blocked(self):
        """测试 UPDATE 语句被阻止"""
        with pytest.raises(ValidationError, match="仅允许执行"):
            DatabaseQueryInput(query="UPDATE users SET name = 'test'")

    def test_insert_statement_blocked(self):
        """测试 INSERT 语句被阻止"""
        with pytest.raises(ValidationError, match="仅允许执行"):
            DatabaseQueryInput(query="INSERT INTO users VALUES (1, 'test')")

    def test_sql_comment_dash(self):
        """测试禁止的 SQL 注释（--）"""
        with pytest.raises(ValidationError, match="不能包含 SQL 注释"):
            DatabaseQueryInput(query="SELECT * FROM users -- comment")

    def test_sql_comment_block(self):
        """测试禁止的 SQL 块注释（/* */）"""
        with pytest.raises(ValidationError, match="不能包含 SQL 注释"):
            DatabaseQueryInput(query="SELECT * FROM users /* comment */")

    def test_multiple_statements(self):
        """测试多条语句（分号分隔）"""
        with pytest.raises(ValidationError, match="仅允许执行单条"):
            DatabaseQueryInput(query="SELECT * FROM users; SELECT * FROM orders")

    def test_empty_query(self):
        """测试空查询"""
        with pytest.raises(ValidationError):
            DatabaseQueryInput(query="")

    def test_max_rows_exceeds_limit(self):
        """测试超过最大行数限制"""
        with pytest.raises(ValidationError):
            DatabaseQueryInput(query="SELECT * FROM users", max_rows=10001)

    def test_max_rows_below_minimum(self):
        """测试低于最小行数"""
        with pytest.raises(ValidationError):
            DatabaseQueryInput(query="SELECT * FROM users", max_rows=0)

    def test_params_unsafe_type(self):
        """测试不安全的参数类型"""
        with pytest.raises(ValidationError, match="类型不安全"):
            DatabaseQueryInput(
                query="SELECT * FROM users WHERE data = :data",
                params={"data": {"key": "value"}}  # 字典不安全
            )

    def test_params_list_unsafe_element(self):
        """测试列表中的不安全元素类型"""
        with pytest.raises(ValidationError, match="元素类型不安全"):
            DatabaseQueryInput(
                query="SELECT * FROM users WHERE id IN :ids",
                params={"ids": [1, 2, {"key": "value"}]}
            )


class TestFormatResult:
    """测试结果格式化"""

    def test_format_basic_result(self):
        """测试基本结果格式化"""
        rows = [{"id": 1, "name": "Alice"}]
        columns = ["id", "name"]
        result = _format_result(rows, columns)

        assert result["columns"] == columns
        assert result["rows"] == rows
        assert result["row_count"] == 1
        assert result["column_count"] == 2

    def test_format_empty_result(self):
        """测试空结果格式化"""
        rows = []
        columns = ["id", "name"]
        result = _format_result(rows, columns)

        assert result["row_count"] == 0
        assert result["column_count"] == 2

    def test_format_multiple_rows(self):
        """测试多行结果格式化"""
        rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"}
        ]
        columns = ["id", "name"]
        result = _format_result(rows, columns)

        assert result["row_count"] == 3
        assert len(result["rows"]) == 3


class TestQueryDatabaseImpl:
    """测试查询实现函数"""

    def test_basic_query_execution(self):
        """测试基本查询执行"""
        result = query_database_impl(query="SELECT * FROM users")

        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert len(result.observation) > 0

    def test_query_with_specific_columns(self):
        """测试指定列的查询"""
        result = query_database_impl(query="SELECT id, name, email FROM users")

        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert len(result.observation) > 0

    def test_query_with_wildcard(self):
        """测试通配符查询"""
        result = query_database_impl(query="SELECT * FROM sales")

        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_max_rows_limit(self):
        """测试最大行数限制"""
        result = query_database_impl(
            query="SELECT * FROM users",
            max_rows=10
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_brief_response_format(self):
        """测试简洁响应格式"""
        result = query_database_impl(
            query="SELECT * FROM users",
            response_format="brief"
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert result.output_level == OutputLevel.BRIEF

    def test_standard_response_format(self):
        """测试标准响应格式"""
        result = query_database_impl(
            query="SELECT * FROM users",
            response_format="standard"
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert result.output_level == OutputLevel.STANDARD

    def test_full_response_format(self):
        """测试详细响应格式"""
        result = query_database_impl(
            query="SELECT * FROM users",
            response_format="full"
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert result.output_level == OutputLevel.FULL

    def test_invalid_connection_name(self):
        """测试无效的连接名称"""
        result = query_database_impl(
            query="SELECT * FROM users",
            connection="nonexistent"
        )

        assert isinstance(result, ToolExecutionResult)
        assert not result.success

    def test_with_query_execution(self):
        """测试 WITH 查询执行"""
        result = query_database_impl(
            query="WITH ranked AS (SELECT * FROM users) SELECT * FROM ranked"
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_observation_format(self):
        """测试 Observation 格式"""
        result = query_database_impl(query="SELECT * FROM users")

        assert isinstance(result, ToolExecutionResult)
        assert len(result.observation) > 0

    def test_telemetry_collected(self):
        """测试遥测数据收集"""
        result = query_database_impl(query="SELECT * FROM users")

        assert isinstance(result, ToolExecutionResult)
        assert result.tool_name == "query_database"
        assert result.duration_ms >= 0


class TestQueryDatabaseTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert query_database_tool.name == "query_database"
        assert "SQL" in query_database_tool.description

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(query_database_tool, StructuredTool)

    def test_tool_args_schema(self):
        """测试工具参数模式"""
        assert query_database_tool.args_schema == DatabaseQueryInput

    def test_tool_invocation(self):
        """测试工具调用"""
        result = query_database_tool.invoke({
            "query": "SELECT id, name FROM users"
        })

        # v2.1: 结果是 ToolExecutionResult
        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_tool_with_max_rows(self):
        """测试工具带最大行数参数"""
        result = query_database_tool.invoke({
            "query": "SELECT * FROM users",
            "max_rows": 5
        })

        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_tool_with_connection(self):
        """测试工具带连接参数"""
        result = query_database_tool.invoke({
            "query": "SELECT * FROM sales",
            "connection": "primary"
        })

        assert isinstance(result, ToolExecutionResult)
        assert result.tool_name == "query_database"


class TestQueryDatabaseIntegration:
    """数据库查询工具集成测试"""

    def test_full_query_workflow(self):
        """测试完整查询工作流"""
        # 1. 创建输入
        input_data = DatabaseQueryInput(
            query="SELECT id, name, email FROM users WHERE active = true",
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

    def test_tool_chain_with_structured_tool(self):
        """测试与 LangChain StructuredTool 的集成"""
        from langchain_core.tools import StructuredTool

        # 确保工具是 StructuredTool
        assert isinstance(query_database_tool, StructuredTool)

        # 调用工具
        result = query_database_tool.invoke({
            "query": "SELECT COUNT(*) as total FROM users"
        })

        # 验证结果
        assert isinstance(result, ToolExecutionResult)
        assert result.success
