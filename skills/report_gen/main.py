"""
报告生成 Skill

自动生成业务分析报告。

支持:
- 多种报告类型: daily (日报), weekly (周报), monthly (月报), custom (自定义)
- 多种输出格式: markdown, html, pdf
- 核心指标汇总
- 章节内容生成
- AI 增强 (Claude)
"""

from typing import Any, Dict, List, Optional, Union
import os
from datetime import datetime, date, timedelta
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


# ===== 报告模板 =====

REPORT_TEMPLATES = {
    "daily": {
        "title": "业务日报",
        "sections": [
            "核心指标概览",
            "关键异动提醒",
            "今日重点关注",
            "明日建议"
        ]
    },
    "weekly": {
        "title": "业务周报",
        "sections": [
            "本周经营概况",
            "核心指标趋势",
            "异动分析",
            "下周策略建议"
        ]
    },
    "monthly": {
        "title": "业务月报",
        "sections": [
            "月度经营总结",
            "关键指标分析",
            "异动复盘",
            "下月规划"
        ]
    },
    "custom": {
        "title": "业务分析报告",
        "sections": [
            "概览",
            "分析",
            "结论",
            "建议"
        ]
    }
}


# ===== 数据聚合 =====

def _aggregate_metrics(data: Any) -> Dict[str, Any]:
    """
    聚合核心指标

    Args:
        data: 输入数据

    Returns:
        聚合后的指标
    """
    if not PANDAS_AVAILABLE:
        return {}

    # 解析数据
    if isinstance(data, pd.DataFrame):
        df = data
    elif isinstance(data, dict):
        df = pd.DataFrame(data)
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        return {}

    if df.empty:
        return {}

    metrics = {}

    # 数值列统计
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) > 0:
            metrics[col] = {
                "total": float(col_data.sum()),
                "mean": float(col_data.mean()),
                "min": float(col_data.min()),
                "max": float(col_data.max()),
                "count": int(len(col_data))
            }

            # 计算增长 (如果有时间序列)
            if len(col_data) >= 2:
                first_val = col_data.iloc[0]
                last_val = col_data.iloc[-1]
                if first_val != 0:
                    growth = ((last_val - first_val) / first_val) * 100
                    metrics[col]["growth_rate"] = round(growth, 2)

    # 数据行数
    metrics["total_records"] = len(df)

    return metrics


# ===== AI 增强内容生成 =====

def _ai_enhance_content(
    report_type: str,
    metrics: Dict[str, Any],
    custom_query: str = ""
) -> Dict[str, Any]:
    """
    使用 AI 增强报告内容

    Args:
        report_type: 报告类型
        metrics: 指标数据
        custom_query: 自定义查询

    Returns:
        AI 生成的内容
    """
    if not ANTHROPIC_AVAILABLE:
        return {
            "summary": "",
            "insights": [],
            "recommendations": []
        }

    api_key = os.environ.get("BA_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "summary": "",
            "insights": [],
            "recommendations": []
        }

    try:
        client = Anthropic(api_key=api_key)

        # 构建提示词
        template = REPORT_TEMPLATES.get(report_type, REPORT_TEMPLATES["custom"])
        sections = template.get("sections", [])

        prompt = f"""你是一个专业的业务分析师，擅长撰写业务分析报告。

【报告类型】
{template['title']}

【报告章节】
{', '.join(sections)}

【核心指标】
{json.dumps(metrics, ensure_ascii=False, indent=2, default=str)}

{f'【用户需求】\n{custom_query}' if custom_query else ''}

【任务】
请根据上述信息生成报告内容，包括：
1. 一段简短的执行摘要 (summary)
2. 3-5 条关键洞察 (insights)
3. 3-5 条可操作建议 (recommendations)

请以 JSON 格式返回，格式如下：
{{
  "summary": "执行摘要...",
  "insights": ["洞察1", "洞察2", ...],
  "recommendations": ["建议1", "建议2", ...]
}}

只返回 JSON，不要包含其他解释。"""

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.5,
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
        return {
            "summary": f"AI 内容生成失败: {str(e)}",
            "insights": [],
            "recommendations": []
        }


# ===== Markdown 报告生成 =====

