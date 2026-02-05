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
- [x] **US-005**: Docker 隔离环境配置
  - [x] 创建 Dockerfile 用于 Python 沙盒容器
  - [x] 创建 docker-compose.yml 用于开发环境
  - [x] 配置 Docker 网络隔离
  - [x] 实现容器资源限制 (CPU/内存)
  - [x] 测试容器启动和代码执行

---

## 🔧 Phase 2: 核心工具 (Priority 2)

- [x] **US-006**: 命令行工具 (LangChain Tool)
  - [x] 创建 tools/execute_command.py
  - [x] 继承 StructuredTool from langchain_core.tools
  - [x] 实现 Docker 隔离的命令执行
  - [x] 支持命令白名单验证
  - [x] 添加 ExecuteCommandInput 模型
  - [x] 16 个单元测试全部通过
- [x] **US-007**: Python 沙盒工具 (LangChain Tool) - 核心
  - [x] 创建 tools/python_sandbox.py
  - [x] 实现 Docker 隔离的 Python 代码执行
  - [x] 实现 import 白名单验证
  - [x] 使用 AST 分析检测危险操作
  - [x] 添加 PythonCodeInput 模型
  - [x] 29 个单元测试全部通过
  - [x] 创建自定义 Docker 镜像包含数据分析库
- [x] **US-008**: Web 搜索工具 (MCP Tool Wrapper)
  - [x] 创建 tools/web_search.py
  - [x] 继承 StructuredTool from langchain_core.tools
  - [x] 实现 MCP 工具包装
  - [x] 支持 recency, max_results, domain_filter 参数
  - [x] 添加 WebSearchInput 模型
  - [x] 22 个单元测试全部通过 (2 skipped 需 MCP)
- [x] **US-009**: Web Reader 工具 (MCP Tool Wrapper)
  - [x] 创建 tools/web_reader.py
  - [x] 继承 StructuredTool from langchain_core.tools
  - [x] 实现 MCP 工具包装
  - [x] 支持多种返回格式: markdown, text
  - [x] 支持 retain_images 参数
  - [x] 添加 WebReaderInput 模型
  - [x] 27 个单元测试全部通过 (2 skipped 需 MCP)
- [x] **US-010**: 文件读取工具 (LangChain Tool)
  - [x] 创建 tools/file_reader.py
  - [x] 继承 StructuredTool from langchain_core.tools
  - [x] 支持 CSV/Excel/JSON/文本文件读取
  - [x] 实现路径安全检查 (allowed_paths 配置)
  - [x] 添加 FileReadInput 模型
  - [x] 61 个单元测试全部通过 (含 Python/SQL 支持)
- [x] **US-011**: SQL 查询工具 (LangChain Tool)
  - [x] 创建 tools/database.py
  - [x] 继承 StructuredTool from langchain_core.tools
  - [x] 实现 SQLAlchemy 集成架构
  - [x] 实现参数化查询支持（防止 SQL 注入）
  - [x] 支持多数据库连接配置
  - [x] 实现查询安全验证（禁止非只读操作）
  - [x] 添加 DatabaseQueryInput 模型
  - [x] 更新 config.py 支持多数据库连接和安全配置
  - [x] 54 个单元测试全部通过
- [x] **US-012**: 向量检索工具 (LangChain Tool)
  - [x] 创建 tools/vector_search.py
  - [x] 继承 StructuredTool from langchain_core.tools
  - [x] 实现 ChromaDB 集成（带内存回退方案）
  - [x] 实现指标/维度定义检索
  - [x] 实现文档向量化和存储（内存示例）
  - [x] 添加 VectorSearchInput 模型
  - [x] 支持元数据过滤（type, category）
  - [x] 51 个单元测试全部通过
- [x] **US-013**: Skill 调用工具 (LangChain Tool) - 核心
  - [x] 创建 tools/skill_invoker.py
  - [x] 继承 StructuredTool from langchain_core.tools
  - [x] 实现 invoke_skill 方法
  - [x] 实现与 run_python 工具的桥接（构建 Python 代码）
  - [x] 支持动态参数传递
  - [x] 添加 InvokeSkillInput 和 SkillConfig 模型
  - [x] 43 个单元测试全部通过
