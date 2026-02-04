"""
统一工具输出格式单元测试
"""

import json
import pytest

from models.tool_output import (
    ResponseFormat,
    ToolTelemetry,
    ToolOutput,
    TelemetryCollector,
    get_telemetry_collector,
    extract_summary,
)
from tools.base import (
    unified_tool,
    ToolOutputParser,
    ReActFormatter,
    TokenOptimizer,
)


class TestResponseFormat:
    """测试 ResponseFormat 枚举"""

    def test_all_formats(self):
        """测试所有格式值"""
        assert ResponseFormat.CONCISE == "concise"
        assert ResponseFormat.STANDARD == "standard"
        assert ResponseFormat.DETAILED == "detailed"
        assert ResponseFormat.RAW == "raw"


class TestToolTelemetry:
    """测试 ToolTelemetry 模型"""

    def test_default_values(self):
        """测试默认值"""
        telemetry = ToolTelemetry()
        assert telemetry.tool_name == ""
        assert telemetry.tool_version == "1.0.0"
        assert telemetry.execution_id != ""  # 应该生成 UUID
        assert telemetry.timestamp != ""
        assert telemetry.latency_ms == 0.0
        assert telemetry.success is True

    def test_custom_values(self):
        """测试自定义值"""
        telemetry = ToolTelemetry(
            tool_name="test_tool",
            latency_ms=100.5,
            output_tokens=250,
            success=False,
            error_code="TestError",
        )
        assert telemetry.tool_name == "test_tool"
        assert telemetry.latency_ms == 100.5
        assert telemetry.output_tokens == 250
        assert telemetry.success is False
        assert telemetry.error_code == "TestError"

    def test_metrics_dict(self):
        """测试自定义指标"""
        telemetry = ToolTelemetry(
            metrics={"custom_metric": 42.0, "another": "value"}
        )
        assert telemetry.metrics["custom_metric"] == 42.0
        assert telemetry.metrics["another"] == "value"


class TestToolOutput:
    """测试 ToolOutput 模型"""

    def test_minimal_output(self):
        """测试最小输出"""
        output = ToolOutput(summary="测试成功")
        assert output.summary == "测试成功"
        assert output.response_format == ResponseFormat.CONCISE
        assert output.result is None
        assert output.observation == ""

    def test_full_output(self):
        """测试完整输出"""
        result = {"data": [1, 2, 3], "count": 3}
        telemetry = ToolTelemetry(tool_name="test", latency_ms=50.0)

        output = ToolOutput(
            result=result,
            summary="返回了 3 个数据项",
            observation="Observation: 返回了 3 个数据项",
            response_format=ResponseFormat.STANDARD,
            telemetry=telemetry,
        )

        assert output.result == result
        assert output.summary == "返回了 3 个数据项"
        assert output.response_format == ResponseFormat.STANDARD
        assert output.telemetry.tool_name == "test"

    def test_model_dump_for_llm_concise(self):
        """测试 CONCISE 模式的模型导出"""
        output = ToolOutput(
            result={"large": "data"},
            summary="简洁摘要",
            response_format=ResponseFormat.CONCISE,
        )

        data = output.model_dump_for_llm()
        assert "result" not in data  # CONCISE 模式不包含 result
        assert data["summary"] == "简洁摘要"
        assert "telemetry" not in data  # 遥测数据始终排除

    def test_model_dump_for_llm_standard(self):
        """测试 STANDARD 模式的模型导出"""
        output = ToolOutput(
            result={"data": "value"},
            summary="标准摘要",
            response_format=ResponseFormat.STANDARD,
        )

        data = output.model_dump_for_llm()
        assert "result" in data  # STANDARD 模式包含 result
        assert data["result"] == {"data": "value"}
        assert "telemetry" not in data

    def test_to_observation_concise(self):
        """测试 CONCISE 模式的 Observation 生成"""
        output = ToolOutput(
            summary="读取成功",
            response_format=ResponseFormat.CONCISE,
            telemetry=ToolTelemetry(success=True),
        )

        observation = output.to_observation()
        assert observation == "Observation: 读取成功"

    def test_to_observation_standard(self):
        """测试 STANDARD 模式的 Observation 生成"""
        output = ToolOutput(
            summary="返回数据",
            result={"count": 5},
            response_format=ResponseFormat.STANDARD,
            telemetry=ToolTelemetry(success=True),
        )

        observation = output.to_observation()
        assert "Observation: 返回数据" in observation
        assert "Result Type: dict" in observation
        assert "Status: Success" in observation

    def test_to_observation_detailed(self):
        """测试 DETAILED 模式的 Observation 生成"""
        output = ToolOutput(
            summary="详细结果",
            result={"key": "value"},
            response_format=ResponseFormat.DETAILED,
            telemetry=ToolTelemetry(
                tool_name="test_tool",
                execution_id="test-id",
                latency_ms=123.45,
                output_tokens=100,
                success=True,
            ),
        )

        observation = output.to_observation()
        assert "Observation: 详细结果" in observation
        assert "Tool: test_tool" in observation
        assert "Execution ID: test-id" in observation
        assert "Latency: 123.45ms" in observation
        assert "Output Tokens: 100" in observation
        assert "Result:" in observation


