"""
数据可视化 Skill 测试
"""

import pytest
import sys
from pathlib import Path

# 添加 skills 目录到路径
skills_dir = Path(__file__).parent.parent.parent / "skills"
sys.path.insert(0, str(skills_dir))

from skills.visualization.main import (
    create_chart,
    recommend_chart_type,
    parse_data,
    get_supported_chart_types,
    get_supported_themes,
    validate_echarts_config,
    export_chart_html,
    ECHARTS_THEMES
)


class TestChartTypeRecommendation:
    """测试图表类型推荐"""

    def test_dict_data_recommendation(self):
        """测试字典数据推荐"""
        # 少量键值对 → 饼图
        data = {"A": 10, "B": 20, "C": 30}
        assert recommend_chart_type(data) == "pie"

        # 多个键值对 → 柱状图
        data = {str(i): i * 10 for i in range(15)}
        assert recommend_chart_type(data) == "bar"

    def test_list_data_recommendation(self):
        """测试列表数据推荐"""
        # 数值列表 → 折线图
        data = [1, 2, 3, 4, 5]
        assert recommend_chart_type(data) == "line"

        # 字典列表 → 柱状图
        data = [{"name": "A", "value": 10}, {"name": "B", "value": 20}]
        assert recommend_chart_type(data) == "bar"

    def test_empty_list_recommendation(self):
        """测试空列表"""
        assert recommend_chart_type([]) == "bar"


class TestDataParsing:
    """测试数据解析"""

    def test_dict_parsing(self):
        """测试字典解析"""
        data = {"A": 10, "B": 20}
        result = parse_data(data)

        assert result["type"] == "dict"
        assert result["columns"] == ["A", "B"]
        assert len(result["rows"]) == 2
        assert result["rows"][0] == {"name": "A", "value": 10}

    def test_list_parsing(self):
        """测试列表解析"""
        data = [1, 2, 3]
        result = parse_data(data)

        assert result["type"] == "list"
        assert result["columns"] == ["value"]
        assert len(result["rows"]) == 3

    def test_dict_list_parsing(self):
        """测试字典列表解析"""
        data = [{"name": "A", "value": 10}, {"name": "B", "value": 20}]
        result = parse_data(data)

        assert result["type"] == "list"
        assert result["columns"] == ["name", "value"]
        assert len(result["rows"]) == 2


class TestChartGeneration:
    """测试图表生成"""

    def test_bar_chart_from_dict(self):
        """测试从字典生成柱状图"""
        data = {"产品A": 100, "产品B": 200, "产品C": 150}
        result = create_chart(data, chart_hint="bar", use_llm=False)

        assert result["chart_type"] == "bar"
        assert "config" in result
        assert "validation" in result
        assert result["metadata"]["data_type"] == "dict"
        assert result["metadata"]["generation_method"] == "rule"

        # 验证配置结构
        config = result["config"]
        assert "series" in config
        assert "xAxis" in config
        assert "yAxis" in config

    def test_pie_chart_from_dict(self):
        """测试从字典生成饼图"""
        data = {"A": 10, "B": 20, "C": 30}
        result = create_chart(data, chart_hint="pie", use_llm=False)

        assert result["chart_type"] == "pie"
        config = result["config"]
        assert "series" in config
        if config["series"]:
            assert config["series"][0]["type"] == "pie"

    def test_line_chart_from_list(self):
        """测试从列表生成折线图"""
        data = [10, 20, 15, 30, 25]
        result = create_chart(data, chart_hint="line", use_llm=False)

        assert result["chart_type"] == "line"
        config = result["config"]
        assert "xAxis" in config
        assert "yAxis" in config

    def test_auto_chart_type_selection(self):
        """测试自动选择图表类型"""
        # 字典应自动选择饼图
        data = {"A": 10, "B": 20}
        result = create_chart(data, use_llm=False)
        assert result["chart_type"] == "pie"

    def test_theme_application(self):
        """测试主题应用"""
        data = {"A": 10, "B": 20}
        result = create_chart(data, theme="dark", use_llm=False)

        assert result["theme"] == "dark"

    def test_invalid_chart_hint(self):
        """测试无效的图表提示"""
        data = {"A": 10, "B": 20}
        # 无效提示应自动选择合适类型
        result = create_chart(data, chart_hint="invalid_type", use_llm=False)
        assert result["chart_type"] in ["pie", "bar"]


