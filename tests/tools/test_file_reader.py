"""
文件读取工具单元测试
"""

import ast
import json
import os
import pytest
import tempfile
from pathlib import Path
from pydantic import ValidationError

from tools.file_reader import (
    FileReadInput,
    file_reader_impl,
    file_reader_tool,
    DEFAULT_ALLOWED_PATHS,
    _detect_format,
    _parse_python_metadata,
    _parse_sql_queries,
    _read_csv,
    _read_excel,
    _read_json,
    _read_text,
    _read_python,
    _read_sql,
)


class TestFileReadInput:
    """测试 FileReadInput 模型"""

    def test_valid_path(self):
        """测试有效的路径"""
        input_data = FileReadInput(path="./data/test.csv")
        assert input_data.path == "./data/test.csv"
        assert input_data.encoding == "utf-8"
        assert input_data.format is None
        assert input_data.sheet_name == 0
        assert input_data.nrows is None
        assert input_data.parse_metadata is False

    def test_custom_format(self):
        """测试自定义格式"""
        input_data = FileReadInput(
            path="./data/test.csv",
            format="csv"
        )
        assert input_data.format == "csv"

    def test_python_format(self):
        """测试 Python 格式"""
        input_data = FileReadInput(
            path="./skills/test/main.py",
            format="python"
        )
        assert input_data.format == "python"

    def test_sql_format(self):
        """测试 SQL 格式"""
        input_data = FileReadInput(
            path="./data/query.sql",
            format="sql"
        )
        assert input_data.format == "sql"

    def test_parse_metadata_true(self):
        """测试启用元数据解析"""
        input_data = FileReadInput(
            path="./skills/test/main.py",
            parse_metadata=True
        )
        assert input_data.parse_metadata is True

    def test_custom_encoding(self):
        """测试自定义编码"""
        input_data = FileReadInput(
            path="./data/test.csv",
            encoding="gbk"
        )
        assert input_data.encoding == "gbk"

    def test_custom_sheet_name(self):
        """测试自定义工作表"""
        input_data = FileReadInput(
            path="./data/test.xlsx",
            sheet_name="Sheet2"
        )
        assert input_data.sheet_name == "Sheet2"

    def test_custom_nrows(self):
        """测试自定义行数限制"""
        input_data = FileReadInput(
            path="./data/test.csv",
            nrows=100
        )
        assert input_data.nrows == 100

    def test_empty_path(self):
        """测试空路径"""
        with pytest.raises(ValidationError) as exc_info:
            FileReadInput(path="")
        assert "路径" in str(exc_info.value) or "path" in str(exc_info.value).lower()

    def test_whitespace_path(self):
        """测试空白路径"""
        with pytest.raises(ValidationError) as exc_info:
            FileReadInput(path="   ")
        assert "路径" in str(exc_info.value) or "path" in str(exc_info.value).lower()

    def test_path_traversal_attack(self):
        """测试路径遍历攻击保护"""
        with pytest.raises(ValidationError) as exc_info:
            FileReadInput(path="../etc/passwd")
        assert ".." in str(exc_info.value)

    def test_path_traversal_in_middle(self):
        """测试路径中间的遍历攻击"""
        with pytest.raises(ValidationError) as exc_info:
            FileReadInput(path="./data/../../etc/passwd")
        assert ".." in str(exc_info.value)

    def test_invalid_format(self):
        """测试无效的格式"""
        with pytest.raises(ValidationError) as exc_info:
            FileReadInput(
                path="./data/test.csv",
                format="xml"
            )
        assert "format" in str(exc_info.value).lower()

    def test_nrows_below_minimum(self):
        """测试行数限制低于最小值"""
        with pytest.raises(ValidationError) as exc_info:
            FileReadInput(
                path="./data/test.csv",
                nrows=0
            )
        assert "nrows" in str(exc_info.value).lower() or "大于" in str(exc_info.value)

    def test_negative_nrows(self):
        """测试负数行数限制"""
        with pytest.raises(ValidationError) as exc_info:
            FileReadInput(
                path="./data/test.csv",
                nrows=-10
            )
        assert "nrows" in str(exc_info.value).lower() or "大于" in str(exc_info.value)

    def test_all_formats(self):
        """测试所有支持的格式"""
        formats = ["csv", "excel", "json", "text", "python", "sql"]

        for fmt in formats:
            input_data = FileReadInput(
                path=f"./data/test.{fmt}",
                format=fmt
            )
            assert input_data.format == fmt

    def test_format_case_insensitive(self):
        """测试格式大小写不敏感"""
        input_data = FileReadInput(
            path="./data/test.csv",
            format="CSV"
        )
        assert input_data.format == "csv"

    def test_allowed_paths(self):
        """测试允许的路径"""
        allowed_paths = [
            "./data/test.csv",
            "./tmp/test.txt",
            "./skills/test/main.py",
            "/data/test.csv",
            "/tmp/test.txt",
            "./test.csv",
            "test.csv",
        ]

        for path in allowed_paths:
            input_data = FileReadInput(path=path)
            assert input_data.path == path

    def test_absolute_path_not_allowed(self):
        """测试不允许的绝对路径"""
        with pytest.raises(ValidationError) as exc_info:
            FileReadInput(path="/etc/passwd")
        assert "允许" in str(exc_info.value) or "allowed" in str(exc_info.value).lower()