class TestExtractSummary:
    """测试 extract_summary 函数"""

    def test_extract_from_dict_success(self):
        """测试从成功字典提取摘要"""
        data = {"success": True, "rows": 100}
        summary = extract_summary(data)
        assert summary == "成功：100 行"

    def test_extract_from_dict_error(self):
        """测试从错误字典提取摘要"""
        data = {"success": False, "error": "文件不存在"}
        summary = extract_summary(data)
        assert summary == "失败：文件不存在"

    def test_extract_from_dict_with_count(self):
        """测试从带 count 的字典提取摘要"""
        data = {"count": 42}
        summary = extract_summary(data)
        # extract_summary 对通用字典的处理
        assert "包含 1 个字段" in summary

    def test_extract_from_dict_generic(self):
        """测试从通用字典提取摘要"""
        data = {"field1": "value1", "field2": "value2", "field3": "value3"}
        summary = extract_summary(data)
        assert "包含 3 个字段" in summary

    def test_extract_from_list(self):
        """测试从列表提取摘要"""
        data = [1, 2, 3, 4, 5]
        summary = extract_summary(data)
        assert summary == "列表，包含 5 项"

    def test_extract_from_string(self):
        """测试从字符串提取摘要"""
        data = "这是一个较长的字符串，超过限制"
        summary = extract_summary(data, max_length=10)
        assert len(summary) <= 10
        assert summary == "这是一个较长的字符串，超过限"[:10]

    def test_extract_from_none(self):
        """测试从 None 提取摘要"""
        summary = extract_summary(None)
        assert summary == "无返回数据"


