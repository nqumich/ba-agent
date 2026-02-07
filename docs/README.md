# BA-Agent (Business Analysis Agent)

**版本**: v2.1.0
**创建日期**: 2025-02-04
**最后更新**: 2026-02-07
**架构**: Single LangChain Agent + Pipeline v2.1 + Configurable Skills
**开发进度**: ~75% (核心框架完成)

---

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/your-org/ba-agent.git
cd ba-agent

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入必要的 API keys
```

### 基本使用

```python
from langchain_openai import ChatOpenAI
from backend.agent import BAAgent

# 创建 Agent
agent = BAAgent(
    llm=ChatOpenAI(model="gpt-4o"),
    tools=[],  # 自动加载默认工具
    skills=[]  # 自动加载默认 Skills
)

# 运行
result = agent.run("帮我分析 sales_data.xlsx 中的 GMV 趋势")
print(result)
```

---

## 项目概述

商业分析助手 Agent，面向非技术业务人员，通过自然语言交互提供：

- **异动检测** - AI 自动发现数据异常
- **归因分析** - 智能分析数据变化原因
- **报告生成** - 一键生成分析报告
- **数据可视化** - 自动生成图表

### 目标用户

- 运营、产品、市场等业务人员
- 不懂 SQL/编程，日常需要查看数据、分析趋势、写报告

---

## 核心功能

| 功能 | 状态 | 说明 |
|------|------|------|
| Agent 框架 | ✅ 完成 | LangGraph + Claude Sonnet 4.5 |
| 核心工具 | ✅ 完成 | 9 个工具 (查询、分析、可视化等) |
| Skills 系统 | ✅ 完成 | 4 个内置 Skill 框架 |
| Pipeline v2.1 | ✅ 完成 | 完整的 Pipeline 系统 |
| 文件系统 | ✅ 完成 | FileStore 统一管理 |
| 记忆系统 | ✅ 完成 | 记忆存储 + 文件引用 |
| Skill 业务逻辑 | ⏳ 待实现 | 4 个 Skill 核心逻辑 |
| FastAPI 服务 | ⏳ 待实现 | REST API 服务 |
| IM Bot 集成 | ⏳ 待实现 | 钉钉/企业微信 |
| Excel 插件 | ⏳ 待实现 | Office.js 侧边栏 |

---

## 文档导航

### 核心文档
- **[PRD.md](PRD.md)** - 产品需求、开发进度、路线图
- **[architecture.md](architecture.md)** - 技术架构设计
- **[implementation.md](implementation.md)** - 实现方案详情
- **[skills.md](skills.md)** - Skills 系统指南

### 开发文档
- **[development.md](development.md)** - 开发指南、项目结构、测试
- **[guides/setup.md](guides/setup.md)** - 环境搭建
- **[guides/context.md](guides/context.md)** - 上下文管理器
- **[guides/migration.md](guides/migration.md)** - 迁移指南

---

## 技术栈

| 组件 | 技术 |
|------|------|
| Agent 框架 | LangGraph |
| LLM | OpenAI GPT-4o / Anthropic Claude |
| 工具执行 | Docker 隔离 |
| 数据存储 | SQLite + 本地文件系统 |
| 向量搜索 | SQLite FTS5 |
| API 框架 | FastAPI (待实现) |

---

## 开发状态

### 测试覆盖
```
总计: 839 个测试
✅ 通过: 839 (100%)
⏭️  跳过: 1 (MCP 相关)
❌ 失败: 0
```

### 最近更新 (2026-02-07)
- ✅ FileStore 与 Pipeline 集成
- ✅ MemoryFlush 支持文件引用
- ✅ MemorySearch 返回文件引用
- ✅ 文档重构精简

---

## 目录结构

```
ba-agent/
├── backend/              # 后端核心模块
│   ├── agent/           # Agent 实现
│   ├── tools/           # 工具实现
│   ├── skills/          # Skills 系统
│   ├── pipeline/        # Pipeline v2.1
│   ├── filestore/       # 文件系统
│   └── memory/          # 记忆系统
├── tools/               # 工具入口 (LangChain)
├── tests/               # 测试套件
├── docs/                # 文档
└── config/              # 配置文件
```

---

## 贡献指南

详见 [development.md](development.md)

---

## 许可证

MIT License
