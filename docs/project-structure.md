# BA-Agent 项目目录结构说明

> 本文档详细说明 BA-Agent 项目的目录结构和各组件的用途
> 更新时间: 2025-02-05

## 目录概览

```
ba-agent/
├── backend/          # 后端核心模块
├── tools/            # LangChain 工具集合
├── skills/           # Skills 实现
├── config/           # 配置管理系统
├── tests/            # 测试套件
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

后端核心代码，包含 Agent 实现、Docker 集成、数据模型等。

### 1.1 backend/agents/ - Agent 实现

```
agents/
├── __init__.py
└── agent.py              # BAAgent 主实现
                            - ChatAnthropic 初始化
                            - LangGraph AgentExecutor
                            - MemorySaver 对话历史
```

**关键功能**:
- 使用 LangGraph create_react_agent 创建 Agent
- 集成 Claude 3.5 Sonnet 模型
- 支持工具调用和记忆管理

### 1.2 backend/docker/ - Docker 沙盒

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

### 1.3 backend/hooks/ - 系统钩子

```
hooks/
├── __init__.py
└── hook_manager.py       # 钩子管理器
                            - 事件订阅/发布
                            - 生命周期钩子
```

### 1.4 backend/orchestration/ - 任务编排

```
orchestration/
├── __init__.py
├── focus_manager.py      # 焦点管理器
└── tool_orchestrator.py  # 工具编排器
```

### 1.5 backend/models/ - 数据模型（统一位置）

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
└── tool_output.py         # 工具输出格式模型
                            - ToolOutput
                            - ToolTelemetry
                            - ResponseFormat
```

**导入方式**:
```python
# 正确 ✅
from backend.models.tool_output import ToolOutput, ToolTelemetry
from backend.models.agent import BAAgentConfig, AgentState

# 错误 ❌ (顶层 models/ 已移除)
from models.tool_output import ToolOutput
```

## 2. tools/ - LangChain 工具集合

所有 LangChain StructuredTool 实现，每个工具一个文件。

### 工具列表

| 文件 | 工具名 | 说明 | 测试 |
|------|--------|------|------|
| base.py | unified_tool | 统一工具输出格式装饰器 | 42 tests ✅ |
| execute_command.py | execute_command | Docker 隔离命令行执行 | 16 tests ✅ |
| python_sandbox.py | run_python | Docker 隔离 Python 执行 | 29 tests ✅ |
| web_search.py | web_search | Web 搜索 (MCP) | 22 tests ✅ |
| web_reader.py | web_reader | Web 读取 (MCP) | 27 tests ✅ |
| file_reader.py | file_reader | 多格式文件读取 | 61 tests ✅ |
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

可复用的分析能力模块。

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
├── skills_registry.json    # Skills 注册表（唯一真实来源）
└── tools.yaml              # 工具配置
```

### settings.yaml - 主配置

包含以下配置：
- **数据库**: PostgreSQL, ClickHouse 连接
- **LLM**: Claude 3.5 Sonnet 配置
- **向量数据库**: ChromaDB 配置
- **Docker**: 镜像、网络、资源限制
- **记忆**: 三层记忆系统配置
- **安全**: SQL 安全策略

支持环境变量覆盖：
```bash
export BA_DATABASE__HOST=localhost
export BA_LLM__API_KEY=sk-xxx
```

### skills.yaml - Skills 运行时配置

```yaml
global:
  skill_timeout: 120
  max_memory: 512m
  enable_cache: true
  cache_ttl: 3600

skills_config:
  anomaly_detection:
    threshold: 2.0
    min_data_points: 7
```

### skills_registry.json - Skills 注册表

记录所有已安装 Skills 的元数据，是 Skills 状态的唯一真实来源。

## 5. tests/ - 测试套件

### 测试目录结构

```
tests/
├── __init__.py
├── conftest.py              # pytest 全局配置
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
└── tools/                   # 工具测试
    ├── conftest.py
    ├── test_database.py
    ├── test_execute_command.py
    ├── test_file_reader.py
    ├── test_python_sandbox.py
    ├── test_skill_invoker.py
    ├── test_skill_manager.py
    ├── test_vector_search.py
    ├── test_web_reader.py
    └── test_web_search.py
```

### 测试统计

- **总计**: 469 个测试
- **通过**: 469 (100%)
- **跳过**: 6 (需要 MCP 依赖)

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/tools/test_skill_manager.py
pytest tests/test_agents/

# 查看覆盖率
pytest --cov=backend --cov=tools --cov-report=html
```

## 6. 三层记忆系统

采用 Clawdbot/Manus 模式的三层记忆架构。

### 实际文件组织

**每日对话日志** (memory/ 目录):
```
memory/
└── 2025-02-04.md          # Layer 1: 每日对话日志
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
- **memory_search**: 语义搜索 MEMORY.md + memory/*.md
- **memory_get**: 读取特定内存文件
- **memory_write**: 写入记忆（自动选择 Layer 1 或 Layer 2）

## 7. docs/ - 项目文档

```
docs/
├── PRD.md                              # 产品需求文档
└── tool-output-format-design.md        # 工具输出格式设计文档
```

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

## 9. 配置文件

### 9.1 根目录配置文件

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

### 9.2 .claude/ - Claude CLI 配置

```
.claude/
├── hooks/               # Claude 钩子脚本
└── hooks.json          # 钩子配置
```

## 10. 构建输出目录（不在版本控制中）

```
venv/                    # Python 虚拟环境
.pytest_cache/          # pytest 缓存
__pycache__/            # Python 字节码缓存
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

# 访问 Skills 配置
skills = config.skills
```

---

**文档版本**: v1.0
**最后更新**: 2025-02-05
**维护者**: BA-Agent Team
