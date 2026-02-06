# BA-Agent 项目目录结构说明

> 本文档详细说明 BA-Agent 项目的目录结构和各组件的用途
> 更新时间: 2026-02-06

## 整体进度

- **Phase 1**: Agent Framework ✅ 100% 完成
- **Phase 2**: Tooling Layer ✅ 100% 完成 (14 工具，764 测试)
- **Phase 3**: Business Skills 🔄 25% 完成 (结构完整，逻辑待实现)
- **Phase 4**: API Layer ❌ 未开始
- **Phase 5**: Delivery Channels ❌ 未开始

**总体进度**: ~50%

## 目录概览

```
ba-agent/
├── backend/          # 后端核心模块
│   ├── agents/       # Agent 实现 (含 MemoryFlush/Compaction)
│   ├── memory/       # 三层记忆系统 (Flush/Search/Watcher)
│   ├── models/       # Pydantic 数据模型
│   ├── docker/       # Docker 沙盒
│   ├── hooks/        # 系统钩子
│   └── orchestration/ # 任务编排
├── tools/            # LangChain 工具集合 (14个)
├── skills/           # Skills 实现 (4个内置，结构完整)
├── config/           # 配置管理系统
├── tests/            # 测试套件 (764个测试)
├── memory/           # 每日对话日志 (Layer 1)
├── docs/             # 项目文档
├── scripts/          # 工具脚本
├── AGENTS.md         # Agent 系统指令
├── CLAUDE.md         # 项目级记忆 (Layer 3)
├── MEMORY.md         # 长期知识记忆 (Layer 2)
├── USER.md           # 用户信息
├── README.md         # 项目概述
├── progress.md       # 开发进度
├── task_plan.md      # 任务计划
└── [配置文件]        # 各种配置文件
```

## 1. backend/ - 后端核心模块

后端核心代码，包含 Agent 实现、Memory 系统、Docker 集成、数据模型、Pipeline 组件等。

### 1.1 backend/agents/ - Agent 实现

```
agents/
├── __init__.py
└── agent.py              # BAAgent 主实现
                            - ChatAnthropic 初始化
                            - LangGraph AgentExecutor
                            - MemorySaver 对话历史
                            - MemoryFlush (Clawdbot 风格)
                            - Conversation Compaction
                            - v2.1: Pipeline 集成
```

**关键功能**:
- 使用 `langchain.agents.create_agent` (LangGraph V2.0 API)
- 集成 Claude Sonnet 4.5 模型
- 支持自定义 API 端点 (LingYi AI)
- 支持工具调用和记忆管理
- **MemoryFlush**: 基于 token 阈值的自动记忆提取和卸载
- **Compaction**: MemoryFlush 后自动压缩对话上下文
- **默认工具**: 10个默认工具自动加载（含 memory_search_v2_tool）

**v2.1.0 Pipeline 集成**:
- `token_counter`: DynamicTokenCounter - 多模型 Token 计数
- `context_manager`: AdvancedContextManager - 智能上下文压缩
- `_get_total_tokens()`: 使用 DynamicTokenCounter 精确计数
- `_compact_conversation()`: 使用 AdvancedContextManager 优先级过滤
- `_check_and_flush()`: 双组件协同工作

### 1.2 backend/memory/ - 三层记忆系统

```
memory/
├── __init__.py
├── flush.py              # MemoryFlush - Clawdbot 风格记忆提取
├── index.py              # MemoryWatcher - 文件监听和索引
├── search.py             # MemorySearch - FTS5 + 向量混合搜索
├── embedding.py          # EmbeddingProvider - 多源 Embedding
├── database.py           # SQLite FTS5 索引管理
└── tools/                # Memory 工具（系统内部，不暴露给 Agent）
    ├── __init__.py
    ├── memory_write.py    # 记忆写入（自动层级选择）
    ├── memory_get.py     # 记忆文件读取
    ├── memory_retain.py  # LLM 记忆提取 (W/B/O 格式)
    ├── memory_search.py  # 旧版记忆搜索
    └── memory_search_v2.py # FTS5 + 向量混合搜索
```

