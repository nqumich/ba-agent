# BA-Agent Ralph Loop - Agent Instructions

## Your Task

你是一个专业的全栈开发工程师，负责实现 BA-Agent (Business Analysis Agent) 项目。

**项目概述**：
- 这是一个商业分析助手Agent，面向非技术业务人员
- 核心能力：异动检测、归因分析、报告生成、数据可视化
- 技术架构：单LangChain Agent + 基础工具 + 可配置Skills
- 参考：Manus AI的架构思想（Analyze → Plan → Execute → Observe循环）

## 当前项目状态

请先查看项目结构和已有文件，了解当前进度。

## 你的工作流程

每个迭代中，按以下顺序工作：

### 1. 检查当前状态
```bash
# 查看项目结构
ls -la

# 查看当前进度
cat scripts/ralph/progress.txt

# 查看待完成任务
python -c "
import json
with open('scripts/ralph/prd.json') as f:
    prd = json.load(f)
for story in prd['userStories']:
    if not story.get('passes', False):
        print(f\"{story['id']}: {story['title']} (priority {story['priority']})\")
"
```

### 2. 选择下一个任务
- 按优先级选择任务（priority 1 → 2 → 3 → 4）
- 同优先级中按ID顺序选择
- 优先处理基础设施和核心框架

### 3. 理解任务需求
- 阅读 `acceptanceCriteria` 了解完成标准
- 阅读 `notes` 了解注意事项

### 4. 实现任务
- 创建/修改必要的文件
- 遵循项目的架构设计原则
- 编写可维护、可扩展的代码

### 5. 验证完成
- 运行相关测试
- 手动验证功能
- 确保符合验收标准

### 6. 更新进度
- 在 `scripts/ralph/progress.txt` 中追加本次迭代记录
- 在 `scripts/ralph/prd.json` 中将任务 `passes` 设为 `true`
- 提交代码：`git add . && git commit -m "feat: [ID] - [Title]"`
- 推送到远程：`git push origin master`

### 7. 记录学习
- 在 `scripts/ralph/progress.txt` 顶部维护"Codebase Patterns"部分
- 记录遇到的问题和解决方案

## 进度记录格式

在 `scripts/ralph/progress.txt` 中追加：

```markdown
## [日期] - [Story ID]
- **任务**: [任务标题]
- **文件变更**: [修改/创建的文件列表]
- **完成标准**: [验收标准确认]
- **Learnings**:
  - [学到的模式]
  - [遇到的问题和解决方案]
---
```

## Codebase Patterns

在 `scripts/ralph/progress.txt` 顶部维护可复用的模式：

```markdown
## Codebase Patterns
- 项目结构：backend/ (核心代码), config/ (配置), skills/ (可配置Skills), docs/ (文档)
- 所有工具继承自 `langchain_core.tools.StructuredTool` (注意：不是 langchain.tools)
- Agent创建使用 `langchain.agents.create_agent` (LangChain 1.2.8+ 推荐方式)
- 所有Skills通过 `config/skills.yaml` 注册
- 使用 Pydantic 定义所有数据模型
- Docker隔离用于代码执行

## 三层记忆管理系统 (已实现)
- Layer 1: memory/YYYY-MM-DD.md - 日常日志
- Layer 2: MEMORY.md - 长期策划知识
- Layer 3: CLAUDE.md, AGENTS.md, USER.md - 项目级记忆
- Manus 三文件模式: task_plan.md, findings.md, progress.md

## 渐进式工具使用系统 (已实现)
- Tool Orchestrator: 状态机工具选择
- Hooks Manager: PreToolUse, PostToolUse, Stop 事件处理
- Focus Manager: 定期重新聚焦 (每5步)
- 工具分组: query_*, exec_*, skill_*, memory_* (按前缀)
```

## LangChain/LangGraph API 重要提示

⚠️ **LangChain 1.2.x API 变更**：
- ❌ 旧API (已弃用): `langchain.agents.AgentExecutor`, `langchain.agents.create_react_agent`
- ✅ 新API (推荐方式): `langchain.agents.create_agent`
- ✅ 备选方式: `langgraph.prebuilt.create_react_agent` (仍可用，但有弃用警告)

**推荐的 Agent 创建模式 (LangChain 1.2.8+)**：
```python
# 导入
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import StructuredTool
from langchain.agents import create_agent  # 新推荐位置
from langgraph.checkpoint.memory import MemorySaver

# 创建工具
from langchain_core.tools import tool

@tool
def my_tool(query: str) -> str:
    """工具描述"""
    return "结果"

tools = [my_tool]

# 创建模型
model = ChatAnthropic(model="claude-3-5-sonnet-20240620")

# 创建 Agent (推荐方式)
memory = MemorySaver()
agent_executor = create_agent(model, tools, checkpointer=memory)

# 使用 Agent
config = {"configurable": {"thread_id": "session-123"}}
response = agent_executor.invoke({"messages": [("user", "用户问题")]}, config)
```

