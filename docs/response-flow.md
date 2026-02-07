# BA-Agent 响应格式流转文档

> **Version**: v2.2.0
> **Last Updated**: 2026-02-07

本文档详细描述 BA-Agent 从大模型返回到前端渲染的完整数据流转过程。

---

## 目录

1. [大模型返回格式](#一大模型返回格式)
2. [后端处理逻辑](#二后端处理逻辑)
3. [API 响应格式](#三api-响应格式)
4. [前端渲染逻辑](#四前端渲染逻辑)
5. [完整示例](#五完整示例)

---

## 一、大模型返回格式

大模型必须严格按照结构化 JSON 格式返回响应，由 `STRUCTURED_RESPONSE_SYSTEM_PROMPT` 定义。

### 1.1 type="tool_call"（调用工具）

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
                "tool_name": "bac_code_agent",
                "tool_call_id": "call_abc123",
                "arguments": {
                    "query": "读取 sales.csv 并计算月度销售额",
                    "outputFileName": "sales_analysis"
                }
            },
            {
                "tool_name": "query_database",
                "tool_call_id": "call_def456",
                "arguments": {
                    "sql": "SELECT * FROM products WHERE category = 'electronics'"
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

### 1.2 type="complete"（完成并返回报告）

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

### 1.3 特殊情况：带 ECharts 图表的 complete

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
3. **带代码块**：包含 markdown 代码块格式

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
query() 方法构建 API 响应
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
| `action.content` (complete) | 直接复制 | `response` (主响应体) |
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
        {"tool_name": "bac_code_agent", "tool_call_id": "call_abc123", "arguments": {...}},
        {"tool_name": "query_database", "tool_call_id": "call_def456", "arguments": {...}}
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

## 三、API 响应格式

### 3.1 tool_call 响应

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
                    "tool_name": "bac_code_agent",
                    "tool_call_id": "call_abc123",
                    "arguments": {
                        "query": "读取 sales.csv 并计算月度销售额",
                        "outputFileName": "sales_analysis"
                    }
                },
                {
                    "tool_name": "query_database",
                    "tool_call_id": "call_def456",
                    "arguments": {
                        "sql": "SELECT * FROM products WHERE category = 'electronics'"
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

### 3.2 complete 响应（纯文本）

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

### 3.3 complete 响应（含 ECharts 图表）

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

## 四、前端渲染逻辑

### 4.1 渲染流程

**代码位置**: `frontend/index.html:814-916`

```
addMessage(content, isUser, metadata)
    ↓
renderStructuredResponse(container, content, metadata)
    ↓
按顺序渲染各个组件
```

### 4.2 组件渲染顺序

| 顺序 | 组件 | 条件 | 渲染方式 |
|------|------|------|----------|
| 1 | task_analysis | metadata.task_analysis 存在 | 蓝色可折叠框 |
| 2 | execution_plan | metadata.execution_plan 存在 | 橙色固定框 |
| 3 | tool_call_status | action_type="tool_call" | 蓝色加载框 + 旋转动画 |
| 4 | final_report | 任何情况 | Markdown/HTML 渲染 |
| 5 | recommended_questions | metadata.recommended_questions 存在 | 灰色可点击按钮 |
| 6 | download_links | metadata.download_links 存在 | 绿色下载按钮 |

### 4.3 组件详细说明

#### 4.3.1 task_analysis（思维链分析）

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

#### 4.3.2 execution_plan（执行计划）

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

#### 4.3.3 tool_call_status（工具调用状态）

**渲染条件**: `metadata.action_type === "tool_call"`

**渲染效果**:
```
┌─────────────────────────────────────┐
│ ⏳ 正在执行: bac_code_agent, query_database │
└─────────────────────────────────────┘
```

**样式**:
- 背景: `#e3f2fd` (浅蓝)
- 旋转动画: CSS `@keyframes spin`
- 显示所有工具名称

#### 4.3.4 final_report（最终报告）

**渲染条件**: 始终渲染

**情况1**: `metadata.contains_html === false`
- 渲染方式: `textContent`
- 样式: `line-height: 1.6; white-space: pre-wrap`
- 保留换行符

**情况2**: `metadata.contains_html === true`
- 渲染方式: `innerHTML`
- 初始化 ECharts 图表
- 响应式调整

#### 4.3.5 recommended_questions（推荐问题）

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

#### 4.3.6 download_links（下载链接）

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

## 五、完整示例

### 5.1 场景：销售数据分析（多轮对话）

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
                "tool_name": "bac_code_agent",
                "tool_call_id": "call_q1_read",
                "arguments": {
                    "query": "读取 sales.csv，按 quarter 列分组计算 sales 列的总和",
                    "outputFileName": "quarterly_sales"
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
                {"tool_name": "bac_code_agent", "tool_call_id": "call_q1_read", "arguments": {...}}
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
│ ⏳ 正在执行: bac_code_agent         │
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

### 5.2 场景：生成可视化图表

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
| `backend/models/response.py` | 结构化响应模型定义 |
| `backend/api/services/ba_agent.py` | 响应解析和处理逻辑 |
| `frontend/index.html` | 前端渲染逻辑 |
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
```

### C. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.2.0 | 2026-02-07 | 重构响应格式：后端返回数据，前端渲染组件 |
| v2.1.0 | 2026-02-06 | 初始结构化响应格式 |
