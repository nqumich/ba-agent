"""
数据可视化 Skill

使用 AI 生成 ECharts 可视化代码。
"""

from typing import Any, Dict, List, Optional, Union
import json
import os
from datetime import datetime

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ===== ECharts 主题配置 =====

ECHARTS_THEMES = {
    "default": {
        "colors": [
            "#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de",
            "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc"
        ]
    },
    "dark": {
        "backgroundColor": "#1a1a1a",
        "textStyle": {"color": "#e0e0e0"},
        "colors": [
            "#4992ff", "#7cffb2", "#fddd60", "#ff6e76", "#6d5dfc",
            "#41c0a6", "#ff9f7f", "#d4a4eb", "#f2a5a5"
        ]
    },
    "macarons": {
        "colors": [
            "#2ec7c9", "#b6a2de", "#5ab1ef", "#ffb980", "#d87a80",
            "#8d98b3", "#e5cf0d", "#97b552", "#95706d", "#dc69aa"
        ]
    },
    "vintage": {
        "colors": [
            "#d87c7c", "#919e8b", "#d7ab82", "#6e7074", "#61a0a8",
            "#efa18d", "#787464", "#cc7e63", "#724e58", "#4b565b"
        ]
    }
}


# ===== 图表类型推荐逻辑 =====

def recommend_chart_type(data: Any) -> str:
    """
    根据数据特征推荐图表类型

    Args:
        data: 输入数据

    Returns:
        推荐的图表类型
    """
    if PANDAS_AVAILABLE and isinstance(data, pd.DataFrame):
        # DataFrame 数据分析
        rows, cols = data.shape

        # 单列数值数据 → 折线图/柱状图
        if cols == 1 and data.iloc[:, 0].dtype in ['int64', 'float64']:
            return "line"

        # 两列数据 → 散点图
        if cols == 2 and all(data.iloc[:, i].dtype in ['int64', 'float64'] for i in range(2)):
            return "scatter"

        # 多列数值数据 → 热力图
        if cols >= 3 and all(data.select_dtypes(include=['number']).shape[0] > 0):
            return "heatmap"

        # 包含类别列 → 柱状图
        for col in data.columns:
            if data[col].dtype == 'object' or data[col].nunique() < 10:
                return "bar"

    elif isinstance(data, dict):
        # 字典数据分析
        values = list(data.values())

        # 简单键值对 → 饼图
        if all(isinstance(v, (int, float)) for v in values):
            if len(values) <= 10:
                return "pie"
            else:
                return "bar"

        # 嵌套结构
        if all(isinstance(v, dict) for v in values if isinstance(v, (dict, list))):
            return "heatmap"

    elif isinstance(data, list):
        # 列表数据分析
        if len(data) == 0:
            return "bar"

        # 数值列表 → 折线图
        if all(isinstance(x, (int, float)) for x in data):
            return "line"

        # 字典列表
        if all(isinstance(x, dict) for x in data):
            return "bar"

    # 默认返回柱状图
    return "bar"


# ===== 数据解析 =====

def parse_data(data: Any) -> Dict[str, Any]:
    """
    解析输入数据为统一格式

    Args:
        data: 输入数据

    Returns:
        解析后的数据字典
    """
    result = {
        "type": "unknown",
        "columns": [],
        "rows": [],
        "metadata": {}
    }

    if PANDAS_AVAILABLE and isinstance(data, pd.DataFrame):
        result["type"] = "dataframe"
        result["columns"] = data.columns.tolist()
        result["rows"] = data.to_dict("records")
        result["metadata"] = {
            "shape": data.shape,
            "dtypes": {col: str(dtype) for col, dtype in data.dtypes.items()}
        }

    elif isinstance(data, dict):
        result["type"] = "dict"
        result["columns"] = list(data.keys())
        # 转换为列表格式
        result["rows"] = [
            {"name": k, "value": v} for k, v in data.items()
        ]

    elif isinstance(data, list):
        result["type"] = "list"
        if data and isinstance(data[0], dict):
            # 字典列表
            result["columns"] = list(data[0].keys()) if data[0] else []
            result["rows"] = data
        else:
            # 简单值列表
            result["columns"] = ["value"]
            result["rows"] = [{"value": v} for v in data]

    return result


# ===== ECharts 配置生成 =====