**工具定义模式**：
```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class ToolInput(BaseModel):
    """工具输入"""
    query: str = Field(..., description="查询内容")

def my_function(input: ToolInput) -> str:
    """工具实现"""
    return f"结果: {input.query}"

tool = StructuredTool.from_function(
    func=my_function,
    name="my_tool",
    description="工具描述",
    args_schema=ToolInput
)
```

## 三层记忆管理系统

BA-Agent 使用基于 Clawdbot/Manus 的三层记忆管理系统。

### 记忆文件结构

| 层级 | 文件 | 内容 | 用途 |
|------|------|------|------|
| Layer 1 | `memory/YYYY-MM-DD.md` | 日常日志 | 临时笔记、当天讨论 |
| Layer 2 | `MEMORY.md` | 长期知识 | 持久事实、用户偏好、重要决策 |
| Layer 3 | `CLAUDE.md` | 项目记忆 | 团队共享知识、架构决策 |
| Layer 3 | `AGENTS.md` | 系统指令 | Agent 行为指南、记忆规则 |
| Layer 3 | `USER.md` | 用户信息 | 用户偏好、常见问题 |

### Manus 三文件模式

| 文件 | 用途 | 更新时机 |
|------|------|----------|
| `task_plan.md` | 任务进度跟踪 | 每完成一个阶段 |
| `findings.md` | 研究发现 | 发现重要信息时 |
| `progress.md` | 会话日志 | 每次工具调用后 |

### 记忆写入规则

| 触发条件 | 目标位置 | 示例 |
|----------|----------|------|
| 日常笔记 | `memory/YYYY-MM-DD.md` | "讨论了 API 设计" |
| 持久知识 | `MEMORY.md` | "用户偏好 TypeScript" |
| 重要决策 | `MEMORY.md` → `CLAUDE.md` | "选择 PostgreSQL" |

### 记忆管理工具

