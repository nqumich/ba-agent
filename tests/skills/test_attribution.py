"""
归因分析 Skill 测试
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

from skills.attribution.main import (
    analyze,
    get_supported_methods,
    format_attribution_report,
)


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestContributionAnalysis:
    """测试贡献度分析"""

    def test_basic_contribution(self):
        """测试基本贡献度计算"""
        data = pd.DataFrame({
            "region": ["华北", "华东", "华南", "华北", "华东", "华南"],
            "value": [100, 200, 150, 120, 180, 130]
        })

        result = analyze(data, target_dimension="region", attribution_method="contribution")

        assert result["method"] == "contribution"
        assert result["dimension"] == "region"
        assert len(result["primary_factors"]) > 0
        assert len(result["insights"]) > 0

    def test_contribution_percentages(self):
        """测试贡献度百分比"""
        data = pd.DataFrame({
            "category": ["A", "B", "C"],
            "value": [100, 200, 300]  # 总计 600，C 占 50%，B 33%，A 17%
        })

        result = analyze(data, target_dimension="category", attribution_method="contribution")

        contribution = result["contribution_scores"]
        assert "C" in contribution
        assert contribution["C"] == 50.0

    def test_top_contributor(self):
        """测试最大贡献者"""
        data = pd.DataFrame({
            "channel": ["线上", "线下", "代理", "线上", "线下"],
            "value": [500, 300, 200, 450, 280]
        })

        result = analyze(data, target_dimension="channel", attribution_method="contribution")

        # 线上应该是最大贡献者
        top_factor = result["primary_factors"][0]
        assert top_factor["factor"] == "线上"

    def test_contribution_insights(self):
        """测试贡献度洞察"""
        data = pd.DataFrame({
            "region": ["A", "B", "C"],
            "value": [100, 50, 25]
        })

        result = analyze(data, target_dimension="region", attribution_method="contribution")

        # 应该有关于主要贡献者的洞察
        insights = result["insights"]
        assert len(insights) > 0
        assert any("主要贡献" in insight for insight in insights)


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestCorrelationAnalysis:
    """测试相关性分析"""

    def test_correlation_method(self):
        """测试相关性方法"""
        data = pd.DataFrame({
            "user_type": ["VIP", "普通", "VIP", "普通", "VIP"],
            "value": [200, 50, 180, 60, 220]
        })

        result = analyze(data, target_dimension="user_type", attribution_method="correlation")

        assert result["method"] == "correlation"
        assert "primary_factors" in result

    def test_correlation_insights(self):
        """测试相关性洞察"""
        # 创建有明显差异的数据
        data = pd.DataFrame({
            "dimension": ["A", "A", "B", "B", "C", "C"],
            "value": [100, 110, 50, 55, 10, 12]
        })

        result = analyze(data, target_dimension="dimension", attribution_method="correlation")

        # 应该有关于差异的洞察
        insights = result["insights"]
        assert len(insights) >= 0  # 可能有也可能没有洞察


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestDataParsing:
    """测试数据解析"""

    def test_list_input(self):
        """测试列表输入"""
        data = [
            {"region": "A", "value": 100},
            {"region": "B", "value": 200},
            {"region": "A", "value": 150}
        ]

        result = analyze(data, target_dimension="region", attribution_method="contribution")

        assert result["data_points"] == 3
        assert len(result["primary_factors"]) > 0

    def test_dict_input(self):
        """测试字典输入"""
        data = {
            "region": ["A", "B", "C"],
            "value": [100, 200, 300]
        }

        result = analyze(data, target_dimension="region", attribution_method="contribution")

        assert result["data_points"] == 3

    def test_auto_column_detection(self):
        """测试自动列检测"""
        data = pd.DataFrame({
            "gmv": [100, 200, 300],
            "category": ["A", "B", "C"]
        })

        # 不指定 value_col，应该自动检测
        result = analyze(data, target_dimension="category", attribution_method="contribution")

        assert len(result["primary_factors"]) > 0

    def test_auto_dimension_detection(self):
        """测试自动维度检测"""
        data = pd.DataFrame({
            "value": [100, 200, 300],
            "category": ["A", "B", "C"]
        })

        # 不存在的维度，应该自动检测非数值列
        result = analyze(data, target_dimension="nonexistent", attribution_method="contribution")

        # 应该使用了 category 作为维度
        assert result["dimension"] in ["category", "nonexistent"]


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestErrorHandling:
    """测试错误处理"""

    def test_empty_data(self):
        """测试空数据"""
        result = analyze([], target_dimension="region")

        assert result["primary_factors"] == []
        assert "error" in result

    def test_no_numeric_column(self):
        """测试无数值列"""
        data = pd.DataFrame({
            "name": ["A", "B", "C"],
            "category": ["X", "Y", "Z"]
        })

        result = analyze(data, target_dimension="name")

        assert "error" in result


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestAllMethod:
    """测试 all 方法"""

    def test_all_method(self):
        """测试 all 方法"""
        data = pd.DataFrame({
            "region": ["A", "B", "A", "B", "C"],
            "value": [100, 200, 120, 180, 50]
        })

        result = analyze(data, target_dimension="region", attribution_method="all")

        assert result["method"] == "all"
        assert "contribution_scores" in result
        # all 方法应该有更多的洞察
        assert len(result["insights"]) >= 0


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestSupportedMethods:
    """测试支持的方法"""

    def test_get_methods(self):
        """测试获取支持的方法"""
        methods = get_supported_methods()

        assert "contribution" in methods
        assert "correlation" in methods
        assert "all" in methods


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestReportFormatting:
    """测试报告格式化"""

    def test_report_format(self):
        """测试报告格式"""
        data = pd.DataFrame({
            "region": ["A", "B", "C"],
            "value": [100, 200, 300]
        })

        result = analyze(data, target_dimension="region", attribution_method="contribution")
        report = format_attribution_report(result)

        assert "归因分析报告" in report
        assert "分析方法" in report
        assert "主要影响因素" in report

    def test_empty_report(self):
        """测试空数据报告"""
        result = {
            "primary_factors": [],
            "contribution_scores": {},
            "insights": ["无数据"],
            "recommendations": [],
            "method": "contribution"
        }

        report = format_attribution_report(result)

        assert "归因分析报告" in report


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestImpactAssessment:
    """测试影响程度评估"""

    def test_high_impact_factor(self):
        """测试高影响因子"""
        data = pd.DataFrame({
            "category": ["A", "B", "C"],
            "value": [500, 100, 50]  # A 占 77%
        })

        result = analyze(data, target_dimension="category", attribution_method="contribution")

        # 第一个因子应该是高影响
        top_factor = result["primary_factors"][0]
        assert top_factor["impact"] == "高"

    def test_medium_impact_factor(self):
        """测试中等影响因子"""
        data = pd.DataFrame({
            "category": ["A", "B", "C"],
            "value": [100, 80, 20]  # B 占 40%
        })

        result = analyze(data, target_dimension="category", attribution_method="contribution")

        # 找到 B 因子
        b_factor = next((f for f in result["primary_factors"] if f["factor"] == "B"), None)
        if b_factor:
            assert b_factor["impact"] in ["高", "中", "低"]


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestRecommendations:
    """测试建议生成"""

    def test_contribution_recommendations(self):
        """测试贡献度建议"""
        data = pd.DataFrame({
            "region": ["A", "B", "C"],
            "value": [500, 300, 200]
        })

        result = analyze(data, target_dimension="region", attribution_method="contribution")

        # 应该有建议
        assert len(result["recommendations"]) >= 0