def _generate_markdown(
    report_type: str,
    metrics: Dict[str, Any],
    ai_content: Dict[str, Any],
    title_override: Optional[str] = None
) -> str:
    """
    生成 Markdown 格式报告

    Args:
        report_type: 报告类型
        metrics: 指标数据
        ai_content: AI 生成的内容
        title_override: 自定义标题

    Returns:
        Markdown 文本
    """
    template = REPORT_TEMPLATES.get(report_type, REPORT_TEMPLATES["custom"])
    title = title_override or template["title"]
    sections = template.get("sections", [])

    # 获取当前日期
    today = date.today()
    period_str = _get_period_string(report_type, today)

    lines = []
    lines.append(f"# {title}")
    lines.append(f"\n**报告周期**: {period_str}")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("\n---\n")

    # 执行摘要
    summary = ai_content.get("summary", "")
    if summary:
        lines.append("## 执行摘要")
        lines.append(summary)
        lines.append("\n")

    # 核心指标
    if metrics:
        lines.append("## 核心指标")
        lines.append("\n| 指标 | 总计 | 均值 | 最小值 | 最大值 | 增长率 |")
        lines.append("|------|------|------|--------|--------|--------|")

        for key, value in metrics.items():
            if key != "total_records" and isinstance(value, dict):
                name = key.replace("_", " ").title()
                total = value.get("total", 0)
                mean = value.get("mean", 0)
                min_val = value.get("min", 0)
                max_val = value.get("max", 0)
                growth = value.get("growth_rate", 0)
                growth_str = f"{growth:+.1f}%" if "growth_rate" in value else "N/A"

                lines.append(f"| {name} | {total:.2f} | {mean:.2f} | {min_val:.2f} | {max_val:.2f} | {growth_str} |")

        lines.append("\n")

    # 按章节生成内容
    if report_type == "daily":
        if "核心指标概览" in sections:
            lines.append("## 核心指标概览")
            lines.append(_generate_metrics_summary(metrics))
            lines.append("\n")

        if "关键异动提醒" in sections:
            lines.append("## 关键异动提醒")
            lines.extend(_format_insights(ai_content.get("insights", [])))
            lines.append("\n")

        if "今日重点关注" in sections:
            lines.append("## 今日重点关注")
            lines.extend(_format_insights(ai_content.get("insights", [])))
            lines.append("\n")

        if "明日建议" in sections:
            lines.append("## 明日建议")
            lines.extend(_format_recommendations(ai_content.get("recommendations", [])))

    elif report_type == "weekly":
        if "本周经营概况" in sections:
            lines.append("## 本周经营概况")
            lines.append(summary or "详见核心指标部分")
            lines.append("\n")

        if "核心指标趋势" in sections:
            lines.append("## 核心指标趋势")
            lines.append(_generate_metrics_summary(metrics))
            lines.append("\n")

        if "异动分析" in sections:
            lines.append("## 异动分析")
            lines.extend(_format_insights(ai_content.get("insights", [])))
            lines.append("\n")

        if "下周策略建议" in sections:
            lines.append("## 下周策略建议")
            lines.extend(_format_recommendations(ai_content.get("recommendations", [])))

    elif report_type == "monthly":
        if "月度经营总结" in sections:
            lines.append("## 月度经营总结")
            lines.append(summary or "详见核心指标部分")
            lines.append("\n")

        if "关键指标分析" in sections:
            lines.append("## 关键指标分析")
            lines.append(_generate_metrics_summary(metrics))
            lines.append("\n")

        if "异动复盘" in sections:
            lines.append("## 异动复盘")
            lines.extend(_format_insights(ai_content.get("insights", [])))
            lines.append("\n")

        if "下月规划" in sections:
            lines.append("## 下月规划")
            lines.extend(_format_recommendations(ai_content.get("recommendations", [])))

    else:
        # 自定义报告
        for section in sections:
            lines.append(f"## {section}")
            lines.append("*（内容待补充）*")
            lines.append("\n")

    lines.append("\n---")
    lines.append(f"\n*本报告由 BA-Agent 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)


# ===== HTML 报告生成 =====

def _generate_html(
    report_type: str,
    metrics: Dict[str, Any],
    ai_content: Dict[str, Any],
    title_override: Optional[str] = None
) -> str:
    """
    生成 HTML 格式报告

    Args:
        report_type: 报告类型
        metrics: 指标数据
        ai_content: AI 生成的内容
        title_override: 自定义标题

    Returns:
        HTML 文本
    """
    # 先生成 Markdown，再转换（简单实现）
    markdown = _generate_markdown(report_type, metrics, ai_content, title_override)

    # 简单 Markdown 转 HTML
    html = markdown
    html = html.replace("# ", "<h1>").replace("\n", "</h1>\n", 1)
    html = html.replace("## ", "<h2>").replace("\n", "</h2>\n")
    html = html.replace("### ", "<h3>").replace("\n", "</h3>\n")
    html = html.replace("**", "<strong>").replace("**", "</strong>")

    # 表格处理
    lines = html.split("\n")
    in_table = False
    processed_lines = []

    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            if not in_table:
                processed_lines.append("<table>")
                in_table = True
            if "---" in line:
                continue  # 跳过分隔行
            cells = [c.strip() for c in line.split("|")[1:-1]]
            processed_lines.append("<tr>")
            for cell in cells:
                processed_lines.append(f"<td>{cell}</td>")
            processed_lines.append("</tr>")
        else:
            if in_table:
                processed_lines.append("</table>")
                in_table = False
            processed_lines.append(line)

    if in_table:
        processed_lines.append("</table>")

    html = "\n".join(processed_lines)

    # 包装完整 HTML
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title_override or REPORT_TEMPLATES[report_type]['title']}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        h3 {{ color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        td, th {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background-color: #f5f5f5; }}
        strong {{ color: #007bff; }}
        ul {{ margin: 10px 0; }}
        li {{ margin: 5px 0; }}
    </style>
</head>
<body>
{html}
</body>
</html>"""

    return full_html


# ===== 辅助函数 =====

def _get_period_string(report_type: str, report_date: date) -> str:
    """获取周期字符串"""
    if report_type == "daily":
        return report_date.strftime("%Y年%m月%d日")
    elif report_type == "weekly":
        week_start = report_date - timedelta(days=report_date.weekday())
        week_end = week_start + timedelta(days=6)
        return f"{week_start.strftime('%Y%m%d')} - {week_end.strftime('%Y%m%d')}"
    elif report_type == "monthly":
        return report_date.strftime("%Y年%m月")
    else:
        return report_date.strftime("%Y%m%d")


def _generate_metrics_summary(metrics: Dict[str, Any]) -> str:
    """生成指标摘要"""
    if not metrics:
        return "*暂无指标数据*"

    lines = []
    for key, value in metrics.items():
        if key != "total_records" and isinstance(value, dict):
            name = key.replace("_", " ").title()
            total = value.get("total", 0)
            growth = value.get("growth_rate")

            if growth is not None:
                direction = "↑" if growth > 0 else "↓" if growth < 0 else "→"
                lines.append(f"- **{name}**: {total:.2f} ({direction}{abs(growth):.1f}%)")
            else:
                lines.append(f"- **{name}**: {total:.2f}")

    return "\n".join(lines) if lines else "*暂无指标数据*"


def _format_insights(insights: List[str]) -> List[str]:
    """格式化洞察列表"""
    if not insights:
        return ["*暂无洞察*"]
    return [f"- {insight}" for insight in insights]


def _format_recommendations(recommendations: List[str]) -> List[str]:
    """格式化建议列表"""
    if not recommendations:
        return ["*暂无建议*"]
    return [f"{i+1}. {rec}" for i, rec in enumerate(recommendations)]


# ===== 主函数 =====

def generate(
    report_type: str,
    data: Any,
    format: str = 'markdown',
    title: Optional[str] = None,
    use_ai: bool = True,
    query: str = ""
) -> Dict[str, Any]:
    """
    生成业务分析报告

    Args:
        report_type: 报告类型 ('daily', 'weekly', 'monthly', 'custom')
        data: 业务数据 (DataFrame, dict, list)
        format: 输出格式 ('markdown', 'html')
        title: 自定义报告标题
        use_ai: 是否使用 AI 增强内容
        query: 自定义查询（用于 AI 生成）

    Returns:
        生成的报告信息字典
    """
    start_time = datetime.now()

    # 验证报告类型
    if report_type not in REPORT_TEMPLATES:
        report_type = "custom"

    # 聚合指标
    metrics = _aggregate_metrics(data)

    # AI 生成内容
    ai_content = {"summary": "", "insights": [], "recommendations": []}
    if use_ai:
        ai_content = _ai_enhance_content(report_type, metrics, query)

    # 生成报告内容
    content = ""
    if format == "html":
        content = _generate_html(report_type, metrics, ai_content, title)
    else:  # 默认 markdown
        content = _generate_markdown(report_type, metrics, ai_content, title)

    # 计算耗时
    duration_ms = (datetime.now() - start_time).total_seconds() * 1000

    template = REPORT_TEMPLATES[report_type]

    return {
        "title": title or template["title"],
        "report_type": report_type,
        "format": format,
        "content": content,
        "period": _get_period_string(report_type, date.today()),
        "sections": template.get("sections", []),
        "metrics": metrics,
        "insights": ai_content.get("insights", []),
        "recommendations": ai_content.get("recommendations", []),
        "duration_ms": round(duration_ms, 2),
        "generated_at": datetime.now().isoformat()
    }


# ===== 辅助导出函数 =====

def save_report(report: Dict[str, Any], file_path: str) -> bool:
    """
    保存报告到文件

    Args:
        report: generate() 返回的报告字典
        file_path: 保存路径

    Returns:
        是否成功
    """
    try:
        content = report["content"]
        format = report["format"]

        # 确定文件扩展名
        if not file_path.endswith((".md", ".html", ".txt")):
            if format == "html":
                file_path += ".html"
            else:
                file_path += ".md"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True
    except Exception as e:
        return False


def get_supported_report_types() -> List[str]:
    """获取支持的报告类型"""
    return list(REPORT_TEMPLATES.keys())


def get_supported_formats() -> List[str]:
    """获取支持的输出格式"""
    return ["markdown", "html"]


__all__ = [
    "generate",
    "save_report",
    "get_supported_report_types",
    "get_supported_formats",
]
