"""
归因分析 Skill

分析指标变化的归因因素。

支持三种归因方法:
1. contribution - 贡献度分析
2. correlation - 相关性分析
3. ai - AI 智能归因分析 (Claude)
"""

from typing import Any, Dict, List, Optional, Union
import os
from datetime import datetime
import json

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ===== 贡献度分析 =====

def _contribution_analysis(
    data: pd.DataFrame,
    dimension: str,
    value_col: str
) -> Dict[str, Any]:
    """
    贡献度分析 - 计算各维度值对总体变化的贡献

    Args:
        data: DataFrame
        dimension: 维度列名
        value_col: 数值列名

    Returns:
        贡献度分析结果
    """
    if dimension not in data.columns or value_col not in data.columns:
        return {
            "factors": [],
            "total": 0,
            "top_contributor": None,
            "contribution_pct": {}
        }

    # 按维度分组计算贡献
    grouped = data.groupby(dimension)[value_col].agg(['sum', 'count']).reset_index()
    grouped = grouped.sort_values('sum', ascending=False)

    total = grouped['sum'].sum()
    if total == 0:
        return {
            "factors": [],
            "total": 0,
            "top_contributor": None,
            "contribution_pct": {}
        }

    # 计算贡献度百分比
    grouped['contribution'] = (grouped['sum'] / total * 100).round(2)

    # 提取前 5 个贡献因子
    factors = []
    for _, row in grouped.head(5).iterrows():
        factors.append({
            "dimension_value": str(row[dimension]),
            "value": float(row['sum']),
            "contribution_pct": float(row['contribution']),
            "count": int(row['count'])
        })

    # 找出最大贡献者
    top_contributor = grouped.iloc[0]
    top_contributor_info = {
        "dimension_value": str(top_contributor[dimension]),
        "value": float(top_contributor['sum']),
        "contribution_pct": float(top_contributor['contribution'])
    }

    # 贡献度分布
    contribution_pct = dict(zip(
        grouped[dimension].astype(str),
        grouped['contribution'].tolist()
    ))

    return {
        "factors": factors,
        "total": float(total),
        "top_contributor": top_contributor_info,
        "contribution_pct": contribution_pct
    }


# ===== 相关性分析 =====

def _correlation_analysis(
    data: pd.DataFrame,
    dimension: str,
    value_col: str
) -> Dict[str, Any]:
    """
    相关性分析 - 分析维度与指标的相关性

    Args:
        data: DataFrame
        dimension: 维度列名
        value_col: 数值列名

    Returns:
        相关性分析结果
    """
    if dimension not in data.columns or value_col not in data.columns:
        return {
            "correlations": [],
            "insights": []
        }

    # 创建数值编码的维度
    data_encoded = data.copy()
    unique_values = data_encoded[dimension].unique()
    value_map = {v: i for i, v in enumerate(unique_values)}
    data_encoded[f"{dimension}_encoded"] = data_encoded[dimension].map(value_map)

    # 计算相关性
    corr = data_encoded[[f"{dimension}_encoded", value_col]].corr()

    correlation_value = corr.iloc[0, 1] if not corr.empty else 0

    # 按维度值分组统计
    grouped = data_encoded.groupby(dimension)[value_col].agg(['mean', 'std', 'count']).reset_index()
    grouped = grouped.sort_values('mean', ascending=False)

    correlations = []
    for _, row in grouped.iterrows():
        correlations.append({
            "dimension_value": str(row[dimension]),
            "mean_value": float(row['mean']),
            "std": float(row['std']) if pd.notna(row['std']) else 0,
            "count": int(row['count'])
        })

    # 生成洞察
    insights = []
    if abs(correlation_value) > 0.3:
        direction = "正相关" if correlation_value > 0 else "负相关"
        strength = "强" if abs(correlation_value) > 0.7 else "中等"
        insights.append(f"{dimension} 与 {value_col} 存在 {strength}{direction}")

    if len(grouped) > 1:
        max_mean = grouped.iloc[0]['mean']
        min_mean = grouped.iloc[-1]['mean']
        if max_mean > 0:
            ratio = max_mean / min_mean if min_mean != 0 else float('inf')
            if ratio > 2:
                insights.append(f"不同 {dimension} 之间差异显著，最大值是最小值的 {ratio:.1f} 倍")

    return {
        "correlations": correlations,
        "correlation_coefficient": float(correlation_value),
        "insights": insights
    }


# ===== AI 智能归因分析 =====

