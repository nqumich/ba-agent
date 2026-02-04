# BA-Agent 长期记忆

> 本文件存储长期策划知识、用户偏好、重要决策
> Layer 2: Long-term Memory

## 用户偏好

*随着用户使用不断更新*

## 重要决策

### 2025-02-04: API 架构决策
- **选择**: LangGraph Agent + LangChain 1.2.8+
- **原因**: LangChain 1.2.x 弃用了旧 API，新架构更稳定
- **技术选型**:
  - Agent 创建: `langchain.agents.create_agent`
  - 工具定义: `langchain_core.tools.StructuredTool`
  - 记忆管理: `langgraph.checkpoint.memory.MemorySaver`

### 2025-02-04: MCP 工具集成
- **选择**: 使用 Z.ai 的 MCP 工具进行 Web 搜索和读取
- **工具**:
  - `mcp__web-search-prime__webSearchPrime`
  - `mcp__web_reader__webReader`

### 2025-02-04: 数据可视化方案
- **选择**: ECharts (通过 Gemini 3 Pro 生成代码)
- **原因**:
  - 交互性强
  - 中文支持好
  - 无需 Python 图表库 (避免渲染问题)

### 2025-02-04: Python 版本
- **当前**: Python 3.12 ARM64
- **限制**: Python 3.14 ARM64 暂不支持 chromadb

### 2025-02-05: 统一工具输出格式系统
- **选择**: 基于 Anthropic、Claude Code、Manus 等最佳实践实现的统一工具输出格式
- **核心组件**:
  - `models/tool_output.py`: ToolOutput, ToolTelemetry, ResponseFormat
  - `tools/base.py`: unified_tool 装饰器, ReActFormatter, TokenOptimizer
- **功能特性**:
  - **模型上下文传递**: summary, observation, result 三层结构
  - **工程遥测**: 延迟、Token 使用、错误追踪、缓存状态
  - **响应格式**: CONCISE/STANDARD/DETAILED/RAW 四种模式
  - **ReAct 兼容**: 标准 Observation 格式
  - **Token 优化**: 紧凑格式、YAML、XML
- **参考**: [工具输出格式设计文档](docs/tool-output-format-design.md)

### 2025-02-05: ReAct 输出格式规范
- **选择**: 在 AGENTS.md 中定义完整的 ReAct 输出格式规范
- **核心格式**: Thought → Action → Observation → Final Answer
- **关键特性**:
  - 与统一工具输出格式对齐
  - 明确的工具调用格式: `Action: <工具名称>[<参数1>=<值1>, ...]`
  - 标准化 Observation 格式: 包含 summary, observation, result
  - 完整的 Few-Shot 示例
- **版本**: AGENTS.md v2.0

## 项目里程碑

| 日期 | 里程碑 | 状态 |
|------|--------|------|
| 2025-02-04 | 项目初始化完成 | ✅ |
| 2025-02-04 | 依赖安装完成 | ✅ |
| 2025-02-04 | LangChain 1.2.x API 修复完成 | ✅ |
| 2025-02-05 | Phase 1 基础设施完成 (5/5) | ✅ |
| 2025-02-05 | Phase 2 核心工具部分完成 (5/8) | ✅ |
| 2025-02-05 | 统一工具输出格式系统完成 | ✅ |
| 2025-02-05 | ReAct 输出格式规范完成 | ✅ |
| 2025-02-05 | 278 个测试全部通过 | ✅ |
| - | SQL 查询工具 | ⏳ |
| - | 向量检索工具 | ⏳ |
| - | Skill 调用工具 | ⏳ |

## 经验教训

### LangChain API 迁移
**教训**: LangChain 1.2.x 有重大 API 变更
- ❌ 旧 API: `langchain.agents.AgentExecutor`
- ✅ 新 API: `langchain.agents.create_agent`
- **要点**: StructuredTool 从 `langchain.tools` 移至 `langchain_core.tools`

### Python 版本兼容性
**教训**: Python 3.14 ARM64 暂不支持某些包
- chromadb 依赖 onnxruntime，暂不支持 ARM64
- **方案**: 使用 Python 3.12 或等待上游支持

## 术语表

| 术语 | 解释 |
|------|------|
| GMV | Gross Merchandise Value，商品交易总额 |
| 异动检测 | 识别数据异常波动的技术 |
| 归因分析 | 分析业务指标变化驱动因素的方法 |
| MCP | Model Context Protocol，模型上下文协议 |
| Skill | 可配置的分析能力模块 |
| ReAct | Reasoning + Acting，Agent 思考与行动的循环模式 |
| ToolOutput | 统一工具输出格式，包含 summary, observation, result |
| ToolTelemetry | 工程遥测数据，包含延迟、Token、错误追踪 |
| ResponseFormat | 响应格式控制: CONCISE/STANDARD/DETAILED/RAW |

## 链接

- 项目进度: `scripts/ralph/progress.txt`
- 任务列表: `scripts/ralph/prd.json`
- 系统指令: `AGENTS.md`
- 用户信息: `USER.md`

---

**说明**: 本文件存储长期策划知识。日常笔记记录在 `memory/YYYY-MM-DD.md` 中。
