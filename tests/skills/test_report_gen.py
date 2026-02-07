"""
报告生成 Skill 测试
"""

import pytest
import sys
from pathlib import Path

# 添加 skills 目录到路径
skills_dir = Path(__file__).parent.parent.parent / "skills"
sys.path.insert(0, str(skills_dir))

# 需要导入 pandas 和 numpy 进行测试
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from skills.report_gen.main import (
    generate,
    save_report,
    get_supported_report_types,
    get_supported_formats,
)


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestDailyReport:
    """测试日报生成"""

    def test_daily_report_generation(self):
        """测试日报生成"""
        data = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "gmv": [1000, 1200, 1100],
            "orders": [50, 60, 55]
        })

        result = generate("daily", data, use_ai=False)

        assert result["report_type"] == "daily"
        assert result["title"] == "业务日报"
        assert "content" in result
        assert len(result["content"]) > 0

    def test_daily_report_sections(self):
        """测试日报章节"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("daily", data, use_ai=False)

        # 应该有日报的章节
        assert "sections" in result
        assert "核心指标概览" in result["sections"]
        assert "明日建议" in result["sections"]


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestWeeklyReport:
    """测试周报生成"""

    def test_weekly_report_generation(self):
        """测试周报生成"""
        data = pd.DataFrame({
            "gmv": [5000, 6000, 5500],
            "orders": [250, 300, 275]
        })

        result = generate("weekly", data, use_ai=False)

        assert result["report_type"] == "weekly"
        assert result["title"] == "业务周报"

    def test_weekly_report_sections(self):
        """测试周报章节"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("weekly", data, use_ai=False)

        assert "本周经营概况" in result["sections"]
        assert "下周策略建议" in result["sections"]


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestMonthlyReport:
    """测试月报生成"""

    def test_monthly_report_generation(self):
        """测试月报生成"""
        data = pd.DataFrame({
            "gmv": [50000, 60000, 55000]
        })

        result = generate("monthly", data, use_ai=False)

        assert result["report_type"] == "monthly"
        assert result["title"] == "业务月报"

    def test_monthly_report_sections(self):
        """测试月报章节"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("monthly", data, use_ai=False)

        assert "月度经营总结" in result["sections"]
        assert "下月规划" in result["sections"]


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestMetricsAggregation:
    """测试指标聚合"""

    def test_basic_metrics(self):
        """测试基本指标计算"""
        data = pd.DataFrame({
            "gmv": [100, 200, 300],
            "orders": [10, 20, 30]
        })

        result = generate("daily", data, use_ai=False)

        metrics = result["metrics"]
        assert "gmv" in metrics
        assert "orders" in metrics
        assert metrics["gmv"]["total"] == 600
        assert metrics["gmv"]["mean"] == 200
        assert metrics["gmv"]["min"] == 100
        assert metrics["gmv"]["max"] == 300

    def test_growth_rate_calculation(self):
        """测试增长率计算"""
        data = pd.DataFrame({
            "value": [100, 150, 200]  # 100% 增长
        })

        result = generate("daily", data, use_ai=False)

        metrics = result["metrics"]
        assert "growth_rate" in metrics["value"]
        # (200 - 100) / 100 * 100 = 100%
        assert metrics["value"]["growth_rate"] == 100.0

    def test_list_data_input(self):
        """测试列表数据输入"""
        data = [
            {"gmv": 100, "orders": 10},
            {"gmv": 200, "orders": 20},
            {"gmv": 300, "orders": 30}
        ]

        result = generate("daily", data, use_ai=False)

        assert result["metrics"]["gmv"]["total"] == 600

    def test_dict_data_input(self):
        """测试字典数据输入"""
        data = {
            "gmv": [100, 200, 300],
            "orders": [10, 20, 30]
        }

        result = generate("daily", data, use_ai=False)

        assert result["metrics"]["gmv"]["total"] == 600


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestMarkdownFormat:
    """测试 Markdown 格式"""

    def test_markdown_content(self):
        """测试 Markdown 内容"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("daily", data, format="markdown", use_ai=False)

        content = result["content"]
        assert "# 业务日报" in content
        assert "## 核心指标" in content
        assert "|" in content  # 表格

    def test_markdown_table(self):
        """测试 Markdown 表格"""
        data = pd.DataFrame({
            "gmv": [100, 200, 300]
        })

        result = generate("daily", data, format="markdown", use_ai=False)

        content = result["content"]
        assert "| Gmv |" in content or "| gmv |" in content


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestHTMLFormat:
    """测试 HTML 格式"""

    def test_html_content(self):
        """测试 HTML 内容"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("daily", data, format="html", use_ai=False)

        content = result["content"]
        assert "<!DOCTYPE html>" in content
        # 检查有基本的 HTML 结构即可
        assert "<html>" in content
        assert "<body>" in content
        # 标题可能被转换了，检查原文中的内容
        assert "业务日报" in content

    def test_html_styling(self):
        """测试 HTML 样式"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("daily", data, format="html", use_ai=False)

        content = result["content"]
        assert "<style>" in content
        assert "font-family" in content


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestCustomReport:
    """测试自定义报告"""

    def test_custom_report_type(self):
        """测试自定义报告类型"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("custom", data, use_ai=False)

        assert result["report_type"] == "custom"
        assert result["title"] == "业务分析报告"

    def test_custom_title(self):
        """测试自定义标题"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("daily", data, title="我的日报", use_ai=False)

        assert result["title"] == "我的日报"

    def test_invalid_report_type(self):
        """测试无效报告类型"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("invalid_type", data, use_ai=False)

        # 应该回退到 custom
        assert result["report_type"] == "custom"


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestReportSaving:
    """测试报告保存"""

    def test_save_markdown_report(self, tmp_path):
        """测试保存 Markdown 报告"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("daily", data, format="markdown", use_ai=False)
        file_path = tmp_path / "test_report.md"

        success = save_report(result, str(file_path))

        assert success is True
        assert file_path.exists()

    def test_save_html_report(self, tmp_path):
        """测试保存 HTML 报告"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("daily", data, format="html", use_ai=False)
        file_path = tmp_path / "test_report"

        success = save_report(result, str(file_path))

        assert success is True
        assert (tmp_path / "test_report.html").exists()


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestSupportedOptions:
    """测试支持的选项"""

    def test_supported_report_types(self):
        """测试支持的报告类型"""
        types = get_supported_report_types()

        assert "daily" in types
        assert "weekly" in types
        assert "monthly" in types
        assert "custom" in types

    def test_supported_formats(self):
        """测试支持的格式"""
        formats = get_supported_formats()

        assert "markdown" in formats
        assert "html" in formats


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestReportMetadata:
    """测试报告元数据"""

    def test_report_metadata(self):
        """测试报告元数据"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        result = generate("daily", data, use_ai=False)

        assert "title" in result
        assert "report_type" in result
        assert "format" in result
        assert "period" in result
        assert "generated_at" in result
        assert "duration_ms" in result

    def test_period_string(self):
        """测试周期字符串"""
        data = pd.DataFrame({
            "value": [100, 200, 300]
        })

        daily_result = generate("daily", data, use_ai=False)
        assert "年" in daily_result["period"]
        assert "月" in daily_result["period"]
        assert "日" in daily_result["period"]

        weekly_result = generate("weekly", data, use_ai=False)
        assert "-" in weekly_result["period"]  # 周报应该有日期范围

        monthly_result = generate("monthly", data, use_ai=False)
        assert "年" in monthly_result["period"]
        assert "月" in monthly_result["period"]


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestEmptyData:
    """测试空数据处理"""

    def test_empty_dataframe(self):
        """测试空 DataFrame"""
        data = pd.DataFrame()

        result = generate("daily", data, use_ai=False)

        # 应该仍然生成报告，只是没有指标
        assert "content" in result
        assert len(result["content"]) > 0

    def test_no_numeric_columns(self):
        """测试无数值列"""
        data = pd.DataFrame({
            "name": ["A", "B", "C"],
            "category": ["X", "Y", "Z"]
        })

        result = generate("daily", data, use_ai=False)

        # 应该仍然生成报告
        assert "content" in result
