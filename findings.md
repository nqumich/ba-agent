# BA-Agent 研究发现

> 本文件存储在开发过程中的重要发现和研究结果
> Manus 三文件模式之二

## LangChain 1.2.x API 变更

**发现日期**: 2025-02-04
**重要性**: ⚠️ 重要

### 问题描述
LangChain 1.2.x 有重大 API 变更，旧 API 不再可用。

### 旧 API (已弃用)
```python
# ❌ 不再可用
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import StructuredTool
```

### 新 API (推荐方式)
```python
# ✅ 推荐方式 (LangChain 1.2.8+)
from langchain.agents import create_agent
from langchain_core.tools import StructuredTool, tool
from langgraph.checkpoint.memory import MemorySaver

# 创建 Agent
memory = MemorySaver()
agent = create_agent(model, tools, checkpointer=memory)
```

### 影响
- 所有工具定义需要使用 `langchain_core.tools.StructuredTool`
- Agent 创建需要使用 `langchain.agents.create_agent`
- 需要安装完整的 `langchain` 包 (不只是 `langchain-core`)

---

## Python 3.14 ARM64 兼容性问题

**发现日期**: 2025-02-04
**重要性**: ⚠️ 重要

### 问题描述
Python 3.14 ARM64 暂不支持某些包。

### 受影响的包
- `chromadb`: 依赖 `onnxruntime`，暂不支持 ARM64

### 解决方案
- 使用 Python 3.12 (当前版本)
- 或等待上游支持

---

## MCP 工具集成

**发现日期**: 2025-02-04
**重要性**: ℹ️ 信息

### 可用的 MCP 工具
- `mcp__web-search-prime__webSearchPrime`: Web 搜索功能
- `mcp__web_reader__webReader`: 网页内容提取功能

### 集成方式
需要创建 LangChain 包装器来调用这些 MCP 工具。

---

## 三层记忆管理系统

**发现日期**: 2025-02-04
**重要性**: ✅ 核心设计

### 架构参考
- Clawdbot/Moltbot 的三层 Markdown 记忆
- Progressive Context Generation (渐进式解析)
- Manus AI 的三文件模式

### 三层定义

| 层级 | 文件 | 内容 | 持久性 |
|------|------|------|--------|
| Layer 1 | `memory/YYYY-MM-DD.md` | 日常笔记、临时讨论 | 每日 |
| Layer 2 | `MEMORY.md` | 长期知识、用户偏好、决策 | 永久 |
| Layer 3 | `CLAUDE.md`, `AGENTS.md` | 项目架构、系统指令 | 永久 |

### Manus 三文件模式

| 文件 | 用途 |
|------|------|
| `task_plan.md` | 跟踪阶段和进度 |
| `findings.md` | 存储研究和发现 |
| `progress.md` | 会话日志和测试结果 |

---

## 数据可视化方案

**发现日期**: 2025-02-04
**重要性**: ℹ️ 设计决策

### 选择
使用 **ECharts** (通过 Gemini 3 Pro 生成代码，前端渲染)

### 原因
- 交互性强
- 中文支持好
- 无需 Python 图表库 (避免渲染问题)
- 适合 Web 应用

### 实现方式
1. 用户请求可视化
2. Agent 调用 Gemini 3 Pro 生成 ECharts 代码
3. 系统校验代码语法和安全性
4. 返回 JSON 配置给前端渲染

---

## 待研究的问题

- [ ] Chroma 替代方案 (Python 3.14 ARM64)
- [ ] 记忆索引和检索的详细实现
- [ ] Hooks 系统的具体实现方式
- [ ] 向量数据库的替代方案

---

**最后更新**: 2025-02-04 15:30