**关键功能**:
- **MemoryFlush**: 无声回复模式，自动提取结构化记忆
- **MemoryWatcher**: 文件变更监听，自动更新索引
- **MemorySearch**: BM25 + Cosine 混合搜索
- **EmbeddingProvider**: OpenAI/Zhipuai/Local 三重回退机制
- **Memory Tools**: 系统内部工具，仅供 MemoryFlush/MemoryWatcher 使用

### 1.3 backend/docker/ - Docker 沙盒

```
docker/
├── __init__.py
└── sandbox.py            # DockerSandbox 沙盒执行器
                            - 命令执行隔离
                            - Python 代码执行隔离
                            - 资源限制（CPU/内存）
```

**安全特性**:
- 独立 bridge 网络隔离
- CPU quota 和内存限制
- 超时控制

### 1.4 backend/pipeline/ - Pipeline 组件 (v2.1.0)

```
pipeline/
├── __init__.py             # Pipeline 统一导出
├── timeout/                # 超时处理
│   └── __init__.py         # ToolTimeoutHandler（同步）
├── storage/                # 数据存储
│   └── __init__.py         # DataStorage（artifact 存储）
├── wrapper.py              # PipelineToolWrapper（LangChain 集成）
├── cache/                  # 幂等性缓存
│   └── idempotency_cache.py  # IdempotencyCache（跨轮次缓存）
├── token/                  # Token 计数
│   └── token_counter.py    # DynamicTokenCounter（多模型支持）
└── context/                # 上下文管理
    └── context_manager.py  # AdvancedContextManager（智能压缩）
```

**Pipeline 核心模型** (backend/models/pipeline/):
```
models/pipeline/
├── __init__.py
├── output_level.py         # OutputLevel (BRIEF/STANDARD/FULL)
├── cache_policy.py         # ToolCachePolicy (NO_CACHE/CACHEABLE/TTL_*)
├── tool_result.py          # ToolExecutionResult（单一源模型）
└── tool_request.py         # ToolInvocationRequest（工具调用请求）
```

**v2.1.0 特性**:

| 组件 | 功能 | 优势 |
|------|------|------|
| **DynamicTokenCounter** | 多模型 Token 计数 | OpenAI tiktoken、Anthropic、fallback |
| **AdvancedContextManager** | 智能上下文压缩 | 优先级过滤（EXTRACT）+ LLM 摘要（SUMMARIZE） |
| **IdempotencyCache** | 跨轮次缓存 | 语义键（排除 tool_call_id） |
| **DataStorage** | Artifact 存储 | 安全 ID 替代真实路径 |
| **ToolTimeoutHandler** | 同步超时 | 线程池（非 asyncio） |

### 1.5 backend/hooks/ - 系统钩子

```
hooks/
├── __init__.py
└── hook_manager.py       # 钩子管理器
                            - 事件订阅/发布
                            - 生命周期钩子
```

### 1.5 backend/orchestration/ - 任务编排

```
orchestration/
├── __init__.py
├── focus_manager.py      # 焦点管理器
└── tool_orchestrator.py  # 工具编排器
```

### 1.6 backend/models/ - 数据模型（统一位置）

**重要**: 所有 Pydantic 数据模型统一放在此目录。

```
models/
├── __init__.py            # 统一导出所有模型
├── agent.py               # Agent 相关模型
├── analysis.py            # 分析结果模型
├── base.py                # 基础模型（Mixin）
├── memory.py              # 记忆模型
├── query.py               # 查询相关模型
├── report.py              # 报告模型
├── skill.py               # Skill 相关模型
├── tool.py                # 工具调用模型
├── tool_output.py         # 工具输出格式模型（v2.0.0）
│                           - ToolOutput
│                           - ToolTelemetry
│                           - ResponseFormat
└── pipeline/              # Pipeline 模型（v2.1.0）
    ├── __init__.py
    ├── output_level.py    # OutputLevel (BRIEF/STANDARD/FULL)
    ├── cache_policy.py    # ToolCachePolicy (NO_CACHE/CACHEABLE/TTL_*)
    ├── tool_result.py     # ToolExecutionResult（单一源模型）
    └── tool_request.py    # ToolInvocationRequest（工具调用请求）
```

