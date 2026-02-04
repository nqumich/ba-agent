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

## 项目里程碑

| 日期 | 里程碑 | 状态 |
|------|--------|------|
| 2025-02-04 | 项目初始化完成 | ✅ |
| 2025-02-04 | 依赖安装完成 | ✅ |
| 2025-02-04 | LangChain 1.2.x API 修复完成 | ✅ |
| - | 核心数据模型定义 | ⏳ |
| - | LangGraph Agent 框架 | ⏳ |

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

## 链接

- 项目进度: `scripts/ralph/progress.txt`
- 任务列表: `scripts/ralph/prd.json`
- 系统指令: `AGENTS.md`
- 用户信息: `USER.md`

---

**说明**: 本文件存储长期策划知识。日常笔记记录在 `memory/YYYY-MM-DD.md` 中。
