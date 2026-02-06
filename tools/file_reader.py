"""
文件读取工具 (v2.1 - Pipeline Only)

支持读取 CSV、Excel、JSON、文本、Python、SQL 文件

v2.1 变更：
- 使用 ToolExecutionResult 返回
- 支持 OutputLevel (BRIEF/STANDARD/FULL)
- 添加 response_format 参数
"""

import ast
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool

# Pipeline v2.1 模型
from backend.models.pipeline import (
    OutputLevel,
    ToolExecutionResult,
    ToolCachePolicy,
)


# 默认允许的路径配置
DEFAULT_ALLOWED_PATHS = [
    "/data",           # 数据目录
    "/tmp",            # 临时目录
    "./data",          # 当前目录下的 data
    "./tmp",           # 当前目录下的 tmp
    ".",               # 当前目录
    "./skills",        # Skills 目录（用于加载技能代码）
]


class FileReadInput(BaseModel):
    """文件读取工具的输入参数"""

    path: str = Field(
        ...,
        description="要读取的文件路径"
    )
    format: Optional[str] = Field(
        default=None,
        description="文件格式: csv, excel, json, text, python, sql。不指定则自动检测"
    )
    encoding: Optional[str] = Field(
        default="utf-8",
        description="文本编码，默认 utf-8"
    )
    sheet_name: Optional[Union[str, int]] = Field(
        default=0,
        description="Excel 工作表名称或索引，默认第一个表"
    )
    nrows: Optional[int] = Field(
        default=None,
        description="最大读取行数（用于预览），None 表示读取全部"
    )
    parse_metadata: Optional[bool] = Field(
        default=False,
        description="是否解析元数据（Python: AST解析函数/类/导入；SQL: 提取查询语句）"
    )
    # 支持 OutputLevel 字符串
    response_format: Optional[str] = Field(
        default="standard",
        description="响应格式: brief, standard, full"
    )

    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str) -> str:
        """验证路径安全性"""
        v = v.strip()
        if not v:
            raise ValueError("文件路径不能为空")

        # 检查路径遍历攻击
        if ".." in v:
            raise ValueError("路径中不能包含 '..'（路径遍历保护）")

        # 检查绝对路径
        path_obj = Path(v).resolve()
        allowed = False
        for allowed_path in DEFAULT_ALLOWED_PATHS:
            allowed_obj = Path(allowed_path).resolve()
            try:
                if path_obj.is_relative_to(allowed_obj):
                    allowed = True
                    break
            except (ValueError, AttributeError):
                # is_relative_to 可能在某些版本不可用
                try:
                    path_obj.relative_to(allowed_obj)
                    allowed = True
                    break
                except ValueError:
                    pass

        if not allowed:
            raise ValueError(
                f"路径 '{v}' 不在允许的目录中。"
                f"允许的目录: {', '.join(DEFAULT_ALLOWED_PATHS)}"
            )

        return v

    @field_validator('format')
    @classmethod
    def validate_format(cls, v: Optional[str]) -> Optional[str]:
        """验证格式参数"""
        if v is None:
            return None
        allowed = ["csv", "excel", "json", "text", "python", "sql"]
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"format 必须是以下之一: {', '.join(allowed)}")
        return v_lower

    @field_validator('nrows')
    @classmethod
    def validate_nrows(cls, v: Optional[int]) -> Optional[int]:
        """验证行数限制"""
        if v is not None and v <= 0:
            raise ValueError("nrows 必须大于 0")
        return v


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


def _detect_format(path: str) -> str:
    """根据文件扩展名检测格式"""
    ext = Path(path).suffix.lower()
    format_map = {
        '.csv': 'csv',
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.json': 'json',
        '.txt': 'text',
        '.md': 'text',
        '.log': 'text',
        '.py': 'python',
        '.sql': 'sql',
    }
    return format_map.get(ext, 'text')