**导入方式**:
```python
# 正确 ✅
from backend.models.tool_output import ToolOutput, ToolTelemetry
from backend.models.agent import BAAgentConfig, AgentState

# 错误 ❌ (顶层 models/ 已移除)
from models.tool_output import ToolOutput
```

## 2. tools/ - Agent 工具集合

所有 LangChain StructuredTool 实现，每个工具一个文件。
**注意**: 这些是主 Agent 可用的业务工具。Memory 相关的系统内部工具已移至 `backend/memory/tools/`。

### 工具列表

| 文件 | 工具名 | 说明 | 测试 |
|------|--------|------|------|
| base.py | unified_tool | 统一工具输出格式装饰器 | 42 tests ✅ |
| execute_command.py | execute_command | Docker 隔离命令行执行 | 16 tests ✅ |
| python_sandbox.py | run_python | Docker 隔离 Python 执行 | 29 tests ✅ |
| web_search.py | web_search | Web 搜索 (Z.ai MCP) | 22 tests ✅ |
| web_reader.py | web_reader | Web 读取 (Z.ai MCP) | 27 tests ✅ |
| file_reader.py | file_reader | 多格式文件读取 | 61 tests ✅ |
| file_write.py | file_write | 通用文件写入 (append/overwrite/prepend) | 14 tests ✅ |
| database.py | query_database | SQL 查询 | 54 tests ✅ |
| vector_search.py | search_knowledge | 向量检索 | 51 tests ✅ |
| skill_invoker.py | invoke_skill | Skill 调用 | 43 tests ✅ |
| skill_manager.py | skill_package | Skill 包管理 | 43 tests ✅ |

### 工具开发规范

1. **继承 StructuredTool**: 所有工具继承自 `langchain_core.tools.StructuredTool`
2. **统一输出格式**: 使用 `@unified_tool` 装饰器
3. **输入验证**: 使用 Pydantic BaseModel 定义输入参数
4. **遥测收集**: 自动收集延迟、Token 使用、错误信息

## 3. skills/ - Skills 实现

可复用的分析能力模块。**注意**: 当前结构已完整，但各 Skill 的核心业务逻辑为待实现的 stub。

### 目录结构

```
skills/
├── __init__.py             # Skills 包初始化
├── anomaly_detection/      # 异动检测 Skill
│   ├── __init__.py
│   ├── SKILL.md           # YAML frontmatter + 文档
│   └── main.py            # 入口函数: detect()
├── attribution/            # 归因分析 Skill
│   ├── __init__.py
│   ├── SKILL.md
│   └── main.py            # 入口函数: analyze()
├── report_gen/             # 报告生成 Skill
│   ├── __init__.py
│   ├── SKILL.md
│   └── main.py            # 入口函数: generate()
└── visualization/          # 数据可视化 Skill
    ├── __init__.py
    ├── SKILL.md
    └── main.py            # 入口函数: create_chart()
```

### SKILL.md 格式

每个 Skill 必须包含 SKILL.md 文件，格式如下：

```yaml
---
name: skill_name
display_name: "显示名称"
description: "描述"
version: "1.0.0"
category: "Analysis|Reporting|Visualization"
author: "作者"
entrypoint: "skills/skill_name/main.py"
function: "main_function"
requirements:
  - "pandas"
  - "numpy"
config:
  param1: value1
tags:
  - "tag1"
  - "tag2"
examples:
  - "示例问题1"
  - "示例问题2"
---

# Skill 文档内容
```

## 4. config/ - 配置管理系统

### 配置文件

```
config/
├── __init__.py             # 配置包初始化
├── config.py               # 配置管理核心类
├── settings.yaml           # 主配置文件
├── skills.yaml             # Skills 运行时配置
└── tools.yaml              # 工具配置
```

**注意**: `skills_registry.json` 目前缺失，需要创建以跟踪已安装 Skills 的元数据。

### settings.yaml - 主配置

