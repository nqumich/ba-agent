"""
Python 沙盒工具

使用 Docker 隔离环境安全执行 Python 代码
支持数据分析库（pandas, numpy, scipy, statsmodels 等）
"""

import ast
import re
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool

from config import get_config
from backend.docker.sandbox import get_sandbox


# 允许导入的模块白名单（数据分析相关）
ALLOWED_IMPORTS = {
    # 标准库（安全）
    'json', 'csv', 'datetime', 'math', 'statistics', 'random',
    'collections', 'itertools', 'functools', 'typing', 're', 'string',
    'decimal', 'fractions', 'hashlib', 'base64', 'uuid', 'pathlib',
    'os.path', 'time', 'copy', 'pprint', 'textwrap',

    # 数据分析核心库
    'pandas', 'numpy', 'scipy', 'statsmodels',

    # Excel 处理
    'openpyxl', 'xlrd', 'xlsxwriter',

    # 数据可视化（如果安装）
    'matplotlib', 'seaborn', 'plotly',
}


class PythonCodeInput(BaseModel):
    """Python 沙盒工具的输入参数"""

    code: str = Field(
        ...,
        description="要执行的 Python 代码（仅支持白名单库）"
    )
    timeout: Optional[int] = Field(
        default=60,
        ge=5,
        le=300,
        description="执行超时时间（秒），范围 5-300"
    )

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        """验证代码安全性"""
        # 检查空代码
        if not v or not v.strip():
            raise ValueError("代码不能为空")

        # 检查危险操作
        dangerous_patterns = [
            r'\bimport\s+os\s*',
            r'\bimport\s+subprocess\s*',
            r'\bimport\s+shutil\s*',
            r'\bimport\s+sys\s*',
            r'\bfrom\s+os\s+import',
            r'\bfrom\s+subprocess\s+import',
            r'\bfrom\s+shutil\s+import',
            r'\bfrom\s+sys\s+import',
            r'\bexec\s*\(',
            r'\beval\s*\(',
            r'\b__import__\s*\(',
            r'\bcompile\s*\(',
            r'\bopen\s*\([^)]*,\s*[\'"]w[\'"]',  # 写文件
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError(
                    f"代码包含不安全的操作: {pattern}"
                )

        # 使用 AST 检查 import 语句
        try:
            tree = ast.parse(v)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        if module_name not in ALLOWED_IMPORTS:
                            allowed = ', '.join(sorted(ALLOWED_IMPORTS))
                            raise ValueError(
                                f"不允许导入模块 '{module_name}'。"
                                f"允许的模块: {allowed}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split('.')[0]
                        if module_name not in ALLOWED_IMPORTS:
                            allowed = ', '.join(sorted(ALLOWED_IMPORTS))
                            raise ValueError(
                                f"不允许从模块 '{module_name}' 导入。"
                                f"允许的模块: {allowed}"
                            )
        except SyntaxError as e:
            raise ValueError(f"代码语法错误: {e}")

        return v


def run_python_impl(code: str, timeout: int = 60) -> str:
    """
    执行 Python 代码的实现函数

    Args:
        code: 要执行的 Python 代码
        timeout: 超时时间（秒）

    Returns:
        执行结果字符串（包含输出和错误）
    """
    sandbox = get_sandbox()
    config = get_config()

    # 执行代码
    result = sandbox.execute_python(
        code=code,
        timeout=timeout,
        memory_limit=config.docker.memory_limit,
        cpu_limit=config.docker.cpu_limit,
        network_disabled=config.docker.network_disabled,
    )

    # 格式化返回结果
    if result['success']:
        output = result['stdout']
        if not output:
            return "代码执行成功，无输出"
        return output
    else:
        return f"代码执行失败:\n{result['stderr']}"


# 创建 LangChain 工具
run_python_tool = StructuredTool.from_function(
    func=run_python_impl,
    name="run_python",
    description="""
执行安全的 Python 代码（Docker 隔离环境）。

支持的数据分析库：
- pandas: 数据处理和分析
- numpy: 数值计算
- scipy: 科学计算
- statsmodels: 统计建模
- openpyxl: Excel 读写
- matplotlib/seaborn/plotly: 数据可视化

使用示例：
- run_python(code="import pandas as pd; df = pd.DataFrame({'a': [1,2,3]}); print(df)")
- run_python(code="import numpy as np; print(np.array([1,2,3]).mean())")

限制：
- 仅支持白名单库（数据分析相关）
- 超时时间: 5-300 秒
- 禁止文件写入、网络访问等危险操作
    """.strip(),
    args_schema=PythonCodeInput,
)


def get_allowed_imports() -> List[str]:
    """获取允许导入的模块列表"""
    return sorted(ALLOWED_IMPORTS)


# 导出
__all__ = [
    "PythonCodeInput",
    "run_python_impl",
    "run_python_tool",
    "get_allowed_imports",
    "ALLOWED_IMPORTS",
]
