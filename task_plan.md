# BA-Agent 任务计划

> 本文件跟踪 BA-Agent 的开发阶段和进度
> Manus 三文件模式之一

## 📋 总体目标

构建一个完整的商业分析助手 Agent，具备异动检测、归因分析、报告生成、数据可视化能力。

---

## 🎯 Phase 1: 基础设施 (Priority 1)

- [x] **US-001**: 项目初始化与目录结构创建
- [x] **US-002**: 核心数据模型定义 (Pydantic)
  - [x] 创建 models/ 目录
  - [x] 定义 Query 和 QueryResult 模型
  - [x] 定义 ToolInput 和 ToolOutput 模型
  - [x] 定义 SkillConfig 和 SkillResult 模型
  - [x] 定义 Anomaly, Attribution, Report, ChartConfig 等业务模型
  - [x] 添加类型验证和序列化测试
- [x] **US-003**: 配置管理系统
  - [x] 创建 config/config.py 配置加载类
  - [x] 创建 config/settings.yaml 配置文件模板
  - [x] 支持环境变量覆盖配置
  - [x] 实现密钥管理 (API keys 等)
  - [x] 创建 config.py 单元测试
- [x] **US-004**: LangGraph Agent 基础框架
  - [x] 创建 backend/agents/agent.py 主 Agent 类
  - [x] 初始化 ChatAnthropic (Claude 3.5 Sonnet)
  - [x] 创建 Agent prompt template (system message 定义)
  - [x] 实现 AgentExecutor: 使用 langgraph.prebuilt.create_react_agent
  - [x] 添加 MemorySaver checkpointer 支持对话历史
  - [x] 添加基础测试验证 Agent 可正常响应
- [ ] **US-005**: Docker 隔离环境配置
  - [ ] 创建 Dockerfile 用于 Python 沙盒容器
  - [ ] 创建 docker-compose.yml 用于开发环境
  - [ ] 配置 Docker 网络隔离
  - [ ] 实现容器资源限制 (CPU/内存)
  - [ ] 测试容器启动和代码执行

---

## 🔧 Phase 2: 核心工具 (Priority 2)

- [ ] **US-006**: 命令行工具 (LangChain Tool)
- [ ] **US-007**: Python 沙盒工具 (LangChain Tool) - 核心
- [ ] **US-008**: Web 搜索工具 (MCP Tool Wrapper)
- [ ] **US-009**: Web Reader 工具 (MCP Tool Wrapper)
- [ ] **US-010**: 文件读取工具 (LangChain Tool)
- [ ] **US-011**: SQL 查询工具 (LangChain Tool)
- [ ] **US-012**: 向量检索工具 (LangChain Tool)
- [ ] **US-013**: Skill 调用工具 (LangChain Tool) - 核心

---

## 🧩 Phase 3: Skills 系统 (Priority 2)

- [ ] **US-014**: Skills 配置系统
- [ ] **US-015**: 示例 Skill - 异动检测
- [ ] **US-016**: 示例 Skill - 归因分析
- [ ] **US-017**: 示例 Skill - 报告生成
- [ ] **US-018**: 示例 Skill - 数据可视化

---

## 🔌 Phase 4: 集成与部署 (Priority 3-4)

- [ ] **US-019**: Agent System Prompt 与工具集成
- [ ] **US-020**: 知识库初始化
- [ ] **US-021**: API 服务实现 (FastAPI)
- [ ] **US-022**: IM Bot 集成 (企业微信/钉钉)
- [ ] **US-023**: Excel 插件
- [ ] **US-024**: 日志与监控系统
- [ ] **US-025**: 单元测试与覆盖率
- [ ] **US-026**: 文档完善

---

## 📝 记忆管理任务 (新增)

- [x] **创建三层记忆文件结构**
  - [x] CLAUDE.md - 项目级记忆
  - [x] AGENTS.md - Agent 系统指令
  - [x] USER.md - 用户信息
  - [x] MEMORY.md - 长期策划知识
  - [x] memory/YYYY-MM-DD.md - 每日日志
- [ ] **实现记忆管理工具**
  - [ ] memory_search - 语义搜索 MEMORY.md + memory/*.md
  - [ ] memory_get - 读取特定内存文件
  - [ ] memory_write - 写入记忆 (自动选择 Layer 1 或 Layer 2)
- [ ] **实现 Hooks 系统**
  - [ ] PreToolUse: 使用工具前重新读取计划
  - [ ] PostToolUse: 每 N 次操作后提示保存发现
  - [ ] Stop: 验证完成状态

---

## 📊 进度统计

- **总任务数**: 26
- **已完成**: 5 (19.2%)
- **进行中**: 0 (0%)
- **待开始**: 21 (80.8%)

---

**最后更新**: 2025-02-04 23:45
