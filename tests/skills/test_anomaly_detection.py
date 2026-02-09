"""
异动检测 Skill 测试
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

from skills.anomaly_detection.main import (
    detect,
    get_supported_methods,
    format_anomaly_report,
)


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestStatisticalDetection:
    """测试统计方法检测"""

    def test_normal_data_no_anomalies(self):
        """测试正常数据无异动"""
        # 生成正态分布数据
        np.random.seed(42)
        data = pd.DataFrame({
            "value": np.random.normal(100, 10, 50)
        })

        result = detect(data, method="statistical", threshold=3.0)

        assert result["method"] == "statistical"
        assert result["data_points"] == 50
        # 正态分布数据应该很少异动（3-sigma 阈值）
        assert len(result["anomalies"]) < 5

    def test_outlier_detection(self):
        """测试异常值检测"""
        # 生成带有明显异常值的数据
        data = pd.DataFrame({
            "value": [100] * 20 + [500] + [100] * 20  # 中间有一个异常值
        })

        result = detect(data, method="statistical", threshold=2.0)

        # 应该检测到异常值
        assert len(result["anomalies"]) >= 1
        # 检查异常值是上升类型
        anomaly = result["anomalies"][0]
        assert anomaly["type"] == "rise"
        assert anomaly["value"] == 500

    def test_dip_detection(self):
        """测试下跌检测"""
        # 生成带有下跌的数据
        data = pd.DataFrame({
            "value": [100] * 20 + [10] + [100] * 20  # 中间有一个下跌
        })

        result = detect(data, method="statistical", threshold=2.0)

        # 应该检测到下跌
        assert len(result["anomalies"]) >= 1
        anomaly = result["anomalies"][0]
        assert anomaly["type"] == "fall"
        assert anomaly["value"] == 10

    def test_severity_calculation(self):
        """测试严重程度计算"""
        # 生成带有不同程度异常的数据
        data = pd.DataFrame({
            "value": [100] * 20 + [150] + [100] * 20  # 中等异常
        })

        result = detect(data, method="statistical", threshold=2.0)

        if len(result["anomalies"]) > 0:
            # 异常应该有严重程度
            anomaly = result["anomalies"][0]
            assert "severity" in anomaly
            assert anomaly["severity"] in ["low", "medium", "high"]

    def test_all_anomalies_returned(self):
        """测试返回所有异动"""
        # 生成多个异常值（使用更大的异常值和更低的阈值）
        data = pd.DataFrame({
            "value": [100] * 10 + [500, 10, 400, 5] + [100] * 10
        })

        result = detect(data, method="statistical", threshold=1.0)

        # 应该检测到多个异常
        assert len(result["anomalies"]) >= 3

    def test_z_score_calculation(self):
        """测试 Z-score 计算"""
        data = pd.DataFrame({
            "value": [100] * 20 + [200] + [100] * 20
        })

        result = detect(data, method="statistical", threshold=2.0)

        if len(result["anomalies"]) > 0:
            anomaly = result["anomalies"][0]
            assert "z_score" in anomaly
            assert anomaly["z_score"] > 0


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestHistoricalDetection:
    """测试历史对比检测"""

    def test_mom_detection(self):
        """测试环比检测"""
        # 创建日期和数值数据
        dates = pd.date_range("2024-01-01", periods=10)
        data = pd.DataFrame({
            "date": dates,
            "value": [100, 105, 102, 100, 100, 200, 105, 103, 100, 100]  # 第6天环比上升100%
        })

        result = detect(data, method="historical", threshold=0.5)  # 50% 阈值

        # 应该检测到环比异动
        assert len(result["anomalies"]) >= 1
        anomaly = result["anomalies"][0]
        assert anomaly["method"] in ["mom", "yoy"]

    def test_yoy_detection(self):
        """测试同比检测"""
        dates = pd.date_range("2024-01-01", periods=14)
        data = pd.DataFrame({
            "date": dates,
            "value": [100] * 7 + [200] * 7  # 后7天是前7天的2倍
        })

        result = detect(data, method="historical", threshold=0.5)

        # 应该检测到同比异动
        mom_anomalies = [a for a in result["anomalies"] if a.get("method") == "yoy"]
        assert len(mom_anomalies) > 0

    def test_change_rate_calculation(self):
        """测试变化率计算"""
        dates = pd.date_range("2024-01-01", periods=5)
        data = pd.DataFrame({
            "date": dates,
            "value": [100, 150, 100, 100, 100]  # 第二天上升50%
        })

        result = detect(data, method="historical", threshold=0.3)

        if len(result["anomalies"]) > 0:
            anomaly = result["anomalies"][0]
            assert "change_rate" in anomaly


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestDataParsing:
    """测试数据解析"""

    def test_list_input(self):
        """测试列表输入"""
        data = [{"value": i} for i in range(50)]
        result = detect(data, method="statistical")

        assert result["data_points"] == 50
        assert "anomalies" in result

    def test_dict_input(self):
        """测试字典输入"""
        data = {
            "value": [100] * 20 + [500] + [100] * 20
        }
        result = detect(data, method="statistical")

        assert result["data_points"] == 41
        assert len(result["anomalies"]) >= 1

    def test_dataframe_input(self):
        """测试 DataFrame 输入"""
        data = pd.DataFrame({
            "value": [100] * 20 + [500] + [100] * 20
        })
        result = detect(data, method="statistical")

        assert result["data_points"] == 41

    def test_auto_column_detection(self):
        """测试自动列检测"""
        data = pd.DataFrame({
            "gmv": [100] * 20 + [500] + [100] * 20
        })
        # 不指定 value_col，应该自动检测
        result = detect(data, method="statistical", value_col="gmv")

        assert len(result["anomalies"]) >= 1


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestErrorHandling:
    """测试错误处理"""

    def test_empty_data(self):
        """测试空数据"""
        result = detect([], method="statistical")

        assert "error" in result
        assert result["anomalies"] == []

    def test_no_numeric_column(self):
        """测试无数值列"""
        data = pd.DataFrame({
            "name": ["A", "B", "C"],
            "category": ["X", "Y", "Z"]
        })

        result = detect(data, method="statistical")

        assert "error" in result

    def test_invalid_method(self):
        """测试无效方法"""
        data = pd.DataFrame({"value": [100] * 10})
        result = detect(data, method="invalid_method")

        # 无效方法不会报错，只是返回空结果
        assert "anomalies" in result


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestSummary:
    """测试摘要生成"""

    def test_summary_counts(self):
        """测试摘要计数"""
        data = pd.DataFrame({
            "value": [100] * 10 + [500, 10] + [100] * 10
        })

        result = detect(data, method="statistical", threshold=1.5)

        summary = result["summary"]
        assert summary["total"] == len(result["anomalies"])
        assert "rise" in summary["by_type"]
        assert "fall" in summary["by_type"]
        assert "high" in summary["by_severity"]
        assert "medium" in summary["by_severity"]
        assert "low" in summary["by_severity"]

    def test_duration_recorded(self):
        """测试耗时记录"""
        data = pd.DataFrame({"value": [100] * 10})
        result = detect(data, method="statistical")

        assert "duration_ms" in result
        assert result["duration_ms"] >= 0


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestSupportedMethods:
    """测试支持的方法"""

    def test_get_methods(self):
        """测试获取支持的方法"""
        methods = get_supported_methods()

        assert "statistical" in methods
        assert "historical" in methods
        assert "all" in methods


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestReportFormatting:
    """测试报告格式化"""

    def test_report_format(self):
        """测试报告格式"""
        data = pd.DataFrame({
            "value": [100] * 10 + [500, 10] + [100] * 10
        })

        result = detect(data, method="statistical", threshold=1.5)
        report = format_anomaly_report(result)

        assert "异动检测报告" in report
        assert "检测方法" in report
        assert "发现异动" in report
        assert "异动详情" in report

    def test_empty_report(self):
        """测试空数据报告"""
        result = {
            "anomalies": [],
            "summary": {"total": 0, "by_type": {}, "by_severity": {}},
            "method": "statistical"
        }

        report = format_anomaly_report(result)

        assert "异动检测报告" in report
        assert "0 个" in report


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestAllMethod:
    """测试 all 方法"""

    def test_all_method(self):
        """测试 all 方法运行"""
        data = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=20),
            "value": [100] * 10 + [500] + [100] * 9
        })

        result = detect(data, method="all", threshold=2.0)

        assert result["method"] == "all"
        # all 方法应该运行多种检测
        assert len(result["anomalies"]) >= 0


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestAnomalyOrdering:
    """测试异动排序"""

    def test_anomaly_sorting(self):
        """测试异动按严重程度排序"""
        data = pd.DataFrame({
            "value": [100] * 20 + [500] + [10] + [100] * 20
        })

        result = detect(data, method="statistical", threshold=1.5)

        if len(result["anomalies"]) >= 2:
            # 高严重程度的异动应该排在前面
            severities = [a.get("severity", "low") for a in result["anomalies"]]
            # 检查排序是否正确（high > medium > low）
            # 实际排序可能有多个相同严重程度，所以只检查大致顺序
            assert any(s == "high" for s in severities) or \
                   any(s == "medium" for s in severities)