def _parse_python_metadata(code: str) -> dict:
    """
    解析 Python 代码元数据

    使用 AST 解析提取：
    - 导入的模块
    - 定义的函数
    - 定义的类
    """
    metadata = {
        "imports": [],
        "functions": [],
        "classes": [],
    }

    try:
        tree = ast.parse(code)

        # 提取导入
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    metadata["imports"].append({
                        "module": alias.name,
                        "alias": alias.asname
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    metadata["imports"].append({
                        "module": f"{module}.{alias.name}" if module else alias.name,
                        "alias": alias.asname
                    })

        # 提取顶级函数和类
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                metadata["functions"].append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "lineno": node.lineno,
                    "docstring": ast.get_docstring(node)
                })
            elif isinstance(node, ast.ClassDef):
                metadata["classes"].append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "docstring": ast.get_docstring(node),
                    "methods": [
                        n.name for n in node.body if isinstance(n, ast.FunctionDef)
                    ]
                })

    except SyntaxError:
        metadata["parse_error"] = "Python 代码存在语法错误"

    return metadata


def _read_python(path: str, encoding: str, parse_metadata: bool = False) -> dict:
    """
    读取 Python 文件

    Args:
        path: 文件路径
        encoding: 文件编码
        parse_metadata: 是否解析 AST 元数据
    """
    try:
        with open(path, 'r', encoding=encoding) as f:
            code = f.read()

        result = {
            "success": True,
            "format": "python",
            "encoding": encoding,
            "lines": len(code.splitlines()),
            "content": code,
        }

        if parse_metadata:
            result["metadata"] = _parse_python_metadata(code)

        return result

    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(path, 'r', encoding='gbk') as f:
                code = f.read()
            result = {
                "success": True,
                "format": "python",
                "encoding": "gbk",
                "lines": len(code.splitlines()),
                "content": code,
            }
            if parse_metadata:
                result["metadata"] = _parse_python_metadata(code)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"读取 Python 文件失败（尝试了 utf-8 和 gbk）: {str(e)}",
                "format": "python"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"读取 Python 文件失败: {str(e)}",
            "format": "python"
        }


def _parse_sql_queries(content: str) -> list:
    """
    解析 SQL 文件中的查询语句

    按分号分割，并过滤注释和空语句
    """
    # 移除单行注释
    content = re.sub(r'--.*$', '', content, flags=re.MULTILINE)
    # 移除多行注释
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

    # 按分号分割
    queries = []
    for query in content.split(';'):
        query = query.strip()
        if query:
            queries.append(query)

    return queries


def _read_sql(path: str, encoding: str, parse_metadata: bool = False) -> dict:
    """
    读取 SQL 文件

    Args:
        path: 文件路径
        encoding: 文件编码
        parse_metadata: 是否解析查询语句
    """
    try:
        with open(path, 'r', encoding=encoding) as f:
            content = f.read()

        result = {
            "success": True,
            "format": "sql",
            "encoding": encoding,
            "lines": len(content.splitlines()),
            "content": content,
        }

        if parse_metadata:
            result["queries"] = _parse_sql_queries(content)
            result["query_count"] = len(result["queries"])

        return result

    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='gbk') as f:
                content = f.read()
            result = {
                "success": True,
                "format": "sql",
                "encoding": "gbk",
                "lines": len(content.splitlines()),
                "content": content,
            }
            if parse_metadata:
                result["queries"] = _parse_sql_queries(content)
                result["query_count"] = len(result["queries"])
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"读取 SQL 文件失败（尝试了 utf-8 和 gbk）: {str(e)}",
                "format": "sql"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"读取 SQL 文件失败: {str(e)}",
            "format": "sql"
        }