class TestTelemetryCollector:
    """测试 TelemetryCollector"""

    def test_singleton(self):
        """测试单例模式"""
        collector1 = get_telemetry_collector()
        collector2 = get_telemetry_collector()
        assert collector1 is collector2

    def test_record_metrics(self):
        """测试记录遥测数据"""
        collector = TelemetryCollector()

        telemetry1 = ToolTelemetry(tool_name="tool1", latency_ms=100, output_tokens=50)
        telemetry2 = ToolTelemetry(tool_name="tool2", latency_ms=200, output_tokens=100)

        collector.record(telemetry1)
        collector.record(telemetry2)

        assert len(collector.metrics) == 2
        assert collector.aggregated["total_calls"] == 2
        assert collector.aggregated["total_tokens"] == 150
        assert collector.aggregated["avg_latency_ms"] == 150.0

    def test_aggregated_with_errors(self):
        """测试包含错误的聚合统计"""
        collector = TelemetryCollector()

        telemetry1 = ToolTelemetry(tool_name="tool1", success=True)
        telemetry2 = ToolTelemetry(tool_name="tool2", success=False)
        telemetry3 = ToolTelemetry(tool_name="tool3", success=False)

        collector.record(telemetry1)
        collector.record(telemetry2)
        collector.record(telemetry3)

        assert collector.aggregated["error_rate"] == 2/3

    def test_aggregated_with_cache(self):
        """测试缓存命中率统计"""
        collector = TelemetryCollector()

        telemetry1 = ToolTelemetry(cache_hit=True)
        telemetry2 = ToolTelemetry(cache_hit=False)
        telemetry3 = ToolTelemetry(cache_hit=True)

        collector.record(telemetry1)
        collector.record(telemetry2)
        collector.record(telemetry3)

        assert collector.aggregated["cache_hit_rate"] == 2/3

    def test_get_report(self):
        """测试生成报告"""
        collector = TelemetryCollector()

        telemetry = ToolTelemetry(
            tool_name="test_tool",
            latency_ms=123.4,
            output_tokens=456,
            success=True,
        )
        collector.record(telemetry)

        report = collector.get_report()
        assert "总调用次数: 1" in report
        assert "总 Token 使用: 456" in report
        assert "平均延迟: 123.40ms" in report
        assert "错误率: 0.00%" in report

    def test_get_metrics_by_tool(self):
        """测试按工具名筛选"""
        collector = TelemetryCollector()

        telemetry1 = ToolTelemetry(tool_name="tool_a")
        telemetry2 = ToolTelemetry(tool_name="tool_b")
        telemetry3 = ToolTelemetry(tool_name="tool_a")

        collector.record(telemetry1)
        collector.record(telemetry2)
        collector.record(telemetry3)

        tool_a_metrics = collector.get_metrics_by_tool("tool_a")
        assert len(tool_a_metrics) == 2

        tool_b_metrics = collector.get_metrics_by_tool("tool_b")
        assert len(tool_b_metrics) == 1

    def test_reset(self):
        """测试重置收集器"""
        collector = TelemetryCollector()

        collector.record(ToolTelemetry())
        assert len(collector.metrics) == 1

        collector.reset()
        assert len(collector.metrics) == 0
        assert collector.aggregated["total_calls"] == 0


class TestUnifiedTool:
    """测试 unified_tool 装饰器"""

    def test_decorator_basic(self):
        """测试基本装饰器功能"""
        @unified_tool("test_tool")
        def test_function(x: int) -> dict:
            return {"result": x * 2}

        result = test_function(5)
        assert isinstance(result, str)  # 返回 JSON 字符串

        data = json.loads(result)
        assert "summary" in data
        assert "observation" in data
        assert "telemetry" not in data  # 遥测数据被排除

    def test_decorator_with_error(self):
        """测试错误处理"""
        @unified_tool("failing_tool")
        def failing_function():
            raise ValueError("测试错误")

        result = failing_function()
        data = json.loads(result)

        assert "错误" in data.get("summary", "")
        assert "Error" in data.get("observation", "")

    def test_decorator_concise_format(self):
        """测试 CONCISE 格式"""
        @unified_tool("test_tool", response_format=ResponseFormat.CONCISE)
        def test_function():
            return {"large": "data", "set": "of", "keys": "here"}

        result = test_function()
        data = json.loads(result)

        # CONCISE 模式下 result 为 None，但字段仍然存在
        assert data.get("result") is None
        assert data.get("response_format") == "concise"

    def test_decorator_standard_format(self):
        """测试 STANDARD 格式"""
        @unified_tool("test_tool", response_format=ResponseFormat.STANDARD)
        def test_function():
            return {"data": "value"}

        result = test_function()
        data = json.loads(result)

        assert "result" in data  # STANDARD 包含 result
        assert data.get("response_format") == "standard"

    def test_decorator_with_custom_summary(self):
        """测试自定义摘要函数"""
        def custom_summary(data):
            return f"自定义摘要：{len(data)} 项"

        @unified_tool("test_tool", extract_summary_func=custom_summary)
        def test_function():
            return [1, 2, 3, 4, 5]

        result = test_function()
        data = json.loads(result)

        assert data.get("summary") == "自定义摘要：5 项"