class TestValidation:
    """测试配置验证"""

    def test_valid_config(self):
        """测试有效配置验证"""
        config = {
            "series": [{"type": "bar", "data": [1, 2, 3]}]
        }
        result = validate_echarts_config(config)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_missing_series(self):
        """测试缺少 series"""
        config = {"title": "Test"}
        result = validate_echarts_config(config)

        assert result["valid"] is False
        assert "series" in result["errors"][0]

    def test_invalid_series_type(self):
        """测试无效的 series 类型"""
        config = {
            "series": "not a list"
        }
        result = validate_echarts_config(config)

        assert result["valid"] is False
        assert "series 必须是数组" in result["errors"][0]

    def test_empty_series_warning(self):
        """测试空系列警告"""
        config = {
            "series": []
        }
        result = validate_echarts_config(config)

        assert result["valid"] is True
        assert "series 为空" in result["warnings"][0]

    def test_dangerous_keywords(self):
        """测试危险关键词检测"""
        config = {
            "series": [{
                "type": "bar",
                "data": [1, 2, 3],
                "label": {"formatter": "eval('malicious code')"}
            }]
        }
        result = validate_echarts_config(config)

        assert result["valid"] is False
        assert any("eval" in error for error in result["errors"])


class TestThemes:
    """测试主题"""

    def test_available_themes(self):
        """测试可用主题"""
        themes = get_supported_themes()
        assert "default" in themes
        assert "dark" in themes
        assert "macarons" in themes
        assert "vintage" in themes

    def test_theme_structure(self):
        """测试主题结构"""
        for theme_name, theme_config in ECHARTS_THEMES.items():
            assert "colors" in theme_config
            assert isinstance(theme_config["colors"], list)
            assert len(theme_config["colors"]) > 0


class TestSupportedTypes:
    """测试支持的类型"""

    def test_supported_chart_types(self):
        """测试支持的图表类型"""
        types = get_supported_chart_types()
        assert "line" in types
        assert "bar" in types
        assert "pie" in types
        assert "scatter" in types
        assert "heatmap" in types


class TestHTMLExport:
    """测试 HTML 导出"""

    def test_html_export(self):
        """测试 HTML 导出功能"""
        config = {
            "title": {"text": "测试图表"},
            "series": [{"type": "bar", "data": [1, 2, 3]}]
        }

        html = export_chart_html(config)

        assert "<!DOCTYPE html>" in html
        assert "echarts" in html.lower()
        assert "chart-container" in html

    def test_html_custom_size(self):
        """测试自定义尺寸"""
        config = {"series": []}
        html = export_chart_html(config, width="1000px", height="800px")

        assert "1000px" in html
        assert "800px" in html


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_data(self):
        """测试空数据"""
        result = create_chart({}, use_llm=False)
        assert "config" in result
        assert result["metadata"]["data_rows"] == 0

    def test_single_value(self):
        """测试单个值"""
        result = create_chart({"A": 1}, use_llm=False)
        assert "config" in result

    def test_large_dataset(self):
        """测试大数据集"""
        # 生成大量数据
        data = {f"项{i}": i * 10 for i in range(100)}
        result = create_chart(data, chart_hint="bar", use_llm=False)

        # 应该限制类别数量
        config = result["config"]
        if "xAxis" in config and "data" in config["xAxis"]:
            assert len(config["xAxis"]["data"]) <= 50


class TestLLMMode:
    """测试 LLM 模式"""

    def test_llm_disabled(self):
        """测试禁用 LLM"""
        data = {"A": 10, "B": 20}
        result = create_chart(data, use_llm=False)

        assert result["metadata"]["generation_method"] == "rule"

    def test_llm_enabled_without_query(self):
        """测试启用 LLM 但没有查询"""
        data = {"A": 10, "B": 20}
        result = create_chart(data, use_llm=True, user_query="")

        # 没有 user_query 时应该使用规则生成
        assert result["metadata"]["generation_method"] == "rule"


class TestMetadata:
    """测试元数据"""

    def test_metadata_content(self):
        """测试元数据内容"""
        data = {"A": 10, "B": 20}
        result = create_chart(data, use_llm=False)

        metadata = result["metadata"]
        assert "data_type" in metadata
        assert "data_rows" in metadata
        assert "data_columns" in metadata
        assert "generation_method" in metadata
        assert "duration_ms" in metadata

    def test_duration_recorded(self):
        """测试耗时记录"""
        data = {"A": 10, "B": 20}
        result = create_chart(data, use_llm=False)

        assert result["metadata"]["duration_ms"] >= 0
