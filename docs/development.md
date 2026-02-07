# BA-Agent 开发指南

> **Version**: v2.1.0
> **Last Updated**: 2026-02-07

完整的开发指南，包括项目结构、测试、贡献流程等。

---

## 目录

- [开发状态](#开发状态)
- [项目结构](#项目结构)
- [环境搭建](#环境搭建)
- [测试](#测试)
- [贡献指南](#贡献指南)

---

## 开发状态

### 总体进度: ~75%

| Phase | 状态 | 说明 |
|-------|------|------|
| **Phase 1**: Agent 框架 | ✅ 完成 | LangGraph + Claude Sonnet 4.5 |
| **Phase 2**: 核心工具 | ✅ 完成 | 9 个工具，完整测试覆盖 |
| **Phase 3**: Skills 系统 | ✅ 完成 | 4 个内置 Skill 框架 |
| **Pipeline v2.1** | ✅ 完成 | 完整的 Pipeline 系统 |
| **文件系统** | ✅ 完成 | FileStore 统一管理 |
| **记忆系统** | ✅ 完成 | 记忆存储 + 文件引用 |
| **Skill 业务逻辑** | ⏳ 待实现 | 4 个 Skill 核心逻辑 |
| **FastAPI 服务** | ⏳ 待实现 | REST API 服务 |
| **IM Bot 集成** | ⏳ 待实现 | 钉钉/企业微信 |
| **Excel 插件** | ⏳ 待实现 | Office.js 侧边栏 |

---

## 项目结构

### 整体目录

```
ba-agent/
├── backend/          # 后端核心模块
│   ├── agents/       # Agent 实现
│   ├── memory/       # 记忆系统
│   ├── pipeline/     # Pipeline v2.1
│   ├── filestore/    # 文件系统
│   ├── skills/       # Skills 系统
│   ├── models/       # Pydantic 模型
│   ├── docker/       # Docker 沙盒
│   ├── hooks/        # 系统钩子
│   └── orchestration/ # 任务编排
├── tools/            # LangChain 工具集合
├── skills/           # Skills 实现
├── config/           # 配置管理
├── tests/            # 测试套件
├── memory/           # 每日对话日志
├── docs/             # 项目文档
├── scripts/          # 工具脚本
├── AGENTS.md         # Agent 系统指令
├── CLAUDE.md         # 项目级记忆
├── MEMORY.md         # 长期知识记忆
├── USER.md           # 用户信息
└── README.md         # 项目概述
```

### backend/agents/

```
agents/
├── __init__.py
└── agent.py          # BAAgent 主实现
                       - LangGraph AgentExecutor
                       - MemoryFlush
                       - Conversation Compaction
                       - Pipeline v2.1 集成
```

### backend/memory/

```
memory/
├── __init__.py
├── flush.py          # MemoryFlush - 记忆提取
├── flush_enhanced.py # Enhanced MemoryFlush - 文件引用
├── search_enhanced.py # Enhanced MemorySearch
├── index.py          # MemoryWatcher - 文件监听
├── schema.py         # SQLite Schema
├── embedding.py      # EmbeddingProvider
├── vector_search.py  # 向量搜索引擎
└── tools/            # Memory 工具
    ├── memory_write.py
    ├── memory_get.py
    ├── memory_retain.py
    ├── memory_search.py
    └── memory_search_v2.py
```

### backend/pipeline/

```
pipeline/
├── __init__.py              # 统一导出
├── timeout/__init__.py      # ToolTimeoutHandler
├── storage/__init__.py      # DataStorage
├── wrapper.py               # PipelineToolWrapper
├── cache/                   # 幂等性缓存
│   └── idempotency_cache.py
├── token/                   # Token 计数
│   └── token_counter.py
├── context/                 # 上下文管理
│   └── context_manager.py
└── filestore_integration.py # FileStore 集成
```

### backend/filestore/

```
filestore/
├── __init__.py
├── base.py                  # 基础接口
├── file_store.py            # FileStore 主类
├── stores/                  # 具体存储实现
│   ├── artifact_store.py
│   ├── upload_store.py
│   ├── memory_store.py
│   ├── report_store.py
│   └── ...
├── security.py              # 安全控制
├── lifecycle.py             # 生命周期管理
├── config.py                # 配置加载
└── factory.py               # 工厂函数
```

### backend/skills/

```
skills/
├── __init__.py
├── loader.py                # SkillLoader
├── registry.py              # SkillRegistry
├── activator.py             # SkillActivator
├── formatter.py             # SkillMessageFormatter
├── installer.py             # SkillInstaller
└── models.py                # Pydantic 模型
```

### tools/

```
tools/
├── execute_command.py       # Docker 命令执行
├── run_python.py            # Python 代码执行
├── web_search.py            # Web 搜索 (MCP)
├── web_reader.py            # Web 读取 (MCP)
├── file_reader.py           # 文件读取
├── file_writer.py           # 文件写入
├── query_database.py        # 数据库查询
├── search_knowledge.py      # 向量检索
└── invoke_skill.py          # Skill 调用
```

### skills/

```
skills/
├── anomaly_detection/       # 异动检测
├── attribution/             # 归因分析
├── report_gen/              # 报告生成
└── visualization/           # 数据可视化
```

### tests/

```
tests/
├── test_agents/             # Agent 测试
├── test_memory/             # Memory 测试
├── test_filestore/          # FileStore 测试
├── test_skills/             # Skills 测试
├── tools/                   # 工具测试
├── models/                  # 模型测试
└── backend/                 # 后端组件测试
```

---

## 环境搭建

### 系统要求

- Python 3.12+
- Docker (用于沙盒执行)
- SQLite 3

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-org/ba-agent.git
cd ba-agent

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入必要的 API keys

# 5. 初始化数据库
python -c "from backend.memory import ensure_memory_index_schema; ..."

# 6. 运行测试
pytest tests/ -v
```

### 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | ✅ |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | ✅ |
| `ZHIPUAI_API_KEY` | 智谱 AI API 密钥 | - |
| `DATABASE_URL` | 数据库连接字符串 | - |
| `LOG_LEVEL` | 日志级别 (DEBUG/INFO/WARNING/ERROR) | - |

---

## 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定模块
pytest tests/test_memory/
pytest tests/test_filestore/
pytest tests/tools/

# 显示详细输出
pytest -v

# 显示打印输出
pytest -s

# 生成覆盖率报告
pytest --cov=backend --cov-report=html
```

### 测试状态

```
总计: 839 个测试
✅ 通过: 839 (100%)
⏭️  跳过: 1 (MCP 相关)
❌ 失败: 0
```

### 编写测试

```python
# tests/test_example.py
import pytest
from backend.memory import MemoryFlush

class TestMemoryFlush:
    def test_init(self):
        """测试初始化"""
        flush = MemoryFlush()
        assert flush.config.soft_threshold == 4000

    def test_add_message(self):
        """测试添加消息"""
        flush = MemoryFlush()
        flush.add_message("user", "Hello")
        assert flush.message_count == 1
```

---

## 贡献指南

### 代码风格

- 使用 PEP 8 风格指南
- 使用类型注解
- 编写 docstring
- 最大行长度: 100

### Git 提交规范

```
类型(范围): 简短描述

详细描述

关联 Issue: #123
```

**类型**:
- `feat`: 新功能
- `fix`: 修复 Bug
- `docs`: 文档更新
- `test`: 测试相关
- `refactor`: 重构
- `style`: 代码风格
- `chore`: 构建/工具

### Pull Request 流程

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 审查标准

- [ ] 测试通过
- [ ] 代码符合风格指南
- [ ] 有适当的文档
- [ ] 没有引入新的警告
- [ ] 向后兼容

---

## 研究发现

### LangChain 1.2.x API 变更
**重要性**: ⚠️ 重要

**问题**: LangChain 1.2.x 有重大 API 变更，旧 API 不再可用

**解决方案**:
```python
# 新 API (LangChain 1.2.8+)
from langchain.agents import create_agent
from langchain_core.tools import StructuredTool, tool
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
agent = create_agent(model, tools, checkpointer=memory)
```

### Python 3.14 ARM64 兼容性
**重要性**: ⚠️ 重要

**问题**: Python 3.14 ARM64 暂不支持某些包 (如 chromadb)

**解决方案**: 使用 Python 3.12

### 三层记忆管理系统
**重要性**: ✅ 核心设计

**架构**: 基于 Clawdbot/Moltbot 的三层 Markdown 记忆

| 层级 | 文件 | 内容 | 持久性 |
|------|------|------|--------|
| Layer 1 | `memory/YYYY-MM-DD.md` | 日常笔记、临时讨论 | 每日 |
| Layer 2 | `MEMORY.md` | 长期知识、用户偏好 | 永久 |
| Layer 3 | `CLAUDE.md`, `AGENTS.md` | 项目架构、系统指令 | 永久 |

### 数据可视化方案
**选择**: ECharts (通过 Gemini 3 Pro 生成代码)

**原因**:
- 交互性强
- 中文支持好
- 无需 Python 图表库
- 适合 Web 应用

---

## 相关文档

- [README.md](README.md) - 快速开始
- [PRD.md](PRD.md) - 产品需求
- [architecture.md](architecture.md) - 技术架构
- [skills.md](skills.md) - Skills 系统
- [guides/setup.md](guides/setup.md) - 环境搭建
