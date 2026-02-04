"""
数据库查询工具单元测试
"""

import pytest
from pydantic import ValidationError

from tools.database import (
    DatabaseQueryInput,
    query_database_impl,
    query_database_tool,
    _format_result,
)
from models.tool_output import ToolOutput


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

    def test_trailing_semicolon(self):
        """测试结尾分号"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users;"
        )
        # 分号应该被移除
        assert ";" not in input_data.query
        assert "SELECT" in input_data.query

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

    def test_params_with_tuple(self):
        """测试元组参数"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users WHERE id IN :ids",
            params={"ids": (1, 2, 3)}
        )
        assert input_data.params == {"ids": (1, 2, 3)}

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

    def test_response_format_concise(self):
        """测试简洁响应格式"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users",
            response_format="concise"
        )
        assert input_data.response_format == "concise"

    def test_response_format_detailed(self):
        """测试详细响应格式"""
        input_data = DatabaseQueryInput(
            query="SELECT * FROM users",
            response_format="detailed"
        )
        assert input_data.response_format == "detailed"

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

    def test_forbidden_keyword_in_middle(self):
        """测试中间位置的禁止关键字（在子查询中）"""
        with pytest.raises(ValidationError, match="禁止的关键字"):
            DatabaseQueryInput(query="SELECT * FROM users WHERE id IN (SELECT id FROM (SELECT DELETE FROM temp) AS subquery)")

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
        result_json = query_database_impl(query="SELECT * FROM users")
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert "成功" in result.summary
        assert result.result is not None
        assert "rows" in result.result
        assert "columns" in result.result

    def test_query_with_specific_columns(self):
        """测试指定列的查询"""
        result_json = query_database_impl(query="SELECT id, name, email FROM users")
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result["columns"] == ["id", "name", "email"]

    def test_query_with_wildcard(self):
        """测试通配符查询"""
        result_json = query_database_impl(query="SELECT * FROM sales")
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert "columns" in result.result

    def test_max_rows_limit(self):
        """测试最大行数限制"""
        result_json = query_database_impl(
            query="SELECT * FROM users",
            max_rows=10
        )
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result["row_count"] <= 10

    def test_concise_response_format(self):
        """测试简洁响应格式"""
        result_json = query_database_impl(
            query="SELECT * FROM users",
            response_format="concise"
        )
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result is None  # Concise 格式不返回详细数据
        assert "成功" in result.summary

    def test_standard_response_format(self):
        """测试标准响应格式"""
        result_json = query_database_impl(
            query="SELECT * FROM users",
            response_format="standard"
        )
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result is not None
        assert "rows" in result.result

    def test_detailed_response_format(self):
        """测试详细响应格式"""
        result_json = query_database_impl(
            query="SELECT * FROM users",
            response_format="detailed"
        )
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result is not None

    def test_invalid_connection_name(self):
        """测试无效的连接名称"""
        result_json = query_database_impl(
            query="SELECT * FROM users",
            connection="nonexistent"
        )
        result = ToolOutput.model_validate_json(result_json)

        assert not result.telemetry.success
        assert "失败" in result.summary

    def test_with_query_execution(self):
        """测试 WITH 查询执行"""
        result_json = query_database_impl(
            query="WITH ranked AS (SELECT * FROM users) SELECT * FROM ranked"
        )
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert "成功" in result.summary

    def test_observation_format(self):
        """测试 Observation 格式"""
        result_json = query_database_impl(query="SELECT * FROM users")
        result = ToolOutput.model_validate_json(result_json)

        assert "Observation:" in result.observation
        assert "Status:" in result.observation

    def test_telemetry_collected(self):
        """测试遥测数据收集"""
        result_json = query_database_impl(query="SELECT * FROM users")
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.tool_name == "query_database"
        assert result.telemetry.latency_ms >= 0
        assert result.telemetry.execution_id != ""


class TestQueryDatabaseTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert query_database_tool.name == "query_database"
        assert "SQL" in query_database_tool.description
        assert "SELECT" in query_database_tool.description

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

        # 结果应该是 JSON 字符串
        assert isinstance(result, str)
        # 可以解析为 ToolOutput
        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success

    def test_tool_with_max_rows(self):
        """测试工具带最大行数参数"""
        result = query_database_tool.invoke({
            "query": "SELECT * FROM users",
            "max_rows": 5
        })

        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success
        assert output.result["row_count"] <= 5

    def test_tool_with_connection(self):
        """测试工具带连接参数"""
        result = query_database_tool.invoke({
            "query": "SELECT * FROM sales",
            "connection": "primary"
        })

        output = ToolOutput.model_validate_json(result)
        # 即使连接不存在，工具也应该正常处理错误
        assert output.telemetry is not None

    def test_tool_description_contains_security_info(self):
        """测试工具描述包含安全信息"""
        description = query_database_tool.description
        assert "参数化查询" in description or "防止" in description
        assert "只读" in description or "SELECT" in description


class TestQueryDatabaseIntegration:
    """集成测试"""

    def test_full_query_workflow(self):
        """测试完整查询工作流"""
        # 1. 创建输入
        input_data = DatabaseQueryInput(
            query="SELECT id, name, email FROM users WHERE active = true",
            max_rows=100,
            response_format="standard"
        )

        # 2. 执行查询
        result_json = query_database_impl(
            query=input_data.query,
            max_rows=input_data.max_rows,
            response_format=input_data.response_format
        )

        # 3. 解析结果
        result = ToolOutput.model_validate_json(result_json)

        # 4. 验证
        assert result.telemetry.success
        assert "成功" in result.summary
        assert result.result["columns"] == ["id", "name", "email"]
        assert result.result["row_count"] <= 100
        assert "Observation:" in result.observation

    def test_tool_chain_with_structured_tool(self):
        """测试通过 StructuredTool 链式调用"""
        # 使用 LangChain 工具调用
        result = query_database_tool.invoke({
            "query": "SELECT category, COUNT(*) as count FROM sales GROUP BY category",
            "response_format": "detailed"
        })

        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success
        assert output.result is not None
