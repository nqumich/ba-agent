"""
Agent 结构化响应模型 (v3.5)

定义 Agent 返回的结构化响应格式，支持：
- 多轮对话 (current_round)
- 工具调用 (type="tool_call")
- 最终报告 (type="complete")
- 推荐问题和下载链接
- 代码块管理和引用

系统提示词从 docs/prompts.md 加载，不使用备用提示词
"""

from typing import List, Optional, Any, Union, Dict, Literal
from pydantic import BaseModel, Field
from pathlib import Path


class FileInfo(BaseModel):
    """
    统一文件信息格式

    用于代码文件和上传文件的统一描述，便于管理和展示
    """

    file_id: str = Field(
        ...,
        description="文件唯一标识，代码文件为 code_xxx，上传文件为 upload_xxx"
    )
    filename: str = Field(
        ...,
        description="文件名，包含扩展名"
    )
    file_type: str = Field(
        ...,
        description="文件类型/扩展名，如 python, js, csv, md 等"
    )
    size_bytes: int = Field(
        ...,
        description="文件大小（字节）"
    )
    description: str = Field(
        ...,
        description="文件描述"
    )

    # 代码文件特有字段
    language: Optional[str] = Field(
        default=None,
        description="代码语言类型，仅代码文件有值"
    )

    @property
    def size_formatted(self) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.size_bytes < 1024.0:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024.0
        return f"{self.size_bytes:.1f} TB"

    def to_markdown(self) -> str:
        """
        转换为 markdown 格式

        格式: - [file_id] filename (file_type) - description | size
        """
        desc = f" - {self.description}" if self.description else ""
        return f"- [{self.file_id}] {self.filename} ({self.file_type}){desc} | {self.size_formatted}"

    @classmethod
    def from_code_metadata(
        cls,
        file_id: str,
        filename: str,
        file_type: str,
        size_bytes: int,
        description: str,
        language: str
    ) -> "FileInfo":
        """从代码元数据创建 FileInfo"""
        return cls(
            file_id=file_id,
            filename=filename,
            file_type=file_type,
            size_bytes=size_bytes,
            description=description,
            language=language
        )

    @classmethod
    def from_upload_metadata(
        cls,
        file_id: str,
        filename: str,
        file_type: str,
        size_bytes: int,
        description: str
    ) -> "FileInfo":
        """从上传文件元数据创建 FileInfo"""
        return cls(
            file_id=file_id,
            filename=filename,
            file_type=file_type,
            size_bytes=size_bytes,
            description=description,
            language=None
        )


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