def _generate_title(config: Dict[str, Any], theme: str) -> Dict[str, Any]:
    """生成标题配置"""
    return {
        "text": config.get("title", "数据可视化"),
        "subtext": config.get("subtitle", ""),
        "left": config.get("title_position", "center"),
        "textStyle": {
            "fontSize": config.get("title_size", 18),
            "fontWeight": "bold"
        }
    }


def _generate_tooltip(chart_type: str) -> Dict[str, Any]:
    """生成提示框配置"""
    tooltip_config = {
        "trigger": "item"
    }

    # 根据图表类型调整 trigger
    if chart_type in ["line", "bar", "scatter", "heatmap"]:
        tooltip_config["trigger"] = "axis"

    if chart_type == "axis":
        tooltip_config["axisPointer"] = {"type": "cross"}

    return tooltip_config


def _generate_legend(data_columns: List[str]) -> Dict[str, Any]:
    """生成图例配置"""
    return {
        "show": len(data_columns) > 1,
        "data": data_columns,
        "top": "bottom"
    }


def _generate_line_chart(parsed_data: Dict[str, Any], theme: str) -> Dict[str, Any]:
    """生成折线图配置"""
    rows = parsed_data["rows"]
    columns = parsed_data["columns"]

    if not rows:
        return {"series": []}

    # 提取 X 轴数据（通常是第一列或索引）
    if len(columns) > 1:
        x_data = [str(row.get(columns[0], i)) for i, row in enumerate(rows)]
        y_columns = columns[1:]
    else:
        x_data = [str(i) for i in range(len(rows))]
        y_columns = columns

    # 生成数据系列
    series = []
    colors = ECHARTS_THEMES.get(theme, ECHARTS_THEMES["default"])["colors"]

    for i, col in enumerate(y_columns):
        y_data = [row.get(col, 0) for row in rows]
        series.append({
            "name": col,
            "type": "line",
            "data": y_data,
            "smooth": True,
            "itemStyle": {"color": colors[i % len(colors)]}
        })

    return {
        "xAxis": {
            "type": "category",
            "data": x_data,
            "boundaryGap": False
        },
        "yAxis": {
            "type": "value"
        },
        "series": series
    }


def _generate_bar_chart(parsed_data: Dict[str, Any], theme: str) -> Dict[str, Any]:
    """生成柱状图配置"""
    rows = parsed_data["rows"]
    columns = parsed_data["columns"]

    if not rows:
        return {"series": []}

    # 提取类别和数据
    if len(columns) >= 2:
        categories = [str(row.get(columns[0], i)) for i, row in enumerate(rows)]
        value_columns = columns[1:2]  # 默认只取第一个数值列
    else:
        categories = [row.get("name", str(i)) for i, row in enumerate(rows)]
        value_columns = ["value"]

    # 生成数据系列
    series = []
    colors = ECHARTS_THEMES.get(theme, ECHARTS_THEMES["default"])["colors"]

    for i, col in enumerate(value_columns):
        data = [row.get(col, 0) for row in rows]
        series.append({
            "name": col,
            "type": "bar",
            "data": data,
            "itemStyle": {
                "color": colors[i % len(colors)],
                "borderRadius": [4, 4, 0, 0]
            }
        })

    return {
        "xAxis": {
            "type": "category",
            "data": categories[:50]  # 限制最多50个类别
        },
        "yAxis": {
            "type": "value"
        },
        "series": series
    }


def _generate_pie_chart(parsed_data: Dict[str, Any], theme: str) -> Dict[str, Any]:
    """生成饼图配置"""
    rows = parsed_data["rows"]
    colors = ECHARTS_THEMES.get(theme, ECHARTS_THEMES["default"])["colors"]

    data = []
    for i, row in enumerate(rows):
        name = row.get("name", row.get("category", f"项{i+1}"))
        value = row.get("value", row.get("count", 0))
        data.append({
            "name": str(name),
            "value": value,
            "itemStyle": {"color": colors[i % len(colors)]}
        })

    return {
        "series": [{
            "type": "pie",
            "radius": ["40%", "70%"],
            "avoidLabelOverlap": False,
            "itemStyle": {
                "borderRadius": 10,
                "borderColor": "#fff",
                "borderWidth": 2
            },
            "label": {
                "show": True,
                "formatter": "{b}: {d}%"
            },
            "emphasis": {
                "label": {
                    "show": True,
                    "fontSize": 20,
                    "fontWeight": "bold"
                }
            },
            "data": data
        }]
    }


