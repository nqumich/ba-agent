# BA-Agent 项目架构

> 本文件从用户视角描述 BA-Agent 的架构和能力
> Layer 3: Context Bootstrap

---

## 项目概述

BA-Agent (Business Analysis Agent) 是一个面向跨境电商企业的商业数据分析助手。

**目标用户**：业务分析师、运营人员、非技术背景的业务决策者

**核心价值**：通过自然语言对话完成数据异动检测、归因分析、报告生成、数据可视化

**当前版本**: v2.1.0 (Pipeline 完成)

---

## 开发进度

**总体进度**: ~70% (19/27 User Stories 完成)

**最新完成** (2026-02-06):
- ✅ Pipeline v2.1.0 完成 - 所有 8 个工具已迁移到 ToolExecutionResult
- ✅ Phase 7 完成 - 移除旧 ResponseFormat/ToolOutput 模型
- ✅ 746 个测试全部通过

**已完成的主要功能**:
- ✅ Agent 框架 (LangGraph + Claude Sonnet 4.5)
- ✅ 9 个核心工具 (命令行、Python、Web搜索、文件读写、数据库、向量检索等)
- ✅ Skills 配置系统 (支持 4 个内置 Skill)
- ✅ 三层记忆系统 (MemoryFlush + MemoryWatcher + 混合搜索)
- ✅ Pipeline v2.1.0 (Token计数、上下文管理、缓存、超时处理)
- ✅ MCP 集成 (Web搜索 + Web读取)

**待实现**:
- ⏳ 4 个 Skill 的核心业务逻辑
- ⏳ FastAPI 服务
- ⏳ IM Bot 集成
- ⏳ Excel 插件

---

## 核心功能

| 功能 | 说明 | 状态 |
|------|------|------|
| **异动检测** | 识别数据异常波动并解释原因 | 🔧 框架完成，逻辑待实现 |
| **归因分析** | 深入分析业务指标变化的驱动因素 | 🔧 框架完成，逻辑待实现 |
| **报告生成** | 自动生成日报、周报、月报 | 🔧 框架完成，逻辑待实现 |
| **数据可视化** | 创建清晰的图表展示数据趋势 | 🔧 框架完成，逻辑待实现 |

---

## 如何使用

### 常见问题示例

1. "今天的 GMV 怎么样？" → 实时数据查询
2. "为什么昨天 GMV 下降了？" → 异动检测 + 归因分析
3. "帮我生成本周的销售报告" → 报告生成
4. "把最近 30 天的趋势用图表展示" → 数据可视化

### 使用方式

- **开发模式**: Python API 直接调用
- **未来**: IM Bot (企业微信、钉钉)
- **未来**: Excel 插件 - 直接在 Excel 中分析数据
- **未来**: API - 集成到现有系统

---

## 数据要求

BA-Agent 可以分析以下类型的数据：

| 数据类型 | 格式 |
|----------|------|
| 销售数据 | CSV, Excel, 数据库 |
| 流量数据 | CSV, Excel, 数据库 |
| 广告数据 | CSV, Excel, 数据库 |

### 关键指标

系统可以分析以下核心指标：
- GMV（商品交易总额）
- 订单量、转化率
- AOV（平均订单金额）
- ROAS（广告回报率）

---

## 技术架构 v2.1.0

### 核心组件

| 组件 | 技术 | 说明 |
|------|------|------|
| Agent 框架 | LangGraph + Claude Sonnet 4.5 | 可扩展的 Agent 系统 |
| 工具框架 | LangChain Core | 结构化工具定义 |
| 输出格式 | Pipeline v2.1 ToolExecutionResult | OutputLevel (BRIEF/STANDARD/FULL) |
| 数据分析 | pandas, numpy, scipy | Docker 隔离的 Python 执行 |
| 容器隔离 | Docker | 安全的命令和代码执行 |
| 记忆管理 | 三层 Markdown | Clawdbot/Manus 模式 |
| MCP 集成 | Z.ai (智谱) | Web 搜索 + Web 读取 |
| LingYi AI | Claude/Gemini API | 自定义 API 端点支持 |

### Pipeline v2.1.0 特性

- **OutputLevel**: BRIEF/STANDARD/FULL 三级输出控制
- **ToolCachePolicy**: NO_CACHE/CACHEABLE/TTL_*/ETERNAL 缓存策略
- **DynamicTokenCounter**: 多模型 Token 计数
- **AdvancedContextManager**: 智能上下文压缩
- **IdempotencyCache**: 跨轮次语义缓存
- **ToolTimeoutHandler**: 同步超时控制
- **DataStorage**: 安全 artifact 存储

---

## 安全和隐私

- 所有代码执行在隔离环境中进行
- 数据只读访问，不修改业务数据
- 支持私有化部署

---

## 获取帮助

- 查看用户信息: `USER.md`
- 查看长期知识: `MEMORY.md`
- 查看详细指令: `AGENTS.md`
- 查看任务计划: `task_plan.md`
- 查看开发进度: `progress.md`

---

**最后更新**: 2026-02-06 (Pipeline v2.1.0 完成)