class CodeBlock(BaseModel):
    """代码块定义"""

    code_id: str = Field(
        ...,
        description="代码唯一标识，格式: code_{描述}_{随机字符}，如 code_sales_analysis_abc123"
    )
    language: str = Field(
        default="python",
        description="代码语言，如 python, sql, javascript 等"
    )
    description: Optional[str] = Field(
        default=None,
        description="代码描述，用于后续识别和检索"
    )
    code: str = Field(
        ...,
        description="代码内容，不包含 markdown 代码块标记（```）"
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

    code_blocks: Optional[List[CodeBlock]] = Field(
        default=None,
        description="代码块列表，当 content 包含代码时提供。用于代码管理和后续引用"
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

    def get_code_blocks(self) -> List[CodeBlock]:
        """获取代码块列表"""
        if self.action.code_blocks:
            return self.action.code_blocks
        return []

    def has_code_blocks(self) -> bool:
        """判断是否包含代码块"""
        return bool(self.action.code_blocks)


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

    提取 ### STRUCTURED_RESPONSE_SYSTEM_PROMPT 和 ### 之间的内容
    """
    from pathlib import Path
    import re

    docs_path = Path(__file__).parent.parent.parent / "docs" / "prompts.md"

    if not docs_path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {docs_path}")

    content = docs_path.read_text(encoding='utf-8')

    # 提取 STRUCTURED_RESPONSE_SYSTEM_PROMPT 部分
    # 查找从 ### STRUCTURED_RESPONSE_SYSTEM_PROMPT 到下一个 ### 之间的内容
    pattern = r'### STRUCTURED_RESPONSE_SYSTEM_PROMPT\s+(.*?)(?=### |\Z)'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        raise ValueError(f"提示词文件中未找到 ### STRUCTURED_RESPONSE_SYSTEM_PROMPT 标记: {docs_path}")

    prompt_text = match.group(1).strip()
    # 移除 markdown 代码块标记（如果存在）
    prompt_text = re.sub(r'^```\w*\n?', '', prompt_text, flags=re.MULTILINE)
    prompt_text = prompt_text.rstrip('`\n')

    return prompt_text


# 系统提示词（从 docs/prompts.md 加载）
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


def validate_structured_response(response: StructuredResponse) -> tuple[bool, List[str]]:
    """
    校验结构化响应格式

    Args:
        response: 结构化响应对象

    Returns:
        (is_valid, error_messages): 是否有效，错误信息列表
    """
    errors = []

    # 校验基础字段
    if not response.task_analysis or len(response.task_analysis.strip()) < 10:
        errors.append("task_analysis 不能为空且长度应至少 10 个字符")

    if not response.execution_plan or "R1" not in response.execution_plan:
        errors.append("execution_plan 不能为空且必须包含 R1 轮次说明")

    if response.current_round < 1:
        errors.append("current_round 必须大于 0")

    # 校验 action 字段
    action = response.action

    if action.type == "tool_call":
        if not isinstance(action.content, list):
            errors.append("type=tool_call 时 content 必须是数组")

        if not action.content:
            errors.append("type=tool_call 时 content 不能为空")

        if len(action.content) > 6:
            errors.append("单次最多支持 6 个工具调用")

        # 校验每个工具调用
        for i, tool_call in enumerate(action.content):
            if not isinstance(tool_call, dict):
                errors.append(f"工具调用 {i+1} 必须是对象")
                continue

            if "tool_name" not in tool_call:
                errors.append(f"工具调用 {i+1} 缺少 tool_name 字段")

            if "tool_call_id" not in tool_call:
                errors.append(f"工具调用 {i+1} 缺少 tool_call_id 字段")

            if "arguments" not in tool_call:
                errors.append(f"工具调用 {i+1} 缺少 arguments 字段")

    elif action.type == "complete":
        if not isinstance(action.content, str):
            errors.append("type=complete 时 content 必须是字符串")

        if not action.content:
            errors.append("type=complete 时 content 不能为空")

        # 校验 code_blocks
        if action.code_blocks:
            for i, code_block in enumerate(action.code_blocks):
                if "code_id" not in code_block:
                    errors.append(f"代码块 {i+1} 缺少 code_id 字段")

                if "code" not in code_block:
                    errors.append(f"代码块 {i+1} 缺少 code 字段")

                if not code_block.get("code"):
                    errors.append(f"代码块 {i+1} 的 code 不能为空")

                # 校验 code_id 格式
                code_id = code_block.get("code_id", "")
                if not code_id.startswith("code_"):
                    errors.append(f"代码块 {i+1} 的 code_id 必须以 'code_' 开头")

    else:
        errors.append(f"action.type 必须是 'tool_call' 或 'complete'，当前为: {action.type}")

    return len(errors) == 0, errors


def generate_retry_prompt(errors: List[str]) -> str:
    """
    生成重试提示词

    Args:
        errors: 错误信息列表

    Returns:
        重试提示词
    """
    errors_text = "\n".join([f"- {e}" for e in errors])

    return f"""你的上一次响应格式需要调整，请按照以下要求重新生成：

## 需要修正的问题

{errors_text}

## 正确格式要求

请严格按照以下 JSON 格式返回响应：

```json
{{
    "task_analysis": "[完整的思维链分析：需求理解、任务分解、风险预判、策略选择]",
    "execution_plan": "R1: [步骤1]; R2: [步骤2]; R3: [步骤3]",
    "current_round": 1,
    "action": {{
        "type": "tool_call 或 complete",
        "content": "...",
        "recommended_questions": ["后续问题1", "后续问题2"],  // 仅 type=complete 时可选
        "download_links": ["文件1.xlsx"],  // 仅 type=complete 时可选
        "code_blocks": [  // 当需要提供代码时
            {{
                "code_id": "code_描述_随机字符",
                "language": "python",
                "description": "代码描述",
                "code": "代码内容（不含标记）"
            }}
        ]
    }}
}}
```

## 关键要点

1. **task_analysis**: 展示完整思维链，包含需求理解、任务分解、策略选择
2. **execution_plan**: 使用 R1/R2/R3 标记，明确每轮的具体目标
3. **tool_call**: content 必须是数组，每个工具调用必须有 tool_name, tool_call_id, arguments
4. **complete with code**:
   - content 中放文字描述（说明代码用途和使用方式）
   - code_blocks 中放代码，每个必须有 code_id, language, code

请重新生成正确的响应。"""


# ===== 代码引用处理 =====

def extract_code_references(content: str) -> List[str]:
    """
    从内容中提取所有代码引用标识

    Args:
        content: 包含 <code_ref>code_id</code_ref> 标签的文本

    Returns:
        代码标识列表，按出现顺序排列

    Example:
        >>> content = "分析代码：<code_ref>code_sales</code_ref>"
        >>> extract_code_references(content)
        ['code_sales']
    """
    import re
    pattern = r'<code_ref>\s*(code_[a-zA-Z0-9_]+)\s*</code_ref>'
    matches = re.findall(pattern, content)
    return matches


def resolve_code_references(
    content: str,
    code_blocks: List[CodeBlock]
) -> tuple[str, List[dict]]:
    """
    解析代码引用标签，返回处理后的内容和代码信息列表

    Args:
        content: 包含 <code_ref>code_id</code_ref> 标签的文本
        code_blocks: 代码块列表

    Returns:
        (处理后的内容, 代码信息列表)
        代码信息列表格式: [{"code_id": "...", "language": "...", "description": "...", "index": 0}, ...]
        index 表示代码在内容中出现的顺序

    Example:
        >>> content = "分析代码：\\n\\n<code_ref>code_sales</code_ref>\\n\\n结果：..."
        >>> code_blocks = [CodeBlock(code_id="code_sales", ...)]
        >>> new_content, code_infos = resolve_code_references(content, code_blocks)
        >>> # new_content 中 <code_ref> 被替换为占位符 {{CODE:0}}
        >>> # code_infos 包含代码的元信息
    """
    import re

    # 创建 code_id 到 code_block 的映射
    code_map = {cb.code_id: cb for cb in code_blocks}

    # 查找所有 <code_ref> 标签并记录位置
    pattern = r'<code_ref>\s*(code_[a-zA-Z0-9_]+)\s*</code_ref>'
    matches = list(re.finditer(pattern, content))

    if not matches:
        return content, []

    code_infos = []
    processed_content = content
    offset = 0  # 用于处理替换后的位置偏移

    for idx, match in enumerate(matches):
        code_id = match.group(1)

        if code_id not in code_map:
            # 代码不存在，保留原标签并添加警告
            continue

        code_block = code_map[code_id]

        # 记录代码信息
        code_infos.append({
            "code_id": code_id,
            "language": code_block.language,
            "description": code_block.description or code_id,
            "index": idx
        })

        # 将标签替换为占位符
        placeholder = f"{{{{CODE:{idx}}}}}"
        start = match.start() + offset
        end = match.end() + offset
        processed_content = processed_content[:start] + placeholder + processed_content[end:]
        offset += len(placeholder) - (end - start)

    return processed_content, code_infos


def extract_file_references(content: str) -> List[str]:
    """
    从内容中提取所有文件引用标识

    Args:
        content: 包含 <file_ref>file_id</file_ref> 标签的文本

    Returns:
        文件标识列表，按出现顺序排列

    Example:
        >>> content = "数据文件：<file_ref>upload_001</file_ref>"
        >>> extract_file_references(content)
        ['upload_001']
    """
    import re
    pattern = r'<file_ref>\s*(upload_[a-zA-Z0-9_]+)\s*</file_ref>'
    matches = re.findall(pattern, content)
    return matches


def resolve_file_references(
    content: str,
    file_list: List[dict]
) -> tuple[str, List[dict]]:
    """
    解析文件引用标签，返回处理后的内容和文件信息列表

    Args:
        content: 包含 <file_ref>file_id</file_ref> 标签的文本
        file_list: 文件信息列表

    Returns:
        (处理后的内容, 文件信息列表)
        文件信息列表格式: [{"file_id": "...", "filename": "...", "file_type": "...", "index": 0}, ...]
        index 表示文件在内容中出现的顺序

    Example:
        >>> content = "数据文件：\\n\\n<file_ref>upload_001</file_ref>\\n\\n分析：..."
        >>> files = [{"file_id": "upload_001", "filename": "data.csv", ...}]
        >>> new_content, file_infos = resolve_file_references(content, files)
        >>> # new_content 中 <file_ref> 被替换为占位符 {{FILE:0}}
        >>> # file_infos 包含文件的元信息
    """
    import re

    # 创建 file_id 到文件信息的映射
    file_map = {f["file_id"]: f for f in file_list}

    # 查找所有 <file_ref> 标签并记录位置
    pattern = r'<file_ref>\s*(upload_[a-zA-Z0-9_]+)\s*</file_ref>'
    matches = list(re.finditer(pattern, content))

    if not matches:
        return content, []

    file_infos = []
    processed_content = content
    offset = 0  # 用于处理替换后的位置偏移

    for idx, match in enumerate(matches):
        file_id = match.group(1)

        if file_id not in file_map:
            # 文件不存在，保留原标签并添加警告
            continue

        file_info = file_map[file_id]

        # 记录文件信息
        file_infos.append({
            "file_id": file_id,
            "filename": file_info["filename"],
            "file_type": file_info["file_type"],
            "size_bytes": file_info["size_bytes"],
            "description": file_info.get("description", file_info["filename"]),
            "index": idx
        })

        # 将标签替换为占位符
        placeholder = f"{{{{FILE:{idx}}}}}"
        start = match.start() + offset
        end = match.end() + offset
        processed_content = processed_content[:start] + placeholder + processed_content[end:]
        offset += len(placeholder) - (end - start)

    return processed_content, file_infos


__all__ = [
    "FileInfo",
    "StructuredResponse",
    "Action",
    "ToolCall",
    "CodeBlock",
    "STRUCTURED_RESPONSE_SYSTEM_PROMPT",
    "parse_structured_response",
    "validate_structured_response",
    "generate_retry_prompt",
    "FINAL_REPORT_CONTENT_TYPES",
    "extract_code_references",
    "resolve_code_references",
    "extract_file_references",
    "resolve_file_references",
]