- [x] **US-014**: Skills 配置系统
  - [x] 创建 config/skills.yaml 配置文件
  - [x] 定义 Skills 注册格式（name, entrypoint, function, requirements, config）
  - [x] 实现 _load_skills_config 和 _get_skill_config
  - [x] 支持 4 个示例 Skill 配置
  - [x] 全局配置（timeout, memory, cache）

---

## 🧩 Phase 3: Skills 系统 (Priority 2)

- [x] **US-014**: Skills 配置系统
  - [x] 创建 config/skills.yaml 配置文件
  - [x] 定义 Skills 注册格式 (name, entrypoint, function, requirements, config)
  - [x] 创建 skills/ 配置加载器（内置）
  - [x] 实现 Skill 发现和验证
  - [x] 实现 Skill 参数解析
  - [x] 支持全局配置
- [x] **US-014-ARCH-01**: Skills 系统架构重构 (Anthropic Agent Skills)
  - [x] 创建 backend/skills/message_protocol.py (SkillMessage, ContextModifier, SkillActivationResult)
  - [x] 创建 backend/skills/skill_tool.py (Meta-Tool: activate_skill)
  - [x] 创建 backend/skills/loader.py (Level 1: Frontmatter 元数据)
  - [x] 创建 backend/skills/registry.py (技能注册缓存)
  - [x] 创建 backend/skills/activator.py (技能激活逻辑)
  - [x] 创建 backend/skills/formatter.py (SkillMessageFormatter)
  - [x] 创建 backend/skills/installer.py (外部技能安装)
  - [x] 三层渐进式披露: 元数据 → 完整 SKILL.md → 资源文件
  - [x] 语义匹配: Agent 通过 LLM 推理选择技能
  - [x] 消息注入: 激活后注入到对话上下文
  - [x] 132 个单元测试全部通过
- [x] **US-014-ARCH-02**: Context Modifier 完全实现
  - [x] _check_tool_allowed(): 检查工具权限
  - [x] _switch_model_for_skill(): 实际切换 LLM 模型
  - [x] _get_active_skill_model(): 获取当前技能模型
  - [x] _is_model_invocation_disabled(): 检查 LLM 调用禁用
  - [x] _apply_context_modifier(): 总是设置 current_skill
  - [x] 5 个 Context Modifier 应用测试全部通过
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
- [x] **实现双记忆系统架构 (2026-02-05)**
  - [x] 分离开发记忆 (~/.ba-agent-dev/) 和用户记忆 (memory/)
  - [x] 创建 SOUL.md - Agent 身份定义
  - [x] 创建 bank/ - 结构化知识库 (world/experience/opinions)
  - [x] 更新 AGENTS.md - 移除开发引用
  - [x] 精简 CLAUDE.md - 用户视角
  - [x] 重写 MEMORY.md - 仅用户知识
  - [x] 迁移开发日志到 ~/.ba-agent-dev/daily-notes/
- [ ] **实现记忆管理工具**
  - [ ] memory_search - 语义搜索用户记忆
  - [x] memory_get - 读取特定内存文件 ✅ (13 测试通过)
  - [ ] memory_write - 写入记忆 (自动选择层级)
- [x] **实现 Hooks 系统**
  - [x] PreToolUse: 统一安全检查 (check-security.sh)
  - [x] PostToolUse: 日志记录 + 输出总结 (log-and-summarize.sh)
  - [x] PostToolUse: 每 N 次操作后提示保存发现 (prompt-save-finding.sh)
  - [x] PostToolUse: Skill 进度更新 (session-manager.sh)
  - [x] Stop: 会话摘要 + 完成度检查 (session-manager.sh)
  - [x] UserPromptSubmit: 输入验证 (validate-input.sh)
  - [x] Hooks 优化: 11个脚本精简至5个 (-54%)

---

## 📊 进度统计

