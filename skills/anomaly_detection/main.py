"""
异动检测 Skill

检测数据中的异常波动并分析可能原因。

支持三种检测方法:
1. statistical - 基于 3-sigma 的统计检测
2. historical - 历史对比 (同比/环比)
3. ai - AI 智能识别 (Claude)
"""

from typing import Any, Dict, List, Optional, Union
import os
from datetime import datetime, timedelta

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ===== 异动严重程度评估 =====

def _calculate_severity(
    value: float,
    expected: float,
    std: float,
    threshold: float
) -> str:
    """
    计算异动严重程度

    Args:
        value: 实际值
        expected: 期望值
        std: 标准差
        threshold: 阈值

    Returns:
        严重程度: low, medium, high
    """
    if std == 0:
        return "low"

    z_score = abs(value - expected) / std

    if z_score < threshold:
        return "low"
    elif z_score < threshold * 1.5:
        return "medium"
    else:
        return "high"


# ===== 统计方法检测 (3-sigma) =====

def _statistical_detection(
    data: pd.DataFrame,
    value_col: str,
    threshold: float = 2.0
) -> List[Dict[str, Any]]:
    """
    使用 3-sigma 统计方法检测异动

    Args:
        data: DataFrame
        value_col: 数值列名
        threshold: 标准差倍数阈值

    Returns:
        异动列表
    """
    anomalies = []

    # 计算统计量
    mean = data[value_col].mean()
    std = data[value_col].std()

    if std == 0:
        return anomalies

    # 检测异动
    for idx, row in data.iterrows():
        value = row[value_col]
        z_score = abs(value - mean) / std

        if z_score >= threshold:
            anomalies.append({
                "date": str(row.get("date", idx)),
                "value": float(value),
                "expected": float(mean),
                "deviation": float(value - mean),
                "z_score": float(z_score),
                "type": "rise" if value > mean else "fall",
                "severity": _calculate_severity(value, mean, std, threshold),
                "method": "statistical",
                "reason": f"值 {value:.2f} 偏离均值 {mean:.2f} 达 {z_score:.1f} 个标准差"
            })

    return anomalies


# ===== 历史对比检测 (同比/环比) =====

def _historical_detection(
    data: pd.DataFrame,
    date_col: str,
    value_col: str,
    threshold: float = 0.2
) -> List[Dict[str, Any]]:
    """
    使用历史对比方法检测异动

    Args:
        data: DataFrame
        date_col: 日期列名
        value_col: 数值列名
        threshold: 变化率阈值 (默认 20%)

    Returns:
        异动列表
    """
    anomalies = []

    if date_col not in data.columns:
        return anomalies

    # 确保日期列是 datetime 类型
    data = data.copy()
    data[date_col] = pd.to_datetime(data[date_col])

    # 按日期排序
    data = data.sort_values(date_col)

    # 计算环比 (相比前一个周期)
    data["prev_value"] = data[value_col].shift(1)
    data["mom_change"] = (data[value_col] - data["prev_value"]) / data["prev_value"]

    # 计算同比 (相比去年同期)
    data["yoy_value"] = data[value_col].shift(7)  # 假设7天为一个周期
    data["yoy_change"] = (data[value_col] - data["yoy_value"]) / data["yoy_value"]

    # 检测环比异动
    for idx, row in data.iterrows():
        if pd.notna(row["mom_change"]) and abs(row["mom_change"]) >= threshold:
            change_pct = row["mom_change"] * 100
            anomalies.append({
                "date": str(row[date_col].date()),
                "value": float(row[value_col]),
                "prev_value": float(row["prev_value"]),
                "change_rate": float(change_pct),
                "type": "rise" if row["mom_change"] > 0 else "fall",
                "severity": "high" if abs(change_pct) >= 50 else "medium",
                "method": "mom",  # Month-over-Month / 环比
                "reason": f"环比{'上升' if row['mom_change'] > 0 else '下降'} {abs(change_pct):.1f}%"
            })

        # 检测同比异动
        if pd.notna(row["yoy_change"]) and abs(row["yoy_change"]) >= threshold:
            change_pct = row["yoy_change"] * 100
            anomalies.append({
                "date": str(row[date_col].date()),
                "value": float(row[value_col]),
                "yoy_value": float(row["yoy_value"]),
                "change_rate": float(change_pct),
                "type": "rise" if row["yoy_change"] > 0 else "fall",
                "severity": "high" if abs(change_pct) >= 50 else "medium",
                "method": "yoy",  # Year-over-Year / 同比
                "reason": f"同比{'上升' if row['yoy_change'] > 0 else '下降'} {abs(change_pct):.1f}%"
            })

    return anomalies