class TestDetectFormat:
    """测试格式检测"""

    def test_detect_csv(self):
        """测试检测 CSV"""
        assert _detect_format("test.csv") == "csv"
        assert _detect_format("./data/test.CSV") == "csv"

    def test_detect_excel_xlsx(self):
        """测试检测 XLSX"""
        assert _detect_format("test.xlsx") == "excel"
        assert _detect_format("./data/test.XLSX") == "excel"

    def test_detect_excel_xls(self):
        """测试检测 XLS"""
        assert _detect_format("test.xls") == "excel"

    def test_detect_json(self):
        """测试检测 JSON"""
        assert _detect_format("test.json") == "json"
        assert _detect_format("./data/test.JSON") == "json"

    def test_detect_text_txt(self):
        """测试检测 TXT"""
        assert _detect_format("test.txt") == "text"

    def test_detect_text_md(self):
        """测试检测 Markdown"""
        assert _detect_format("test.md") == "text"

    def test_detect_text_log(self):
        """测试检测 LOG"""
        assert _detect_format("test.log") == "text"

    def test_detect_python(self):
        """测试检测 Python"""
        assert _detect_format("test.py") == "python"
        assert _detect_format("./skills/main.PY") == "python"

    def test_detect_sql(self):
        """测试检测 SQL"""
        assert _detect_format("test.sql") == "sql"
        assert _detect_format("./data/query.SQL") == "sql"

    def test_detect_unknown_extension(self):
        """测试未知扩展名默认为 text"""
        assert _detect_format("test.unknown") == "text"
        assert _detect_format("test") == "text"


class TestParsePythonMetadata:
    """测试 Python 元数据解析"""

    def test_parse_simple_function(self):
        """测试解析简单函数"""
        code = '''
def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"
'''
        metadata = _parse_python_metadata(code)
        assert len(metadata["functions"]) == 1
        assert metadata["functions"][0]["name"] == "hello"
        assert metadata["functions"][0]["args"] == ["name"]
        assert metadata["functions"][0]["docstring"] == "Say hello to someone."

    def test_parse_class_with_methods(self):
        """测试解析类及其方法"""
        code = '''
class DataProcessor:
    """Process data for analysis."""

    def __init__(self, config):
        self.config = config

    def process(self, data):
        """Process the data."""
        return data
'''
        metadata = _parse_python_metadata(code)
        assert len(metadata["classes"]) == 1
        assert metadata["classes"][0]["name"] == "DataProcessor"
        assert "process" in metadata["classes"][0]["methods"]
        assert "__init__" in metadata["classes"][0]["methods"]
        assert metadata["classes"][0]["docstring"] == "Process data for analysis."

    def test_parse_imports(self):
        """测试解析导入"""
        code = '''
import pandas as pd
import numpy as np
from sklearn.modelization import train_test_split
from .local_module import local_function
'''
        metadata = _parse_python_metadata(code)
        assert len(metadata["imports"]) == 4

        import_modules = [imp["module"] for imp in metadata["imports"]]
        assert "pandas" in import_modules
        assert "numpy" in import_modules
        assert "sklearn.modelization.train_test_split" in import_modules

    def test_parse_syntax_error(self):
        """测试解析语法错误的代码"""
        code = '''
def broken(
    # Missing closing paren
'''
        metadata = _parse_python_metadata(code)
        assert "parse_error" in metadata

    def test_parse_empty_code(self):
        """测试解析空代码"""
        metadata = _parse_python_metadata("")
        assert len(metadata["functions"]) == 0
        assert len(metadata["classes"]) == 0
        assert len(metadata["imports"]) == 0