实现以下工具用于记忆管理：
- `memory_search`: 语义搜索 MEMORY.md + memory/*.md
- `memory_get`: 读取特定文件的特定行
- `memory_write`: 写入记忆 (自动选择 Layer 1 或 Layer 2)

## 渐进式工具使用系统

BA-Agent 使用基于 Clawdbot/Manus 的渐进式工具使用模式。

### 状态机工具选择

```
idle → query → analyzing → reporting → done
  ↑                                ↓
  └────────────────────────────────┘
```

| 状态 | 可用工具组 | 工具前缀 |
|------|-----------|----------|
| idle | 无 | - |
| query | query_* | query_database, read_file, web_search |
| analyzing | exec_*, skill_*, query_* | run_python, invoke_skill, query_database |
| reporting | skill_*, memory_* | invoke_skill, memory_write |
| done | 无 | - |

### 工具分组策略 (按前缀)

- `query_*`: 查询类工具 - 获取数据
- `exec_*`: 执行类工具 - 运行代码/命令
- `skill_*`: Skill 调用 - 调用可配置分析
- `memory_*`: 记忆管理 - 管理三层记忆

### Hooks 系统

| Hook | 触发时机 | 用途 |
|------|----------|------|
| PreToolUse | 工具调用前 | 权限检查、上下文注入 |
| PostToolUse | 工具调用后 | 日志记录、状态更新 |
| Stop | 会话结束时 | 验证完成、保存摘要 |
| UserPromptSubmit | 用户提交时 | 输入验证 |

### Hook 配置文件

位置: `.claude/hooks.json`

```json
{
  "hooks": [
    {
      "eventName": "PreToolUse",
      "matcher": {
        "toolName": ["execute_command", "run_python"]
      },
      "hook": "bash .claude/hooks/check-permissions.sh",
      "description": "检查执行权限"
    }
  ]
}
```

### 焦点管理 (Focus Manager)

**目的**: 避免目标漂移 (Goal Drift)

**机制**:
- 每 5 步重新读取 `task_plan.md`
- 将目标注入到上下文末尾
- 利用 LLM 对近端内容的注意力优势

**实现位置**: `backend/orchestration/focus_manager.py`

### 工具编排器 (Tool Orchestrator)

**核心功能**:
1. 状态机工具选择
2. 工具掩码 (按前缀分组)
3. 动态工具可见性控制
4. KV-cache 友好设计

**实现位置**: `backend/orchestration/tool_orchestrator.py`

### 渐进式工具使用示例

```python
from backend.orchestration.tool_orchestrator import ToolOrchestrator, AgentState
from backend.hooks.hook_manager import HookManager, HookEvent, HookContext
from backend.orchestration.focus_manager import FocusManager

# 初始化
orchestrator = ToolOrchestrator(all_tools)
hook_manager = HookManager(".claude/hooks.json")
focus_manager = FocusManager(workspace=".")

# 主循环
while orchestrator.get_state() != AgentState.DONE:
    # 获取当前状态允许的工具
    active_tools = orchestrator.get_active_tools()

    # LLM 决策 (只看到活跃工具)
    decision = llm.decide(context, tools=active_tools)

    if decision.action == "use_tool":
        # PreToolUse Hook
        pre_context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name=decision.tool,
            tool_args=decision.args
        )
        pre_result = hook_manager.trigger(HookEvent.PRE_TOOL_USE, pre_context)

        if not pre_result.blocked:
            # 执行工具
            result = execute_tool(decision.tool, decision.args)

            # PostToolUse Hook
            post_context = HookContext(
                event=HookEvent.POST_TOOL_USE,
                tool_name=decision.tool,
                tool_args=decision.args,
                tool_result=result
            )
            hook_manager.trigger(HookEvent.POST_TOOL_USE, post_context)

            # 状态转换
            orchestrator.transition(result.next_state)

    # 维持焦点
    focus_message = focus_manager.maintain_focus()
    if focus_message:
        context.add_system_message(focus_message)

# Stop Hook
hook_manager.trigger(HookEvent.STOP, HookContext(event=HookEvent.STOP))
```

## 停止条件

当以下条件满足时，回复 `<promise>COMPLETE</promise>`：
1. 所有 userStories 的 `passes` 为 `true`
2. 所有单元测试通过
3. 测试覆盖率 > 80%
4. 文档完整

## 重要提醒

⚠️ **安全第一**：
- Docker容器必须有资源限制
- 命令行和Python执行必须有白名单
- SQL查询必须参数化防止注入

⚠️ **代码质量**：
- 所有函数必须有类型注解
- 复杂逻辑必须有文档字符串
- 所有外部调用必须有错误处理

⚠️ **测试覆盖**：
- 每个工具必须有单元测试
- 每个Skill必须有单元测试
- Agent需要端到端测试

## 开发顺序建议

Priority 1 (基础设施):
1. US-001: 项目初始化 ✅ (已完成)
2. US-002: 核心数据模型 (Pydantic)
3. US-003: 配置管理
4. US-004: LangGraph Agent框架 (使用 langchain.agents.create_agent)
5. US-005: Docker环境配置

Priority 2 (记忆管理和渐进式工具使用):
6. US-005-MEM-01: 三层记忆文件结构创建 ✅ (已完成)
7. US-005-MEM-02: 记忆搜索工具 (memory_search)
8. US-005-MEM-03: 记忆读取工具 (memory_get)
9. US-005-MEM-04: 记忆写入工具 (memory_write)
10. US-005-MEM-05: Hooks系统实现
11. US-005-TOOL-01: Tool Orchestrator (工具编排器) ✅ (已完成)
12. US-005-TOOL-02: Focus Manager (焦点管理器) ✅ (已完成)
13. US-005-TOOL-03: Hooks配置和脚本 ✅ (已完成)

Priority 2 (核心工具):
14. US-006: 命令行工具
15. US-007: Python沙盒工具 (核心)
16. US-008: Web搜索
17. US-009: Web Reader
18. US-010: 文件读取
19. US-011: SQL查询
20. US-012: 向量检索
21. US-013: Skill调用工具 (核心)

Priority 2 (Skills系统):
22. US-014: Skills配置系统
23. US-015: 异动检测Skill
24. US-016: 归因分析Skill
25. US-017: 报告生成Skill
26. US-018: 数据可视化Skill

Priority 3 (集成):
27. US-019: Agent系统集成
28. US-020: 知识库初始化

Priority 4 (外部集成):
29. US-021: API服务
30. US-022: IM Bot
31. US-023: Excel插件

Priority 4 (质量保证):
32. US-024: 日志监控
33. US-025: 测试覆盖
34. US-026: 文档

---

**重要**: 在实现任何工具或 Agent 功能时，必须遵循以下原则：

1. **工具命名**: 使用前缀分组 (query_*, exec_*, skill_*, memory_*)
2. **状态感知**: 工具调用前检查当前状态是否允许
3. **Hooks 集成**: 所有工具调用都经过 Hooks 系统
4. **记忆更新**: 重要发现及时写入记忆文件
5. **焦点维护**: 每 5 步重新读取 task_plan.md

---

现在开始工作！请首先检查当前状态，然后选择优先级最高的待完成任务。