包含以下配置：
- **数据库**: PostgreSQL, ClickHouse 连接
- **LLM**: Claude/Gemini 配置 (支持 LingYi AI 代理)
- **向量数据库**: ChromaDB 配置
- **Docker**: 镜像、网络、资源限制
- **记忆**: 三层记忆系统配置
  - `memory.flush.enabled`: MemoryFlush 开关
  - `memory.flush.soft_threshold_tokens`: 软阈值 token 数
  - `memory.flush.compaction_keep_recent`: 压缩对话时保留最近的消息数量
  - `memory.search.hybrid.enabled`: 混合搜索开关
  - `memory.watcher.enabled`: 文件监听开关
- **安全**: SQL 安全策略

支持环境变量覆盖：
```bash
export BA_DATABASE__HOST=localhost
export BA_LLM__API_KEY=sk-xxx
```

## 5. tests/ - 测试套件

### 测试目录结构

```
tests/
├── __init__.py
├── conftest.py              # pytest 全局配置
├── backend/                 # 后端测试
│   ├── test_flush.py        # MemoryFlush 测试
│   └── test_memory_flush_integration.py
├── models/                  # 模型测试
│   ├── __init__.py
│   ├── test_models.py       # 所有模型测试
│   └── test_tool_output.py  # 工具输出格式测试
├── test_agents/             # Agent 测试
│   └── test_agent.py
├── test_config/             # 配置测试
│   └── test_config.py
├── test_docker/             # Docker 测试
│   └── test_sandbox.py
├── mcp_server/              # MCP 测试服务器
│   └── server.py
└── tools/                   # 工具测试
    ├── conftest.py
    ├── test_database.py
    ├── test_execute_command.py
    ├── test_file_reader.py
    ├── test_file_write.py
    ├── test_memory_get.py
    ├── test_memory_retain.py
    ├── test_memory_search_v2.py
    ├── test_memory_write.py
    ├── test_python_sandbox.py
    ├── test_skill_invoker.py
    ├── test_skill_manager.py
    ├── test_vector_search.py
    ├── test_web_reader.py
    ├── test_web_reader_integration.py
    ├── test_web_search.py
    └── test_web_search_integration.py
```

### 测试统计

- **总计**: 746 个测试
- **通过**: 746 (100%)
- **跳过**: 1

**v2.1.0 测试更新**:
- Phase 1-5 (Pipeline): 42 tests passing
- 工具测试: 303 tests passing
- Skills 系统: 137 tests passing
- Memory 系统: 120 tests passing
- Agent 集成: 100 tests passing
- MCP 集成: 9 tests passing (需要 MCP_AVAILABLE=true)
- 其他: 35 tests passing

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/tools/test_skill_manager.py
pytest tests/test_agents/

# 运行 MCP 集成测试
MCP_AVAILABLE=true pytest tests/tools/test_web_search_integration.py
MCP_AVAILABLE=true pytest tests/tools/test_web_reader_integration.py