class TestParseSqlQueries:
    """测试 SQL 查询解析"""

    def test_parse_single_query(self):
        """测试解析单个查询"""
        sql = "SELECT * FROM users WHERE id = 1;"
        queries = _parse_sql_queries(sql)
        assert len(queries) == 1
        assert "SELECT * FROM users" in queries[0]

    def test_parse_multiple_queries(self):
        """测试解析多个查询"""
        sql = """
SELECT * FROM users;
SELECT * FROM orders WHERE status = 'pending';
DELETE FROM logs WHERE created_at < '2024-01-01';
"""
        queries = _parse_sql_queries(sql)
        assert len(queries) == 3
        assert any("users" in q for q in queries)
        assert any("orders" in q for q in queries)
        assert any("logs" in q for q in queries)

    def test_remove_single_line_comments(self):
        """测试移除单行注释"""
        sql = """
-- This is a comment
SELECT * FROM users;  -- inline comment
"""
        queries = _parse_sql_queries(sql)
        assert len(queries) == 1
        assert "comment" not in queries[0]

    def test_remove_multi_line_comments(self):
        """测试移除多行注释"""
        sql = """
/* This is a
multi-line comment */
SELECT * FROM users;
"""
        queries = _parse_sql_queries(sql)
        assert len(queries) == 1
        assert "multi-line" not in queries[0]

    def test_filter_empty_queries(self):
        """测试过滤空查询"""
        sql = "SELECT * FROM users;;\n\n;\nSELECT * FROM orders;"
        queries = _parse_sql_queries(sql)
        assert len(queries) == 2


class TestReadPython:
    """测试 Python 文件读取"""

    def test_read_valid_python(self):
        """测试读取有效的 Python 文件"""
        code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