# ===== AI 智能检测 =====

def _ai_detection(
    data: pd.DataFrame,
    value_col: str,
    threshold: float = 2.0
) -> List[Dict[str, Any]]:
    """
    使用 AI 智能检测异动

    Args:
        data: DataFrame
        value_col: 数值列名
        threshold: 参考阈值

    Returns:
        异动列表
    """
    if not ANTHROPIC_AVAILABLE:
        return []

    api_key = os.environ.get("BA_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return []

    try:
        client = Anthropic(api_key=api_key)

        # 准备数据摘要
        data_summary = {
            "count": len(data),
            "mean": float(data[value_col].mean()),
            "std": float(data[value_col].std()),
            "min": float(data[value_col].min()),
            "max": float(data[value_col].max()),
            "recent_values": data[value_col].tail(10).tolist()
        }

        # 构建 prompt
        prompt = f"""你是一个专业的数据分析师，擅长检测时间序列数据中的异常波动。

【数据摘要】
{data_summary}

【任务】
请分析上述数据，识别出异常波动点。

【要求】
1. 关注最近的数据点
2. 识别突然的上升或下降
3. 分析可能的异动原因

请以 JSON 格式返回异动列表，格式如下：
[
  {{
    "date": "日期索引",
    "value": 数值,
    "type": "rise" 或 "fall",
    "severity": "low", "medium" 或 "high",
    "reason": "异动原因分析"
  }}
]

如果未发现明显异动，返回空列表 []。
只返回 JSON，不要包含其他解释。"""

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # 解析 AI 返回
        content = response.content[0].text.strip()

        # 移除可能的 markdown 标记
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        import json
        anomalies = json.loads(content)

        # 添加方法标识
        for anomaly in anomalies:
            anomaly["method"] = "ai"

        return anomalies

    except Exception as e:
        # AI 检测失败，回退到统计方法
        return []


# ===== 数据解析 =====

def _parse_data(data: Any) -> Optional[pd.DataFrame]:
    """
    解析输入数据为 DataFrame

    Args:
        data: 输入数据 (DataFrame, dict, list)

    Returns:
        DataFrame 或 None
    """
    if not PANDAS_AVAILABLE:
        return None

    if isinstance(data, pd.DataFrame):
        return data

    elif isinstance(data, dict):
        # 字典转 DataFrame
        return pd.DataFrame(data)

    elif isinstance(data, list):
        # 列表转 DataFrame
        return pd.DataFrame(data)

    return None


# ===== 主函数 =====

def detect(
    data: Any,
    method: str = 'statistical',
    threshold: float = 2.0,
    date_col: str = "date",
    value_col: str = "value"
) -> Dict[str, Any]:
    """
    检测数据中的异常波动

    Args:
        data: 输入数据 (DataFrame, dict, list)
        method: 检测方法 ('statistical', 'historical', 'ai', 'all')
        threshold: 异常阈值
        date_col: 日期列名 (用于 historical 方法)
        value_col: 数值列名

    Returns:
        检测结果字典，包含:
        - anomalies: 异动列表
        - summary: 检测摘要
        - method: 使用的检测方法
    """
    start_time = datetime.now()

    # 解析数据
    df = _parse_data(data)
    if df is None or len(df) == 0:
        return {
            "anomalies": [],
            "summary": {"total": 0, "by_type": {}, "by_severity": {}},
            "method": method,
            "error": "数据解析失败或数据为空"
        }

    # 确保有数值列
    if value_col not in df.columns:
        # 尝试自动检测数值列
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            return {
                "anomalies": [],
                "summary": {"total": 0, "by_type": {}, "by_severity": {}},
                "method": method,
                "error": f"未找到数值列，指定的列 '{value_col}' 不存在"
            }
        value_col = numeric_cols[0]

    # 执行检测
    all_anomalies = []

    if method == "statistical" or method == "all":
        anomalies = _statistical_detection(df, value_col, threshold)
        all_anomalies.extend(anomalies)

    if method == "historical" or method == "all":
        anomalies = _historical_detection(df, date_col, value_col, threshold / 10)  # 20% 阈值
        all_anomalies.extend(anomalies)

    if method == "ai":
        anomalies = _ai_detection(df, value_col, threshold)
        all_anomalies.extend(anomalies)

    # 按严重程度排序
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_anomalies.sort(
        key=lambda x: (severity_order.get(x.get("severity", "low"), 3), -abs(x.get("deviation", 0)))
    )

    # 生成摘要
    summary = {
        "total": len(all_anomalies),
        "by_type": {
            "rise": len([a for a in all_anomalies if a.get("type") == "rise"]),
            "fall": len([a for a in all_anomalies if a.get("type") == "fall"])
        },
        "by_severity": {
            "high": len([a for a in all_anomalies if a.get("severity") == "high"]),
            "medium": len([a for a in all_anomalies if a.get("severity") == "medium"]),
            "low": len([a for a in all_anomalies if a.get("severity") == "low"])
        }
    }

    # 计算耗时
    duration_ms = (datetime.now() - start_time).total_seconds() * 1000

    return {
        "anomalies": all_anomalies[:20],  # 最多返回 20 个异动
        "summary": summary,
        "method": method,
        "threshold": threshold,
        "data_points": len(df),
        "duration_ms": round(duration_ms, 2)
    }


# ===== 辅助函数 =====

def get_supported_methods() -> List[str]:
    """获取支持的检测方法"""
    methods = ["statistical", "historical"]
    if ANTHROPIC_AVAILABLE:
        methods.append("ai")
    methods.append("all")
    return methods


def format_anomaly_report(result: Dict[str, Any]) -> str:
    """
    格式化异动检测报告

    Args:
        result: detect() 返回的结果

    Returns:
        格式化的报告文本
    """
    lines = []
    lines.append("=" * 60)
    lines.append("异动检测报告")
    lines.append("=" * 60)
    lines.append("")

    # 摘要
    summary = result.get("summary", {})
    lines.append(f"检测方法: {result.get('method', 'unknown')}")
    lines.append(f"数据点数: {result.get('data_points', 0)}")
    lines.append(f"检测耗时: {result.get('duration_ms', 0)} ms")
    lines.append("")
    lines.append(f"发现异动: {summary.get('total', 0)} 个")
    lines.append(f"  - 上升: {summary.get('by_type', {}).get('rise', 0)} 个")
    lines.append(f"  - 下降: {summary.get('by_type', {}).get('fall', 0)} 个")
    lines.append("")

    if summary.get('by_severity', {}).get('high', 0) > 0:
        lines.append(f"严重程度: 高 {summary.get('by_severity', {}).get('high', 0)} | "
                    f"中 {summary.get('by_severity', {}).get('medium', 0)} | "
                    f"低 {summary.get('by_severity', {}).get('low', 0)}")
    lines.append("")

    # 异动详情
    anomalies = result.get("anomalies", [])
    if anomalies:
        lines.append("异动详情:")
        lines.append("-" * 60)
        for i, anomaly in enumerate(anomalies[:10], 1):
            lines.append(f"{i}. {anomaly.get('date', 'N/A')}")
            lines.append(f"   值: {anomaly.get('value', 0):.2f}")
            lines.append(f"   类型: {'上升' if anomaly.get('type') == 'rise' else '下降'}")
            lines.append(f"   程度: {anomaly.get('severity', 'unknown').upper()}")
            lines.append(f"   原因: {anomaly.get('reason', 'N/A')}")
            lines.append("")

    if len(anomalies) > 10:
        lines.append(f"... 还有 {len(anomalies) - 10} 个异动未显示")

    lines.append("=" * 60)

    return "\n".join(lines)


__all__ = [
    "detect",
    "get_supported_methods",
    "format_anomaly_report",
]
