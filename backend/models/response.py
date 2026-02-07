"""
Agent 结构化响应模型 (v2.0)

定义 Agent 返回的结构化响应格式，支持：
- 多轮对话 (current_round)
- 工具调用 (type="tool_call")
- 最终报告 (type="complete")
- 推荐问题和下载链接
"""

from typing import List, Optional, Any, Union, Dict, Literal
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """工具调用定义"""

    tool_name: str = Field(
        ...,
        description="工具名称，如: bac_code_agent, query_database, web_search"
    )
    tool_call_id: str = Field(
        ...,
        description="工具调用唯一标识符，模型自动生成，用于区分同一次工具调用的输入输出"
    )
    arguments: Dict[str, Any] = Field(
        ...,
        description="工具调用参数，根据具体工具定义"
    )


class Action(BaseModel):
    """动作定义"""

    type: Literal["tool_call", "complete"] = Field(
        ...,
        description="动作类型: tool_call(调用工具) 或 complete(完成并返回最终报告)"
    )

    content: Union[List[ToolCall], str] = Field(
        ...,
        description="当 type=tool_call 时为工具调用数组，当 type=complete 时为最终报告字符串"
    )

    recommended_questions: Optional[List[str]] = Field(
        default=None,
        description="推荐用户后续询问的问题列表，仅当 type=complete 时存在"
    )

    download_links: Optional[List[str]] = Field(
        default=None,
        description="推荐用户下载的文件名列表，仅当 type=complete 时存在"
    )


class StructuredResponse(BaseModel):
    """
    Agent 结构化响应模型

    模型必须按照此格式返回响应：
    {
        "task_analysis": "思维链分析",
        "execution_plan": "执行计划",
        "current_round": 1,
        "action": {...}
    }
    """

    task_analysis: str = Field(
        ...,
        description="思维链：分析用户意图、预判风险、设计操作流程"
    )

    execution_plan: str = Field(
        ...,
        description="执行计划：R1: xxx; R2: xxx; 格式描述各轮次目标"
    )

    current_round: int = Field(
        default=1,
        ge=1,
        description="当前对话轮次，从1开始递增"
    )

    action: Action = Field(
        ...,
        description="动作对象，包含类型、内容、推荐问题等"
    )

    def is_tool_call(self) -> bool:
        """判断当前是否为工具调用"""
        return self.action.type == "tool_call"

    def is_complete(self) -> bool:
        """判断当前是否为完成状态"""
        return self.action.type == "complete"

    def get_tool_calls(self) -> List[ToolCall]:
        """获取工具调用列表"""
        if self.is_tool_call() and isinstance(self.action.content, list):
            return self.action.content
        return []

    def get_final_report(self) -> str:
        """获取最终报告内容"""
        if self.is_complete() and isinstance(self.action.content, str):
            return self.action.content
        return ""


# 最终报告的内容类型定义
FINAL_REPORT_CONTENT_TYPES = {
    "text": "纯文本说明",
    "html": "HTML 代码（如 ECharts 图表）",
    "code": "代码块",
    "table": "表格数据",
    "chart": "图表数据（可转换为可视化）",
    "file_reference": "文件引用"
}


