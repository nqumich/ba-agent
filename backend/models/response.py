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

# ===== 提示词加载 =====

def _load_prompt_from_docs() -> str:
    """
    从 docs/prompts.md 加载结构化响应提示词

    如果文档不存在或读取失败，返回内嵌的备用提示词
    """
    from pathlib import Path
    import re

    docs_path = Path(__file__).parent.parent.parent / "docs" / "prompts.md"

    if not docs_path.exists():
        # 文档不存在，使用备用提示词
        return _get_fallback_prompt()

    try:
        content = docs_path.read_text(encoding='utf-8')

        # 提取 STRUCTURED_RESPONSE_SYSTEM_PROMPT 部分
        # 查找从 ### STRUCTURED_RESPONSE_SYSTEM_PROMPT 到下一个 ### 之间的内容
        pattern = r'### STRUCTURED_RESPONSE_SYSTEM_PROMPT\s+(.*?)(?=### |\Z)'
        match = re.search(pattern, content, re.DOTALL)

        if match:
            prompt_text = match.group(1).strip()
            # 移除 markdown 代码块标记（如果存在）
            prompt_text = re.sub(r'^```\w*\n?', '', prompt_text, flags=re.MULTILINE)
            prompt_text = prompt_text.rstrip('`\n')
            return prompt_text

        # 如果没有找到，返回备用提示词
        return _get_fallback_prompt()

    except Exception as e:
        # 读取失败，使用备用提示词
        import warnings
        warnings.warn(f"无法从文档加载提示词: {e}，使用备用提示词")
        return _get_fallback_prompt()


def _get_fallback_prompt() -> str:
    """
    获取内嵌的备用提示词

    这是当 docs/prompts.md 不存在或读取失败时使用的版本
    """
    return """你必须严格按照以下 JSON 格式返回响应：

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
content 必须为数组，支持单次并行调用（最多6个）。

### type="complete" (完成并返回报告)
content 为字符串，包含最终分析结果或可视化代码。

## 工具调用参数规范

### run_python (Python 代码执行)
- code: 要执行的 Python 代码
- timeout: 执行超时时间（秒），范围 5-300，默认 60
- response_format: brief/standard/full

### file_reader (文件读取)
- path: 文件路径
- format: 文件格式（可选，自动检测）
- encoding: 文本编码，默认 utf-8
- nrows: 最大读取行数
- response_format: brief/standard/full

### query_database (数据库查询)
- query: SQL 查询语句
- connection: 数据库连接名称，默认 primary
- max_rows: 最大返回行数，范围 1-10000
- response_format: brief/standard/full

### web_search (网络搜索)
- query: 搜索关键词
- num_results: 返回结果数量
- response_format: brief/standard/full

## 重要规则

1. 必须返回有效 JSON，所有字符串使用双引号
2. task_analysis 必须有深度，展示思维链
3. execution_plan 要分轮次，R1/R2/R3 明确各轮目标
4. tool_call_id 唯一性，使用 call_xxx 格式
5. current_round 随对话递增，直到 type="complete"
"""


# 系统提示词（从文档加载，失败时使用备用提示词）
STRUCTURED_RESPONSE_SYSTEM_PROMPT = _load_prompt_from_docs()


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
