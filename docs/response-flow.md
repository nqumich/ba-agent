# BA-Agent 响应格式流转文档

> **Version**: v2.7.0
> **Last Updated**: 2026-02-07

本文档详细描述 BA-Agent 从大模型返回到前端渲染的完整数据流转过程。

---

## ⚠️ 文档同步提醒

**重要**：本文档与 `docs/prompts.md` 中的工具参数定义必须保持一致。

- 修改本页面的「工具调用参数规范」时，请同步更新 `prompts.md` 的「工具使用指南」
- 修改 `prompts.md` 的工具定义时，请同步更新本页面的「工具调用参数规范」
- 系统已配置 `.claude/hooks/check-tool-params-update.sh` 自动提醒文档同步

---

---

## 目录

1. [大模型返回格式](#一大模型返回格式)
2. [后端处理逻辑](#二后端处理逻辑)
3. [代码管理流程](#三代码管理流程)
4. [代码引用解析](#四代码引用解析)
5. [后端日志系统](#五后端日志系统)
6. [API 响应格式](#六api-响应格式)
7. [前端渲染逻辑](#七前端渲染逻辑)
8. [完整流程示例](#八完整流程示例)

---

## 一、大模型返回格式

大模型必须严格按照结构化 JSON 格式返回响应，由系统提示词定义。

### 提示词来源

系统提示词从 `docs/prompts.md` 文件加载。如果文件不存在，使用内嵌的备用提示词。

### type="tool_call"（调用工具）

当模型需要调用工具时返回此格式。核心字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| task_analysis | string | 思维链：分析用户意图、预判风险、设计操作流程 |
| execution_plan | string | 执行计划：R1: xxx; R2: xxx; 格式描述各轮次目标 |
| current_round | int | 当前轮次，从 1 开始递增 |
| action.type | "tool_call" | 动作类型为工具调用 |
| action.content | array | 工具调用数组，支持并行调用（最多6个） |

每个工具调用包含：tool_name（工具名称）、tool_call_id（唯一标识）、arguments（参数）。

### type="complete"（完成并返回报告）

当模型完成分析并返回最终报告时返回此格式。核心字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| action.type | "complete" | 动作类型为完成 |
| action.content | string | 最终报告内容（纯文本或包含 code_ref 标签） |
| action.recommended_questions | array (可选) | 推荐用户后续询问的问题列表 |
| action.download_links | array (可选) | 推荐用户下载的文件名列表 |
| action.code_blocks | array (可选) | 需要保存的代码块列表 |

### 特殊情况：包含代码引用的报告

当模型需要在最终报告中展示已创建的代码时，使用 `<code_ref>code_id</code_ref>` 标签引用，而不是输出完整代码。

---

## 二、后端处理逻辑

### 处理流程

```
大模型返回 JSON
    ↓
解析为 StructuredResponse 对象
    ↓
提取内容
    ↓
代码引用解析（如果包含 code_ref）
    ↓
代码块保存（如果包含 code_blocks）
    ↓
上下文清理（减少 token 使用）
    ↓
构建 API 响应
    ↓
记录后端日志
    ↓
返回给前端
```

### 各个 Key 的处理方式

| 模型返回的 Key | 后端处理 | 放入 API 响应的哪个字段 |
|--------------|---------|---------------------|
| task_analysis | 直接复制 | metadata.task_analysis |
| execution_plan | 直接复制 | metadata.execution_plan |
| current_round | 直接复制 | metadata.current_round |
| action.type | 直接复制 | metadata.action_type |
| action.content (tool_call) | 提取工具信息数组 | metadata.tool_calls[] |
| action.content (complete) | 解析 code_ref + 直接复制 | response (主响应体) |
| action.recommended_questions | 直接复制 | metadata.recommended_questions |
| action.download_links | 直接复制 | metadata.download_links |
| action.code_blocks | 验证语言并保存 | metadata.saved_codes[] |

### tool_call 时的特殊处理

提取工具调用信息数组，每个包含工具名称、调用 ID 和参数，状态设置为 processing。

### complete 时的特殊处理

设置状态为 complete，提取推荐问题和下载链接，检测内容是否包含 HTML（如 ECharts 图表）。

---

## 三、代码管理流程

### 代码块检测和保存

当模型响应中包含代码块时，后端会自动处理。

#### 多语言支持

系统支持保存多种语言格式的代码文件：

| 语言类型 | 文件扩展名 | 主要用途 |
|---------|-----------|----------|
| Python | .py | 数据分析、计算、可视化 |
| JavaScript | .js | 前端交互 |
| HTML | .html | 网页结构 |
| CSS | .css | 样式设计 |
| SQL | .sql | 数据库查询 |
| Markdown | .md | 文档 |

其他支持语言：TypeScript, JSON, YAML, XML, Shell, R, Java, C/C++, Go, Rust, PHP, Ruby

#### 语言验证机制

当模型创建代码时，系统会：

1. 检查模型指定的 language 是否在支持列表中
2. 如果不支持，自动降级为 python 并记录警告
3. 根据语言类型选择正确的文件扩展名
4. 将代码保存到对应的文件格式

#### 处理流程

```
模型输出包含 code_blocks
    ↓
对于每个代码块：
    ├─ 验证 language 类型
    ├─ 选择对应的文件扩展名
    ├─ 生成唯一代码标识 (code_id)
    ├─ 保存到 data/code_id.{扩展名}
    └─ 记录元数据 (language, description, 等)
    ↓
代码可用于后续引用
```

#### 代码元数据

每个保存的代码文件包含以下元数据：

| 字段 | 说明 | 来源 |
|------|------|------|
| code_id | 代码唯一标识 | 模型生成 |
| language | 代码语言类型 | 模型指定（验证后） |
| description | 代码描述 | 模型提供 |
| line_count | 代码行数 | 自动计算 |
| char_count | 字符数量 | 自动计算 |

---

## 四、引用解析机制

### 代码引用解析 (code_ref)

当模型在最终报告中需要展示代码时，使用 `<code_ref>code_id</code_ref>` 标签引用，而不是输出完整代码。

#### 标签格式

```
<code_ref>code_sales_analysis</code_ref>
```

#### 解析流程

```
后端收到包含 code_ref 的响应
    ↓
提取所有 code_ref 标签
    ↓
对于每个 code_id：
    ├─ 从 CodeStore 查询代码信息
    ├─ 验证代码是否存在
    ├─ 获取代码的 language 和 description
    └─ 记录到代码信息列表
    ↓
生成处理后的内容：
    ├─ 将 code_ref 替换为占位符 {{CODE:N}}
    └─ 返回代码信息列表
    ↓
传递给前端渲染
```

#### 前端渲染

前端根据后端返回的代码信息列表，按照占位符的顺序渲染代码块。

### 文件引用解析 (file_ref)

当模型在最终报告中需要引用用户上传的文件时，使用 `<file_ref>file_id</file_ref>` 标签引用。

#### 标签格式

```
<file_ref>upload_001</file_ref>
```

#### 解析流程

```
后端收到包含 file_ref 的响应
    ↓
提取所有 file_ref 标签
    ↓
对于每个 file_id：
    ├─ 从 UploadStore 查询文件信息
    ├─ 验证文件是否存在
    ├─ 获取文件的 filename、file_type、size 等
    └─ 记录到文件信息列表
    ↓
生成处理后的内容：
    ├─ 将 file_ref 替换为占位符 {{FILE:N}}
    └─ 返回文件信息列表
    ↓
传递给前端渲染
```

#### 前端渲染

前端根据后端返回的文件信息列表，按照占位符的顺序渲染文件引用组件。

### 统一文件列表

#### 列表构建

每次对话开始时，系统会构建统一文件列表（markdown 格式），包含代码文件和上传文件：

1. 从 CodeStore 查询会话中的所有代码文件
2. 从 UploadStore 查询会话中的所有上传文件
3. 生成 markdown 格式的文件列表
4. 作为系统消息添加到上下文中

#### 列表格式

```
可用文件列表：

**代码文件：**
- [code_sales_analysis] sales_analysis.py (python) - 销售数据分析 | 2.5 KB
- [code_visualization] chart.js (javascript) - 趋势图表 | 1.2 KB

**上传文件：**
- [upload_001] sales_data.csv (csv) - 2024年销售数据 | 15.3 KB
- [upload_002] report_template.md (markdown) - 报告模板 | 4.8 KB

**你可以：**
- 使用 `<code_ref>code_id</code_ref>` 引用代码文件
- 使用 `<file_ref>file_id</file_ref>` 引用上传文件
```

#### 作用

让模型知道本次对话中有哪些文件可以引用，避免重复创建或上传。

---

## 五、后端日志系统

### 日志记录内容

后端会详细记录整个处理过程中的关键信息。

#### 记录的事件类型

| 事件类型 | 说明 |
|---------|------|
| ModelInput | 模型输入内容 |
| ModelOutput | 模型原始输出 |
| BackendProcessing | 后端处理事件 |
| code_saved | 代码保存事件 |
| code_retrieved | 代码检索事件 |
| context_cleaned | 上下文清理事件 |

#### 日志格式

日志以 JSONL 格式存储，每行一个 JSON 对象，包含时间戳和事件详情。

#### 日志存储位置

日志文件保存在 logs/conversations/ 目录，文件名格式为 `conversation_{id}_{timestamp}.jsonl`。

---

## 六、API 响应格式

### tool_call 响应

当 action_type 为 tool_call 时，响应包含工具调用详情，response 字段为空。

主要字段：
- response: 空字符串
- metadata.action_type: "tool_call"
- metadata.tool_calls: 工具调用数组
- metadata.status: "processing"

### complete 响应（纯文本）

当 action_type 为 complete 且不包含 HTML 时，响应包含最终报告内容。

主要字段：
- response: 最终报告内容（纯文本/markdown）
- metadata.content_type: "markdown"
- metadata.contains_html: false
- metadata.recommended_questions: 推荐问题列表
- metadata.download_links: 可下载文件列表

### complete 响应（含 HTML）

当 action_type 为 complete 且包含 HTML 时，响应包含图表等内容。

主要字段：
- response: HTML/JavaScript 内容
- metadata.content_type: "html"
- metadata.contains_html: true

### 包含代码引用的响应

当响应包含 code_ref 标签时，后端会解析并返回代码信息列表。

主要字段：
- response: 处理后的内容（code_ref 替换为占位符）
- metadata.code_refs: 代码信息列表
  - code_id: 代码标识
  - language: 代码语言
  - description: 代码描述
  - index: 显示顺序

---

## 七、前端渲染逻辑

### 渲染流程

前端收到 API 响应后，按顺序渲染各个组件。

### 组件渲染顺序

| 顺序 | 组件 | 条件 | 渲染方式 |
|------|------|------|----------|
| 1 | task_analysis | metadata.task_analysis 存在 | 蓝色可折叠框 |
| 2 | execution_plan | metadata.execution_plan 存在 | 橙色固定框 |
| 3 | tool_call_status | action_type="tool_call" | 蓝色加载框 + 旋转动画 |
| 4 | final_report | 任何情况 | Markdown/HTML 渲染 |
| 5 | code_blocks | metadata.code_refs 存在 | 代码块组件 |
| 6 | recommended_questions | metadata.recommended_questions 存在 | 可点击按钮 |
| 7 | download_links | metadata.download_links 存在 | 下载按钮 |

### 组件详细说明

#### task_analysis（思维链分析）

蓝色可折叠框，展示模型的思维链分析过程。

#### execution_plan（执行计划）

橙色固定框，展示多轮执行的计划（R1, R2, R3...）。

#### tool_call_status（工具调用状态）

蓝色加载框，显示当前正在执行的工具名称。

#### final_report（最终报告）

根据 content_type 决定渲染方式：
- markdown: 保留换行符的文本渲染
- html: 使用 innerHTML 渲染，初始化 ECharts 图表

#### code_blocks（代码块）

当代码信息列表存在时，按照 index 顺序渲染代码块，每个代码块包含：
- 代码语言标识
- 代码描述
- 语法高亮的代码内容
- 查看和下载按钮

#### recommended_questions（推荐问题）

可点击按钮，点击后自动填充到输入框。

#### download_links（下载链接）

下载按钮，链接到文件下载接口。

---

## 八、完整流程示例

### 场景：销售数据分析（多轮对话）

#### 第一轮：工具调用

用户请求分析销售数据。

模型返回 tool_call 类型响应，包含查询数据的工具调用。

后端解析并返回工具调用信息，前端显示加载状态。

#### 第二轮：完成报告

工具执行完成后，模型返回 complete 类型响应，包含分析结果。

后端解析响应，提取推荐问题和下载链接。

前端渲染：
- 思维链分析（可折叠）
- 执行计划
- 分析报告内容
- 推荐问题按钮
- 下载链接按钮

### 场景：代码创建与引用

#### 创建代码

用户请求生成分析代码。

模型返回 complete 响应，包含 code_blocks。

后端处理：
1. 验证 language 类型（如 python）
2. 选择文件扩展名（.py）
3. 保存到 data/code_xxx.py
4. 记录元数据

前端渲染：
- 思维链分析
- 执行计划
- 内容描述
- 代码保存提示

#### 引用代码

用户请求使用之前创建的代码。

模型使用 `file_reader` 工具主动读取代码文件：
1. 模型调用 `file_reader` 工具，指定要读取的 code_id
2. 系统从 CodeStore 读取完整代码
3. 文件内容返回给模型供使用
4. 在下一轮对话中，文件内容被自动清理为梗概以节省 token

### 场景：最终报告中引用代码

用户请求生成包含代码展示的报告。

模型返回 complete 响应，content 中包含 `<code_ref>code_xxx</code_ref>` 标签。

后端解析：
1. 提取所有 code_ref 标签
2. 从 CodeStore 查询代码信息
3. 替换为占位符 {{CODE:N}}
4. 返回代码信息列表

前端渲染：
- 按照占位符顺序渲染代码块
- 每个代码块显示语言、描述和内容

---

## 附录

### 相关文件

| 文件 | 说明 |
|------|------|
| backend/models/response.py | 结构化响应模型定义，包含提示词加载逻辑 |
| backend/api/services/ba_agent.py | 响应解析和处理逻辑 |
| backend/filestore/stores/code_store.py | 代码文件存储管理 |
| backend/core/context_manager.py | 上下文管理器 |
| docs/prompts.md | 系统提示词定义 |
| docs/context-management.md | 上下文管理详细文档 |

### 数据模型定义

结构化响应包含以下主要模型：

- ToolCall: 工具调用定义（tool_name, tool_call_id, arguments）
- CodeBlock: 代码块定义（code_id, code, language, description）
- Action: 动作定义（type, content, recommended_questions, download_links, code_blocks）
- StructuredResponse: 完整响应（task_analysis, execution_plan, current_round, action）

### 工具调用参数规范

#### run_python（Python 代码执行）

**用途**：执行 Python 代码进行数据分析、计算、可视化

**JSON 格式**：
```json
{
    "tool_name": "run_python",
    "tool_call_id": "call_xxx",
    "arguments": {
        "code": "import pandas as pd\nimport matplotlib.pyplot as plt\n...",
        "timeout": 60,
        "response_format": "standard"
    }
}
```

**参数说明**：
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| code | string | 是 | - | 要执行的 Python 代码 |
| timeout | integer | 否 | 60 | 执行超时时间（秒） |
| response_format | string | 否 | standard | 响应格式：brief/standard/full |

**白名单库**：json, csv, datetime, math, statistics, random, pandas, numpy, scipy, statsmodels, openpyxl, xlrd, xlsxwriter, matplotlib, seaborn, plotly

---

#### file_reader（文件读取）

**用途**：读取用户上传的文件内容

**JSON 格式**：
```json
{
    "tool_name": "file_reader",
    "tool_call_id": "call_xxx",
    "arguments": {
        "path": "upload_001",
        "format": "csv",
        "encoding": "utf-8",
        "nrows": 100,
        "response_format": "standard"
    }
}
```

**参数说明**：
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| path | string | 是 | - | 文件引用（upload_xxx 或文件路径） |
| format | string | 否 | auto | 文件格式：csv/excel/json/text/python/sql |
| encoding | string | 否 | utf-8 | 文本编码 |
| nrows | integer | 否 | - | 最大读取行数 |
| response_format | string | 否 | standard | 响应格式：brief/standard/full |

---

#### query_database（数据库查询）

**用途**：查询业务数据库

**JSON 格式**：
```json
{
    "tool_name": "query_database",
    "tool_call_id": "call_xxx",
    "arguments": {
        "query": "SELECT * FROM sales WHERE date >= '2024-01-01'",
        "max_rows": 1000,
        "params": {},
        "response_format": "standard"
    }
}
```

**参数说明**：
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | SQL 查询语句 |
| max_rows | integer | 否 | 1000 | 最大返回行数 |
| params | object | 否 | {} | 查询参数（参数化查询） |
| response_format | string | 否 | standard | 响应格式：brief/standard/full |

---

#### web_search（网络搜索）

**用途**：搜索网络信息

**JSON 格式**：
```json
{
    "tool_name": "web_search",
    "tool_call_id": "call_xxx",
    "arguments": {
        "query": "2024年销售趋势分析",
        "num_results": 10
    }
}
```

**参数说明**：
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | 搜索关键词 |
| num_results | integer | 否 | 10 | 返回结果数量 |

---

#### web_reader（网页读取）

**用途**：读取网页内容

**JSON 格式**：
```json
{
    "tool_name": "web_reader",
    "tool_call_id": "call_xxx",
    "arguments": {
        "url": "https://example.com/article",
        "response_format": "standard"
    }
}
```

**参数说明**：
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| url | string | 是 | - | 网页 URL |
| response_format | string | 否 | standard | 响应格式：brief/standard/full |

---

## 变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.7.0 | 2026-02-07 | 移除自动代码注入机制，改用模型主动调用 file_reader；添加文件读取后内容清理为梗概的机制 |
| v2.6.0 | 2026-02-07 | 补充完整工具参数 JSON 格式规范，包含参数表格和示例 |
| v2.5.0 | 2026-02-07 | 添加统一文件列表机制（代码+上传）、file_ref 标签处理、markdown 格式文件列表 |
| v2.4.0 | 2026-02-07 | 添加代码引用解析、多语言代码文件支持、可用代码列表机制；移除具体代码示例 |
| v2.3.0 | 2026-02-07 | 新增代码管理流程、后端日志系统；更新提示词来源 |
| v2.2.0 | 2026-02-07 | 重构响应格式：后端返回数据，前端渲染组件 |
| v2.1.0 | 2026-02-06 | 初始结构化响应格式 |