def _generate_scatter_chart(parsed_data: Dict[str, Any], theme: str) -> Dict[str, Any]:
    """生成散点图配置"""
    rows = parsed_data["rows"]
    columns = parsed_data["columns"]

    if len(columns) < 2 or not rows:
        return {"series": []}

    x_col = columns[0]
    y_col = columns[1] if len(columns) > 1 else columns[0]

    data = [[row.get(x_col, 0), row.get(y_col, 0)] for row in rows]

    return {
        "xAxis": {
            "type": "value",
            "scale": True,
            "name": x_col
        },
        "yAxis": {
            "type": "value",
            "scale": True,
            "name": y_col
        },
        "series": [{
            "type": "scatter",
            "data": data,
            "symbolSize": 10,
            "itemStyle": {
                "color": ECHARTS_THEMES["default"]["colors"][0]
            }
        }]
    }


def _generate_heatmap_config(parsed_data: Dict[str, Any], theme: str) -> Dict[str, Any]:
    """生成热力图配置"""
    rows = parsed_data["rows"]
    columns = parsed_data["columns"]

    if not rows or not columns:
        return {"series": []}

    # 简化热力图实现
    x_data = columns
    y_data = [str(i) for i in range(len(rows))]

    data = []
    for i, row in enumerate(rows):
        for j, col in enumerate(columns):
            value = row.get(col, 0)
            if isinstance(value, (int, float)):
                data.append([j, i, value])

    return {
        "xAxis": {
            "type": "category",
            "data": x_data
        },
        "yAxis": {
            "type": "category",
            "data": y_data
        },
        "visualMap": {
            "min": 0,
            "max": max([d[2] for d in data]) if data else 100,
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "bottom": "15%"
        },
        "series": [{
            "type": "heatmap",
            "data": data,
            "label": {"show": True}
        }]
    }


# ===== LLM 增强图表生成 =====