# 查看覆盖率
pytest --cov=backend --cov=tools --cov-report=html
```

## 6. 三层记忆系统

采用 Clawdbot/Manus 模式的三层记忆架构，结合了 MemoryFlush、MemoryWatcher 和混合搜索。

### 实际文件组织

**每日对话日志** (memory/ 目录):
```
memory/
├── 2025-02-04.md          # Layer 1: 每日对话日志
└── memory_index.db        # SQLite FTS5 索引
```

**核心记忆文件** (根目录):
```
根目录/
├── AGENTS.md              # Agent 系统指令和记忆指南
├── CLAUDE.md              # Layer 3: 项目级记忆（Context Bootstrap）
├── MEMORY.md              # Layer 2: 长期知识记忆
└── USER.md                # 用户信息
```

### 记忆层级说明

| Layer | 文件位置 | 用途 | 内容 |
|-------|----------|------|------|
| **Layer 1** | `memory/YYYY-MM-DD.md` | 每日对话日志 | 日常笔记、临时讨论、当天上下文 |
| **Layer 2** | 根目录 `MEMORY.md` | 长期知识记忆 | 持久事实、决策、用户偏好 |
| **Layer 3** | 根目录 `CLAUDE.md` | 项目级记忆 | 项目结构、技术架构、重要里程碑 |

### 写入规则

| 触发条件 | 目标位置 | 示例 |
|----------|----------|------|
| 日常笔记、临时讨论 | `memory/YYYY-MM-DD.md` | "讨论了 API 设计" |
| 持久事实、决策 | `MEMORY.md` (根目录) | "用户偏好 TypeScript" |
| 重要里程碑 | `CLAUDE.md` (根目录) | "完成 API 重构" |

### 使用方式

Agent 可以通过以下工具管理记忆：
- **memory_search_v2**: FTS5 + 向量混合搜索 MEMORY.md + memory/*.md
- **memory_get**: 读取特定内存文件
- **memory_write**: 写入记忆（自动选择 Layer 1 或 Layer 2）
- **memory_retain**: LLM 提取结构化记忆 (W/B/O(c=)/S 格式)

### 核心特性

#### MemoryFlush (Clawdbot 风格)
- **触发条件**: `contextTokens > contextWindow - reserveTokens - softThreshold`
- **提取方式**: LLM 静默提取，返回 `_SILENT_` 标记
- **后续动作**: 自动压缩对话上下文 (保留最近 N 条消息)
- **存储位置**: 自动选择 Layer 1 (临时) 或 Layer 2 (持久)

#### MemoryWatcher
- **功能**: 监听 memory/ 目录文件变更
- **自动索引**: 文件变更时自动更新 FTS5 索引
- **状态**: 默认禁用 (避免资源占用)

#### MemorySearch (混合搜索)
- **FTS5 全文搜索**: BM25 算法
- **向量搜索**: Cosine 相似度
- **权重**: 70% 向量 + 30% 文本
- **最小分数**: 0.35

## 7. docs/ - 项目文档

```
docs/
├── PRD.md                              # 产品需求文档（产品视角）
├── project-structure.md                # 本文档 - 项目目录结构和技术架构
├── excel-upload-flow-design.md         # Excel上传流程设计
├── information-pipeline-design.md      # Pipeline 设计文档（简化版）
├── information-pipeline-design-detailed.md  # Pipeline 设计文档（详细版）
├── MIGRATION_GUIDE.md                  # v2.0.0 → v2.1.0 迁移指南
├── context-manager-guide.md            # Context Manager 使用指南
├── tool-output-format-design.md        # 工具输出格式设计
├── mcp-setup.md                        # MCP 服务器配置
└── memory-flush-redesign.md            # MemoryFlush 重设计文档
```

**v2.1.0 新增文档**:
- `excel-upload-flow-design.md`: Excel上传处理流程设计（FastAPI + Agent）
- `information-pipeline-design-detailed.md`: 完整的 Pipeline v2.1.0 设计文档
- `information-pipeline-design.md`: 简化版 Pipeline 设计
- `MIGRATION_GUIDE.md`: 非破坏性升级指南

**2026-02-06 更新**:
- `PRD.md`: 重写为产品导向文档，用户视角
- `project-structure.md`: 更新 LangGraph API 迁移状态

### 其他重要文档

```
根目录:
├── README.md           # 项目概述和快速开始
├── progress.md         # 开发进度和测试结果
├── task_plan.md        # 任务计划和 User Stories
├── findings.md         # 技术研究发现
├── AGENTS.md           # Agent 系统指令和记忆指南
├── CLAUDE.md           # 项目级记忆 (Layer 3: Context Bootstrap)
├── MEMORY.md           # 长期知识记忆 (Layer 2)
└── USER.md             # 用户信息
```

### 三层记忆系统文件说明

| 文件 | 位置 | 层级 | 用途 |
|------|------|------|------|
| `memory/YYYY-MM-DD.md` | memory/ 目录 | Layer 1 | 每日对话日志 |
| `MEMORY.md` | 根目录 | Layer 2 | 长期知识记忆 |
| `CLAUDE.md` | 根目录 | Layer 3 | 项目级记忆 |
| `AGENTS.md` | 根目录 | - | Agent 系统指令 |
| `USER.md` | 根目录 | - | 用户信息 |

## 8. scripts/ - 工具脚本

```
scripts/
└── ralph/              # Ralph Loop 脚本
    ├── prd.json        # PRD JSON 格式
    ├── prompt.md       # Prompt 模板
    ├── progress.txt    # 进度追踪
    └── ralph.sh        # Ralph Loop 执行脚本
