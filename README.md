# BA-Agent

> 商业分析助手 Agent - Business Analysis Agent
> **Version**: v2.3.0
> **Last Updated**: 2026-02-08

面向非技术业务人员的智能数据分析助手，通过自然语言交互提供：
- 🔍 异动检测与解释
- 📊 归因分析
- 📄 报告自动生成
- 📈 数据可视化

## 🎯 项目状态

**开发进度**: ~88% (26/30 User Stories 完成)

**最新进展** (2026-02-08):
- ✅ 完成核心业务 Skills (US-015/016/017/018) - 90 个测试通过
- ✅ 完成 API 服务增强 (US-021) - JWT 认证 + 速率限制 + 错误处理
- ✅ 完成 Web 前端测试控制台 (US-FE-01) - 单页应用 + Agent 对话
- ✅ **完成 LangGraph 上下文管理协调** - ContextCoordinator 统一文件清理入口
- ✅ 1030 个测试全部通过
- ✅ FastAPI 服务 v2.3.0 - REST API + JWT 认证 + Web 前端

**核心功能完成**:
- ✅ **Phase 1**: Agent 框架 (LangGraph + Claude Sonnet 4.5)
- ✅ **Phase 2**: 9 个核心工具（303 个测试）
- ✅ **Phase 3**: Skills 系统完整实现（137 个测试）
- ✅ **Pipeline v2.1**: 完整的 Pipeline 系统（746 个测试）
- ✅ **FileStore**: 统一文件存储系统
- ✅ **核心 Skills**: 异动检测、归因分析、报告生成、数据可视化
- ✅ **上下文协调**: ContextCoordinator 统一文件清理和上下文构建
- ✅ **API 服务**: REST API + JWT 认证 + 速率限制
- ✅ **Web 前端**: 单页应用测试控制台

## 🏗️ 技术架构

### 核心组件

| 组件 | 技术 | 说明 |
|------|------|------|
| Agent 框架 | LangGraph + Claude Sonnet 4.5 | 自定义图结构，支持结构化响应 |
| 工具框架 | LangChain Core | 结构化工具定义 |
| 输出格式 | Pipeline v2.1 ToolExecutionResult + 结构化响应 | OutputLevel (BRIEF/STANDARD/FULL) |
| 响应格式 | 结构化 JSON (task_analysis, execution_plan, action) | tool_call/complete 判定 |
| 数据分析 | pandas, numpy, scipy | Docker 隔离的 Python 执行 |
| 容器隔离 | Docker | 安全的命令和代码执行 |
| 记忆管理 | 三层 Markdown | Clawdbot/Manus 模式 |
| MCP 集成 | Z.ai (智谱) | Web 搜索 + Web 读取 |
| LingYi AI | Claude/Gemini API | 自定义 API 端点支持 |
| 前端渲染 | ECharts 5.4 | 图表可视化 |

### 项目结构

```
ba-agent/
├── backend/                    # 后端核心
│   ├── agents/                # Agent 实现 (BAAgent + 自定义 LangGraph)
│   ├── api/                   # FastAPI 服务
│   │   ├── services/          # BA-Agent 服务封装
│   │   ├── routes/            # API 路由
│   │   └── middleware/        # JWT 认证 + 速率限制
│   ├── core/                  # 核心组件 ⭐ NEW
│   │   ├── context_manager.py     # 上下文管理器
│   │   └── context_coordinator.py  # 上下文协调器 (v2.3.0 新增)
│   ├── docker/                # Docker 沙盒 (DockerSandbox)
│   ├── hooks/                 # 系统钩子
│   ├── models/                # Pydantic 数据模型
│   │   ├── response.py        # 结构化响应格式定义
│   │   ├── pipeline.py        # Pipeline v2.1
│   │   └── agent.py           # Agent 状态模型
│   └── skills/                # Skills 系统
├── tools/                     # LangChain 工具
│   ├── base.py                # 统一工具输出格式包装器
│   ├── execute_command.py     # 命令行执行
│   ├── python_sandbox.py      # Python 沙盒
│   ├── web_search.py          # Web 搜索 (MCP)
│   ├── web_reader.py          # Web Reader (MCP)
│   ├── file_reader.py         # 文件读取
│   ├── file_write.py          # 文件写入
│   ├── database.py            # SQL 查询
│   └── vector_search.py       # 向量检索
├── skills/                    # Skills 目录
│   ├── anomaly_detection/     # 异动检测
│   ├── attribution/           # 归因分析
│   ├── report_gen/            # 报告生成
│   └── visualization/         # 数据可视化
├── frontend/                  # Web 前端
│   └── index.html            # 单页应用 (SPA)
├── config/                    # 配置文件
│   ├── config.py              # 配置管理核心
│   ├── settings.yaml          # 主配置
│   └── .env                   # 环境变量
├── tests/                     # 测试套件
├── memory/                    # 每日对话日志
├── docs/                      # 文档
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

# 启动 API 服务
uvicorn backend.api.main:app --reload --port 8000

# 访问 API 文档
open http://localhost:8000/docs

# 访问 Web 前端测试控制台
open http://localhost:8000
```

