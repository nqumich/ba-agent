# BA-Agent 响应格式流转文档

> **Version**: v2.3.0
> **Last Updated**: 2026-02-07

本文档详细描述 BA-Agent 从大模型返回到前端渲染的完整数据流转过程。

---

## 目录

1. [大模型返回格式](#一大模型返回格式)
2. [后端处理逻辑](#二后端处理逻辑)
3. [代码管理流程](#三代码管理流程)
4. [后端日志系统](#四后端日志系统)
5. [API 响应格式](#五api-响应格式)
6. [前端渲染逻辑](#六前端渲染逻辑)
7. [完整示例](#七完整示例)

---

## 一、大模型返回格式

大模型必须严格按照结构化 JSON 格式返回响应，由 `STRUCTURED_RESPONSE_SYSTEM_PROMPT` 定义。

### 1.1 提示词来源

`STRUCTURED_RESPONSE_SYSTEM_PROMPT` 现在从 `docs/prompts.md` 加载：

```python
# backend/models/response.py

def _load_system_prompt():
    """从 docs/prompts.md 加载系统提示词"""
    prompt_path = Path(__file__).parent.parent.parent / "docs" / "prompts.md"

    if prompt_path.exists():
        content = prompt_path.read_text(encoding="utf-8")
        # 提取 STRUCTURED_RESPONSE_SYSTEM_PROMPT 部分
        for line in content.split('\n'):
            if line.startswith('```text'):
                continue
            # ... 解析逻辑
        return extracted_prompt
    else:
        # 备用提示词
        return get_fallback_prompt()
```

**文件不存在时的备用提示词**：

```python
FALLBACK_PROMPT = """
你必须严格按照以下 JSON 格式返回响应：

{
    "task_analysis": "思维链：1. 识别意图; 2. 预判数据风险; 3. 设计复合指令",
    "execution_plan": "R1: [步骤描述]; R2: [步骤描述]",
    "current_round": 1,
    "action": {
        "type": "tool_call 或 complete",
        "content": "...",
        "recommended_questions": ["问题1", "问题2"],
        "download_links": ["文件1.xlsx"]
    }
}
"""
```

### 1.2 type="tool_call"（调用工具）

当模型需要调用工具时返回此格式：

```json
{
    "task_analysis": "用户需分析销售数据，识别为数据分析任务。1. 需要查询数据库获取销售记录；2. 计算各项指标；3. 生成可视化图表。",
    "execution_plan": "R1: 数据查询与计算; R2: 可视化与报告",
    "current_round": 1,
    "action": {
        "type": "tool_call",
        "content": [
            {
                "tool_name": "run_python",
                "tool_call_id": "call_abc123",
                "arguments": {
                    "code": "import pandas as pd\ndf = pd.read_csv('sales.csv')\nprint(df.groupby('quarter').sum())",
                    "timeout": 60,
                    "response_format": "standard"
                }
            },
            {
                "tool_name": "file_reader",
                "tool_call_id": "call_def456",
                "arguments": {
                    "path": "data/sales.csv",
                    "format": "csv",
                    "nrows": 100,
                    "response_format": "standard"
                }
            }
        ]
    }
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_analysis` | string | 思维链：分析用户意图、预判风险、设计操作流程 |
| `execution_plan` | string | 执行计划：R1: xxx; R2: xxx; 格式描述各轮次目标 |
| `current_round` | int | 当前轮次，从 1 开始递增 |
| `action.type` | "tool_call" | 动作类型为工具调用 |
| `action.content` | array | 工具调用数组，支持并行调用（最多6个） |

### 1.3 type="complete"（完成并返回报告）

当模型完成分析并返回最终报告时返回此格式：

```json
{
    "task_analysis": "分析完成。已获取销售数据，计算了同比增长率，准备好最终报告。",
    "execution_plan": "R1: 数据查询; R2: 数据分析; R3: 生成报告(当前)",
    "current_round": 3,
    "action": {
        "type": "complete",
        "content": "根据数据分析结果：\n\n- Q1 销售额：500万元，同比增长15%\n- Q2 销售额：520万元，同比增长18%\n- Q3 销售额：580万元，同比增长22%\n\n主要增长来源于电子产品线，贡献了60%的增量。",
        "recommended_questions": [
            "各产品线的销售占比如何？",
            "可以按地区分解销售数据吗？"
        ],
        "download_links": ["sales_report.xlsx", "analysis_chart.png"]
    }
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `action.type` | "complete" | 动作类型为完成 |
| `action.content` | string | 最终报告内容（纯文本或 HTML） |
| `action.recommended_questions` | array (可选) | 推荐用户后续询问的问题列表 |
| `action.download_links` | array (可选) | 推荐用户下载的文件名列表 |

### 1.4 特殊情况：带 ECharts 图表的 complete

当模型需要返回可视化图表时，`content` 包含 HTML/JavaScript：

```json
{
    "task_analysis": "数据可视化分析完成",
    "execution_plan": "R1: 数据查询; R2: 生成可视化图表(当前)",
    "current_round": 2,
    "action": {
        "type": "complete",
        "content": "<div class='chart-wrapper'><div id='chart-sales' style='width:600px;height:400px;'></div></div><script>(function(){const chart = echarts.init(document.getElementById('chart-sales'));chart.setOption({xAxis:{type:'category',data:['Q1','Q2','Q3','Q4']},yAxis:{type:'value'},series:[{type:'bar',data:[500,520,580,620]}]});})();</script>"
    }
}
```

**content 格式规则：**

1. **纯文本报告**：普通文本，可包含换行符 `\n`
2. **带 HTML 图表**：包含 `<div>`, `<script>`, `echarts` 等关键词
3. **带代码块**：包含 markdown 代码块格式（将被自动保存和管理）

---

## 二、后端处理逻辑

### 2.1 处理流程

```
大模型返回 JSON
    ↓
_parse_structured_response() 解析为 StructuredResponse 对象
    ↓
_extract_response_content() 提取内容
    ↓
代码块检测和保存（如果存在）
    ↓
上下文清理（减少 token 使用）
    ↓
query() 方法构建 API 响应
    ↓
记录后端日志
    ↓
返回给前端
```

### 2.2 各个 Key 的处理方式

| 模型返回的 Key | 后端处理 | 放入 API 响应的哪个字段 |
|--------------|---------|---------------------|
| `task_analysis` | 直接复制 | `metadata.task_analysis` |
| `execution_plan` | 直接复制 | `metadata.execution_plan` |
| `current_round` | 直接复制 | `metadata.current_round` |
| `action.type` | 直接复制 | `metadata.action_type` |
| `action.content` (tool_call) | 提取工具信息数组 | `metadata.tool_calls[]` |
| `action.content` (complete) | 代码块处理 + 直接复制 | `response` (主响应体) |
| `action.recommended_questions` | 直接复制 | `metadata.recommended_questions` |
| `action.download_links` | 直接复制 | `metadata.download_links` |

### 2.3 tool_call 时的特殊处理

**代码位置**: `backend/api/services/ba_agent.py:330-341`

```python
if structured_response.is_tool_call():
    tool_calls = structured_response.get_tool_calls()
    metadata["tool_calls"] = [
        {
            "tool_name": tc.tool_name,
            "tool_call_id": tc.tool_call_id,
            "arguments": tc.arguments
        }
        for tc in tool_calls
    ]
    metadata["status"] = "processing"
```

**生成的 metadata**:

```json
{
    "action_type": "tool_call",
    "current_round": 1,
    "task_analysis": "...",
    "execution_plan": "...",
    "tool_calls": [
        {"tool_name": "run_python", "tool_call_id": "call_abc123", "arguments": {...}},
        {"tool_name": "file_reader", "tool_call_id": "call_def456", "arguments": {...}}
    ],
    "status": "processing"
}
```

### 2.4 complete 时的特殊处理

**代码位置**: `backend/api/services/ba_agent.py:343-357`

```python
elif structured_response.is_complete():
    metadata["status"] = "complete"

    # 推荐问题和下载链接
    if structured_response.action.recommended_questions:
        metadata["recommended_questions"] = structured_response.action.recommended_questions
    if structured_response.action.download_links:
        metadata["download_links"] = structured_response.action.download_links

    # 检测 final_report 是否包含模型生成的 HTML（如 ECharts 图表）
    final_report = structured_response.get_final_report()
    has_model_html = '<div' in final_report or '<script' in final_report or 'echarts' in final_report.lower()
    metadata["contains_html"] = has_model_html
    metadata["content_type"] = "html" if has_model_html else "markdown"
```

**生成的 metadata**:

```json
{
    "action_type": "complete",
    "current_round": 3,
    "task_analysis": "...",
    "execution_plan": "...",
    "status": "complete",
    "contains_html": false,
    "content_type": "markdown",
    "recommended_questions": ["问题1", "问题2"],
    "download_links": ["file1.xlsx"]
}
```

---

## 三、代码管理流程

### 3.1 代码块检测和保存

当模型响应中包含 Python 代码块时，后端会自动处理：

**检测规则**：

```python
# 正则表达式匹配 Python 代码块
PYTHON_CODE_BLOCK = re.compile(r'```python\n(.*?)\n```', re.DOTALL)
```

**处理流程**：

```
检测到 ```python...``` 代码块
    ↓
生成唯一代码标识: code_YYYYMMDD_random
    ↓
保存到 FileStore: data/code_*.py
    ↓
用 <!-- CODE_SAVED: code_id | description --> 替换原始代码
    ↓
减少后续上下文 token 使用
```

**代码示例**：

```python
# backend/api/services/ba_agent.py

def _save_code_blocks(content: str) -> tuple[str, list[dict]]:
    """检测并保存 Python 代码块"""
    code_blocks = PYTHON_CODE_BLOCK.findall(content)
    saved_codes = []

    for i, code in enumerate(code_blocks):
        # 生成唯一 ID
        code_id = f"code_{datetime.now().strftime('%Y%m%d')}_{secrets.token_hex(4)}"

        # 保存到文件
        file_path = f"data/{code_id}.py"
        FileStore.save_file(file_path, code, "python")

        # 生成描述
        description = code.split('\n')[0][:50] if code else "代码片段"

        # 替换为占位符
        placeholder = f"<!-- CODE_SAVED: {code_id} | {description} -->"
        content = PYTHON_CODE_BLOCK.sub(placeholder, content, count=1)

        saved_codes.append({
            "code_id": code_id,
            "file_path": file_path,
            "description": description,
            "original_length": len(code)
        })

    return content, saved_codes
```

**替换示例**：

原始内容：
```markdown
以下是数据处理代码：

```python
import pandas as pd
df = pd.read_csv('sales.csv')
result = df.groupby('quarter').sum()
print(result)
```

计算结果为...
```

替换后：
```markdown
以下是数据处理代码：

<!-- CODE_SAVED: code_20250207_a1b2c3d4 | import pandas as pd -->

计算结果为...
```

### 3.2 代码检索和 Review

用户可以通过 `file_reader` 工具检索已保存的代码：

**检索请求**：

```json
{
    "tool_name": "file_reader",
    "tool_call_id": "call_retrieve_code",
    "arguments": {
        "path": "data/code_20250207_a1b2c3d4.py",
        "response_format": "standard"
    }
}
```

**读取后处理**：

```python
def _post_process_code_retrieval(code_content: str) -> str:
    """代码读取后的后续处理"""
    # 再次清理上下文
    # 保留概述性描述
    lines = code_content.split('\n')
    if len(lines) > 50:
        # 截断长代码，保留开头和结尾
        head = '\n'.join(lines[:20])
        tail = '\n'.join(lines[-10:])
        return f"{head}\n\n... (省略 {len(lines) - 30} 行) ...\n\n{tail}"
    return code_content
```

---

## 四、后端日志系统

### 4.1 日志记录内容

后端会详细记录整个处理过程中的关键信息：

#### 4.1.1 ModelInput（模型输入）

```json
{
    "type": "ModelInput",
    "role": "user",
    "content": "分析销售数据...",
    "token_count": 150,
    "timestamp": "2026-02-07T10:30:00Z"
}
```

#### 4.1.2 ModelOutput（模型输出）

```json
{
    "type": "ModelOutput",
    "raw_content": "{\"task_analysis\": \"...\", \"action\": {...}}",
    "structured_response": {
        "task_analysis": "...",
        "execution_plan": "...",
        "current_round": 1,
        "action": {
            "type": "tool_call",
            "content": [...]
        }
    },
    "token_count": 500,
    "timestamp": "2026-02-07T10:30:01Z"
}
```

#### 4.1.3 BackendProcessing（后端处理）

**工具调用**：

```json
{
    "type": "BackendProcessing",
    "event": "tool_call",
    "tool_name": "run_python",
    "tool_call_id": "call_abc123",
    "arguments": {
        "code": "...",
        "timeout": 60
    },
    "timestamp": "2026-02-07T10:30:02Z"
}
```

**代码保存**：

```json
{
    "type": "BackendProcessing",
    "event": "code_saved",
    "code_id": "code_20250207_a1b2c3d4",
    "file_path": "data/code_20250207_a1b2c3d4.py",
    "original_length": 1250,
    "description": "import pandas as pd...",
    "timestamp": "2026-02-07T10:30:03Z"
}
```

**代码检索**：

```json
{
    "type": "BackendProcessing",
    "event": "code_retrieved",
    "code_id": "code_20250207_a1b2c3d4",
    "content_length": 1250,
    "truncated": true,
    "timestamp": "2026-02-07T10:30:04Z"
}
```

**上下文清理**：

```json
{
    "type": "BackendProcessing",
    "event": "context_cleaned",
    "original_tokens": 5000,
    "cleaned_tokens": 3000,
    "saved_tokens": 2000,
    "timestamp": "2026-02-07T10:30:05Z"
}
```

### 4.2 日志格式

**文件名**：`conversation_{conversation_id}_{timestamp}.jsonl`

**按轮次分组**：

```jsonl
{"type": "round_start", "round": 1, "timestamp": "2026-02-07T10:30:00Z"}
{"type": "ModelInput", "role": "user", "content": "...", "token_count": 150, "timestamp": "2026-02-07T10:30:00Z"}
{"type": "ModelOutput", "raw_content": "...", "structured_response": {...}, "token_count": 500, "timestamp": "2026-02-07T10:30:01Z"}
{"type": "BackendProcessing", "event": "tool_call", "tool_name": "run_python", "timestamp": "2026-02-07T10:30:02Z"}
{"type": "BackendProcessing", "event": "code_saved", "code_id": "code_20250207_a1b2c3d4", "timestamp": "2026-02-07T10:30:03Z"}
{"type": "round_end", "round": 1, "duration_ms": 1234, "timestamp": "2026-02-07T10:30:04Z"}
```

**日志存储位置**：`logs/conversations/`

---

## 五、API 响应格式

### 5.1 tool_call 响应

**端点**: `POST /api/v1/agent/query`

```json
{
    "success": true,
    "data": {
        "response": "",
        "conversation_id": "conv_a87365d8983d",
        "duration_ms": 1234,
        "tool_calls": [],
        "artifacts": [],
        "metadata": {
            "content_type": "text",
            "has_structured_response": true,
            "action_type": "tool_call",
            "current_round": 1,
            "task_analysis": "用户需分析销售数据，识别为数据分析任务。1. 需要查询数据库获取销售记录；2. 计算各项指标；3. 生成可视化图表。",
            "execution_plan": "R1: 数据查询与计算; R2: 可视化与报告",
            "tool_calls": [
                {
                    "tool_name": "run_python",
                    "tool_call_id": "call_abc123",
                    "arguments": {
                        "code": "import pandas as pd\ndf = pd.read_csv('sales.csv')\nprint(df.groupby('quarter').sum())",
                        "timeout": 60,
                        "response_format": "standard"
                    }
                },
                {
                    "tool_name": "file_reader",
                    "tool_call_id": "call_def456",
                    "arguments": {
                        "path": "data/sales.csv",
                        "format": "csv",
                        "nrows": 100,
                        "response_format": "standard"
                    }
                }
            ],
            "status": "processing"
        }
    }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `response` | string | 空字符串（tool_call 时无 final_report） |
| `conversation_id` | string | 对话 ID |
| `duration_ms` | number | 处理耗时（毫秒） |
| `metadata.status` | "processing" | 状态为处理中 |
| `metadata.tool_calls` | array | 工具调用详情 |

### 5.2 complete 响应（纯文本）

```json
{
    "success": true,
    "data": {
        "response": "根据数据分析结果：\n\n- Q1 销售额：500万元，同比增长15%\n- Q2 销售额：520万元，同比增长18%\n- Q3 销售额：580万元，同比增长22%\n\n主要增长来源于电子产品线，贡献了60%的增量。",
        "conversation_id": "conv_a87365d8983d",
        "duration_ms": 5678,
        "tool_calls": [],
        "artifacts": [],
        "metadata": {
            "content_type": "markdown",
            "has_structured_response": true,
            "action_type": "complete",
            "current_round": 3,
            "task_analysis": "分析完成。已获取销售数据，计算了同比增长率，准备好最终报告。",
            "execution_plan": "R1: 数据查询; R2: 数据分析; R3: 生成报告(当前)",
            "status": "complete",
            "contains_html": false,
            "recommended_questions": [
                "各产品线的销售占比如何？",
                "可以按地区分解销售数据吗？"
            ],
            "download_links": ["sales_report.xlsx", "analysis_chart.png"]
        }
    }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `response` | string | 最终报告内容（纯文本/markdown） |
| `metadata.content_type` | "markdown" | 内容类型为 markdown |
| `metadata.contains_html` | false | 不包含模型生成的 HTML |
| `metadata.recommended_questions` | array | 推荐问题列表 |
| `metadata.download_links` | array | 可下载文件列表 |

### 5.3 complete 响应（含 ECharts 图表）

```json
{
    "success": true,
    "data": {
        "response": "<div class='chart-wrapper'><div id='chart-sales' style='width:600px;height:400px;'></div></div><script>(function(){const chart = echarts.init(document.getElementById('chart-sales'));chart.setOption({xAxis:{type:'category',data:['Q1','Q2','Q3','Q4']},yAxis:{type:'value'},series:[{type:'bar',data:[500,520,580,620]}]});})();</script>",
        "conversation_id": "conv_a87365d8983d",
        "duration_ms": 5678,
        "tool_calls": [],
        "artifacts": [],
        "metadata": {
            "content_type": "html",
            "has_structured_response": true,
            "action_type": "complete",
            "current_round": 2,
            "task_analysis": "数据可视化分析完成",
            "execution_plan": "R1: 数据查询; R2: 生成可视化图表(当前)",
            "status": "complete",
            "contains_html": true
        }
    }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `response` | string | 最终报告内容（HTML/JavaScript） |
| `metadata.content_type` | "html" | 内容类型为 HTML |
| `metadata.contains_html` | true | 包含模型生成的 HTML |

---

## 六、前端渲染逻辑

### 6.1 渲染流程

**代码位置**: `frontend/index.html:814-916`

```
addMessage(content, isUser, metadata)
    ↓
renderStructuredResponse(container, content, metadata)
    ↓
按顺序渲染各个组件
```

### 6.2 组件渲染顺序

| 顺序 | 组件 | 条件 | 渲染方式 |
|------|------|------|----------|
| 1 | task_analysis | metadata.task_analysis 存在 | 蓝色可折叠框 |
| 2 | execution_plan | metadata.execution_plan 存在 | 橙色固定框 |
| 3 | tool_call_status | action_type="tool_call" | 蓝色加载框 + 旋转动画 |
| 4 | final_report | 任何情况 | Markdown/HTML 渲染 |
| 5 | saved_code_notice | response 包含 CODE_SAVED 标记 | 灰色提示框 |
| 6 | recommended_questions | metadata.recommended_questions 存在 | 灰色可点击按钮 |
| 7 | download_links | metadata.download_links 存在 | 绿色下载按钮 |

### 6.3 组件详细说明

#### 6.3.1 task_analysis（思维链分析）

**渲染条件**: `metadata.task_analysis` 存在

**渲染效果**:
```
┌─────────────────────────────────────┐
│ 💡 思维链分析 ▼                     │
│ 用户需分析销售数据，识别为数据...   │
└─────────────────────────────────────┘
```

**样式**:
- 背景: `#f0f7ff` (浅蓝)
- 左边框: `3px solid #2196F3` (蓝色)
- 可折叠: `<details>` 元素

#### 6.3.2 execution_plan（执行计划）

**渲染条件**: `metadata.execution_plan` 存在

**渲染效果**:
```
┌─────────────────────────────────────┐
│ 📋 执行计划                         │
│ R1: 数据查询与计算; R2: 可视化     │
└─────────────────────────────────────┘
```

**样式**:
- 背景: `#fff3e0` (浅橙)
- 左边框: `3px solid #FF9800` (橙色)

#### 6.3.3 tool_call_status（工具调用状态）

**渲染条件**: `metadata.action_type === "tool_call"`

**渲染效果**:
```
┌─────────────────────────────────────┐
│ ⏳ 正在执行: run_python, file_reader │
└─────────────────────────────────────┘
```

**样式**:
- 背景: `#e3f2fd` (浅蓝)
- 旋转动画: CSS `@keyframes spin`
- 显示所有工具名称

#### 6.3.4 final_report（最终报告）

**渲染条件**: 始终渲染

**情况1**: `metadata.contains_html === false`
- 渲染方式: `textContent`
- 样式: `line-height: 1.6; white-space: pre-wrap`
- 保留换行符

**情况2**: `metadata.contains_html === true`
- 渲染方式: `innerHTML`
- 初始化 ECharts 图表
- 响应式调整

#### 6.3.5 saved_code_notice（代码保存提示）

**渲染条件**: `response` 包含 `<!-- CODE_SAVED: ... -->` 标记

**渲染效果**:
```
┌─────────────────────────────────────┐
│ 📝 代码已保存                       │
│ Python 代码已保存到 code_20250207_...│
│ [查看代码] [下载代码]               │
└─────────────────────────────────────┘
```

**交互**: 点击"查看代码"通过 file_reader 检索代码

#### 6.3.6 recommended_questions（推荐问题）

**渲染条件**: `metadata.recommended_questions` 数组非空

**渲染效果**:
```
┌─────────────────────────────────────┐
│ 🤔 推荐问题                         │
│ [💡 各产品线的销售占比如何？]      │
│ [💡 可以按地区分解销售数据吗？]    │
└─────────────────────────────────────┘
```

**交互**: 点击按钮自动填充到输入框并聚焦

#### 6.3.7 download_links（下载链接）

**渲染条件**: `metadata.download_links` 数组非空

**渲染效果**:
```
┌─────────────────────────────────────┐
│ 📦 可下载文件                       │
│ [📥 sales_report.xlsx] [📥 analysis_chart.png] │
└─────────────────────────────────────┘
```

**链接格式**: `/api/v1/files/download/{filename}`

---

## 七、完整示例

### 7.1 场景：销售数据分析（多轮对话）

#### 第一轮：工具调用

**用户输入**: "分析 sales.csv 文件，计算季度销售额"

**大模型返回**:
```json
{
    "task_analysis": "用户请求分析 CSV 文件中的销售数据。1. 需要读取文件；2. 按季度分组统计；3. 计算总额。",
    "execution_plan": "R1: 读取数据并计算; R2: 生成分析报告",
    "current_round": 1,
    "action": {
        "type": "tool_call",
        "content": [
            {
                "tool_name": "run_python",
                "tool_call_id": "call_q1_read",
                "arguments": {
                    "code": "import pandas as pd\ndf = pd.read_csv('sales.csv')\nresult = df.groupby('quarter')['sales'].sum()\nprint(result)",
                    "timeout": 60,
                    "response_format": "standard"
                }
            }
        ]
    }
}
```

**API 响应**:
```json
{
    "data": {
        "response": "",
        "metadata": {
            "action_type": "tool_call",
            "current_round": 1,
            "task_analysis": "用户请求分析 CSV 文件...",
            "execution_plan": "R1: 读取数据并计算; R2: 生成分析报告",
            "tool_calls": [
                {"tool_name": "run_python", "tool_call_id": "call_q1_read", "arguments": {...}}
            ],
            "status": "processing"
        }
    }
}
```

**前端渲染**:
```
┌─────────────────────────────────────┐
│ 💡 思维链分析 ▼                     │
│ 用户请求分析 CSV 文件中的销售...   │
├─────────────────────────────────────┤
│ 📋 执行计划                         │
│ R1: 读取数据并计算; R2: 生成分析报告│
├─────────────────────────────────────┤
│ ⏳ 正在执行: run_python             │
└─────────────────────────────────────┘
```

#### 第二轮：完成报告

**工具执行结果返回给模型后，模型继续分析**

**大模型返回**:
```json
{
    "task_analysis": "工具执行完成，已获取季度销售数据。Q1: 500万, Q2: 520万, Q3: 580万, Q4: 620万。需要生成分析报告。",
    "execution_plan": "R1: 读取数据并计算; R2: 生成分析报告(当前)",
    "current_round": 2,
    "action": {
        "type": "complete",
        "content": "## 销售数据分析报告\n\n### 季度销售额\n- Q1: 500万元\n- Q2: 520万元 (环比增长4%)\n- Q3: 580万元 (环比增长11.5%)\n- Q4: 620万元 (环比增长6.9%)\n\n### 趋势分析\n全年销售额呈现稳定增长趋势，Q3 增长最为显著，主要受促销活动推动。",
        "recommended_questions": [
            "各产品线的销售贡献如何？",
            "可以生成可视化图表吗？"
        ],
        "download_links": ["quarterly_sales.xlsx"]
    }
}
```

**API 响应**:
```json
{
    "data": {
        "response": "## 销售数据分析报告\n\n### 季度销售额\n- Q1: 500万元\n- Q2: 520万元 (环比增长4%)\n- Q3: 580万元 (环比增长11.5%)\n- Q4: 620万元 (环比增长6.9%)\n\n### 趋势分析\n全年销售额呈现稳定增长趋势，Q3 增长最为显著，主要受促销活动推动。",
        "metadata": {
            "action_type": "complete",
            "current_round": 2,
            "task_analysis": "工具执行完成，已获取季度销售数据...",
            "execution_plan": "R1: 读取数据并计算; R2: 生成分析报告(当前)",
            "status": "complete",
            "content_type": "markdown",
            "contains_html": false,
            "recommended_questions": ["各产品线的销售贡献如何？", "可以生成可视化图表吗？"],
            "download_links": ["quarterly_sales.xlsx"]
        }
    }
}
```

**前端渲染**:
```
┌─────────────────────────────────────┐
│ 💡 思维链分析 ▼                     │
│ 工具执行完成，已获取季度销售数据... │
├─────────────────────────────────────┤
│ 📋 执行计划                         │
│ R1: 读取数据并计算; R2: 生成分析报告│
├─────────────────────────────────────┤
│ ## 销售数据分析报告                 │
│                                     │
│ ### 季度销售额                      │
│ - Q1: 500万元                       │
│ - Q2: 520万元 (环比增长4%)          │
│ ...                                 │
├─────────────────────────────────────┤
│ 🤔 推荐问题                         │
│ [💡 各产品线的销售贡献如何？]      │
│ [💡 可以生成可视化图表吗？]        │
├─────────────────────────────────────┤
│ 📦 可下载文件                       │
│ [📥 quarterly_sales.xlsx]           │
└─────────────────────────────────────┘
```

### 7.2 场景：代码块保存和检索

#### 用户请求生成分析代码

**用户输入**: "生成分析销售数据的 Python 代码"

**大模型返回**:
```json
{
    "task_analysis": "用户需要生成销售数据分析的 Python 代码。需要编写完整的数据处理和分析脚本。",
    "execution_plan": "R1: 生成分析代码(当前)",
    "current_round": 1,
    "action": {
        "type": "complete",
        "content": "以下是销售数据分析代码：\n\n```python\nimport pandas as pd\nimport matplotlib.pyplot as plt\n\ndf = pd.read_csv('sales.csv')\nquarterly = df.groupby('quarter').sum()\n\nplt.figure(figsize=(10, 6))\nquarterly['sales'].plot(kind='bar')\nplt.title('季度销售趋势')\nplt.savefig('sales_trend.png')\n```\n\n代码已保存，您可以通过文件读取工具查看完整代码。"
    }
}
```

**后端处理**:

```python
# 检测到 Python 代码块
code_id = "code_20250207_a1b2c3d4"
file_path = "data/code_20250207_a1b2c3d4.py"

# 保存代码
FileStore.save_file(file_path, code, "python")

# 替换为占位符
content = content.replace(
    "```python\n...```",
    "<!-- CODE_SAVED: code_20250207_a1b2c3d4 | import pandas as pd... -->"
)

# 记录日志
logger.info({
    "type": "BackendProcessing",
    "event": "code_saved",
    "code_id": code_id,
    "original_length": len(code)
})
```

**API 响应**:
```json
{
    "data": {
        "response": "以下是销售数据分析代码：\n\n<!-- CODE_SAVED: code_20250207_a1b2c3d4 | import pandas as pd... -->\n\n代码已保存，您可以通过文件读取工具查看完整代码。",
        "metadata": {
            "action_type": "complete",
            "current_round": 1,
            "saved_codes": [
                {
                    "code_id": "code_20250207_a1b2c3d4",
                    "file_path": "data/code_20250207_a1b2c3d4.py",
                    "description": "import pandas as pd...",
                    "original_length": 250
                }
            ]
        }
    }
}
```

**前端渲染**:
```
┌─────────────────────────────────────┐
│ 💡 思维链分析 ▼                     │
│ 用户需要生成销售数据分析的 Python... │
├─────────────────────────────────────┤
│ 📋 执行计划                         │
│ R1: 生成分析代码(当前)              │
├─────────────────────────────────────┤
│ 以下是销售数据分析代码：             │
│                                     │
│ 📝 代码已保存                       │
│ Python 代码已保存到 code_20250207... │
│ [查看代码] [下载代码]               │
│                                     │
│ 代码已保存，您可以通过文件读取工具...│
└─────────────────────────────────────┘
```

#### 用户请求查看代码

**用户输入**: "查看保存的代码"

**大模型返回**:
```json
{
    "task_analysis": "用户想查看之前保存的代码，需要使用 file_reader 读取。",
    "execution_plan": "R1: 读取代码文件(当前)",
    "current_round": 1,
    "action": {
        "type": "tool_call",
        "content": [
            {
                "tool_name": "file_reader",
                "tool_call_id": "call_read_code",
                "arguments": {
                    "path": "data/code_20250207_a1b2c3d4.py",
                    "format": "python",
                    "response_format": "full"
                }
            }
        ]
    }
}
```

### 7.3 场景：生成可视化图表

**用户输入**: "生成销售趋势的可视化图表"

**大模型返回**:
```json
{
    "task_analysis": "用户需要可视化销售趋势数据。已准备好季度销售数据，可以生成 ECharts 柱状图。",
    "execution_plan": "R1: 生成可视化图表(当前)",
    "current_round": 1,
    "action": {
        "type": "complete",
        "content": "<div class='chart-wrapper' style='margin: 20px 0;'><div id='chart-sales-trend' style='width:100%;height:400px;'></div></div><script>(function(){const chart = echarts.init(document.getElementById('chart-sales-trend'));chart.setOption({title:{text:'季度销售趋势'},tooltip:{},xAxis:{type:'category',data:['Q1','Q2','Q3','Q4']},yAxis:{type:'value',name:'销售额(万元)'},series:[{type:'bar',data:[500,520,580,620],itemStyle:{color:'#2196F3'}}]});})();</script>"
    }
}
```

**API 响应**:
```json
{
    "data": {
        "response": "<div class='chart-wrapper' style='margin: 20px 0;'><div id='chart-sales-trend' style='width:100%;height:400px;'></div></div><script>...</script>",
        "metadata": {
            "action_type": "complete",
            "current_round": 1,
            "task_analysis": "用户需要可视化销售趋势数据...",
            "execution_plan": "R1: 生成可视化图表(当前)",
            "status": "complete",
            "content_type": "html",
            "contains_html": true
        }
    }
}
```

**前端渲染**:
```
┌─────────────────────────────────────┐
│ 💡 思维链分析 ▼                     │
│ 用户需要可视化销售趋势数据...       │
├─────────────────────────────────────┤
│ 📋 执行计划                         │
│ R1: 生成可视化图表(当前)            │
├─────────────────────────────────────┤
│     [ECharts 柱状图渲染区域]        │
│                                     │
│    季度销售趋势                     │
│    ▂▃▅▇▃▂                          │
│    500 520 580 620                  │
└─────────────────────────────────────┘
```

---

## 附录

### A. 相关文件

| 文件 | 说明 |
|------|------|
| `backend/models/response.py` | 结构化响应模型定义，包含提示词加载逻辑 |
| `backend/api/services/ba_agent.py` | 响应解析和处理逻辑，包含代码保存功能 |
| `backend/core/file_store.py` | 文件存储管理 |
| `backend/core/logger.py` | 后端日志系统 |
| `frontend/index.html` | 前端渲染逻辑 |
| `docs/prompts.md` | 系统提示词定义 |
| `docs/api.md` | API 端点文档 |

### B. 数据模型定义

```python
# backend/models/response.py

class ToolCall(BaseModel):
    tool_name: str
    tool_call_id: str
    arguments: Dict[str, Any]

class Action(BaseModel):
    type: Literal["tool_call", "complete"]
    content: Union[List[ToolCall], str]
    recommended_questions: Optional[List[str]] = None
    download_links: Optional[List[str]] = None

class StructuredResponse(BaseModel):
    task_analysis: str
    execution_plan: str
    current_round: int = 1
    action: Action

# 提示词加载函数
def _load_system_prompt() -> str:
    """从 docs/prompts.md 加载系统提示词"""
    # ... 实现逻辑
```

### C. 工具调用参数规范

#### run_python (Python 代码执行)

```json
{
    "tool_name": "run_python",
    "tool_call_id": "call_xxx",
    "arguments": {
        "code": "要执行的 Python 代码（仅支持白名单库）",
        "timeout": 60,
        "response_format": "standard"
    }
}
```

**参数说明**：
- `code` (必需): 要执行的 Python 代码
- `timeout` (可选): 执行超时时间（秒），范围 5-300，默认 60
- `response_format` (可选): 响应格式，可选值：brief/standard/full，默认 standard

**白名单库**: json, csv, datetime, math, statistics, random, pandas, numpy, scipy, statsmodels, openpyxl, xlrd, xlsxwriter, matplotlib, seaborn, plotly

#### file_reader (文件读取)

```json
{
    "tool_name": "file_reader",
    "tool_call_id": "call_xxx",
    "arguments": {
        "path": "文件路径",
        "format": "csv",
        "encoding": "utf-8",
        "sheet_name": 0,
        "nrows": 100,
        "parse_metadata": false,
        "response_format": "standard"
    }
}
```

**参数说明**：
- `path` (必需): 文件路径
- `format` (可选): 文件格式，可选值：csv/excel/json/text/python/sql，不指定则自动检测
- `encoding` (可选): 文本编码，默认 utf-8
- `sheet_name` (可选): Excel 工作表名称或索引，默认第一个表
- `nrows` (可选): 最大读取行数，None 表示读取全部
- `parse_metadata` (可选): 是否解析元数据，默认 false
- `response_format` (可选): 响应格式，可选值：brief/standard/full，默认 standard

#### query_database (数据库查询)

```json
{
    "tool_name": "query_database",
    "tool_call_id": "call_xxx",
    "arguments": {
        "query": "SELECT ...",
        "connection": "primary",
        "params": {},
        "max_rows": 1000,
        "response_format": "standard"
    }
}
```

**参数说明**：
- `query` (必需): SQL 查询语句
- `connection` (可选): 数据库连接名称，默认 primary
- `params` (可选): 查询参数（用于参数化查询，防止 SQL 注入）
- `max_rows` (可选): 最大返回行数，范围 1-10000，默认 1000
- `response_format` (可选): 响应格式，可选值：brief/standard/full，默认 standard

#### web_search (网络搜索)

```json
{
    "tool_name": "web_search",
    "tool_call_id": "call_xxx",
    "arguments": {
        "query": "搜索关键词",
        "num_results": 10,
        "response_format": "standard"
    }
}
```

**参数说明**：
- `query` (必需): 搜索关键词
- `num_results` (可选): 返回结果数量，默认 10
- `response_format` (可选): 响应格式，可选值：brief/standard/full，默认 standard

#### web_reader (网页读取)

```json
{
    "tool_name": "web_reader",
    "tool_call_id": "call_xxx",
    "arguments": {
        "url": "https://example.com",
        "response_format": "standard"
    }
}
```

**参数说明**：
- `url` (必需): 网页 URL
- `response_format` (可选): 响应格式，可选值：brief/standard/full，默认 standard

### D. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.3.0 | 2026-02-07 | 新增代码管理流程、后端日志系统；更新提示词来源；更新工具调用参数 |
| v2.2.0 | 2026-02-07 | 重构响应格式：后端返回数据，前端渲染组件 |
| v2.1.0 | 2026-02-06 | 初始结构化响应格式 |