```

## 9. .claude/ - Claude CLI 配置

```
.claude/
├── hooks/               # Claude 钩子脚本 (5个)
│   ├── check-security.sh
│   ├── log-and-summarize.sh
│   ├── prompt-save-finding.sh
│   ├── session-manager.sh
│   └── validate-input.sh
└── hooks.json          # 钩子配置
```

## 10. 配置文件

### 根目录配置文件

| 文件 | 用途 |
|------|------|
| `.env.example` | 环境变量模板 |
| `.dockerignore` | Docker 构建忽略规则 |
| `.gitignore` | Git 忽略规则 |
| `Dockerfile` | 主服务镜像构建 |
| `Dockerfile.sandbox` | Python 沙盒镜像构建 |
| `docker-compose.yml` | 开发环境编排 |
| `pytest.ini` | pytest 配置 |
| `requirements.txt` | Python 依赖 |

## 11. API 集成配置

### LingYi AI 代理 (可选)

支持使用 LingYi AI 作为 Claude/Gemini API 的代理端点：

```bash
# .env 配置
ANTHROPIC_API_KEY=your_lingyi_api_key
ANTHROPIC_BASE_URL=https://api.lingyaai.cn/v1/messages

GOOGLE_API_KEY=your_lingyi_gemini_key
GOOGLE_BASE_URL=https://api.lingyaai.cn/v1
```

### Z.ai MCP 集成

```bash
# .env 配置
MCP_AVAILABLE=true
ZAI_MCP_API_KEY=your_zhipuai_api_key
```

## 12. 构建输出目录（不在版本控制中）

```
venv/                    # Python 虚拟环境
.pytest_cache/          # pytest 缓存
__pycache__/            # Python 字节码缓存
skills/test_*/          # 测试生成的 Skill 目录
```

## 开发规范

### 代码风格

- 所有函数必须有类型注解
- 复杂逻辑必须有文档字符串
- 所有外部调用必须有错误处理

### 安全要求

- Docker 容器必须有资源限制
- 命令行和 Python 执行必须有白名单
- SQL 查询必须参数化防止注入

### 测试要求

- 每个工具必须有单元测试
- 每个 Skill 必须有单元测试
- 测试覆盖率 > 80%

## 常见路径

### 导入示例

```python
# 数据模型
from backend.models.tool_output import ToolOutput, ToolTelemetry
from backend.models.agent import BAAgentConfig

# 工具
from tools.execute_command import execute_command_tool
from tools.skill_manager import skill_package_tool

# 配置
from config import get_config

# Skills
from skills.anomaly_detection import detect
```

### 配置访问

```python
from config import get_config

config = get_config()

# 访问数据库配置
db_host = config.database.host

# 访问 LLM 配置
api_key = config.llm.api_key

# 获取 MCP 配置
mcp_config = get_config_manager().get_mcp_config()
```

---

**文档版本**: v1.6 (LangGraph API 迁移完成)
**最后更新**: 2026-02-06 18:00
**维护者**: BA-Agent Team
**测试状态**: 746/746 通过 (100%)

**v2.1.0 完成**:
- ✅ 新增 `backend/pipeline/` 模块
- ✅ 新增 `backend/models/pipeline/` 模型
- ✅ BAAgent 集成 DynamicTokenCounter 和 AdvancedContextManager
- ✅ 所有 8 个工具迁移到 ToolExecutionResult
- ✅ Phase 7 完成：移除旧 ResponseFormat/ToolOutput 模型
- ✅ 全部 Phase 1-7 完成，测试通过

**2026-02-06 更新**:
- ✅ LangGraph API 迁移: `langgraph.prebuilt.create_react_agent` → `langchain.agents.create_agent`
- ✅ 使用别名避免命名冲突: `langchain_create_agent`
- ✅ 默认工具加载机制: 10个默认工具自动加载
- ✅ 新增 Excel 上传流程设计文档
- ✅ PRD.md 重写为产品导向文档
