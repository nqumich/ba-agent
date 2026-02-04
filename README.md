# BA-Agent

> 商业分析助手 Agent - Business Analysis Agent

面向非技术业务人员的智能数据分析助手，通过自然语言交互提供：
- 🔍 异动检测与解释
- 📊 归因分析
- 📄 报告自动生成
- 📈 数据可视化

## 🎯 项目状态

**开发进度**: ~63% (17/27 User Stories 完成)

**最新进展** (2025-02-05):
- ✅ 完成命令行执行工具 (US-006) - 16 测试通过
- ✅ 完成 Python 沙盒工具 (US-007) - 核心，29 测试通过
- ✅ 完成 Web 搜索工具 (US-008) - 22 测试通过
- ✅ 完成 Web Reader 工具 (US-009) - 27 测试通过
- ✅ 完成文件读取工具 (US-010) - 61 测试通过，支持 Python/SQL
- ✅ 完成 SQL 查询工具 (US-011) - 54 测试通过
- ✅ 完成向量检索工具 (US-012) - 51 测试通过
- ✅ 完成 Skill 调用工具 (US-013) - 核心，43 测试通过
- ✅ 完成 Skills 配置系统 (US-014)
- ✅ 完成统一工具输出格式系统 (US-INFRA-01) - 42 测试通过
- ✅ 完成 Skill 包管理工具 - 支持外部 Skill 导入
- ✅ 重组 Phase 3 Skills 结构 - 统一 SKILL.md 格式
- ✅ 创建自定义 Docker 镜像包含数据分析库
- ✅ Claude Hooks 系统优化 - 从11个脚本精简至5个
- ✅ **MCP 集成测试完成** - 9/9 测试通过
- ✅ **LingYi AI API 配置** - Claude/Gemini 支持
- ✅ **481 个测试全部通过**

**Phase 2 完成**: 9/9 核心工具全部完成 ✅

**Phase 3 完成**: Skills 结构重组 + MCP 集成 ✅

**Hooks 优化完成**: 11个脚本 → 5个脚本 (-54%) ✅

## 🏗️ 技术架构

### 核心组件

| 组件 | 技术 | 说明 |
|------|------|------|
| Agent 框架 | LangGraph + Claude Sonnet 4.5 | 可扩展的 Agent 系统 |
| 工具框架 | LangChain Core | 结构化工具定义 |
| 输出格式 | 统一工具输出格式 | ReAct 兼容 + 工程遥测 |
| 数据分析 | pandas, numpy, scipy | Docker 隔离的 Python 执行 |
| 容器隔离 | Docker | 安全的命令和代码执行 |
| 记忆管理 | 三层 Markdown | Clawdbot/Manus 模式 |
| MCP 集成 | Z.ai (智谱) | Web 搜索 + Web 读取 |
| LingYi AI | Claude/Gemini API | 自定义 API 端点支持 |

### 项目结构

```
ba-agent/
├── backend/                    # 后端核心
│   ├── agents/                # Agent 实现 (BAAgent)
│   ├── docker/                # Docker 沙盒 (DockerSandbox)
│   ├── hooks/                 # 系统钩子
│   ├── orchestration/         # 任务编排
│   └── models/                # Pydantic 数据模型（统一位置）
├── tools/                     # LangChain 工具
│   ├── base.py                # 统一工具输出格式包装器
│   ├── execute_command.py     # 命令行执行
│   ├── python_sandbox.py      # Python 沙盒
│   ├── web_search.py          # Web 搜索 (MCP)
│   ├── web_reader.py          # Web Reader (MCP)
│   ├── file_reader.py         # 文件读取
│   ├── database.py            # SQL 查询
│   ├── vector_search.py       # 向量检索
│   ├── skill_invoker.py       # Skill 调用
│   └── skill_manager.py       # Skill 包管理
├── skills/                    # Skills 目录
│   ├── anomaly_detection/     # 异动检测
│   ├── attribution/           # 归因分析
│   ├── report_gen/            # 报告生成
│   └── visualization/         # 数据可视化
├── config/                    # 配置文件
│   ├── config.py              # 配置管理核心
│   ├── settings.yaml          # 主配置
│   ├── skills.yaml            # Skills 配置
│   ├── skills_registry.json   # Skills 注册表
│   └── tools.yaml             # 工具配置
├── tests/                     # 测试套件
│   ├── test_agents/           # Agent 测试
│   ├── test_config/           # 配置测试
│   ├── test_docker/           # Docker 测试
│   ├── mcp_server/            # MCP 测试服务器
│   ├── tools/                 # 工具测试
│   └── models/                # 模型测试
├── memory/                    # 每日对话日志
├── docs/                      # 文档
├── .claude/hooks/             # Claude CLI 钩子 (5个脚本)
├── AGENTS.md                  # Agent 系统指令
├── CLAUDE.md                  # 项目级记忆
├── MEMORY.md                  # 长期知识记忆
├── USER.md                    # 用户信息
├── progress.md                # 开发进度
├── task_plan.md               # 任务计划
├── Dockerfile                 # 主服务镜像
├── Dockerfile.sandbox         # Python 沙盒镜像
└── docker-compose.yml         # 开发环境
```

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Docker & Docker Compose
- API Keys (至少一个):
  - `ANTHROPIC_API_KEY` (Claude)
  - 或 `GOOGLE_API_KEY` (Gemini)
  - 或 `ZHIPUAI_API_KEY` (智谱 GLM)

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
# 编辑 .env 填入 API Keys
```

### API 配置 (可选 - LingYi AI 代理)

如需使用 LingYi AI 作为 Claude/Gemini API 代理：

```bash
# .env 配置
ANTHROPIC_API_KEY=your_lingyi_api_key
ANTHROPIC_BASE_URL=https://api.lingyaai.cn/v1/messages