- **总任务数**: 29 (新增 US-014-ARCH-01, US-014-ARCH-02)
- **已完成**: 19 (65.5%)
  - Phase 1: 5/5 (100%)
  - Phase 2: 9/9 (100%) ✅
  - Phase 3: 3/4 (75%) ✅ 新增
  - Phase 4: 0/7 (0%)
  - 基础设施: 1/1 (100%)
  - 记忆管理: 2/2 (100%) ✅
- **进行中**: 1 (3.4%) - US-INFRA-02: 信息管道设计
- **待开始**: 9 (31.0%)

**已完成的 User Story**:
- ✅ US-001: 项目初始化与目录结构创建
- ✅ US-002: 核心数据模型定义 (Pydantic)
- ✅ US-003: 配置管理系统
- ✅ US-004: LangGraph Agent 基础框架
- ✅ US-005: Docker 隔离环境配置
- ✅ US-006: 命令行工具 (16 测试通过)
- ✅ US-007: Python 沙盒工具 (29 测试通过)
- ✅ US-008: Web 搜索工具 (22 测试通过)
- ✅ US-009: Web Reader 工具 (27 测试通过)
- ✅ US-010: 文件读取工具 (61 测试通过，含 Python/SQL 支持)
- ✅ US-011: SQL 查询工具 (54 测试通过)
- ✅ US-012: 向量检索工具 (51 测试通过)
- ✅ US-013: Skill 调用工具 (43 测试通过)
- ✅ US-014: Skills 配置系统
- ✅ US-014-ARCH-01: Skills 系统架构重构 (Anthropic Agent Skills, 132 测试通过)
- ✅ US-014-ARCH-02: Context Modifier 完全实现 (5 测试通过)
- ✅ US-005-MEM-01: 三层记忆文件结构
- ✅ US-005-MEM-02: Hooks 系统实现与优化 (5个脚本，-54%)
- ✅ US-INFRA-01: 统一工具输出格式系统 (42 测试通过)

**测试统计**: 631 passed, 6 skipped (+132 Skills, +5 Context Modifier, +13 memory_get, +42 ToolOutput)

**下一任务**: US-015 - 示例 Skill: 异动检测

---

## 🎁 额外完成的功能

### Claude Hooks 系统优化 (US-005-MEM-02, 2025-02-05)

基于最佳实践实现的 Claude Code Hooks 系统：

**核心文件**:
- `.claude/hooks/check-security.sh` - 统一安全检查 (PreToolUse)
- `.claude/hooks/log-and-summarize.sh` - 日志记录 + 输出总结 (PostToolUse)
- `.claude/hooks/session-manager.sh` - 会话管理 + 完成度检查 (PostToolUse + Stop)
- `.claude/hooks/prompt-save-finding.sh` - 保存提示 (每5次)
- `.claude/hooks/validate-input.sh` - 输入验证 (UserPromptSubmit)
- `.claude/hooks.json` - Hooks 配置

**功能特性**:
1. **PreToolUse 安全检查**: 命令白名单、SQL 注入检测、Skill 安装验证
2. **PostToolUse 活动记录**: 记录所有 9 个工具活动到 progress.md
3. **PostToolUse 智能总结**: 根据工具类型生成简洁摘要
4. **Stop 会话管理**: 保存会话摘要到 memory/、检查任务完成度
5. **输入验证**: 提示长度限制

**优化收益**:
- 脚本数量: 11 → 5 (-54%)
- 总行数: ~250 → ~160 (-36%)
- case 分支: 18 → 9 (-50%)

### 统一工具输出格式系统 (US-INFRA-01, 2025-02-05)

基于 Anthropic、Claude Code、Manus 等 Agent 产品的最佳实践，实现了统一的工具输出格式：

**核心文件**:
- `models/tool_output.py` - ToolOutput, ToolTelemetry 模型
- `tools/base.py` - unified_tool 装饰器，ReActFormatter
- `docs/tool-output-format-design.md` - 设计文档
- `tests/models/test_tool_output.py` - 42 个测试通过