def _ai_attribution(
    data: pd.DataFrame,
    dimension: str,
    value_col: str,
    query: str = ""
) -> Dict[str, Any]:
    """
    使用 AI 进行智能归因分析

    Args:
        data: DataFrame
        dimension: 维度列名
        value_col: 数值列名
        query: 用户查询描述

    Returns:
        AI 分析结果
    """
    if not ANTHROPIC_AVAILABLE:
        return {
            "primary_factors": [],
            "insights": ["AI 服务不可用"],
            "recommendations": []
        }

    api_key = os.environ.get("BA_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "primary_factors": [],
            "insights": ["未配置 API Key"],
            "recommendations": []
        }

    try:
        client = Anthropic(api_key=api_key)

        # 准备数据摘要
        if dimension in data.columns:
            grouped = data.groupby(dimension)[value_col].agg(['sum', 'mean', 'count']).reset_index()
            grouped = grouped.sort_values('sum', ascending=False)

            data_summary = {
                "total_records": len(data),
                "total_value": float(data[value_col].sum()),
                "dimension": dimension,
                "dimension_values": grouped.head(10).to_dict('records'),
                "value_range": {
                    "min": float(data[value_col].min()),
                    "max": float(data[value_col].max()),
                    "mean": float(data[value_col].mean())
                }
            }
        else:
            data_summary = {
                "total_records": len(data),
                "total_value": float(data[value_col].sum()),
                "columns": data.columns.tolist()
            }

        # 构建提示词
        user_context = f"\n【用户问题】\n{query}" if query else ""

        prompt = f"""你是一个专业的数据分析师，擅长进行归因分析。

【数据摘要】
{json.dumps(data_summary, ensure_ascii=False, indent=2)}
{user_context}

【任务】
请分析上述数据，识别出影响指标变化的主要因素。

【要求】
1. 找出贡献最大的维度值
2. 分析各因素的影响程度
3. 提供可操作的洞察和建议

请以 JSON 格式返回分析结果，格式如下：
{{
  "primary_factors": [
    {{
      "factor": "因素名称",
      "impact": "高/中/低",
      "description": "因素描述"
    }}
  ],
  "insights": [
    "洞察1",
    "洞察2"
  ],
  "recommendations": [
    "建议1",
    "建议2"
  ]
}}

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

        result = json.loads(content)
        return result

    except Exception as e:
        # AI 分析失败
        return {
            "primary_factors": [],
            "insights": [f"AI 分析失败: {str(e)}"],
            "recommendations": []
        }


# ===== 数据解析 =====

def _parse_data(data: Any) -> Optional[pd.DataFrame]:
    """解析输入数据为 DataFrame"""
    if not PANDAS_AVAILABLE:
        return None

    if isinstance(data, pd.DataFrame):
        return data

    elif isinstance(data, dict):
        return pd.DataFrame(data)

    elif isinstance(data, list):
        return pd.DataFrame(data)

    return None


# ===== 主函数 =====

def analyze(
    data: Any,
    target_dimension: str,
    attribution_method: str = 'contribution',
    value_col: str = "value",
    query: str = ""
) -> Dict[str, Any]:
    """
    分析指标变化的归因因素

    Args:
        data: 输入数据 (DataFrame, dict, list)
        target_dimension: 目标分析维度
        attribution_method: 归因方法 ('contribution', 'correlation', 'ai', 'all')
        value_col: 数值列名
        query: 用户查询描述 (用于 AI 方法)

    Returns:
        归因分析结果
    """
    start_time = datetime.now()

    # 解析数据
    df = _parse_data(data)
    if df is None or len(df) == 0:
        return {
            "primary_factors": [],
            "contribution_scores": {},
            "insights": ["数据解析失败或数据为空"],
            "recommendations": [],
            "error": "数据解析失败"
        }

    # 检测数值列
    if value_col not in df.columns:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            return {
                "primary_factors": [],
                "contribution_scores": {},
                "insights": ["未找到数值列"],
                "recommendations": [],
                "error": "未找到数值列"
            }
        value_col = numeric_cols[0]

    # 自动检测维度列
    if target_dimension not in df.columns:
        # 尝试找非数值列作为维度
        non_numeric_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
        if non_numeric_cols:
            target_dimension = non_numeric_cols[0]
        else:
            target_dimension = df.columns[0]

    # 执行分析
    result = {
        "method": attribution_method,
        "dimension": target_dimension,
        "value_column": value_col,
        "primary_factors": [],
        "contribution_scores": {},
        "insights": [],
        "recommendations": [],
        "data_points": len(df)
    }

    if attribution_method == "contribution" or attribution_method == "all":
        contrib_result = _contribution_analysis(df, target_dimension, value_col)

        # 提取主要因子
        if contrib_result.get("factors"):
            for factor in contrib_result["factors"][:3]:
                result["primary_factors"].append({
                    "factor": factor["dimension_value"],
                    "impact": "高" if factor["contribution_pct"] > 30 else "中" if factor["contribution_pct"] > 10 else "低",
                    "description": f"贡献 {factor['contribution_pct']}%，值 {factor['value']:.2f}"
                })

        result["contribution_scores"] = contrib_result.get("contribution_pct", {})

        if contrib_result.get("top_contributor"):
            top = contrib_result["top_contributor"]
            result["insights"].append(
                f"主要贡献来自 {top['dimension_value']}，占比 {top['contribution_pct']}%"
            )

    if attribution_method == "correlation" or attribution_method == "all":
        corr_result = _correlation_analysis(df, target_dimension, value_col)

        result["insights"].extend(corr_result.get("insights", []))

        if attribution_method == "correlation":
            for corr in corr_result.get("correlations", [])[:3]:
                result["primary_factors"].append({
                    "factor": corr["dimension_value"],
                    "impact": "高" if abs(corr["mean_value"]) > 0 else "中",
                    "description": f"均值 {corr['mean_value']:.2f}"
                })

    if attribution_method == "ai":
        ai_result = _ai_attribution(df, target_dimension, value_col, query)

        result["primary_factors"] = ai_result.get("primary_factors", [])
        result["insights"] = ai_result.get("insights", [])
        result["recommendations"] = ai_result.get("recommendations", [])

    # 生成通用建议
    if attribution_method in ["contribution", "all"] and not result["recommendations"]:
        if result["contribution_scores"]:
            top_factor = max(result["contribution_scores"].items(),
                           key=lambda x: x[1])[0]
            result["recommendations"].append(
                f"重点关注 {top_factor} 的变化趋势"
            )

    # 计算耗时
    duration_ms = (datetime.now() - start_time).total_seconds() * 1000
    result["duration_ms"] = round(duration_ms, 2)

    return result


# ===== 辅助函数 =====

def get_supported_methods() -> List[str]:
    """获取支持的归因方法"""
    methods = ["contribution", "correlation"]
    if ANTHROPIC_AVAILABLE:
        methods.append("ai")
    methods.append("all")
    return methods


def format_attribution_report(result: Dict[str, Any]) -> str:
    """
    格式化归因分析报告

    Args:
        result: analyze() 返回的结果

    Returns:
        格式化的报告文本
    """
    lines = []
    lines.append("=" * 60)
    lines.append("归因分析报告")
    lines.append("=" * 60)
    lines.append("")

    # 基本信息
    lines.append(f"分析方法: {result.get('method', 'unknown')}")
    lines.append(f"分析维度: {result.get('dimension', 'N/A')}")
    lines.append(f"数据点数: {result.get('data_points', 0)}")
    lines.append("")

    # 主要因素
    primary_factors = result.get("primary_factors", [])
    if primary_factors:
        lines.append("主要影响因素:")
        lines.append("-" * 60)
        for i, factor in enumerate(primary_factors, 1):
            lines.append(f"{i}. {factor.get('factor', 'N/A')}")
            lines.append(f"   影响: {factor.get('impact', 'unknown')}")
            lines.append(f"   描述: {factor.get('description', 'N/A')}")
            lines.append("")

    # 洞察
    insights = result.get("insights", [])
    if insights:
        lines.append("分析洞察:")
        lines.append("-" * 60)
        for insight in insights:
            lines.append(f"• {insight}")
        lines.append("")

    # 建议
    recommendations = result.get("recommendations", [])
    if recommendations:
        lines.append("建议措施:")
        lines.append("-" * 60)
        for rec in recommendations:
            lines.append(f"• {rec}")
        lines.append("")

    # 贡献度分布
    contribution = result.get("contribution_scores", {})
    if contribution:
        lines.append("贡献度分布:")
        lines.append("-" * 60)
        for factor, pct in sorted(contribution.items(),
                                  key=lambda x: x[1],
                                  reverse=True)[:5]:
            lines.append(f"  {factor}: {pct:.1f}%")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


__all__ = [
    "analyze",
    "get_supported_methods",
    "format_attribution_report",
]
