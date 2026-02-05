# Skill System Integration - Plan A (Agent自主决策)

> **Version**: 1.0.0
> **Date**: 2026-02-05
> **Status**: ✅ Implemented

## Overview

Plan A implements a **meta-tool architecture** where the Agent uses LLM reasoning to decide when to activate skills based on semantic matching. This follows Claude Code's Agent Skills specification.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          BAAgent                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Tools Array:                                                   │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │ activate_skill (Meta-Tool)                               │  │   │
│  │  │  ┌────────────────────────────────────────────────────┐  │  │   │
│  │  │  │ Description contains all available skills:         │  │  │   │
│  │  │  │ - anomaly_detection: 检测数据异常...               │  │  │   │
│  │  │  │ - attribution: 分析指标变化...                     │  │  │   │
│  │  │  │ - report_gen: 生成分析报告...                      │  │  │   │
│  │  │  └────────────────────────────────────────────────────┘  │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │ other_tool                                               │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Skills System Components:                                      │   │
│  │  - SkillLoader: Scan and load skills                            │   │
│  │  - SkillRegistry: Cache skill metadata                          │   │
│  │  - SkillActivator: Activate skills and inject messages          │   │
│  │  - SkillMessageFormatter: Format messages for Agent             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

                          User Request
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Agent LLM          │
                    │   Semantic Matching  │
                    └──────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
            ┌─────────────┐      ┌──────────────┐
            │ Activate    │      │ Use Other    │
            │ Skill Tool  │      │ Tools        │
            └─────────────┘      └──────────────┘
                    │
                    ▼
            ┌─────────────────────┐
            │ SkillActivator      │
            │ .activate_skill()   │
            └─────────────────────┘
                    │
                    ▼
            ┌─────────────────────┐
            │ Inject Messages:    │
            │ 1. Metadata (vis.)  │
            │ 2. Instructions     │
            │    (hidden/isMeta)  │
            │ 3. Permissions      │
            └─────────────────────┘
                    │
                    ▼
            ┌─────────────────────┐
            │ Follow Skill        │
            │ Workflow            │
            └─────────────────────┘
```

## Implementation Details

### 1. Skill Meta-Tool Creation

**File**: `backend/skills/skill_tool.py`

The `create_skill_tool()` function creates a LangChain StructuredTool that wraps all available skills:

```python
def create_skill_tool(
    skill_registry: SkillRegistry,
    skill_activator: SkillActivator,
) -> Optional[BaseTool]:
    """Create a Skill meta-tool that wraps all available skills."""
    # Get formatted skills list
    skills_list = skill_registry.get_formatted_skills_list()

    # Build tool description with skills list
    description = f"""Activate a skill to provide specialized instructions...

**Available Skills:**
{skills_list}
...

**How to use:**
1. Match the user's request to a skill by semantic similarity
2. Invoke this tool with the skill name
3. The skill's instructions will be injected into the conversation
4. Follow the skill's workflow to complete the task
"""

    # Create LangChain tool
    return StructuredTool.from_function(
        name="activate_skill",
        description=description,
        func=_activate_skill_wrapper(skill_activator),
        args_schema=SkillActivationInput,
    )
```

**Key Points**:
- Tool description contains formatted list of all skills for semantic discovery
- Agent uses LLM reasoning to decide when to invoke based on user intent
- When invoked, loads full SKILL.md and injects into conversation

### 2. BAAgent Integration

**File**: `backend/agents/agent.py`

```python
class BAAgent:
    def __init__(self, ...):
        # ... existing setup ...

        # Initialize Skills System
        self.skill_loader = self._init_skill_loader()
        self.skill_registry = SkillRegistry(self.skill_loader) if self.skill_loader else None
        self.skill_activator = SkillActivator(
            self.skill_loader,
            self.skill_registry
        ) if self.skill_loader else None

        # Create Skill meta-tool and add to tools array
        self.skill_tool = self._init_skill_tool()
        if self.skill_tool:
            self.tools.append(self.skill_tool)

        # Active skill context modifier tracking
        self._active_skill_context: Dict[str, Any] = {}

    def _init_skill_tool(self) -> Optional[BaseTool]:
        """Initialize Skill meta-tool"""
        if self.skill_registry is None or self.skill_activator is None:
            return None
        return create_skill_tool(self.skill_registry, self.skill_activator)
```

### 3. Skill Activation Flow

When the Agent invokes the `activate_skill` tool:

```python
def _activate_skill_wrapper(skill_activator: SkillActivator):
    """Create a wrapper function for skill activation."""
    def _activate(skill_name: str) -> str:
        try:
            # Activate the skill
            messages, context_modifier = skill_activator.activate_skill(skill_name)

            # Log activation (hidden from user)
            logger.info(f"Activated skill '{skill_name}'...")

            # Return visible message to user
            # Actual skill instructions injected as hidden messages
            return f"Activated skill: {skill_name}"

        except SkillActivationError as e:
            return f"Failed to activate skill '{skill_name}': {str(e)}"

    return _activate