def _read_csv(path: str, encoding: str, nrows: Optional[int] = None) -> dict:
    """读取 CSV 文件"""
    try:
        import pandas as pd
    except ImportError:
        return {
            "success": False,
            "error": "pandas 未安装，无法读取 CSV 文件",
            "format": "csv"
        }

    try:
        df = pd.read_csv(path, encoding=encoding, nrows=nrows)
        return {
            "success": True,
            "format": "csv",
            "rows": len(df),
            "columns": list(df.columns),
            "data": df.to_dict(orient='records'),
            "preview": df.head(10).to_dict(orient='records') if nrows is None else df.to_dict(orient='records')
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"读取 CSV 失败: {str(e)}",
            "format": "csv"
        }


def _read_excel(path: str, sheet_name: Union[str, int], nrows: Optional[int] = None) -> dict:
    """读取 Excel 文件"""
    try:
        import pandas as pd
    except ImportError:
        return {
            "success": False,
            "error": "pandas 未安装，无法读取 Excel 文件",
            "format": "excel"
        }

    try:
        df = pd.read_excel(path, sheet_name=sheet_name, nrows=nrows)
        return {
            "success": True,
            "format": "excel",
            "sheet": sheet_name,
            "rows": len(df),
            "columns": list(df.columns),
            "data": df.to_dict(orient='records'),
            "preview": df.head(10).to_dict(orient='records') if nrows is None else df.to_dict(orient='records')
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"读取 Excel 失败: {str(e)}",
            "format": "excel"
        }


def _read_json(path: str, encoding: str) -> dict:
    """读取 JSON 文件"""
    try:
        with open(path, 'r', encoding=encoding) as f:
            data = json.load(f)
        return {
            "success": True,
            "format": "json",
            "data": data
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON 解析失败: {str(e)}",
            "format": "json"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"读取 JSON 失败: {str(e)}",
            "format": "json"
        }


def _read_text(path: str, encoding: str, nrows: Optional[int] = None) -> dict:
    """读取文本文件"""
    try:
        with open(path, 'r', encoding=encoding) as f:
            if nrows:
                lines = [f.readline() for _ in range(nrows)]
            else:
                lines = f.readlines()

        content = ''.join(lines)
        return {
            "success": True,
            "format": "text",
            "encoding": encoding,
            "lines": len(lines),
            "content": content,
            "preview": content[:5000] if nrows is None else content  # 预览最多 5000 字符
        }
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(path, 'r', encoding='gbk') as f:
                if nrows:
                    lines = [f.readline() for _ in range(nrows)]
                else:
                    lines = f.readlines()
            content = ''.join(lines)
            return {
                "success": True,
                "format": "text",
                "encoding": "gbk",
                "lines": len(lines),
                "content": content,
                "preview": content[:5000] if nrows is None else content
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"读取文本失败（尝试了 utf-8 和 gbk）: {str(e)}",
                "format": "text"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"读取文本失败: {str(e)}",
            "format": "text"
        }


