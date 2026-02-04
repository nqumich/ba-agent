"""
Skill 调用工具单元测试
"""

import json
import pytest
from pydantic import ValidationError

from tools.skill_invoker import (
    InvokeSkillInput,
    invoke_skill_impl,
    invoke_skill_tool,
    SkillConfig,
    _load_skills_config,
    _get_skill_config,
    _build_skill_code,
    _get_default_skills_config,
)


class TestLoadSkillsConfig:
    """测试加载 Skills 配置"""

    def test_load_default_config(self):
        """测试加载默认配置"""
        config = _load_skills_config()
        assert "skills" in config
        assert "global" in config

    def test_default_skills_exist(self):
        """测试默认 Skills 存在"""
        config = _load_skills_config()
        skills = config["skills"]
        assert "anomaly_detection" in skills
        assert "attribution" in skills
        assert "report_gen" in skills
        assert "visualization" in skills

    def test_global_config(self):
        """测试全局配置"""
        config = _load_skills_config()
        global_config = config["global"]
        assert "skill_timeout" in global_config
        assert "enable_cache" in global_config


class TestGetSkillConfig:
    """测试获取 Skill 配置"""

    def test_get_anomaly_detection_config(self):
        """测试获取异动检测配置"""
        config = _get_skill_config("anomaly_detection")
        assert config.name == "异动检测"
        assert config.function == "detect"
        assert "pandas" in config.requirements

    def test_get_attribution_config(self):
        """测试获取归因分析配置"""
        config = _get_skill_config("attribution")
        assert config.name == "归因分析"
        assert config.function == "analyze"

    def test_get_invalid_skill_raises_error(self):
        """测试获取不存在的 Skill 抛出错误"""
        with pytest.raises(ValueError, match="不存在"):
            _get_skill_config("invalid_skill")

    def test_skill_config_model(self):
        """测试 SkillConfig 模型"""
        skill_data = {
            "name": "测试 Skill",
            "description": "测试描述",
            "entrypoint": "skills/test/main.py",
            "function": "test_func",
            "requirements": ["pandas"],
            "config": {"param1": "value1"}
        }
        config = SkillConfig(**skill_data)
        assert config.name == "测试 Skill"
        assert config.config["param1"] == "value1"


class TestBuildSkillCode:
    """测试构建 Skill 代码"""

    def test_build_anomaly_detection_code(self):
        """测试构建异动检测代码"""
        config = _get_skill_config("anomaly_detection")
        code = _build_skill_code(config)

        assert "def detect" in code
        assert "anomaly_detection" in code.lower() or "异动" in code
        assert "return result" in code

    def test_build_attribution_code(self):
        """测试构建归因分析代码"""
        config = _get_skill_config("attribution")
        code = _build_skill_code(config)

        assert "def analyze" in code
        assert "attribution" in code.lower() or "归因" in code

    def test_build_code_with_params(self):
        """测试带参数构建代码"""
        config = _get_skill_config("anomaly_detection")
        params = {"threshold": 2.5, "data": [1, 2, 3]}
        code = _build_skill_code(config, params)

        assert "threshold" in code or "params" in code
        assert "detect(params" in code

    def test_build_code_without_params(self):
        """测试不带参数构建代码"""
        config = _get_skill_config("anomaly_detection")
        code = _build_skill_code(config, None)

        assert "detect(params" in code or "params = {}" in code


class TestInvokeSkillInput:
    """测试 InvokeSkillInput 模型"""

    def test_basic_invoke(self):
        """测试基本调用输入"""
        input_data = InvokeSkillInput(
            skill_name="anomaly_detection"
        )
        assert input_data.skill_name == "anomaly_detection"
        assert input_data.timeout == 60

    def test_with_params(self):
        """测试带参数调用"""
        input_data = InvokeSkillInput(
            skill_name="attribution",
            params={"metric": "gmv"}
        )
        assert input_data.params == {"metric": "gmv"}

    def test_custom_timeout(self):
        """测试自定义超时"""
        input_data = InvokeSkillInput(
            skill_name="report_gen",
            timeout=120
        )
        assert input_data.timeout == 120

    def test_cache_disabled(self):
        """测试禁用缓存"""
        input_data = InvokeSkillInput(
            skill_name="visualization",
            use_cache=False
        )
        assert input_data.use_cache is False

    def test_response_format_concise(self):
        """测试简洁响应格式"""
        input_data = InvokeSkillInput(
            skill_name="anomaly_detection",
            response_format="concise"
        )
        assert input_data.response_format == "concise"

    def test_empty_skill_name_raises_error(self):
        """测试空 Skill 名称抛出错误"""
        with pytest.raises(ValidationError):
            InvokeSkillInput(skill_name="")

    def test_invalid_skill_name_raises_error(self):
        """测试无效 Skill 名称抛出错误"""
        with pytest.raises(ValidationError, match="不存在"):
            InvokeSkillInput(skill_name="invalid_skill_name")

    def test_timeout_below_minimum(self):
        """测试超时低于最小值"""
        with pytest.raises(ValidationError):
            InvokeSkillInput(skill_name="anomaly_detection", timeout=3)

    def test_timeout_above_maximum(self):
        """测试超时超过最大值"""
        with pytest.raises(ValidationError):
            InvokeSkillInput(skill_name="anomaly_detection", timeout=301)

    def test_params_with_complex_data(self):
        """测试复杂数据参数"""
        params = {
            "data": [1, 2, 3, 4, 5],
            "config": {"nested": {"value": 123}},
            "metric": "gmv"
        }
        input_data = InvokeSkillInput(
            skill_name="anomaly_detection",
            params=params
        )
        assert input_data.params == params