```

**Result**: Three messages are injected into the conversation:

1. **Metadata Message** (visible, `isMeta: false`):
   ```
   <command-message>The "异动检测" skill is loading</command-message>
   <command-name>anomaly_detection</command-name>
   ```

2. **Instruction Message** (hidden, `isMeta: true`):
   ```markdown
   # 异动检测分析 Skill

   ## 描述

   检测数据中的异常波动...

   ## 分析流程

   1. 理解需求
   2. 数据获取
   ...
   ```

3. **Permissions Message** (conditional, if `allowed_tools` specified):
   ```json
   {
     "type": "command_permissions",
     "allowed_tools": ["Read", "Write", "Bash(python:*)"],
     "model": "claude-sonnet-4-20250514"
   }
   ```

### 4. Three-Level Progressive Disclosure

| Level | What | When | Token Cost |
|-------|------|------|------------|
| **Level 1** | Skill frontmatter (name, description) | Agent startup | ~100 tokens/skill |
| **Level 2** | Full SKILL.md instructions | Skill activation | <5,000 tokens |
| **Level 3** | Resources (scripts/, references/, assets/) | On-demand via tools | Variable |

**Level 3 Example** (from SKILL.md):
```markdown
## 可用资源

- **脚本**: `{baseDir}/scripts/analysis.py` - 数据分析脚本
- **参考**: `{baseDir}/references/api.md` - API文档

## 使用流程

1. 运行分析脚本: 使用 Bash 工具执行 `python {baseDir}/scripts/analysis.py`
2. 查看参考文档: 使用 Read 工具加载 `{baseDir}/references/api.md`
```

The Agent follows these instructions using its normal tools (Read, Bash, etc.).

### 5. Context Modifier

When a skill is activated, the context modifier is returned:

```python
{
    "allowed_tools": ["Read", "Write", "Bash(python:*)"],
    "model": "claude-sonnet-4-20250514",
    "disable_model_invocation": False
}
```

This can be used to:
- Grant tool permissions without additional approval
- Switch to a different model for the task
- Prevent the skill from invoking the model itself

## Advantages of Plan A

1. **Semantic Discovery**: LLM reasoning-based matching vs algorithmic routing
2. **No Explicit Invocation**: Skills don't need to be explicitly called
3. **Progressive Disclosure**: Minimal token cost at startup
4. **Open Standard**: Compatible with Claude Code's skills format
5. **Context Injection**: Skills modify Agent behavior, not just return results

## File Changes

### New Files
- `backend/skills/skill_tool.py` - Skill meta-tool creation
- `tests/skills/test_skill_tool.py` - Skill tool tests (13 tests)
- `tests/skills/conftest.py` - Shared fixtures for skills tests

### Modified Files
- `backend/skills/__init__.py` - Added `create_skill_tool` export
- `backend/agents/agent.py` - Integrated skill tool into BAAgent
- `tests/test_agents/test_agent.py` - Updated tests for skill tool presence

## Test Results

```
tests/skills/ ................... 122 passed
tests/test_agents/test_agent.py .. 15 passed
Total: 137 skills + agent tests passing
```

## Example Workflow

**User**: "帮我检测一下GMV的异常波动"

1. **Agent LLM** sees user request and matches to `anomaly_detection` skill
2. **Agent** invokes `activate_skill` tool with `skill_name="anomaly_detection"`
3. **SkillActivator** loads full SKILL.md and injects messages
4. **Agent** reads skill instructions and follows workflow:
   - Use `query_database` tool to get GMV data
   - Use `python_sandbox` tool to detect anomalies (3-sigma method)
   - Generate analysis report
5. **Agent** returns results to user

## Comparison with Claude Code

| Feature | BA-Agent (Plan A) | Claude Code |
|---------|------------------|-------------|
| Meta-tool architecture | ✅ `activate_skill` | ✅ `Skill` |
| Progressive disclosure | ✅ 3 levels | ✅ 3 levels |
| Semantic matching | ✅ LLM reasoning | ✅ LLM reasoning |
| Context injection | ✅ Messages + permissions | ✅ Messages + permissions |
| Resource loading | ✅ Via SKILL.md instructions | ✅ Via SKILL.md instructions |
| Open standard | ✅ Compatible | ✅ Originator |

## Next Steps

1. ✅ Create skill meta-tool
2. ✅ Integrate with BAAgent
3. ✅ Add tests
4. ⏳ Implement context modifier application in conversation flow
5. ⏳ Add skill lifecycle management (activate/deactivate)
6. ⏳ Implement skill dependencies