def file_reader_impl(
    path: str,
    format: Optional[str] = None,
    encoding: str = "utf-8",
    sheet_name: Union[str, int] = 0,
    nrows: Optional[int] = None,
    parse_metadata: bool = False,
    response_format: str = "standard",
) -> ToolExecutionResult:
    """
    文件读取的实现函数 (v2.1 - Pipeline)

    Args:
        path: 文件路径
        format: 文件格式（不指定则自动检测）
        encoding: 文本编码
        sheet_name: Excel 工作表
        nrows: 最大读取行数
        parse_metadata: 是否解析元数据
        response_format: 响应格式

    Returns:
        ToolExecutionResult
    """
    start_time = time.time()

    # 生成 tool_call_id
    tool_call_id = f"call_read_file_{uuid.uuid4().hex[:12]}"

    # 解析输出级别
    output_level = _parse_output_level(response_format)

    try:
        # 检查文件是否存在
        if not os.path.exists(path):
            return ToolExecutionResult.create_error(
                tool_call_id=tool_call_id,
                error_message=f"文件不存在: {path}",
                error_type="FileNotFound",
                tool_name="read_file",
            ).with_duration((time.time() - start_time) * 1000)

        # 检查是否是文件
        if not os.path.isfile(path):
            return ToolExecutionResult.create_error(
                tool_call_id=tool_call_id,
                error_message=f"路径不是文件: {path}",
                error_type="NotAFile",
                tool_name="read_file",
            ).with_duration((time.time() - start_time) * 1000)

        # 检测格式
        if format is None:
            format = _detect_format(path)

        # 根据格式读取文件
        if format == "csv":
            raw_data = _read_csv(path, encoding, nrows)
        elif format == "excel":
            raw_data = _read_excel(path, sheet_name, nrows)
        elif format == "json":
            raw_data = _read_json(path, encoding)
        elif format == "python":
            raw_data = _read_python(path, encoding, parse_metadata)
        elif format == "sql":
            raw_data = _read_sql(path, encoding, parse_metadata)
        else:  # text
            raw_data = _read_text(path, encoding, nrows)

        raw_data["path"] = path

        duration_ms = (time.time() - start_time) * 1000

        # 创建 ToolExecutionResult
        return ToolExecutionResult.from_raw_data(
            tool_call_id=tool_call_id,
            raw_data=raw_data,
            output_level=output_level,
            tool_name="read_file",
            cache_policy=ToolCachePolicy.NO_CACHE,
        ).with_duration(duration_ms)

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        # 创建错误结果
        return ToolExecutionResult.create_error(
            tool_call_id=tool_call_id,
            error_message=str(e),
            error_type=type(e).__name__,
            tool_name="read_file",
        ).with_duration(duration_ms)


# 创建 LangChain 工具
file_reader_tool = StructuredTool.from_function(
    func=file_reader_impl,
    name="read_file",
    description="""
读取本地文件，支持多种格式。

使用场景：
- 读取 CSV 数据文件进行分析
- 读取 Excel 报表数据
- 读取 JSON 配置文件
- 读取文本日志文件
- 读取 Python 源代码（用于 Skills 加载）
- 读取 SQL 查询文件

支持的功能：
- CSV 文件（使用 pandas）
- Excel 文件（.xlsx, .xls，支持多工作表）
- JSON 文件
- 文本文件（.txt, .md, .log 等）
- Python 文件（.py，可选 AST 解析提取函数/类/导入）
- SQL 文件（.sql，可选提取多条查询语句）

参数：
- path: 文件路径（必须在允许的目录内）
- format: 文件格式（csv, excel, json, text, python, sql），不指定则自动检测
- encoding: 文本编码（默认 utf-8）
- sheet_name: Excel 工作表名称或索引（默认第一个表）
- nrows: 最大读取行数（用于预览，默认读取全部）
- parse_metadata: 是否解析元数据（Python: AST解析；SQL: 提取查询）

安全限制：
- 仅允许读取允许目录内的文件
- 路径中不能包含 '..'（防止路径遍历）
- 允许的目录: /data, /tmp, ./data, ./tmp, ., ./skills

Python 文件解析（parse_metadata=True）：
- 提取所有导入（import/from...import）
- 提取所有函数定义（名称、参数、行号、文档字符串）
- 提取所有类定义（名称、方法、行号、文档字符串）

SQL 文件解析（parse_metadata=True）：
- 按分号分割多条查询
- 自动移除注释（-- 和 /* */）
- 返回查询列表

使用示例：
- read_file(path="./data/sales.csv")
- read_file(path="./skills/anomaly_detection/main.py", format="python", parse_metadata=True)
- read_file(path="./data/query.sql", format="sql", parse_metadata=True)
- read_file(path="./data/report.xlsx", sheet_name="Sheet2")
- read_file(path="./data/config.json")
    """.strip(),
    args_schema=FileReadInput,
)


# 导出
__all__ = [
    "FileReadInput",
    "file_reader_impl",
    "file_reader_tool",
    "DEFAULT_ALLOWED_PATHS",
    "_parse_python_metadata",
    "_parse_sql_queries",
]