### Web 前端测试控制台

BA-Agent 提供了完整的单页应用 (SPA) 前端测试控制台：

**功能**:
- 🔐 JWT 登录/登出
- 💬 Agent 对话界面
- 📁 文件管理（拖拽上传/下载/删除）
- 🎯 Skills 管理（列表/分类查看）

**访问方式**:
```bash
# 启动 API 服务器
uvicorn backend.api.main:app --reload --port 8000

# 浏览器访问前端
open http://localhost:8000

# 默认登录账号
用户名: admin
密码: admin123
```

**前端技术栈**:
- 纯 HTML/CSS/JavaScript（无框架依赖）
- JWT 令牌管理 (localStorage)
- 响应式设计
- 拖拽上传支持

### API 认证

API 服务 v2.2.0 默认启用 JWT 认证：

```bash
# 登录获取令牌
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# 使用令牌访问受保护的端点
curl http://localhost:8000/api/v1/files \
  -H "Authorization: Bearer <access_token>"
```

**默认用户**:
- 管理员: `admin` / `admin123` (全部权限)
- 普通用户: `user` / `user123` (读写权限)

**环境变量**:
```bash
BA_JWT_SECRET_KEY=your-secret-key-change-in-production
BA_JWT_EXPIRE_MINUTES=60
BA_RATE_LIMIT_IP_PER_MINUTE=60
```

## 📚 文档

### 核心文档
- [产品 PRD](docs/README.md) - 产品需求文档
- [项目架构](docs/architecture.md) - 架构设计（v2.2.0 更新 ContextCoordinator）
- [上下文管理](docs/context-management.md) - 上下文管理详细文档（v1.5.0 更新）
- [系统提示词](docs/prompts.md) - Agent 提示词定义和规范
- [响应格式流转](docs/response-flow.md) - 大模型返回格式与前端渲染完整流程（v2.8.0 更新）
- [API 文档](docs/api.md) - REST API 端点（v2.3.0 更新）
- [Skills 指南](docs/skills.md) - Skills 开发指南
- [开发指南](docs/development.md) - 开发环境与测试（v2.3.0 更新）
- [开发进度](progress.md) - 详细开发日志

### 文档目录
- [docs/README.md](docs/README.md) - 文档导航和概述

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
总计: 1030 个测试
✅ 通过: 1030 (100%)
⏭️  跳过: 1 (MCP 相关)
❌ 失败: 0
```

### 测试分类

| 类别 | 测试数 | 状态 |
|------|--------|------|
| 基础设施 | 135 | ✅ |
| 核心工具 | 303 | ✅ |
| Skills 系统 | 200+ | ✅ |
| Context Coordinator | 24 | ✅ (v2.3.0 新增) |
| Context Manager | 41 | ✅ (增强测试) |
| Pipeline v2.1 | 100+ | ✅ |
| Memory 系统 | 120 | ✅ |
| Agent 集成 | 25 | ✅ |
| API 服务 | 36 | ✅ |
| MCP 集成 | 9 | ✅ |
| FileStore 系统 | 100+ | ✅ |

## 🔜 待实现的功能

- [ ] IM Bot 集成 (钉钉/企业微信)
- [ ] Excel 插件 (Office.js)

## 🏗️ 最新架构更新 (v2.3.0)

### ContextCoordinator 协调层

新增统一的上下文协调机制，解决文件清理逻辑分散的问题：

**架构改进**:
```
API Layer → Coordination Layer → (LangGraph | ContextManager | Memory Flush)
```

**核心功能**:
- 统一的文件清理入口（所有清理通过 ContextCoordinator）
- 新/旧对话使用相同的处理流程
- 明确的职责划分（LangGraph 管理历史，ContextManager 管理清理）

**新增组件**:
- `backend/core/context_coordinator.py` - 上下文协调器
- `backend/core/context_manager.py` - 增强 LangChain 消息清理
- 24 个新测试通过

## 📝 许可证

MIT License

---

**最后更新**: 2026-02-08