**功能特性**:
1. **模型上下文传递**: summary, observation, result
2. **工程遥测**: 延迟、Token 使用、错误追踪、缓存状态
3. **响应格式控制**: CONCISE/STANDARD/DETAILED/RAW
4. **ReAct 兼容**: 标准 Observation 格式
5. **Token 优化**: 紧凑格式、YAML、XML
6. **遥测收集**: TelemetryCollector 单例

### Skills 系统架构重构 (US-014-ARCH-01/02, 2026-02-05)

基于 Anthropic Agent Skills 规范的 Meta-Tool 架构：

**核心文件**:
- `backend/skills/message_protocol.py` - SkillMessage, ContextModifier, SkillActivationResult
- `backend/skills/skill_tool.py` - Meta-Tool 实现 (activate_skill)
- `backend/skills/loader.py` - SkillLoader (渐进式披露 Level 1)
- `backend/skills/registry.py` - SkillRegistry (缓存)
- `backend/skills/activator.py` - SkillActivator (激活逻辑)
- `backend/skills/formatter.py` - SkillMessageFormatter
- `backend/skills/installer.py` - SkillInstaller (外部技能)
- `docs/skill-system-redesign.md` - 设计文档
- `docs/skill-implementation-compatibility-report.md` - 兼容性报告
- `backend/agents/agent.py` - BAAgent 集成

**功能特性**:
1. **Meta-Tool 模式**: 单一 activate_skill 工具包装所有技能
2. **三层渐进式披露**:
   - Level 1: Frontmatter 元数据 (~100 tokens/skill) - 启动时加载
   - Level 2: 完整 SKILL.md (<5,000 tokens) - 激活时加载
   - Level 3: 资源文件 (scripts/, references/, assets/) - 按需加载
3. **语义匹配**: Agent 使用 LLM 推理自主选择技能
4. **消息注入**: 激活后注入消息到对话上下文
5. **Context Modifier**: allowed_tools, model, disable_model_invocation
6. **完全兼容 Claude Code**: 相同的 SKILL.md 格式和架构

**测试覆盖**: 137 个 Skills 相关测试全部通过

### 信息管道设计 v1.4 (US-INFRA-02, 2026-02-05) - 概念修正

基于 Claude Code 和 Manus AI 的实际实现，修正了之前设计中三个概念混淆的问题：

**核心概念修正**:

1. **ReAct Pattern** - Agent 执行循环，不是工具输出格式
   ```
   Thought: 我需要搜索天气信息
   Action: call web_search("扬州天气")
   Observation: [工具执行结果 - 纯字符串]
   ```
   - 这是控制流程模式，不是数据格式
   - Agent 通过此模式进行推理

2. **Tool Output Format** - 简单的 observation 字符串
   ```json
   {
     "role": "user",
     "content": [{
       "type": "tool_result",
       "tool_use_id": "call_xxx",
       "content": "扬州今天晴天，25°C"
     }]
   }
   ```
   - 移除了错误的 summary/observation/result 三层结构
   - 匹配 Claude Code 的直接、简单方法
   - 工具结果作为 `role: "user"` 消息发送

3. **Progressive Disclosure** - 仅用于 Skills 系统
   - Level 1: Frontmatter (~100 tokens) - 启动时加载所有技能元数据
   - Level 2: Full SKILL.md (~5000 tokens) - 激活时加载完整指令
   - Level 3: 资源文件 - 按需加载 scripts/references/assets

**设计文件**: `docs/information-pipeline-design.md` v1.4

**关键变更**:
- 添加了 "Core Concepts Clarification" 章节
- 简化了 `ToolExecutionResult` 为单个 `observation` 字段
- 移除了错误的三层结构引用
- 更新了所有序列图和代码示例
- 添加了详细的 ReAct 附录说明

**学习要点**:
- ReAct = 控制流程 (Agent 如何推理)
- Tool Output = 数据格式 (工具如何返回数据)
- Progressive Disclosure = 信息呈现策略 (Skills 如何加载)
- 这三个是独立概念，不应混淆

---

**最后更新**: 2026-02-05 信息管道设计 v1.4 (概念修正)