GOOGLE_API_KEY=your_lingyi_gemini_key
GOOGLE_BASE_URL=https://api.lingyaai.cn/v1
```

### MCP 集成配置 (Z.ai 智谱)

```bash
# .env 配置
MCP_AVAILABLE=true
ZAI_MCP_API_KEY=your_zhipuai_api_key
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_docker/
pytest tests/tools/

# 运行 MCP 集成测试
MCP_AVAILABLE=true pytest tests/tools/test_web_search_integration.py
MCP_AVAILABLE=true pytest tests/tools/test_web_reader_integration.py
```

### 启动开发环境

```bash
# 启动 Docker 服务
docker-compose up -d

# 启动 Agent (Python)
python -c "from backend.agents.agent import create_agent; agent = create_agent(); print(agent.invoke('你好'))"
```

## 📚 文档

- [产品 PRD](docs/PRD.md) - 产品需求文档
- [项目结构](docs/project-structure.md) - 目录结构说明
- [工具输出格式](docs/tool-output-format-design.md) - 统一输出设计
- [任务计划](task_plan.md) - 开发进度跟踪
- [开发进度](progress.md) - 详细开发日志
- [MCP 配置](docs/mcp-setup.md) - MCP 服务器配置

## 🔧 已完成的工具

| 工具 | 说明 | 测试 |
|------|------|------|
| execute_command | Docker 隔离的命令行执行 | 16/16 ✅ |
| run_python | Docker 隔离的 Python 代码执行 | 29/29 ✅ |
| web_search | Web 搜索 (Z.ai MCP) | 22/22 ✅ |
| web_reader | Web 读取 (Z.ai MCP) | 27/27 ✅ |
| file_reader | 文件读取 (CSV/Excel/JSON/文本) | 61/61 ✅ |
| query_database | SQL 查询 (参数化，多数据库) | 54/54 ✅ |
| search_knowledge | 向量检索 (ChromaDB/内存回退) | 51/51 ✅ |
| invoke_skill | Skill 调用 (桥接 Skills) | 43/43 ✅ |
| skill_package | Skill 包管理 (GitHub/ZIP) | 43/43 ✅ |

**Phase 2 完成**: 9/9 核心工具全部实现 ✅

## 🧩 Phase 3: Skills 系统

**已完成**:
- [x] Skills 配置系统 (config/skills.yaml)
- [x] Skill 注册表 (config/skills_registry.json)
- [x] Skill 包管理工具 (tools/skill_manager.py)
- [x] 统一 SKILL.md 格式 (YAML frontmatter)
- [x] 4 个内置 Skill 结构
- [x] MCP 集成测试 (Web 搜索 + Web 读取)

**待实现**:
- [ ] 异动检测 Skill 完整实现
- [ ] 归因分析 Skill 完整实现
- [ ] 报告生成 Skill 完整实现
- [ ] 数据可视化 Skill 完整实现

## 📊 测试覆盖

```
总计: 481 个测试
✅ 通过: 481 (100%)
⏭️  跳过: 0
❌ 失败: 0
```

### 测试分类

| 类别 | 测试数 | 状态 |
|------|--------|------|
| 基础设施 | 135 | ✅ |
| 核心工具 | 303 | ✅ |
| Skills 系统 | 43 | ✅ |
| MCP 集成 | 9 | ✅ |

## 🔜 待实现的功能

- [ ] FastAPI 服务
- [ ] IM Bot 集成 (钉钉/企业微信)
- [ ] Excel 插件 (Office.js)
- [ ] Skills 完整实现

## 📝 许可证

MIT License

---

**最后更新**: 2025-02-05
