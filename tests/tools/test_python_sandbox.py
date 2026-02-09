"""
Python 沙盒工具单元测试
"""

import pytest
from unittest.mock import Mock, patch
from pydantic import ValidationError

from tools.python_sandbox import (
    PythonCodeInput,
    run_python_impl,
    run_python_tool,
    ALLOWED_IMPORTS,
    get_allowed_imports,
)
from backend.docker.sandbox import reset_sandbox, DockerSandbox

# Pipeline v2.1 模型
from backend.models.pipeline import ToolExecutionResult, OutputLevel


class TestPythonCodeInput:
    """测试 PythonCodeInput 模型"""

    def test_valid_code(self):
        """测试有效的 Python 代码"""
        code = "import pandas as pd\nprint('Hello')"
        input_data = PythonCodeInput(code=code)
        assert input_data.code == code

    def test_valid_code_with_timeout(self):
        """测试带超时参数的有效代码"""
        code = "print('test')"
        input_data = PythonCodeInput(code=code, timeout=120)
        assert input_data.code == code
        assert input_data.timeout == 120

    def test_empty_code(self):
        """测试空代码"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="")

        assert "不能为空" in str(exc_info.value)

    def test_whitespace_only_code(self):
        """测试仅包含空白的代码"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="   \n\t  ")

        assert "不能为空" in str(exc_info.value)

    def test_timeout_below_minimum(self):
        """测试超时时间低于最小值"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="print('test')", timeout=4)

        assert "greater than or equal to 5" in str(exc_info.value)

    def test_timeout_above_maximum(self):
        """测试超时时间高于最大值"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="print('test')", timeout=301)

        assert "less than or equal to 300" in str(exc_info.value)

    def test_dangerous_import_os(self):
        """测试危险的 os 导入"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="import os")

        assert "不安全的操作" in str(exc_info.value)

    def test_dangerous_import_subprocess(self):
        """测试危险的 subprocess 导入"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="import subprocess")

        assert "不安全的操作" in str(exc_info.value)

    def test_dangerous_from_os_import(self):
        """测试危险的 from os import"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="from os import path")

        assert "不安全的操作" in str(exc_info.value)

    def test_dangerous_exec(self):
        """测试危险的 exec"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="exec('print(1)')")

        assert "不安全的操作" in str(exc_info.value)

    def test_dangerous_eval(self):
        """测试危险的 eval"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="eval('1+1')")

        assert "不安全的操作" in str(exc_info.value)

    def test_dangerous_file_write(self):
        """测试文件写入"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="open('test.txt', 'w')")

        assert "不安全的操作" in str(exc_info.value)

    def test_forbidden_module_import(self):
        """测试不允许的模块导入"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="import requests")

        assert "不允许导入模块 'requests'" in str(exc_info.value)

    def test_allowed_imports(self):
        """测试允许的模块"""
        allowed_modules = [
            "pandas",
            "numpy",
            "scipy",
            "statsmodels",
            "json",
            "csv",
            "datetime",
            "math",
        ]

        for module in allowed_modules:
            code = f"import {module}"
            input_data = PythonCodeInput(code=code)
            assert input_data.code == code

    def test_syntax_error(self):
        """测试语法错误"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="print('test")

        assert "语法错误" in str(exc_info.value)

    def test_from_import_allowed(self):
        """测试允许的 from import"""
        code = "from pandas import DataFrame"
        input_data = PythonCodeInput(code=code)
        assert input_data.code == code

    def test_from_import_forbidden(self):
        """测试不允许的 from import"""
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="from sys import path")

        assert "不安全的操作" in str(exc_info.value)


class TestRunPythonImpl:
    """测试 run_python_impl 函数"""

    @patch('tools.python_sandbox.get_sandbox')
    @patch('tools.python_sandbox.get_config')
    def test_successful_execution(self, mock_get_config, mock_get_sandbox):
        """测试成功执行"""
        # Mock 配置
        mock_config = Mock()
        mock_config.docker.memory_limit = "512m"
        mock_config.docker.cpu_limit = "1.0"
        mock_config.docker.network_disabled = True
        mock_get_config.return_value = mock_config

        # Mock 沙盒
        mock_sandbox = Mock()
        mock_sandbox.execute_python.return_value = {
            'success': True,
            'stdout': 'Hello from Python\n123',
            'stderr': '',
            'exit_code': 0,
        }
        mock_get_sandbox.return_value = mock_sandbox

        # 执行
        result = run_python_impl("print('Hello from Python')", timeout=60)

        # 验证
        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert 'Hello from Python' in result.observation
        mock_sandbox.execute_python.assert_called_once()

    @patch('tools.python_sandbox.get_sandbox')
    @patch('tools.python_sandbox.get_config')
    def test_failed_execution(self, mock_get_config, mock_get_sandbox):
        """测试执行失败"""
        # Mock 配置
        mock_config = Mock()
        mock_config.docker.memory_limit = "512m"
        mock_config.docker.cpu_limit = "1.0"
        mock_config.docker.network_disabled = True
        mock_get_config.return_value = mock_config

        # Mock 沙盒
        mock_sandbox = Mock()
        mock_sandbox.execute_python.return_value = {
            'success': False,
            'stdout': '',
            'stderr': 'NameError: name undefined is not defined',
            'exit_code': 1,
        }
        mock_get_sandbox.return_value = mock_sandbox

        # 执行
        result = run_python_impl("print(undefined)", timeout=60)

        # 验证
        assert isinstance(result, ToolExecutionResult)
        assert not result.success
        assert "NameError" in result.observation

    @patch('tools.python_sandbox.get_sandbox')
    @patch('tools.python_sandbox.get_config')
    def test_empty_output(self, mock_get_config, mock_get_sandbox):
        """测试空输出"""
        # Mock 配置
        mock_config = Mock()
        mock_config.docker.memory_limit = "512m"
        mock_config.docker.cpu_limit = "1.0"
        mock_config.docker.network_disabled = True
        mock_get_config.return_value = mock_config

        # Mock 沙盒
        mock_sandbox = Mock()
        mock_sandbox.execute_python.return_value = {
            'success': True,
            'stdout': '',
            'stderr': '',
            'exit_code': 0,
        }
        mock_get_sandbox.return_value = mock_sandbox

        # 执行
        result = run_python_impl("x = 1", timeout=60)

        # 验证
        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert "代码执行成功" in result.observation


class TestRunPythonTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert run_python_tool.name == "run_python"
        assert "Docker 隔离" in run_python_tool.description
        assert "pandas" in run_python_tool.description
        assert run_python_tool.args_schema == PythonCodeInput

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(run_python_tool, StructuredTool)

    @patch('tools.python_sandbox.get_config')
    @patch('tools.python_sandbox.get_sandbox')
    def test_tool_invocation(self, mock_sandbox_for_sandbox, mock_config_for_config):
        """测试工具调用"""
        # 注意：patch 参数从下往上应用，所以第一个参数是 get_sandbox 的 mock
        # Mock 配置
        mock_config = Mock()
        mock_config.docker.memory_limit = "512m"
        mock_config.docker.cpu_limit = "1.0"
        mock_config.docker.network_disabled = True
        mock_config_for_config.return_value = mock_config

        # Mock 沙盒
        mock_sandbox = Mock()
        mock_sandbox.execute_python.return_value = {
            'success': True,
            'stdout': '42',
            'stderr': '',
            'exit_code': 0,
        }
        mock_sandbox_for_sandbox.return_value = mock_sandbox

        # 通过工具调用
        result = run_python_tool.invoke({
            "code": "print(42)",
            "timeout": 60
        })

        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert "42" in result.observation

        # 验证 sandbox.execute_python 被调用
        mock_sandbox.execute_python.assert_called_once()
        call_args = mock_sandbox.execute_python.call_args
        assert call_args[1]['code'] == "print(42)"
        assert call_args[1]['timeout'] == 60


class TestAllowedImports:
    """测试允许的导入列表"""

    def test_get_allowed_imports(self):
        """测试获取允许的导入列表"""
        imports = get_allowed_imports()
        assert isinstance(imports, list)
        assert 'pandas' in imports
        assert 'numpy' in imports
        assert 'scipy' in imports

    def test_allowed_imports_constant(self):
        """测试 ALLOWED_IMPORTS 常量"""
        assert isinstance(ALLOWED_IMPORTS, set)
        assert 'pandas' in ALLOWED_IMPORTS
        assert 'os' not in ALLOWED_IMPORTS
        assert 'subprocess' not in ALLOWED_IMPORTS


class TestPythonSandboxIntegration:
    """集成测试（需要 Docker）"""

    def setup_method(self):
        """每个测试前重置沙盒"""
        reset_sandbox()

    @pytest.mark.slow
    @pytest.mark.docker
    def test_real_docker_simple_print(self):
        """测试简单 print 语句"""
        result = run_python_impl("print('Hello from Docker Python')", timeout=30)
        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert "Hello from Docker Python" in result.observation

    @pytest.mark.slow
    @pytest.mark.docker
    def test_real_docker_pandas_basic(self):
        """测试 pandas 基本操作（使用自定义镜像）"""
        # 使用包含数据分析库的自定义镜像
        sandbox = DockerSandbox()
        original_image = sandbox.config.docker.image
        sandbox.config.docker.image = "ba-agent/python-sandbox:latest"

        code = """
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
print(df.to_string())
"""
        result = sandbox.execute_python(code, timeout=60)
        # execute_python 返回字典
        assert result['success'] == True
        assert "a" in result['stdout']
        assert "1" in result['stdout']
        assert "4" in result['stdout']

        # 恢复原始镜像
        sandbox.config.docker.image = original_image

    @pytest.mark.slow
    @pytest.mark.docker
    def test_real_docker_numpy_calculation(self):
        """测试 numpy 计算（使用自定义镜像）"""
        # 使用包含数据分析库的自定义镜像
        sandbox = DockerSandbox()
        original_image = sandbox.config.docker.image
        sandbox.config.docker.image = "ba-agent/python-sandbox:latest"

        code = """
import numpy as np
arr = np.array([1, 2, 3, 4, 5])
print(f"Mean: {arr.mean()}")
print(f"Sum: {arr.sum()}")
"""
        result = sandbox.execute_python(code, timeout=60)
        # execute_python 返回字典
        assert result['success'] == True
        assert "Mean: 3.0" in result['stdout']
        assert "Sum: 15" in result['stdout']

        # 恢复原始镜像
        sandbox.config.docker.image = original_image

    @pytest.mark.slow
    @pytest.mark.docker
    def test_real_docker_forbidden_import_blocked(self):
        """测试禁止的导入被阻止"""
        # 这个测试应该失败在验证阶段，不会执行到 Docker
        with pytest.raises(ValidationError) as exc_info:
            PythonCodeInput(code="import os; print(os.getcwd())")
        assert "不安全的操作" in str(exc_info.value)
