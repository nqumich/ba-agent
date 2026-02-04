# BA-Agent

> 商业分析助手 Agent - Business Analysis Agent

面向非技术业务人员的智能数据分析助手，通过自然语言交互提供：
- 🔍 异动检测与解释
- 📊 归因分析
- 📄 报告自动生成
- 📈 数据可视化

## 🎯 项目状态

**开发进度**: 51.9% (14/27 User Stories 完成)

**最新进展** (2025-02-05):
- ✅ 完成命令行执行工具 (US-006) - 16 测试通过
- ✅ 完成 Python 沙盒工具 (US-007) - 核心，29 测试通过
- ✅ 完成 Web 搜索工具 (US-008) - 22 测试通过
- ✅ 完成 Web Reader 工具 (US-009) - 27 测试通过
- ✅ 完成文件读取工具 (US-010) - 61 测试通过，支持 Python/SQL
- ✅ 完成 SQL 查询工具 (US-011) - 54 测试通过
- ✅ 完成向量检索工具 (US-012) - 51 测试通过
- ✅ 完成统一工具输出格式系统 (US-INFRA-01) - 42 测试通过
- ✅ 创建自定义 Docker 镜像包含数据分析库
- ✅ 383 个测试全部通过

**下一任务**: Skill 调用工具 (US-013)

## 🏗️ 技术架构

### 核心组件

| 组件 | 技术 | 说明 |
|------|------|------|
| Agent 框架 | LangGraph + Claude 3.5 Sonnet | 可扩展的 Agent 系统 |
| 工具框架 | LangChain Core | 结构化工具定义 |
| 输出格式 | 统一工具输出格式 | ReAct 兼容 + 工程遥测 |
| 数据分析 | pandas, numpy, scipy | Docker 隔离的 Python 执行 |
| 容器隔离 | Docker | 安全的命令和代码执行 |
| 记忆管理 | 三层 Markdown | Clawdbot/Manus 模式 |

### 项目结构

```
ba-agent/
├── backend/                # 后端核心
│   ├── agents/            # Agent 实现 (BAAgent)
│   ├── docker/            # Docker 沙盒 (DockerSandbox)
│   └── models/            # Pydantic 数据模型
├── tools/                 # LangChain 工具
│   ├── base.py            # 统一工具输出格式包装器
│   ├── execute_command.py # 命令行执行
│   ├── python_sandbox.py  # Python 沙盒
│   ├── web_search.py      # Web 搜索 (MCP)
│   ├── web_reader.py      # Web Reader (MCP)
│   ├── file_reader.py     # 文件读取 (含 Python/SQL 解析)
│   ├── database.py        # SQL 查询 (SQLAlchemy 集成)
│   └── vector_search.py   # 向量检索 (ChromaDB/内存回退)
├── skills/                # 可配置分析 Skills
│   ├── anomaly_detection/ # 异动检测
│   ├── attribution/       # 归因分析
│   ├── report_gen/        # 报告生成
│   └── visualization/    # 数据可视化
├── config/                # 配置文件
│   ├── settings.yaml      # 主配置
│   ├── skills.yaml        # Skills 配置
│   └── tools.yaml         # 工具配置
├── tests/                 # 测试 (278 个测试全部通过)
│   ├── test_docker/       # Docker 沙盒测试
│   ├── tools/             # 工具测试
│   └── models/            # 模型测试
├── memory/                # 三层记忆系统
│   ├── 2025-02-04.md      # 每日日志
│   ├── MEMORY.md          # 长期知识
│   ├── CLAUDE.md          # 项目级记忆
│   ├── AGENTS.md          # Agent 系统指令
│   └── USER.md            # 用户信息
├── docs/                  # 文档
├── scripts/ralph/         # Ralph Loop 脚本
├── Dockerfile             # 主服务镜像
├── Dockerfile.sandbox     # Python 沙盒镜像 (含数据分析库)
└── docker-compose.yml     # 开发环境编排
```

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Docker & Docker Compose
- ANTHROPIC_API_KEY

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd ba-agent

# 创建虚拟环境
python3.12 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 ANTHROPIC_API_KEY
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_docker/
pytest tests/tools/

# 查看测试覆盖率
pytest --cov=backend --cov=tools --cov-report=html
```

### 启动开发环境

```bash
# 启动 Docker 服务 (PostgreSQL, ClickHouse)
docker-compose up -d

# 启动 API 服务
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 文档

- [产品 PRD](docs/PRD.md) - 产品需求文档
- [任务计划](task_plan.md) - 开发进度跟踪
- [开发进度](progress.md) - 详细开发日志
- [研究发现](findings.md) - 技术研究发现

## 🔧 已完成的工具

| 工具 | 说明 | 测试 |
|------|------|------|
| execute_command | Docker 隔离的命令行执行 | 16/16 ✅ |
| run_python | Docker 隔离的 Python 代码执行 | 29/29 ✅ |
| web_search | Web 搜索 (MCP: mcp__web-search-prime__webSearchPrime) | 22/22 ✅ |
| web_reader | Web 读取 (MCP: mcp__web_reader__webReader) | 27/27 ✅ |
| file_reader | 文件读取 (CSV/Excel/JSON/文本/Python/SQL) | 61/61 ✅ |
| query_database | SQL 查询 (参数化查询，多数据库支持) | 54/54 ✅ |
| search_knowledge | 向量检索 (ChromaDB/内存回退) | 51/51 ✅ |

## 🔧 基础设施

| 组件 | 说明 | 测试 |
|------|------|------|
| unified_tool | 统一工具输出格式装饰器 | 42/42 ✅ |
| ToolOutput | 工具输出数据模型 | ✅ |
| ToolTelemetry | 工程遥测数据模型 | ✅ |
| ReActFormatter | ReAct 格式化工具 | ✅ |
| TokenOptimizer | Token 优化工具 | ✅ |

## 📊 测试覆盖

```
总计: 389 个测试
✅ 通过: 383 (98.5%)
⏭️  跳过: 6 (需要 MCP 依赖)
❌ 失败: 0
```

## 🔜 待实现的工具 (Phase 2)

- [x] Web 搜索工具 (MCP: mcp__web-search-prime__webSearchPrime)
- [x] Web Reader 工具 (MCP: mcp__web_reader__webReader)
- [x] 文件读取工具 (CSV/Excel/JSON/文本/Python/SQL)
- [x] SQL 查询工具 (SQLAlchemy)
- [x] 向量检索工具 (ChromaDB)
- [ ] Skill 调用工具 (核心) - 下一任务
- [ ] 记忆管理工具 (memory_search, memory_get, memory_write)

## 🧩 待实现的 Skills (Phase 3)

- [ ] 异动检测 Skill
- [ ] 归因分析 Skill
- [ ] 报告生成 Skill
- [ ] 数据可视化 Skill

## 📝 许可证

MIT License

---

**最后更新**: 2025-02-05