def _generate_with_llm(
    parsed_data: Dict[str, Any],
    chart_type: str,
    user_query: str,
    theme: str
) -> Optional[Dict[str, Any]]:
    """
    使用 LLM 生成优化的 ECharts 配置

    Args:
        parsed_data: 解析后的数据
        chart_type: 图表类型
        user_query: 用户查询
        theme: 主题

    Returns:
        ECharts 配置或 None
    """
    if not ANTHROPIC_AVAILABLE:
        return None

    api_key = os.environ.get("BA_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        client = Anthropic(api_key=api_key)

        # 构建提示词
        prompt = f"""你是一个专业的数据可视化专家，擅长使用 ECharts 生成图表配置。

【数据信息】
类型: {parsed_data['type']}
列名: {parsed_data['columns']}
数据行数: {len(parsed_data['rows'])}

【数据样本】
{json.dumps(parsed_data['rows'][:5], ensure_ascii=False)}

【用户需求】
{user_query}

【要求的图表类型】
{chart_type}

【要求】
1. 生成完整的 ECharts option 配置（JSON格式）
2. 确保代码语法正确，可直接在前端使用
3. 添加合适的标题、图例、提示框
4. 主题: {theme}
5. 数据处理：数值格式化、日期格式化等

请返回纯 JSON 格式的 ECharts option，不要包含任何解释文字。
必须返回的是标准的 JSON 对象，不是 markdown 代码块。
"""

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # 提取 JSON
        content = response.content[0].text

        # 移除可能的 markdown 代码块标记
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 解析 JSON
        echarts_config = json.loads(content)
        return echarts_config

    except Exception as e:
        # LLM 生成失败，回退到规则生成
        return None


# ===== 验证 =====

def validate_echarts_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证 ECharts 配置

    Args:
        config: ECharts 配置

    Returns:
        验证结果
    """
    errors = []
    warnings = []

    # 必需字段检查
    if "series" not in config:
        errors.append("缺少必需字段: series")

    # 安全性检查
    config_str = json.dumps(config, ensure_ascii=False)
    dangerous_keywords = ["eval", "Function", "document.", "window."]
    for keyword in dangerous_keywords:
        if keyword in config_str:
            errors.append(f"检测到不安全关键词: {keyword}")

    # 数据系列检查
    if "series" in config:
        if not isinstance(config["series"], list):
            errors.append("series 必须是数组")

        if len(config["series"]) == 0:
            warnings.append("series 为空")

        # 检查数据点数量
        for i, series in enumerate(config["series"]):
            if "data" in series and isinstance(series["data"], list):
                if len(series["data"]) > 10000:
                    warnings.append(f"series[{i}] 数据点过多 ({len(series['data'])})")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


# ===== 主函数 =====

def create_chart(
    data: Any,
    chart_hint: Optional[str] = None,
    theme: str = 'default',
    user_query: str = "",
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    创建数据可视化图表

    Args:
        data: 要可视化的数据 (DataFrame 或 dict)
        chart_hint: 图表类型提示 (line/bar/pie/scatter/heatmap/map)
        theme: 主题配置 (default/dark/macarons/vintage)
        user_query: 用户查询描述（用于 LLM 优化）
        use_llm: 是否使用 LLM 优化图表

    Returns:
        ECharts 配置对象
    """
    start_time = datetime.now()

    # 解析数据
    parsed_data = parse_data(data)

    # 确定图表类型
    if chart_hint and chart_hint in ["line", "bar", "pie", "scatter", "heatmap", "map", "gauge", "funnel"]:
        chart_type = chart_hint
    else:
        chart_type = recommend_chart_type(data)

    # 尝试使用 LLM 生成
    echarts_config = None
    if use_llm and user_query:
        echarts_config = _generate_with_llm(
            parsed_data,
            chart_type,
            user_query,
            theme
        )

    # 规则生成（LLM 失败或未启用时）
    if echarts_config is None:
        # 生成基础配置
        echarts_config = {
            "title": _generate_title({}, theme),
            "tooltip": _generate_tooltip(chart_type),
            "legend": _generate_legend(parsed_data["columns"]),
            "theme": theme
        }

        # 根据图表类型生成特定配置
        if chart_type == "line":
            echarts_config.update(_generate_line_chart(parsed_data, theme))
        elif chart_type == "bar":
            echarts_config.update(_generate_bar_chart(parsed_data, theme))
        elif chart_type == "pie":
            echarts_config.update(_generate_pie_chart(parsed_data, theme))
        elif chart_type == "scatter":
            echarts_config.update(_generate_scatter_chart(parsed_data, theme))
        elif chart_type == "heatmap":
            echarts_config.update(_generate_heatmap_config(parsed_data, theme))
        else:
            # 默认使用柱状图
            echarts_config.update(_generate_bar_chart(parsed_data, theme))

        # 应用主题颜色
        theme_config = ECHARTS_THEMES.get(theme, ECHARTS_THEMES["default"])
        if "backgroundColor" in theme_config:
            echarts_config["backgroundColor"] = theme_config["backgroundColor"]

    # 验证配置
    validation = validate_echarts_config(echarts_config)

    # 计算耗时
    duration_ms = (datetime.now() - start_time).total_seconds() * 1000

    return {
        "config": echarts_config,
        "chart_type": chart_type,
        "theme": theme,
        "validation": validation,
        "metadata": {
            "data_type": parsed_data["type"],
            "data_rows": len(parsed_data["rows"]),
            "data_columns": parsed_data["columns"],
            "generation_method": "llm" if (use_llm and user_query) else "rule",
            "duration_ms": round(duration_ms, 2)
        }
    }


# ===== 辅助函数 =====

def get_supported_chart_types() -> List[str]:
    """获取支持的图表类型"""
    return ["line", "bar", "pie", "scatter", "heatmap", "map", "gauge", "funnel"]


def get_supported_themes() -> List[str]:
    """获取支持的主题"""
    return ["default", "dark", "macarons", "vintage"]


def export_chart_html(config: Dict[str, Any], width: str = "800px", height: str = "600px") -> str:
    """
    导出为完整的 HTML 文件

    Args:
        config: ECharts 配置
        width: 图表宽度
        height: 图表高度

    Returns:
        HTML 字符串
    """
    html_template = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ECharts 图表</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background-color: #f5f5f5;
        }}
        #chart-container {{
            width: {width};
            height: {height};
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
        }}
    </style>
</head>
<body>
    <div id="chart-container"></div>
    <script>
        var chart = echarts.init(document.getElementById('chart-container'));
        var option = {json.dumps(config, ensure_ascii=False, indent=2)};
        chart.setOption(option);

        window.addEventListener('resize', function() {{
            chart.resize();
        }});
    </script>
</body>
</html>'''

    return html_template


__all__ = [
    "create_chart",
    "recommend_chart_type",
    "get_supported_chart_types",
    "get_supported_themes",
    "validate_echarts_config",
    "export_chart_html",
]