class Calculator:
    """A simple calculator."""
    pass
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # 创建 ./skills 目录
            os.makedirs("./skills/test", exist_ok=True)
            allowed_path = "./skills/test/main.py"
            os.rename(temp_path, allowed_path)

            result = _read_python(allowed_path, "utf-8")
            assert result["success"] is True
            assert result["format"] == "python"
            assert result["lines"] >= 8  # 至少 8 行（可能因空行而不同）
            assert "def add" in result["content"]
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)

    def test_read_python_with_metadata(self):
        """测试读取 Python 文件并解析元数据"""
        code = '''
import pandas as pd

def analyze(data):
    """Analyze data."""
    return data.describe()
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            os.makedirs("./skills/test", exist_ok=True)
            allowed_path = "./skills/test/main.py"
            os.rename(temp_path, allowed_path)

            result = _read_python(allowed_path, "utf-8", parse_metadata=True)
            assert result["success"] is True
            assert "metadata" in result
            assert len(result["metadata"]["functions"]) == 1
            assert result["metadata"]["functions"][0]["name"] == "analyze"
            assert "pandas" in [imp["module"] for imp in result["metadata"]["imports"]]
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)


class TestReadSql:
    """测试 SQL 文件读取"""

    def test_read_valid_sql(self):
        """测试读取有效的 SQL 文件"""
        sql = "-- Get all users\nSELECT * FROM users WHERE active = true;"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(sql)
            temp_path = f.name

        try:
            os.makedirs("./data", exist_ok=True)
            allowed_path = "./data/query.sql"
            os.rename(temp_path, allowed_path)

            result = _read_sql(allowed_path, "utf-8")
            assert result["success"] is True
            assert result["format"] == "sql"
            assert "SELECT * FROM users" in result["content"]
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)

    def test_read_sql_with_metadata(self):
        """测试读取 SQL 文件并解析查询"""
        sql = """
SELECT * FROM users;
SELECT * FROM orders WHERE status = 'pending';
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(sql)
            temp_path = f.name

        try:
            os.makedirs("./data", exist_ok=True)
            allowed_path = "./data/query.sql"
            os.rename(temp_path, allowed_path)

            result = _read_sql(allowed_path, "utf-8", parse_metadata=True)
            assert result["success"] is True
            assert "queries" in result
            assert result["query_count"] == 2
            assert any("users" in q for q in result["queries"])
            assert any("orders" in q for q in result["queries"])
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)


class TestReadJson:
    """测试 JSON 读取"""

    def test_read_valid_json(self):
        """测试读取有效的 JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"key": "value", "number": 42}, f)
            temp_path = f.name

        try:
            # 创建 ./data 目录
            os.makedirs("./data", exist_ok=True)
            # 移动文件到允许的路径
            allowed_path = "./data/test.json"
            os.rename(temp_path, allowed_path)

            result = _read_json(allowed_path, "utf-8")
            assert result["success"] is True
            assert result["format"] == "json"
            assert result["data"]["key"] == "value"
            assert result["data"]["number"] == 42
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)

    def test_read_invalid_json(self):
        """测试读取无效的 JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json}")
            temp_path = f.name

        try:
            os.makedirs("./data", exist_ok=True)
            allowed_path = "./data/invalid.json"
            os.rename(temp_path, allowed_path)

            result = _read_json(allowed_path, "utf-8")
            assert result["success"] is False
            assert "JSON 解析失败" in result["error"]
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)


class TestReadText:
    """测试文本读取"""

    def test_read_simple_text(self):
        """测试读取简单文本"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Hello, World!\nLine 2\nLine 3")
            temp_path = f.name

        try:
            os.makedirs("./data", exist_ok=True)
            allowed_path = "./data/test.txt"
            os.rename(temp_path, allowed_path)

            result = _read_text(allowed_path, "utf-8")
            assert result["success"] is True
            assert result["format"] == "text"
            assert result["lines"] == 3
            assert "Hello, World!" in result["content"]
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)

    def test_read_text_with_nrows(self):
        """测试读取文本时限制行数"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for i in range(100):
                f.write(f"Line {i}\n")
            temp_path = f.name

        try:
            os.makedirs("./data", exist_ok=True)
            allowed_path = "./data/test.txt"
            os.rename(temp_path, allowed_path)

            result = _read_text(allowed_path, "utf-8", nrows=10)
            assert result["success"] is True
            assert result["lines"] == 10
            assert "Line 0" in result["content"]
            assert "Line 9" in result["content"]
            assert "Line 10" not in result["content"]
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)


class TestFileReaderImpl:
    """测试 file_reader_impl 函数"""

    def test_read_nonexistent_file(self):
        """测试读取不存在的文件"""
        result = file_reader_impl(path="./data/nonexistent.csv")
        result_dict = json.loads(result)
        assert result_dict["success"] is False
        assert "不存在" in result_dict["error"]

    def test_read_directory_as_file(self):
        """测试将目录作为文件读取"""
        os.makedirs("./data", exist_ok=True)
        result = file_reader_impl(path="./data")
        result_dict = json.loads(result)
        assert result_dict["success"] is False
        assert "不是文件" in result_dict["error"]

    def test_read_python_file_impl(self):
        """测试通过实现函数读取 Python 文件"""
        code = 'def test(): pass'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            os.makedirs("./skills/test", exist_ok=True)
            allowed_path = "./skills/test/main.py"
            os.rename(temp_path, allowed_path)

            result = file_reader_impl(path=allowed_path)
            result_dict = json.loads(result)
            assert result_dict["success"] is True
            assert result_dict["format"] == "python"
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)

    def test_read_sql_file_impl(self):
        """测试通过实现函数读取 SQL 文件"""
        sql = "SELECT * FROM test;"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(sql)
            temp_path = f.name

        try:
            os.makedirs("./data", exist_ok=True)
            allowed_path = "./data/query.sql"
            os.rename(temp_path, allowed_path)

            result = file_reader_impl(path=allowed_path, parse_metadata=True)
            result_dict = json.loads(result)
            assert result_dict["success"] is True
            assert result_dict["format"] == "sql"
            assert "queries" in result_dict
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)


class TestFileReaderTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert file_reader_tool.name == "read_file"
        assert "read_file" in str(file_reader_tool.args_schema) or "FileReadInput" in str(file_reader_tool.args_schema)
        assert "读取" in file_reader_tool.description or "read" in file_reader_tool.description.lower()

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(file_reader_tool, StructuredTool)

    def test_tool_invocation(self):
        """测试工具调用"""
        # 创建测试文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            os.makedirs("./data", exist_ok=True)
            allowed_path = "./data/test.txt"
            os.rename(temp_path, allowed_path)

            result = file_reader_tool.invoke({
                "path": allowed_path,
                "format": "text",
                "encoding": "utf-8",
            })
            result_dict = json.loads(result)
            assert result_dict["success"] is True
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)

    def test_tool_invocation_python(self):
        """测试工具调用读取 Python 文件"""
        code = 'def hello(): return "world"'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            os.makedirs("./skills/test", exist_ok=True)
            allowed_path = "./skills/test/main.py"
            os.rename(temp_path, allowed_path)

            result = file_reader_tool.invoke({
                "path": allowed_path,
                "parse_metadata": True,
            })
            result_dict = json.loads(result)
            assert result_dict["success"] is True
            assert result_dict["format"] == "python"
            assert "metadata" in result_dict
        finally:
            if os.path.exists(allowed_path):
                os.remove(allowed_path)


class TestFileReaderParams:
    """测试参数组合"""

    def test_all_parameters(self):
        """测试所有参数"""
        input_data = FileReadInput(
            path="./data/test.xlsx",
            format="excel",
            encoding="utf-8",
            sheet_name="Data",
            nrows=50
        )
        assert input_data.path == "./data/test.xlsx"
        assert input_data.format == "excel"
        assert input_data.encoding == "utf-8"
        assert input_data.sheet_name == "Data"
        assert input_data.nrows == 50

    def test_minimal_parameters(self):
        """测试最小参数（只有 path）"""
        input_data = FileReadInput(path="./data/test.csv")
        assert input_data.path == "./data/test.csv"
        assert input_data.format is None  # 默认值
        assert input_data.encoding == "utf-8"  # 默认值
        assert input_data.sheet_name == 0  # 默认值
        assert input_data.nrows is None  # 默认值

    def test_sheet_name_as_integer(self):
        """测试工作表索引为整数"""
        input_data = FileReadInput(
            path="./data/test.xlsx",
            sheet_name=2
        )
        assert input_data.sheet_name == 2

    def test_python_file_with_parse_metadata(self):
        """测试 Python 文件启用元数据解析"""
        input_data = FileReadInput(
            path="./skills/test/main.py",
            format="python",
            parse_metadata=True
        )
        assert input_data.format == "python"
        assert input_data.parse_metadata is True

    def test_sql_file_with_parse_metadata(self):
        """测试 SQL 文件启用元数据解析"""
        input_data = FileReadInput(
            path="./data/query.sql",
            format="sql",
            parse_metadata=True
        )
        assert input_data.format == "sql"
        assert input_data.parse_metadata is True


class TestDefaultAllowedPaths:
    """测试默认允许的路径"""

    def test_default_allowed_paths_constant(self):
        """测试默认允许路径常量"""
        assert isinstance(DEFAULT_ALLOWED_PATHS, list)
        assert len(DEFAULT_ALLOWED_PATHS) > 0
        assert "/data" in DEFAULT_ALLOWED_PATHS
        assert "/tmp" in DEFAULT_ALLOWED_PATHS
        assert "./data" in DEFAULT_ALLOWED_PATHS
        assert "./tmp" in DEFAULT_ALLOWED_PATHS
        assert "./skills" in DEFAULT_ALLOWED_PATHS