# 系统提示词模板
STRUCTURED_RESPONSE_SYSTEM_PROMPT = """你必须严格按照以下 JSON 格式返回响应：

```json
{{
    "task_analysis": "思维链：1. 识别意图; 2. 预判数据风险; 3. 设计复合指令",
    "execution_plan": "R1: [步骤描述]; R2: [步骤描述]",
    "current_round": 1,
    "action": {{
        "type": "tool_call 或 complete",
        "content": "...",
        "recommended_questions": ["问题1", "问题2"],  // 仅 type=complete 时可选
        "download_links": ["文件1.xlsx"]  // 仅 type=complete 时可选
    }}
}}
```

## Action Type 定义

### type="tool_call" (调用工具)
content 必须为数组，支持单次并行调用（最多6个）：

```json
{{
    "task_analysis": "用户需分析销售数据，识别为数据分析任务",
    "execution_plan": "R1: 数据查询与计算; R2: 可视化与报告",
    "current_round": 1,
    "action": {{
        "type": "tool_call",
        "content": [
            {{
                "tool_name": "bac_code_agent",
                "tool_call_id": "call_abc123",
                "arguments": {{
                    "query": "读取数据并计算销售额",
                    "outputFileName": "sales_result"
                }}
            }}
        ]
    }}
}}
```

### type="complete" (完成并返回报告)
content 为字符串，包含最终分析结果或可视化代码：

```json
{{
    "task_analysis": "分析完成，已获取所需数据",
    "execution_plan": "R1: 数据查询; R2: 生成报告(当前)",
    "current_round": 2,
    "action": {{
        "type": "complete",
        "content": "根据分析结果，Q1销售额同比增长15%，主要来源于..."
    }}
}}
```

## 最终报告 Content 格式

当 type="complete" 时，content 可以是以下格式：

### 1. 纯文本报告
```
content: "根据数据分析，Q1销售额达到500万元，同比增长15%..."
```

### 2. 带 HTML 图表
```
content: "
数据分析显示Q1销售额增长显著：

<div class='chart-wrapper'>
    <div id='chart-sales' style='width:600px;height:400px;'></div>
</div>
<script>
(function(){
    const chart = echarts.init(document.getElementById('chart-sales'));
    chart.setOption({
        xAxis: {type: 'category', data: ['Q1', 'Q2', 'Q3', 'Q4']},
        yAxis: {type: 'value'},
        series: [{type: 'bar', data: [500, 520, 580, 620]}]
    });
})();
</script>
"
```

### 3. 带代码块的报告
```
content: "
以下是数据处理代码：

\`\`\`python
import pandas as pd
df = pd.read_csv('sales.csv')
result = df.groupby('quarter').sum()
\`\`\`

计算结果为...
"
```

## 工具调用参数规范

### bac_code_agent (Python 代码执行)
```json
{{
    "tool_name": "bac_code_agent",
    "tool_call_id": "call_xxx",
    "arguments": {{
        "query": "执行的分析任务描述",
        "outputFileName": "输出文件名（可选）",
        "fileNameList": ["需要使用的文件列表"],
        "analysisQuery": "对结果的分析要求（可选）"
    }}
}}
```

### query_database (数据库查询)
```json
{{
    "tool_name": "query_database",
    "tool_call_id": "call_xxx",
    "arguments": {{
        "sql": "SELECT * FROM sales WHERE quarter = 'Q1'"
    }}
}}
```

### web_search (网络搜索)
```json
{{
    "tool_name": "web_search",
    "tool_call_id": "call_xxx",
    "arguments": {{
        "query": "搜索关键词"
    }}
}}
```

## 重要规则

1. **必须返回有效 JSON**：所有字符串使用双引号，特殊字符正确转义
2. **task_analysis 必须有深度**：不仅是重述问题，要展示思维链
3. **execution_plan 要分轮次**：R1/R2/R3 明确各轮目标
4. **tool_call_id 唯一性**：使用 call_xxx 格式，xxx 为随机字符串
5. **推荐问题相关性**：基于当前分析结果提出有价值的后续问题
6. **多轮对话感知**：current_round 随对话递增，直到 type="complete"

## 完整示例

### 示例1：数据分析任务
```json
{{
    "task_analysis": "用户请求分析销售数据异动。1. 识别为数据分析任务；2. 需要查询历史数据对比；3. 计算增长率并可视化。",
    "execution_plan": "R1: 查询历史销售数据并计算增长率；R2: 生成可视化图表和结论报告",
    "current_round": 1,
    "action": {{
        "type": "tool_call",
        "content": [
            {{
                "tool_name": "bac_code_agent",
                "tool_call_id": "call_sales_001",
                "arguments": {{
                    "query": "1. 读取sales.csv；2. 按季度汇总；3. 计算同比增长率；4. 输出前5行异常数据",
                    "outputFileName": "sales_analysis_result",
                    "fileNameList": ["sales.csv"]
                }}
            }}
        ]
    }}
}}
```

### 示例2：完成报告
```json
{{
    "task_analysis": "数据已处理完成，识别关键趋势和异常点，生成可视化报告。",
    "execution_plan": "R1: 数据处理；R2: 报告生成(当前)",
    "current_round": 2,
    "action": {{
        "type": "complete",
        "content": "销售数据分析完成。关键发现：\\n\\n1. Q3销售额增长最快，达到25%\\n2. 华东地区贡献了40%的销售额\\n3. 产品A的销量出现异常下降\\n\\n下图展示了各季度销售趋势：\\n\\n<div class='chart-wrapper'><div id='chart-trend' style='width:100%;height:400px;'></div></div><script>(function(){{const chart = echarts.init(document.getElementById('chart-trend'));chart.setOption({{xAxis: {{type: 'category', data: ['Q1','Q2','Q3','Q4']}}, yAxis: {{type: 'value'}}, series: [{{type: 'line', data: [120, 150, 180, 175]}}]}});}})();</script>",
        "recommended_questions": [
            "Q3销售额快速增长的原因是什么？",
            "产品A销量下降的具体原因分析",
            "各地区的销售占比变化趋势"
        ],
        "download_links": ["sales_analysis_result.xlsx"]
    }}
}}
```
"""


def parse_structured_response(response_text: str) -> Optional[StructuredResponse]:
    """
    从模型响应中解析结构化响应

    Args:
        response_text: 模型的原始响应文本

    Returns:
        解析后的 StructuredResponse，如果解析失败则返回 None
    """
    import json
    import re
    import uuid

    def generate_tool_call_id() -> str:
        """生成工具调用ID"""
        return f"call_{uuid.uuid4().hex[:10]}"

    try:
        # 尝试直接解析
        return StructuredResponse.model_validate_json(response_text)
    except Exception:
        pass

    # 尝试提取 JSON 代码块
    json_block_pattern = r'```json\s*\n(.*?)\n```'
    matches = re.findall(json_block_pattern, response_text, re.DOTALL)

    for match in matches:
        try:
            return StructuredResponse.model_validate_json(match.strip())
        except Exception:
            continue

    # 尝试提取任何完整的 JSON 对象
    json_object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_object_pattern, response_text, re.DOTALL)

    for match in matches:
        try:
            data = json.loads(match)
            # 检查是否包含必要字段
            if "task_analysis" in data or "action" in data:
                return StructuredResponse.model_validate(data)
        except Exception:
            continue

    # 解析完全失败，构建兜底响应
    logger = __import__('logging').getLogger(__name__)
    logger.warning(f"无法解析结构化响应，使用兜底格式。原始内容: {response_text[:200]}")

    return StructuredResponse(
        task_analysis="无法解析模型响应，使用兜底格式",
        execution_plan="R1: 返回原始内容",
        current_round=1,
        action=Action(
            type="complete",
            content=response_text,
            recommended_questions=["请重新描述您的需求"]
        )
    )


__all__ = [
    "StructuredResponse",
    "Action",
    "ToolCall",
    "STRUCTURED_RESPONSE_SYSTEM_PROMPT",
    "parse_structured_response",
    "FINAL_REPORT_CONTENT_TYPES",
]