class TestToolOutputParser:
    """测试 ToolOutputParser"""

    def test_parse_valid_json(self):
        """测试解析有效 JSON"""
        output_json = json.dumps({
            "summary": "测试",
            "observation": "Observation: 测试",
            "response_format": "concise",
        })

        output = ToolOutputParser.parse(output_json)
        assert output.summary == "测试"
        assert output.observation == "Observation: 测试"

    def test_parse_invalid_json(self):
        """测试解析无效 JSON"""
        output_json = "not a json"

        output = ToolOutputParser.parse(output_json)
        assert "解析输出失败" in output.summary

    def test_get_observation(self):
        """测试提取 Observation"""
        output_json = json.dumps({
            "observation": "Observation: 测试观察",
        })

        obs = ToolOutputParser.get_observation(output_json)
        assert obs == "Observation: 测试观察"

    def test_get_summary(self):
        """测试提取 Summary"""
        output_json = json.dumps({
            "summary": "测试摘要",
        })

        summary = ToolOutputParser.get_summary(output_json)
        assert summary == "测试摘要"

    def test_is_success(self):
        """测试判断成功"""
        success_json = json.dumps({"summary": "成功"})
        assert ToolOutputParser.is_success(success_json) is True

        error_json = json.dumps({"summary": "Error: 失败"})
        assert ToolOutputParser.is_success(error_json) is False


class TestReActFormatter:
    """测试 ReActFormatter"""

    def test_format_action(self):
        """测试格式化 Action"""
        action = ReActFormatter.format_action(
            "file_reader",
            {"path": "./data/test.csv", "nrows": 10}
        )
        assert "Action: file_reader" in action
        # 检查路径和参数存在（使用单引号）
        assert "path=" in action and "./data/test.csv" in action
        assert "nrows=10" in action

    def test_format_thought(self):
        """测试格式化 Thought"""
        thought = ReActFormatter.format_thought("我需要读取文件")
        assert thought == "Thought: 我需要读取文件"

    def test_format_step(self):
        """测试格式化完整步骤"""
        step = ReActFormatter.format_step(
            thought="我需要读取文件",
            action='Action: file_reader[path=\'./data/test.csv\']',
            observation="Observation: 成功读取",
        )
        assert "Thought: 我需要读取文件" in step
        assert "Action:" in step
        assert "Observation:" in step


class TestTokenOptimizer:
    """测试 TokenOptimizer"""

    def test_to_compact(self):
        """测试紧凑格式"""
        data = {"name": "test", "count": 5, "active": True}
        compact = TokenOptimizer.to_compact(data)

        assert "name:test" in compact
        assert "count:5" in compact
        assert "active:True" in compact

    def test_to_compact_with_complex_types(self):
        """测试复杂类型的紧凑格式"""
        data = {
            "simple": "value",
            "list": [1, 2, 3],
            "dict": {"key": "value"},
        }
        compact = TokenOptimizer.to_compact(data)

        assert "simple:value" in compact
        assert "list:[3 items]" in compact
        assert "dict:{1 keys}" in compact

    def test_to_safe_yaml(self):
        """测试安全 YAML 格式"""
        data = {"name": "test", "count": 5, "active": True}
        yaml_str = TokenOptimizer.to_safe_yaml(data)

        assert "name: test" in yaml_str
        assert "count: 5" in yaml_str
        assert "active: True" in yaml_str

    def test_to_xml(self):
        """测试 XML 格式"""
        xml_str = TokenOptimizer.to_xml(
            "file_reader",
            "成功读取文件",
            metadata={"tokens": 100, "latency": "45.2"}
        )

        assert '<tool_result name="file_reader">' in xml_str
        assert "<summary>成功读取文件</summary>" in xml_str
        # metadata 使用引号包裹值
        assert 'tokens="100"' in xml_str
        assert 'latency="45.2"' in xml_str
        assert "</tool_result>" in xml_str