class TestInvokeSkillImpl:
    """测试 Skill 调用实现函数"""

    def test_invoke_anomaly_detection(self):
        """测试调用异动检测 Skill"""
        result_json = invoke_skill_impl(skill_name="anomaly_detection")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert "成功" in result.summary or "执行" in result.summary
        assert result.result is not None
        assert result.result["skill_name"] == "anomaly_detection"

    def test_invoke_attribution(self):
        """测试调用归因分析 Skill"""
        result_json = invoke_skill_impl(skill_name="attribution")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result["skill_name"] == "attribution"

    def test_invoke_report_gen(self):
        """测试调用报告生成 Skill"""
        result_json = invoke_skill_impl(skill_name="report_gen")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result["skill_name"] == "report_gen"

    def test_invoke_visualization(self):
        """测试调用数据可视化 Skill"""
        result_json = invoke_skill_impl(skill_name="visualization")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result["skill_name"] == "visualization"

    def test_invoke_with_params(self):
        """测试带参数调用 Skill"""
        result_json = invoke_skill_impl(
            skill_name="anomaly_detection",
            params={"threshold": 2.5, "min_data_points": 20}
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success

    def test_invoke_with_custom_timeout(self):
        """测试自定义超时时间"""
        result_json = invoke_skill_impl(
            skill_name="attribution",
            timeout=90
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success

    def test_concise_response_format(self):
        """测试简洁响应格式"""
        result_json = invoke_skill_impl(
            skill_name="anomaly_detection",
            response_format="concise"
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        # Concise 格式可能不返回详细结果
        assert "成功" in result.summary or "执行" in result.summary

    def test_standard_response_format(self):
        """测试标准响应格式"""
        result_json = invoke_skill_impl(
            skill_name="anomaly_detection",
            response_format="standard"
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result is not None
        assert "execution_result" in result.result

    def test_detailed_response_format(self):
        """测试详细响应格式"""
        result_json = invoke_skill_impl(
            skill_name="anomaly_detection",
            response_format="detailed"
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success

    def test_observation_format(self):
        """测试 Observation 格式"""
        result_json = invoke_skill_impl(skill_name="anomaly_detection")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert "Observation:" in result.observation
        assert "Status:" in result.observation

    def test_telemetry_collected(self):
        """测试遥测数据收集"""
        result_json = invoke_skill_impl(skill_name="attribution")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.tool_name == "invoke_skill"
        assert result.telemetry.latency_ms >= 0

    def test_execution_result_structure(self):
        """测试执行结果结构"""
        result_json = invoke_skill_impl(skill_name="anomaly_detection")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert "skill_name" in result.result
        assert "skill_config" in result.result
        assert "execution_result" in result.result
        assert "execution_time_ms" in result.result

    def test_execution_result_contains_data(self):
        """测试执行结果包含数据"""
        result_json = invoke_skill_impl(skill_name="anomaly_detection")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        exec_result = result.result["execution_result"]
        assert "status" in exec_result
        assert exec_result["status"] == "success"


class TestInvokeSkillTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert invoke_skill_tool.name == "invoke_skill"
        assert "Skill" in invoke_skill_tool.description

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(invoke_skill_tool, StructuredTool)

    def test_tool_args_schema(self):
        """测试工具参数模式"""
        assert invoke_skill_tool.args_schema == InvokeSkillInput

    def test_tool_invocation(self):
        """测试工具调用"""
        result = invoke_skill_tool.invoke({
            "skill_name": "anomaly_detection"
        })

        # 结果应该是 JSON 字符串
        assert isinstance(result, str)
        # 可以解析为 ToolOutput
        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success

    def test_tool_with_params(self):
        """测试工具带参数调用"""
        result = invoke_skill_tool.invoke({
            "skill_name": "attribution",
            "params": {"metric": "gmv"}
        })

        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success

    def test_tool_description_contains_available_skills(self):
        """测试工具描述包含可用 Skills"""
        description = invoke_skill_tool.description
        assert "anomaly_detection" in description
        assert "attribution" in description


class TestSkillIntegration:
    """集成测试"""

    def test_full_skill_workflow(self):
        """测试完整 Skill 工作流"""
        # 1. 创建输入
        input_data = InvokeSkillInput(
            skill_name="anomaly_detection",
            params={"data": [100, 95, 85, 120, 110]},
            timeout=60
        )

        # 2. 执行 Skill
        result_json = invoke_skill_impl(
            skill_name=input_data.skill_name,
            params=input_data.params,
            timeout=input_data.timeout
        )

        # 3. 解析结果
        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        result = ToolOutput.model_validate_json(result_json)

        # 4. 验证
        assert result.telemetry.success
        assert result.result["skill_name"] == "anomaly_detection"
        assert result.result["execution_result"]["status"] == "success"

    def test_multiple_skill_invocations(self):
        """测试多次调用不同 Skills"""
        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput

        skills_to_test = ["anomaly_detection", "attribution", "report_gen"]

        for skill_name in skills_to_test:
            result = ToolOutput.model_validate_json(
                invoke_skill_impl(skill_name=skill_name)
            )
            assert result.telemetry.success
            assert result.result["skill_name"] == skill_name

    def test_skill_params_propagation(self):
        """测试参数传递到 Skill"""
        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput

        params = {"custom_param": "custom_value", "threshold": 2.0}
        result = ToolOutput.model_validate_json(
            invoke_skill_impl(
                skill_name="anomaly_detection",
                params=params
            )
        )

        assert result.telemetry.success
