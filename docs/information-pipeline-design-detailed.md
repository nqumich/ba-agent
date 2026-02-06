# BA-Agent Information Pipeline Design Document

> **Date**: 2026-02-06
> **Version**: v2.0.0 (LangChain Implementation Alignment)
> **Author**: BA-Agent Development Team
> **Status**: Design Phase

---

## v2.0.0 Major Update

This version aligns the design document with the actual BA-Agent implementation using **LangChain ChatAnthropic + Synchronous Tools**.

**Key Changes**:
1. **Carrier vs Semantic separation**: Explicit distinction between Observation (semantic) and Carrier (transport)
2. **LangChain as primary protocol**: BaseMessage (HumanMessage/AIMessage/ToolMessage) is the main message format
3. **Claude Code format demoted**: StandardMessage is now "external/research format" only
4. **Tool result conversion**: `to_tool_message()` returns ToolMessage, `to_user_message()` deprecated
5. **tool_call_id source**: Clarified that tool_call_id comes from AIMessage.tool_calls, not generated
6. **Synchronous compression**: Removed async compression, added background thread for LLM summarization
7. **OutputLevel clarification**: Changed from "Progressive Disclosure" to "verbosity/detail level"

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Core Concepts Clarification](#core-concepts-clarification)
3. [Claude Code Research Findings](#claude-code-research-findings)
4. [Proposed Information Pipeline Architecture](#proposed-information-pipeline-architecture)
5. [Configuration Classes](#configuration-classes)
5. [Message Format Specifications](#message-format-specifications)
6. [Tool ↔ Agent Communication Protocol](#tool--agent-communication-protocol)
7. [Skill ↔ Agent Communication Protocol](#skill--agent-communication-protocol)
8. [Multi-Round Conversation Flow](#multi-round-conversation-flow)
9. [Context Management Strategy](#context-management-strategy)
10. [Implementation Roadmap](#implementation-roadmap)

---

## Configuration Classes

> **v1.9.4 新增**: 统一的配置类架构

所有配置类都实现了统一的接口：

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseConfig(ABC):
    """配置类基类接口"""

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseConfig":
        """从字典创建配置"""
        ...

    @abstractmethod
    def validate(self) -> bool:
        """验证配置有效性"""
        ...
```

### 配置类列表

| 配置类 | 用途 | 格式 |
|--------|------|------|
| `EncoderConfig` | Token 编码器配置 | @dataclass |
| `ContextCompressionConfig` | 上下文压缩配置 | 普通类 |
| `ObservabilityConfig` | 可观测性配置 | @dataclass |

### 统一方法

所有配置类支持：
- `to_dict()`: 序列化为字典
- `from_dict()`: 从字典反序列化
- `validate()`: 验证配置有效性

### 使用示例

```python
# 序列化配置
config = ContextCompressionConfig()
config_dict = config.to_dict()

# 保存到文件
import json
with open("config.json", "w") as f:
    json.dump(config_dict, f)

# 从文件加载
with open("config.json") as f:
    loaded = ContextCompressionConfig.from_dict(json.load(f))

# 验证配置
loaded.validate()  # 抛出 ValueError 如果无效
```

---

## Executive Summary

This document defines the comprehensive information pipeline architecture for BA-Agent, based on research into Claude Code, Manus AI, and OpenManus implementations.

### Key Design Principles

1. **Simple Message Format**: Follow Claude Code's straightforward message structure
2. **ReAct Execution Loop**: Agent uses Thought→Action→Observation pattern for reasoning
3. **Simple Tool Output**: Tools return plain observation strings, not complex multi-layer formats
4. **Progressive Disclosure**: Applied to Skills system (metadata → full instruction → resources)
5. **Context Modifiers**: Skills can modify agent execution context
6. **Efficient Memory Management**: Context compression and token optimization

---

## Core Concepts Clarification

> **CRITICAL**: This section clarifies three concepts that were previously conflated.

### Concept 1: ReAct Pattern (Agent Execution Loop)

**ReAct** (Reasoning + Acting) is the **agent's execution pattern**, NOT a tool output format.

```
Thought: I need to search for weather information in Yangzhou
Action: call web_search("扬州天气")
Observation: [tool execution result - plain string]
Thought: Based on the weather data, I should also check tomorrow's forecast
Action: call web_search("扬州明天天气")
Observation: [tool execution result - plain string]
Thought: I now have all the information to answer the user
Final Answer: The weather in Yangzhou today is...
```

**Key Points**:
- **Thought**: Agent's internal reasoning (visible in extended thinking mode)
- **Action**: Tool invocation (tool_use content block)
- **Observation**: The tool's execution result (tool_result content block)
- This is a **control flow pattern**, not a data format

### Concept 2: Tool Output Format

**Tool Output** has THREE ORTHOGONAL aspects:

1. **ReAct Observation** (Semantic): What information the tool returns for Agent reasoning
2. **Output Level** (Engineering): How detailed the observation is (token optimization)
3. **Carrier** (Transport): How the observation is delivered to the LLM

These are INDEPENDENT concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Tool Output Design                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ReAct Observation (Semantic)         Output Level (Engineering)│
│  ────────────────────────────────     ───────────────────────│
│  • What the LLM sees and reasons      • BRIEF: Key facts only │
│  • The actual content string          • STANDARD: Usable info │
│  • Direct input to next Thought        • FULL: Complete data  │
│                                                              │
│  Example: File search tool            Example: Same data,     │
│  observation: "Found 3 .py files"     different formatting:  │
│                                        BRIEF:   "3 files"     │
│                                        STANDARD: "file1.py..."│
│                                        FULL:    [all paths]  │
│                                                              │
│  Carrier (Transport)                                           │
│  ────────────────────────                                    │
│  • Research Layer (Claude Code):    role="user" tool_result   │
│  • Implementation Layer (LangChain): ToolMessage              │
│  • Carrier is chosen by framework, NOT by tool logic         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Research Layer (Claude Code Format)**:
```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "call_abc123",
      "content": "File found: /path/to/file.py\nAnother file: /path/to/another.py",
      "is_error": false
    }
  ]
}
```

**Implementation Layer (LangChain ChatAnthropic)**:
```python
from langchain_core.messages import ToolMessage

# Tool execution produces observation string
observation = "File found: /path/to/file.py\nAnother file: /path/to/another.py"

# Carrier: ToolMessage with tool_call_id from AIMessage.tool_calls
tool_message = ToolMessage(
    content=observation,
    tool_call_id="call_abc123"  # Must match AIMessage.tool_calls[0]["id"]
)
```

**Key Points**:
- **Observation** (Semantic) remains constant: plain string that LLM reasons with
- **Carrier** varies by framework:
  - Claude Code: `role="user"` with `type="tool_result"` block
  - LangChain: `ToolMessage(content=observation, tool_call_id=...)`
- **Output Level** controls HOW we format the observation from raw data
- **No** summary/observation/result three-layer structure (that was confusion)
- The agent sees the tool result as a simple text observation regardless of carrier

### Concept 3: Progressive Disclosure

**Progressive Disclosure** is an **information presentation strategy** for the Skills system.

```
Level 1: Frontmatter (~100 tokens/skill)
  ├── skill name, description, capabilities
  └── Loaded at startup for all skills

Level 2: Full SKILL.md (~5000 tokens/skill)
  ├── Complete instructions
  └── Loaded when skill is activated

Level 3: Resource files
  ├── scripts/, references/, assets/
  └── Loaded on-demand as needed
```

**Key Points**:
- Applied to **Skills system** only
- Optimizes token usage by loading info progressively
- Not related to tool output format
- Not related to ReAct execution loop

### Summary of Separation

| Concept | Purpose | Scope | Example |
|---------|---------|-------|---------|
| **ReAct** | Agent reasoning pattern | Control flow | Thought → Action → Observation loop |
| **ReAct Observation** | What tool returns | Semantic (content) | "Found 3 Python files" |
| **Output Level** | How detailed to format | Engineering (token) | BRIEF/STANDARD/FULL |
| **Carrier** | How observation is delivered | Transport layer | ToolMessage / tool_result block |
| **Progressive Disclosure** | Information loading strategy | Skills system | Level 1→2→3 for Skills |

These are **FIVE separate concepts**:
1. **ReAct**: The reasoning loop pattern
2. **Observation**: The semantic content returned by tools
3. **Output Level**: How detailed to format the observation (orthogonal to observation)
4. **Carrier**: Transport mechanism for delivering observation to LLM (framework-dependent)
5. **Progressive Disclosure**: How to load skill information (unrelated to tools)

---

## Claude Code Research Findings

### 1. Message Format Structure

Based on tracing Claude Code's LLM traffic:

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Find all Python files in the project",
          "cache_control": {"type": "ephemeral"}
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {
          "type": "thinking",
          "thinking": "I need to search for Python files using the Glob tool..."
        },
        {
          "type": "tool_use",
          "id": "call_xxx",
          "name": "Glob",
          "input": {"pattern": "**/*.py"}
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "tool_result",
          "tool_use_id": "call_xxx",
          "content": "src/main.py\nutils/helpers.py\ntests/test_main.py",
          "is_error": false
        }
      ]
    }
  ]
}
```

### 2. Critical Insights

1. **Tool results are user messages** (Research Layer): Claude Code receives tool results as `role: "user"` messages
2. **Observation = ReAct Observation**: The `content` field IS the Observation that LLM reasons with
3. **Output Level ≠ ReAct**: Output level controls formatting detail, orthogonal to the Observation semantic
4. **ReAct is execution flow**: The Thought→Action→Observation pattern is how the agent reasons, not a data format
5. **Minimal wrapping**: No unnecessary layers between tool execution and agent observation

### 2.1 Implementation Layer (LangChain ChatAnthropic)

**IMPORTANT**: The research layer format above is for reference. BA-Agent's actual implementation uses LangChain's message protocol.

**LangChain Tool-Call Loop**:
```python
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Step 1: User sends message
messages = [HumanMessage(content="Find all Python files")]

# Step 2: LLM responds with AIMessage containing tool_calls
ai_message = AIMessage(
    content="",
    tool_calls=[{
        "id": "call_abc123",      # Generated by LLM
        "name": "Glob",
        "args": {"pattern": "**/*.py"}
    }]
)
messages.append(ai_message)

# Step 3: Execute tool, create ToolMessage with matching tool_call_id
tool_result = execute_tool("Glob", {"pattern": "**/*.py"})
tool_message = ToolMessage(
    content=tool_result,           # Observation string
    tool_call_id="call_abc123"     # MUST match AIMessage.tool_calls[0]["id"]
)
messages.append(tool_message)

# Step 4: LLM processes tool result and generates next response
next_ai_message = llm.invoke(messages)
```

**Key Implementation Constraints**:
- **tool_call_id source**: MUST come from `AIMessage.tool_calls[i]["id"]`, NOT generated by tool
- **Carrier**: Use `ToolMessage(content=observation, tool_call_id=...)` NOT `role="user"` blocks
- **Synchronous tools**: All tool functions are `def` (not `async def`), executed synchronously
- **ReAct loop**: AIMessage(tool_calls) → ToolMessage(result) → AIMessage(next_action/answer)

**Comparison**:

| Aspect | Research (Claude Code) | Implementation (LangChain) |
|--------|------------------------|---------------------------|
| Tool call format | `type: "tool_use"` in AIMessage | `AIMessage.tool_calls` list |
| Tool call ID | LLM-generated in block | LLM-generated in `.tool_calls[i]["id"]` |
| Tool result carrier | `role: "user"`, `type: "tool_result"` | `ToolMessage` class |
| Result ID reference | `tool_use_id` field | `tool_call_id` parameter |
| Tool execution | Async (internal) | Sync (`def` functions) |

### 3. Observation Formatting by Output Level

```python
def _format_brief(data: Any) -> str:
    """Format observation: BRIEF level - key facts only"""
    if isinstance(data, list):
        return f"Found {len(data)} items"
    elif isinstance(data, dict):
        if "success" in data:
            status = "Success" if data["success"] else "Failed"
            return f"{status}: {data.get('message', 'Operation completed')}"
        return f"Result has {len(data)} fields"
    return str(data)[:100]

def _format_standard(data: Any) -> str:
    """Format observation: STANDARD level - actionable information"""
    if isinstance(data, list):
        # Show first few items + count
        preview = data[:3]
        items_str = "\n".join(f"  - {item}" for item in preview)
        more = f"\n  ... and {len(data) - 3} more" if len(data) > 3 else ""
        return f"Found {len(data)} items:\n{items_str}{more}"
    elif isinstance(data, dict):
        # Show key fields
        return json.dumps(data, ensure_ascii=False, indent=2)[:500]
    return str(data)[:500]

def _format_full(data: Any) -> str:
    """Format observation: FULL level - complete data"""
    return json.dumps(data, ensure_ascii=False, indent=2)
```

### 3. Sub-Agent Communication

**Parent → Sub-Agent**:
```json
{
  "type": "tool_use",
  "id": "call_eev71b93",
  "name": "Task",
  "input": {
    "description": "Explore codebase",
    "prompt": "...",
    "subagent_type": "Explore"
  }
}
```

**Sub-Agent → Parent**:
```json
{
  "type": "tool_result",
  "tool_use_id": "call_eev71b93",
  "content": [
    {
      "type": "text",
      "text": "## Exploration Report\n\nFound 15 Python files..."
    }
  ]
}
```

### 4. Progressive Disclosure in Practice

Claude Code uses progressive disclosure for **skills/plugins**, not for tool outputs:

- **Discovery Phase**: Plugin metadata only (~100 tokens)
- **Activation Phase**: Full plugin instructions loaded
- **Execution Phase**: Resource files loaded as needed

---

## Proposed Information Pipeline Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         BA-Agent System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   User       │─────>│   BAAgent    │─────>│   Tools      │  │
│  │  Interface   │      │   (LangGraph) │      │  (LangChain) │  │
│  └──────────────┘      └──────┬───────┘      └──────────────┘  │
│                                │                                  │
│                                v                                  │
│                         ┌──────────────┐                         │
│                         │  Skill       │                         │
│                         │  System      │                         │
│                         │ (Meta-Tool)  │                         │
│                         │              │                         │
│                         │ Progressive  │                         │
│                         │ Disclosure:   │                         │
│                         │ L1→L2→L3     │                         │
│                         └──────────────┘                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Message Flow

```
User Request
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Request Processing                                 │
│  - Parse user message                                        │
│  - Load system prompt                                        │
│  - Check active skill context                                │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Agent Reasoning (ReAct Loop)                       │
│  - Thought: What do I need to do?                            │
│  - Action: Which tool should I call?                         │
│  - Observation: What did the tool return?                    │
│  - Repeat until task complete                                │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Tool Execution                                     │
│  - Permission check (Context Modifier)                       │
│  - Tool invocation                                           │
│  - Return simple observation string                          │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Skill Activation (if needed)                       │
│  - Progressive Disclosure: Level 1 → Level 2 → Level 3      │
│  - Inject messages into conversation                         │
│  - Apply Context Modifier                                    │
└─────────────────────────────────────────────────────────────┘
    ↓
Final Response
```

### Sequence Diagrams

#### 1. Standard ReAct Execution Flow

```
User          BAAgent         Tool          LangGraph
  │              │              │               │
  │──Request────>│              │               │
  │              │              │               │
  │              │<─Messages───────────────────│
  │              │              │               │
  │              │──Thought────────────────────>│
  │              │<─What to do next────────────│
  │              │              │               │
  │              │──Action──────>│               │
  │              │<─Result──────│               │
  │              │              │               │
  │              │─Observation─────────────────>│
  │              │              │               │
  │              │<─Next Thought───────────────│
  │              │              │               │
  │ [Loop continues until task complete]
  │              │              │               │
  │<─Response────│              │               │
```

#### 2. Skill Activation with Progressive Disclosure

```
User          BAAgent      SkillSystem      LangGraph
  │              │              │                │
  │──Request────>│              │                │
  │              │              │                │
  │              │──Get Metadata───────────────>│
  │              │<─Level 1 (~100 tokens)──────│
  │              │              │                │
  │              │──Select Skill────────────────│
  │              │              │                │
  │              │──Activate────────────────────>│
  │              │              │                │
  │              │<─Level 2 (~5000 tokens)──────│
  │              │              │                │
  │              │──Inject─────────────────────>│
  │              │              │                │
  │              │──ApplyModifier──────────────>│
  │              │              │                │
  │              │<─ModifiedContext────────────│
  │              │              │                │
  │<─Response────│              │                │
```

---

## Message Format Specifications

> **IMPORTANT**: BA-Agent uses **LangChain BaseMessage** as its primary message protocol. The Claude Code format below is provided for research/reference/debugging purposes only.

### 1. Internal Message Format (Primary) - LangChain BaseMessage

**This is the actual message protocol used in production.**

```python
from langchain_core.messages import (
    HumanMessage,    # User input
    AIMessage,       # LLM responses (may contain tool_calls)
    ToolMessage,     # Tool execution results
    SystemMessage    # System prompts
)

# Example: Tool execution flow
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

# User message
human_msg = HumanMessage(content="Find all Python files")

# LLM responds with tool call
ai_msg = llm.invoke([human_msg])
# ai_msg.tool_calls = [{"id": "call_123", "name": "Glob", "args": {...}}]

# Tool executes and returns ToolMessage
tool_msg = ToolMessage(
    content="file1.py\nfile2.py\nfile3.py",  # Observation string
    tool_call_id=ai_msg.tool_calls[0]["id"]  # MUST match
)

# LLM processes result
next_msg = llm.invoke([human_msg, ai_msg, tool_msg])
```

**Key Principles**:
1. **tool_call_id source**: Always from `AIMessage.tool_calls[i]["id"]`, never generated by tools
2. **ToolMessage content**: Plain observation string (the ReAct Observation)
3. **Synchronous execution**: Tools are `def` functions, executed synchronously
4. **Loop pattern**: AIMessage(tool_calls) → ToolMessage(result) → AIMessage(next)

### 2. External/Research Format (Optional) - Claude Code Blocks

**This format is used for research, debugging, and Claude Code compatibility.**

```python
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum

class MessageType(str, Enum):
    """Message type identifiers"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ContentBlockType(str, Enum):
    """Content block types (Claude Code format)"""
    TEXT = "text"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"

class ContentBlock(BaseModel):
    """Standardized content block (research/debugging only)"""
    type: ContentBlockType

    # Text content
    text: Optional[str] = None

    # Thinking content
    thinking: Optional[str] = None

    # Tool use specific
    id: Optional[str] = None        # tool_use id
    name: Optional[str] = None      # tool name
    input: Optional[Dict[str, Any]] = None    # tool arguments

    # Tool result specific
    tool_use_id: Optional[str] = None  # references tool_use id
    is_error: bool = False

    # Caching
    cache_control: Optional[Dict[str, str]] = None

class StandardMessage(BaseModel):
    """Claude Code compatible message format (for research/debugging)"""
    role: MessageType
    content: List[ContentBlock]

    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Context
    conversation_id: str = ""
    user_id: str ""

    def to_langchain_format(self) -> Dict[str, Any]:
        """Convert to LangChain message format"""
        return {
            "role": self.role.value,
            "content": [block.model_dump(exclude_none=True) for block in self.content],
            "timestamp": self.timestamp,
            "message_id": self.message_id,
        }
```

**Usage Note**: This format is **NOT** used in the actual BA-Agent implementation. It exists only for:
- Research and reference
- Debugging message structures
- Compatibility testing with Claude Code
- Documentation examples

The actual system uses `HumanMessage`, `AIMessage`, and `ToolMessage` from LangChain.

### 2. Tool Call Format

```python
class ToolCallMessage(BaseModel):
    """Format for tool invocation (from Agent)"""
    tool_call_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    parameters: Dict[str, Any]

    def to_content_block(self) -> ContentBlock:
        """Convert to ContentBlock for LLM"""
        return ContentBlock(
            type=ContentBlockType.TOOL_USE,
            id=self.tool_call_id,
            name=self.tool_name,
            input=self.parameters
        )
```

### 3. Tool Result Format (SIMPLE + Output Level Control + File Storage)

```python
import tempfile
from pathlib import Path
from typing import Optional
import hashlib
import json

class OutputLevel(str, Enum):
    """
    Controls the detail level (verbosity) of observation formatting.

    This is an ENGINEERING optimization for token efficiency,
    orthogonal to ReAct Observation (semantic concept).

    NOTE: OutputLevel is NOT "Progressive Disclosure" (which applies
    to Skills system information loading). OutputLevel simply controls
    how verbose the tool result observation should be.

    Decision mechanism (priority order):
    1. Agent specifies in ToolCallMessage.parameters
    2. Tool-specific default from config
    3. Global default from settings (STANDARD)
    4. Dynamic adjustment based on context window usage
    """
    BRIEF = "brief"       # Key facts only (e.g., "Found 5 records")
    STANDARD = "standard" # Actionable information (e.g., record list summary)
    FULL = "full"         # Complete data (e.g., full JSON output)

class ToolResultMessage(BaseModel):
    """Format for tool execution results - Claude Code compatible"""
    tool_call_id: str  # References ToolCallMessage.tool_call_id

    # ReAct Observation: What the LLM sees and reasons with
    # This is formatted according to output_level
    observation: str

    # Control observation detail level (Progressive Disclosure)
    output_level: OutputLevel = OutputLevel.STANDARD

    # Data storage (file-based to avoid memory issues)
    # For large data, store in file and provide path reference
    data_file: Optional[str] = None  # Path to stored data file
    data_size_bytes: int = 0         # Track actual data size
    data_hash: Optional[str] = None   # For deduplication

    # Summary for FULL level (generated by small model)
    data_summary: Optional[str] = None

    # Status
    success: bool = True
    error_code: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_raw_data(
        cls,
        tool_call_id: str,
        raw_data: Any,
        output_level: OutputLevel = OutputLevel.STANDARD,
        storage_dir: Optional[Path] = None
    ) -> "ToolResultMessage":
        """
        Create ToolResultMessage from raw data with specified output level.

        Storage strategy:
        - BRIEF/STANDARD: observation only, no file storage
        - FULL: Store data in file, observation contains summary + reference
        - Large data (>1MB): Always use file storage
        """
        data_str = json.dumps(raw_data, ensure_ascii=False)
        data_size = len(data_str.encode('utf-8'))
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        # Decide if we need file storage
        use_file = (
            output_level == OutputLevel.FULL or
            data_size > 1024 * 1024  # > 1MB
        )

        data_file = None
        data_summary = None

        if use_file and storage_dir:
            # Store data in file
            storage_dir = Path(storage_dir) / "tool_data"
            storage_dir.mkdir(parents=True, exist_ok=True)

            file_name = f"{tool_call_id}_{data_hash}.json"
            file_path = storage_dir / file_name

            with open(file_path, 'w') as f:
                f.write(data_str)

            data_file = str(file_path)

            # Generate summary for FULL level
            data_summary = cls._generate_summary(raw_data)

        # Format observation based on output_level
        observation = cls._format_observation(raw_data, output_level, data_file)

        return cls(
            tool_call_id=tool_call_id,
            observation=observation,
            output_level=output_level,
            data_file=data_file,
            data_size_bytes=data_size,
            data_hash=data_hash,
            data_summary=data_summary,
            success=True
        )

    @staticmethod
    def _generate_summary(raw_data: Any) -> str:
        """
        Generate summary of data (can use small model for complex data).

        For structured data, extract key info directly.
        For unstructured (text, code), use LLM to summarize.
        """
        if isinstance(raw_data, list):
            return f"List with {len(raw_data)} items. " + \
                   f"First item keys: {list(raw_data[0].keys()) if raw_data and isinstance(raw_data[0], dict) else 'N/A'}"
        elif isinstance(raw_data, dict):
            keys = list(raw_data.keys())[:10]
            return f"Dictionary with {len(raw_data)} keys. " + \
                   f"Top keys: {', '.join(keys)}"
        else:
            # For complex data, would call small LLM here
            return str(raw_data)[:200]

    @staticmethod
    def _format_observation(
        raw_data: Any,
        level: OutputLevel,
        data_file: Optional[str] = None
    ) -> str:
        """Format observation according to output level"""
        if level == OutputLevel.BRIEF:
            return ToolResultMessage._format_brief(raw_data)
        elif level == OutputLevel.STANDARD:
            return ToolResultMessage._format_standard(raw_data)
        else:  # FULL
            if data_file:
                # Return file reference for large data
                return f"""Data stored in file: {data_file}
This file can be accessed in subsequent tool calls by referencing the file path.

To access this data, use:
- file_reader tool with the file path
- Or reference in tool_call_id for direct access

Data summary: {ToolResultMessage._generate_summary(raw_data)}"""
            else:
                # Small data, return directly
                return json.dumps(raw_data, ensure_ascii=False, indent=2)

    @staticmethod
    def _format_brief(data: Any) -> str:
        """Format observation: BRIEF level - key facts only"""
        if isinstance(data, list):
            return f"Found {len(data)} items"
        elif isinstance(data, dict):
            if "success" in data:
                status = "Success" if data["success"] else "Failed"
                return f"{status}: {data.get('message', 'Operation completed')}"
            return f"Result has {len(data)} fields"
        return str(data)[:100]

    @staticmethod
    def _format_standard(data: Any) -> str:
        """Format observation: STANDARD level - actionable information"""
        if isinstance(data, list):
            preview = data[:3]
            items_str = "\n".join(f"  - {item}" for item in preview)
            more = f"\n  ... and {len(data) - 3} more" if len(data) > 3 else ""
            return f"Found {len(data)} items:\n{items_str}{more}"
        elif isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False, indent=2)[:500]
        return str(data)[:500]

    def format_error_observation(self) -> str:
        """
        Standardized error observation format.

        Ensures consistent error format across all tools for Agent processing.
        """
        if not self.success:
            return f"""Operation failed.

Error Type: {self.error_type or 'Unknown'}
Error Code: {self.error_code or 'UNKNOWN'}
Error Message: {self.error_message or 'An unknown error occurred'}

Tool Call ID: {self.tool_call_id}"""
        return self.observation

    def to_content_block(self) -> ContentBlock:
        """Convert to ContentBlock for LLM"""
        content = self.format_error_observation() if not self.success else self.observation
        return ContentBlock(
            type=ContentBlockType.TOOL_RESULT,
            tool_use_id=self.tool_call_id,
            content=content,
            is_error=not self.success
        )

    def to_tool_message(self):
        """
        Convert to LangChain ToolMessage for LLM.

        This is the PRIMARY method for BA-Agent implementation.
        Returns a ToolMessage that can be directly added to the message list.

        Args:
            tool_call_id: The ID from AIMessage.tool_calls[i]["id"]

        Returns:
            ToolMessage with observation as content

        Example:
            from langchain_core.messages import ToolMessage

            # After tool execution
            tool_msg = result.to_tool_message()
            messages.append(tool_msg)  # Add to conversation
        """
        from langchain_core.messages import ToolMessage

        content = self.format_error_observation() if not self.success else self.observation

        return ToolMessage(
            content=content,
            tool_call_id=self.tool_call_id
        )

    def to_user_message(self) -> StandardMessage:
        """
        Convert to StandardMessage (Claude Code format).

        DEPRECATED: Use to_tool_message() for LangChain implementation.
        This method exists only for research/debugging compatibility.
        """
        return StandardMessage(
            role=MessageType.USER,
            content=[self.to_content_block()]
        )
```

**Design Decision**:
1. **Single observation field**: The ReAct Observation that LLM sees
2. **Output level control**: Verbosity/detail level for token optimization (NOT Progressive Disclosure)
3. **File-based storage**: Large data stored in files, not memory
4. **Data summary**: Generated for FULL level to provide context
5. **Standardized error format**: Consistent error structure for Agent processing
6. **OutputLevel decision**: Parameter → Tool config → Global default → Dynamic
7. **Primary conversion**: `to_tool_message()` returns LangChain ToolMessage
8. **Legacy conversion**: `to_user_message()` for Claude Code format (deprecated)

**Example Usage**:
```python
# Same raw data, different observation formats based on level
raw_data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}, ...]

# BRIEF level
ToolResultMessage.from_raw_data("call_123", raw_data, OutputLevel.BRIEF)
# observation: "Found 10 items"

# STANDARD level
ToolResultMessage.from_raw_data("call_123", raw_data, OutputLevel.STANDARD)
# observation: "Found 10 items:\n{'id': 1, 'name': 'Alice'}\n{'id': 2, 'name': 'Bob'}..."

# FULL level
ToolResultMessage.from_raw_data("call_123", raw_data, OutputLevel.FULL)
# observation: "[{\"id\": 1, \"name\": \"Alice\"}, ...]"  # Full JSON
```

---

## Tool ↔ Agent Communication Protocol

### Protocol Specification

#### Phase 1: Tool Invocation Request

**Direction**: Agent → Tool

**CRITICAL: tool_call_id Source**

The `tool_call_id` MUST come from the LLM's response (`AIMessage.tool_calls[i]["id"]`), NOT be generated by the request or tool.

```python
# CORRECT: Extract tool_call_id from AIMessage
ai_message = llm.invoke(messages)
for tool_call in ai_message.tool_calls:
    tool_call_id = tool_call["id"]  # From LLM
    tool_name = tool_call["name"]
    parameters = tool_call["args"]

    request = ToolInvocationRequest(
        tool_call_id=tool_call_id,  # From AIMessage
        tool_name=tool_name,
        parameters=parameters,
        ...
    )

# WRONG: Do NOT generate tool_call_id
request = ToolInvocationRequest(
    tool_call_id=str(uuid.uuid4()),  # ❌ Never do this
    ...
)
```

```python
class ToolInvocationRequest(BaseModel):
    """Request format when Agent calls a tool"""
    # CRITICAL: tool_call_id comes from AIMessage.tool_calls[i]["id"]
    # DO NOT generate this value - it must match the LLM's tool call
    tool_call_id: str

    # Tool identification
    tool_name: str
    tool_version: str = "1.0.0"

    # Parameters
    parameters: Dict[str, Any]

    # Output level control (priority: parameter > tool config > global default)
    output_level: Optional[OutputLevel] = None

    # Execution context
    timeout_ms: int = 120000
    retry_on_timeout: bool = True  # Auto-retry on timeout

    # Storage context (for large data)
    storage_dir: Optional[str] = None  # Where to store large data files

    # Security
    caller_id: str  # Agent or skill ID
    permission_level: str = "default"

    # Idempotency (optional)
    idempotency_key: Optional[str] = None

    def get_or_generate_idempotency_key(self) -> str:
        """Get or generate idempotency key for caching tool results"""
        if self.idempotency_key:
            return self.idempotency_key
        # Generate from tool_call_id + parameters hash
        import hashlib
        params_str = json.dumps(self.parameters, sort_keys=True)
        return hashlib.md5(f"{self.tool_call_id}:{params_str}".encode()).hexdigest()

    def get_effective_output_level(
        self,
        tool_config_default: Optional[OutputLevel] = None,
        global_default: OutputLevel = OutputLevel.STANDARD,
        context_window_usage: float = 0.0
    ) -> OutputLevel:
        """
        Determine effective output level with fallback chain.

        Priority:
        1. Explicit parameter (self.output_level)
        2. Tool-specific config (tool_config_default)
        3. Global default (global_default)
        4. Dynamic adjustment based on context window usage

        Args:
            tool_config_default: Default from tool configuration
            global_default: Global system default
            context_window_usage: Current context usage (0.0-1.0)

        Returns:
            Effective output level for this tool call
        """
        # Level 1: Explicit parameter
        if self.output_level is not None:
            return self.output_level

        # Level 2: Tool-specific config
        if tool_config_default is not None:
            return tool_config_default

        # Level 4: Dynamic adjustment (if context window is nearly full)
        if context_window_usage > 0.8:
            return OutputLevel.BRIEF  # Force brief for nearly-full context

        # Level 3: Global default
        return global_default
```

#### Phase 1.5: Retry Policy Configuration

```python
class ToolRetryPolicy(BaseModel):
    """Retry configuration for tool execution"""
    max_retries: int = 3
    retry_on: List[ToolErrorType] = Field(
        default_factory=lambda: [ToolErrorType.TIMEOUT, ToolErrorType.RESOURCE_ERROR]
    )
    backoff_multiplier: float = 1.5
    initial_delay_ms: int = 1000
    max_delay_ms: int = 10000

    # Timeout-specific handling
    timeout_multiplier: float = 2.0  # Increase timeout on retry
    max_timeout_ms: int = 300000     # 5 minutes max

    def should_retry(self, error_type: ToolErrorType, attempt: int) -> bool:
        """Check if operation should be retried"""
        return error_type in self.retry_on and attempt < self.max_retries

    def get_delay(self, attempt: int) -> int:
        """Calculate delay with exponential backoff"""
        delay = self.initial_delay_ms * (self.backoff_multiplier ** attempt)
        return min(int(delay), self.max_delay_ms)

    def get_retry_timeout(self, original_timeout: int, attempt: int) -> int:
        """Calculate timeout for retry attempt"""
        new_timeout = original_timeout * (self.timeout_multiplier ** attempt)
        return min(int(new_timeout), self.max_timeout_ms)
```

#### Phase 2: Tool Execution Result (Observation + Output Level + Retry Support)

**Direction**: Tool → Agent

```python
class ToolExecutionResult(BaseModel):
    """Result format from tool execution"""
    request_id: str

    # ReAct Observation: What LLM sees (semantic concept)
    observation: str

    # Output Level: How detailed the observation is (engineering optimization)
    output_level: OutputLevel = OutputLevel.STANDARD

    # Data storage (file-based for large data)
    data_file: Optional[str] = None
    data_size_bytes: int = 0
    data_summary: Optional[str] = None

    # Retry tracking
    retry_count: int = 0
    last_error: Optional[str] = None

    # Status
    success: bool
    error_code: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Timing
    duration_ms: float = 0.0

    @classmethod
    def from_raw(
        cls,
        request_id: str,
        raw_data: Any,
        output_level: OutputLevel = OutputLevel.STANDARD,
        storage_dir: Optional[str] = None
    ) -> "ToolExecutionResult":
        """
        Create result from raw data with specified output level.
        """
        import time
        start_time = time.time()

        # Use ToolResultMessage's formatting logic
        data_str = json.dumps(raw_data, ensure_ascii=False)
        data_size = len(data_str.encode('utf-8'))
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        use_file = (
            output_level == OutputLevel.FULL or
            data_size > 1024 * 1024
        )

        data_file = None
        data_summary = None

        if use_file and storage_dir:
            storage_dir = Path(storage_dir) / "tool_data"
            storage_dir.mkdir(parents=True, exist_ok=True)
            file_name = f"{request_id}_{data_hash}.json"
            file_path = storage_dir / file_name

            with open(file_path, 'w') as f:
                f.write(data_str)

            data_file = str(file_path)
            data_summary = ToolResultMessage._generate_summary(raw_data)

        observation = ToolResultMessage._format_observation(
            raw_data, output_level, data_file
        )

        duration_ms = (time.time() - start_time) * 1000

        return cls(
            request_id=request_id,
            observation=observation,
            output_level=output_level,
            data_file=data_file,
            data_size_bytes=data_size,
            data_summary=data_summary,
            success=True,
            duration_ms=duration_ms
        )

    def create_retry(self, new_timeout_ms: int) -> "ToolExecutionResult":
        """Create a retry result with updated tracking"""
        return ToolExecutionResult(
            request_id=self.request_id,
            observation=f"Retry {self.retry_count + 1} after: {self.last_error or self.error_message}",
            output_level=self.output_level,
            retry_count=self.retry_count + 1,
            last_error=self.error_message,
            success=False,
            error_type="RETRY",
            error_message=f"Retrying after {self.retry_count + 1} failures"
        )

    def to_tool_message(self):
        """
        Convert to LangChain ToolMessage for LLM.

        This is the PRIMARY method for BA-Agent implementation.

        Returns:
            ToolMessage with observation as content
        """
        from langchain_core.messages import ToolMessage

        if not self.success:
            content = f"""Operation failed.

Error Type: {self.error_type or 'Unknown'}
Error Code: {self.error_code or 'UNKNOWN'}
Error Message: {self.error_message or 'An unknown error occurred'}

Tool Call ID: {self.request_id}"""
        else:
            content = self.observation

        return ToolMessage(
            content=content,
            tool_call_id=self.request_id
        )

    def to_llm_message(self) -> Dict[str, Any]:
        """
        Convert to Claude Code format message for LLM.

        DEPRECATED: Use to_tool_message() for LangChain implementation.
        This method exists only for research/debugging compatibility.

        Returns:
            Dict in Claude Code format (role="user", type="tool_result")
        """
        if not self.success:
            content = f"""Operation failed.

Error Type: {self.error_type or 'Unknown'}
Error Code: {self.error_code or 'UNKNOWN'}
Error Message: {self.error_message or 'An unknown error occurred'}

Tool Call ID: {self.request_id}"""
        else:
            content = self.observation

        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": self.request_id,
                    "content": content,
                    "is_error": not self.success
                }
            ]
        }
```

#### Phase 2.5: Timeout Handling

```python
class ToolTimeoutHandler:
    """
    Handles tool execution timeouts with graceful degradation.

    Strategy:
    1. Pre-execution check: Validate input size
    2. During execution: Monitor with timeout
    3. Post-timeout: Return partial results if available
    """

    @staticmethod
    def validate_input_size(parameters: Dict[str, Any], max_size_mb: int = 10) -> bool:
        """Check if input parameters are too large"""
        import sys
        size_bytes = sys.getsizeof(parameters)
        size_mb = size_bytes / (1024 * 1024)
        return size_mb <= max_size_mb

    @staticmethod
    async def execute_with_timeout(
        func: Callable,
        timeout_ms: int,
        on_timeout: Optional[Callable] = None
    ) -> Any:
        """
        Execute function with timeout handling.

        Args:
            func: Function to execute
            timeout_ms: Timeout in milliseconds
            on_timeout: Optional callback for timeout handling

        Returns:
            Function result or timeout fallback
        """
        import asyncio

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(func),
                timeout=timeout_ms / 1000
            )
        except asyncio.TimeoutError:
            if on_timeout:
                return await on_timeout()
            raise ToolErrorType.TIMEOUT

    @staticmethod
    def create_timeout_fallback(request_id: str) -> ToolExecutionResult:
        """Create fallback result on timeout"""
        return ToolExecutionResult(
            request_id=request_id,
            observation="Tool execution timed out. Partial results may be available.",
            output_level=OutputLevel.BRIEF,
            success=False,
            error_type="TIMEOUT",
            error_code="TIMEOUT",
            error_message="Tool execution exceeded timeout limit"
        )
```

### Error Handling

```python
class ToolErrorType(str, Enum):
    """Standardized error types with retry classification"""

    # 可重试错误 (Transient)
    TIMEOUT = "timeout"                      # 超时
    RATE_LIMIT = "rate_limit"                # 速率限制
    RESOURCE_ERROR = "resource_error"        # 资源暂时不可用
    TRANSIENT_ERROR = "transient_error"      # 其他临时错误

    # 不可重试错误 (Permanent)
    PERMISSION_DENIED = "permission_denied"  # 权限不足
    INVALID_PARAMETERS = "invalid_parameters"  # 参数错误
    NOT_FOUND = "not_found"                  # 资源不存在
    VALIDATION_ERROR = "validation_error"    # 验证失败

    # 执行错误 (需人工介入)
    EXECUTION_ERROR = "execution_error"      # 执行失败
    INTERNAL_ERROR = "internal_error"        # 内部错误
    DEPENDENCY_ERROR = "dependency_error"    # 依赖服务错误

    @property
    def is_retryable(self) -> bool:
        """检查错误是否可重试"""
        return self in {
            self.TIMEOUT,
            self.RATE_LIMIT,
            self.RESOURCE_ERROR,
            self.TRANSIENT_ERROR,
        }

    @property
    def is_permanent(self) -> bool:
        """检查错误是否永久性（不可重试）"""
        return self in {
            self.PERMISSION_DENIED,
            self.INVALID_PARAMETERS,
            self.NOT_FOUND,
            self.VALIDATION_ERROR,
        }

class ToolErrorResponse(BaseModel):
    """Standardized error response"""
    request_id: str
    error_type: ToolErrorType
    error_code: str
    error_message: str

    @property
    def should_retry(self) -> bool:
        """是否应该重试"""
        return self.error_type.is_retryable

    def to_result(self) -> ToolExecutionResult:
        """Convert to ToolExecutionResult"""
        return ToolExecutionResult(
            request_id=self.request_id,
            observation=f"Tool Error [{self.error_code}]: {self.error_message}",
            success=False,
            error_code=self.error_code,
            error_type=self.error_type.value,
            error_message=self.error_message
        )
```

### Idempotency Support

> **注意**: `ToolInvocationRequest` 类已在 [Tool Invocation Request](#phase-1-tool-invocation-request) 节定义（Line 811），包含完整的 idempotency 支持。

幂等性特性：
- `idempotency_key`: 可选的幂等键
- `get_or_generate_idempotency_key()`: 自动生成幂等键
- 配合 `IdempotencyCache` 防止重复执行

```python
# 使用示例
request = ToolInvocationRequest(
    tool_name="web_search",
    parameters={"query": "扬州天气"}
)

# 生成幂等键
key = request.get_or_generate_idempotency_key()

# 检查缓存
cache = get_idempotency_cache()
cached = cache.get_cached_result(key)
if cached:
    return cached  # 返回缓存结果
```

# ========== 通用 TTL 缓存基类 ==========
from typing import TypeVar, Generic, ABC
from datetime import datetime, timedelta
import threading
import logging

logger = logging.getLogger(__name__)

# 泛型类型变量
K = TypeVar('K')  # 键类型
V = TypeVar('V')  # 值类型

class TTLCache(Generic[K, V], ABC):
    """
    通用 TTL 缓存基类

    特性：
    - 泛型键值对支持
    - 自动过期清理
    - 线程安全
    - 最大条目限制
    """

    def __init__(self, ttl: timedelta, max_entries: int = 1000):
        """
        初始化 TTL 缓存

        Args:
            ttl: 条目过期时间
            max_entries: 最大条目数
        """
        self._cache: Dict[K, V] = {}
        self._timestamps: Dict[K, datetime] = {}
        self._ttl = ttl
        self._max_entries = max_entries
        self._lock = threading.Lock()

    def get(self, key: K) -> Optional[V]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回 None
        """
        with self._lock:
            if key in self._cache:
                if datetime.now() - self._timestamps[key] < self._ttl:
                    logger.debug(f"Cache hit: {key}")
                    return self._cache[key]
                else:
                    # 过期，清理
                    del self._cache[key]
                    del self._timestamps[key]
            return None

    def set(self, key: K, value: V):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
        """
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = datetime.now()

            # 清理过期条目
            if len(self._cache) > self._max_entries:
                self._cleanup_expired()

    def _cleanup_expired(self):
        """清理过期条目"""
        now = datetime.now()
        expired_keys = [
            k for k, ts in self._timestamps.items()
            if now - ts > self._ttl
        ]
        for key in expired_keys:
            del self._cache[key]
            del self._timestamps[key]

        logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    def size(self) -> int:
        """获取当前缓存大小"""
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: K) -> bool:
        """检查键是否存在（且未过期）"""
        return self.get(key) is not None


class IdempotencyCache(TTLCache[str, ToolExecutionResult]):
    """
    幂等性缓存 - 防止重复执行

    继承 TTLCache 基类，特化用于工具执行结果缓存。
    """

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 10000):
        """
        初始化幂等性缓存

        Args:
            ttl_seconds: TTL 秒数（默认 1 小时）
            max_entries: 最大条目数（默认 10000）
        """
        super().__init__(
            ttl=timedelta(seconds=ttl_seconds),
            max_entries=max_entries
        )

    def get_cached_result(self, key: str) -> Optional[ToolExecutionResult]:
        """获取缓存的结果（语义化方法名）"""
        return self.get(key)

    def cache_result(self, key: str, result: ToolExecutionResult):
        """缓存结果（语义化方法名）"""
        self.set(key, result)


# 全局幂等性缓存
_global_idempotency_cache: Optional[IdempotencyCache] = None

def get_idempotency_cache() -> IdempotencyCache:
    """获取全局幂等性缓存"""
    global _global_idempotency_cache
    if _global_idempotency_cache is None:
        _global_idempotency_cache = IdempotencyCache()
    return _global_idempotency_cache
```

---

## Skill ↔ Agent Communication Protocol

### Protocol Specification

#### Phase 1: Skill Activation Request

**Direction**: Agent → Skill System (via Meta-Tool)

```python
class SkillActivationRequest(BaseModel):
    """Request to activate a skill"""
    skill_name: str
    activation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Context
    conversation_id: str
    user_request: str
    conversation_history: List[Dict[str, Any]]

    # Progressive Disclosure Control
    load_level: Literal[1, 2, 3] = 2
    # Level 1: Metadata only
    # Level 2: Full instructions (default)
    # Level 3: Include resources

    # Circular dependency prevention
    activation_depth: int = 0
    max_depth: int = 3
    activation_chain: List[str] = Field(default_factory=list)

    def can_activate_nested(self, skill_name: str) -> bool:
        """
        Check if nested skill activation is allowed.

        Detects BOTH direct and indirect cycles:
        - Direct: A activates A
        - Indirect: A → B → C → A

        Args:
            skill_name: Name of skill to activate

        Returns:
            True if activation is allowed, False if cycle detected
        """
        # Check for direct cycle
        if skill_name in self.activation_chain:
            return False

        # Check for depth limit
        if self.activation_depth >= self.max_depth:
            return False

        return True

    def create_nested_request(self, nested_skill: str) -> "SkillActivationRequest":
        """Create request for nested skill activation"""
        if not self.can_activate_nested(nested_skill):
            if nested_skill in self.activation_chain:
                # Build full cycle path for error message
                cycle_path = self.activation_chain + [nested_skill]
                raise ValueError(
                    f"Circular dependency detected: {' → '.join(cycle_path)}"
                )
            else:
                raise ValueError(
                    f"Maximum skill activation depth ({self.max_depth}) exceeded"
                )

        # Create nested request with accumulated chain
        return SkillActivationRequest(
            skill_name=nested_skill,
            conversation_id=self.conversation_id,
            user_request=self.user_request,
            conversation_history=self.conversation_history,
            activation_depth=self.activation_depth + 1,
            max_depth=self.max_depth,
            activation_chain=self.activation_chain + [self.skill_name],
            load_level=self.load_level
        )
```

#### Phase 2: Skill Activation Result

**Direction**: Skill System → Agent

```python
class SkillMessage(BaseModel):
    """Skill message format"""
    type: Literal["metadata", "instruction", "permissions"]
    content: str
    visibility: Literal["visible", "hidden"] = "visible"

class ContextModifier(BaseModel):
    """Context modifier for skill execution"""
    allowed_tools: Optional[List[str]] = None
    model: Optional[str] = None
    disable_model_invocation: bool = False

class SkillActivationResult(BaseModel):
    """Result from skill activation"""
    activation_id: str
    skill_name: str

    # Progressive Disclosure: Messages at requested level
    messages: List[SkillMessage]

    # Context modifier
    context_modifier: ContextModifier

    # Status
    success: bool
    error: Optional[str] = None
```

### Progressive Disclosure Implementation

```python
class SkillLoader:
    """Handles progressive disclosure for skill loading"""

    def load_skill(self, skill_name: str, level: int) -> SkillActivationResult:
        """
        Load skill at specified disclosure level.

        Args:
            skill_name: Name of the skill to load
            level: Disclosure level (1=metadata, 2=full, 3=with resources)
        """
        if level >= 1:
            # Load Level 1: Frontmatter metadata
            metadata = self._load_frontmatter(skill_name)

        if level >= 2:
            # Load Level 2: Full SKILL.md
            instructions = self._load_skill_md(skill_name)

        if level >= 3:
            # Load Level 3: Resource files
            resources = self._load_resources(skill_name)

        # Build message list based on level
        messages = self._build_messages(metadata, instructions, resources, level)

        return SkillActivationResult(
            skill_name=skill_name,
            messages=messages,
            context_modifier=self._get_context_modifier(skill_name),
            success=True
        )

    def _load_frontmatter(self, skill_name: str) -> Dict[str, Any]:
        """Load Level 1: Frontmatter (~100 tokens)"""
        skill_path = self._get_skill_path(skill_name)
        with open(skill_path / "SKILL.md") as f:
            frontmatter = self._parse_yaml_frontmatter(f)
        return frontmatter

    def _load_skill_md(self, skill_name: str) -> str:
        """Load Level 2: Full skill instructions (~5000 tokens)"""
        skill_path = self._get_skill_path(skill_name)
        with open(skill_path / "SKILL.md") as f:
            # Skip frontmatter, return full content
            content = self._extract_markdown_content(f)
        return content

    def _load_resources(self, skill_name: str) -> Dict[str, str]:
        """Load Level 3: Resource files (on-demand)"""
        skill_path = self._get_skill_path(skill_name)
        resources = {}

        # Load scripts
        scripts_dir = skill_path / "scripts"
        if scripts_dir.exists():
            for script in scripts_dir.glob("*.py"):
                resources[script.name] = script.read_text()

        # Load references
        refs_dir = skill_path / "references"
        if refs_dir.exists():
            for ref in refs_dir.glob("*"):
                resources[ref.name] = ref.read_text()

        return resources
```

### Message Injection Protocol

```python
import threading
from contextlib import contextmanager
from typing import Dict, Optional

class LockManager:
    """
    安全的锁管理器，带引用计数

    解决 LRU 缓存驱逐锁的潜在问题：
    - 被驱逐的锁仍可能被线程持有
    - 新请求创建新锁，导致两个线程同时进入"临界区"
    - 使用引用计数确保只驱逐未被使用的锁
    """

    def __init__(self, max_locks: int = 1000):
        self._locks: Dict[str, threading.RLock] = {}
        self._ref_counts: Dict[str, int] = {}
        self._manager_lock = threading.Lock()
        self._max_locks = max_locks

    @contextmanager
    def acquire(self, key: str, timeout: Optional[float] = None):
        """
        获取锁（带引用计数）

        Args:
            key: 锁的唯一标识
            timeout: 获取锁的超时时间（秒）

        Yields:
            RLock 对象
        """
        lock = self._get_or_create_lock(key)
        acquired = lock.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(f"Failed to acquire lock for {key}")

        try:
            yield lock
        finally:
            lock.release()
            self._release_ref(key)

            # 检查是否需要清理
            self._maybe_evict_locks()

    def _get_or_create_lock(self, key: str) -> threading.RLock:
        """获取或创建锁（增加引用计数）"""
        with self._manager_lock:
            if key not in self._locks:
                # 检查是否需要驱逐旧锁
                if len(self._locks) >= self._max_locks:
                    self._evict_unused_locks()

                self._locks[key] = threading.RLock()
                self._ref_counts[key] = 0

            self._ref_counts[key] += 1
            return self._locks[key]

    def _release_ref(self, key: str):
        """释放引用（减少引用计数）"""
        with self._manager_lock:
            if key in self._ref_counts:
                self._ref_counts[key] -= 1

    def _evict_unused_locks(self):
        """只驱逐引用计数为 0 的锁"""
        to_remove = [
            k for k, v in self._ref_counts.items()
            if v == 0
        ][:len(self._locks) // 4]  # 每次清理 25%

        for key in to_remove:
            del self._locks[key]
            del self._ref_counts[key]

        if to_remove:
            logger.debug(f"Evicted {len(to_remove)} unused locks")

    def get_ref_count(self, key: str) -> int:
        """获取当前引用计数"""
        with self._manager_lock:
            return self._ref_counts.get(key, 0)

    def cleanup(self, key: str):
        """
        显式清理指定锁（仅当引用计数为 0 时）

        Args:
            key: 要清理的锁标识

        Returns:
            是否成功清理
        """
        with self._manager_lock:
            if self._ref_counts.get(key, 0) == 0:
                if key in self._locks:
                    del self._locks[key]
                if key in self._ref_counts:
                    del self._ref_counts[key]
                return True
            return False

    def clear_all(self):
        """清空所有锁（危险操作，仅在关闭时使用）"""
        with self._manager_lock:
            self._locks.clear()
            self._ref_counts.clear()

# 全局锁管理器实例
_global_lock_manager: Optional[LockManager] = None

def get_lock_manager() -> LockManager:
    """获取全局锁管理器"""
    global _global_lock_manager
    if _global_lock_manager is None:
        _global_lock_manager = LockManager()
    return _global_lock_manager


# ========== 线程安全 Mixin ==========
class ThreadSafeMixin:
    """
    线程安全混入类（Mixin）

    为类提供简单的线程安全支持。

    使用示例：
    ```python
    class MyClass(ThreadSafeMixin):
        def __init__(self):
            super().__init__()  # 初始化 _lock
            self._data = []

        def add_item(self, item):
            with self._lock:
                self._data.append(item)
    ```
    """

    def __init__(self):
        """
        初始化 Mixin

        注意：子类必须调用 super().__init__()
        """
        self._lock = threading.Lock()

    @contextmanager
    def _with_lock(self):
        """
        获取锁的上下文管理器

        Usage:
            with self._with_lock():
                # 临界区代码
        """
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()


class MessageInjectionProtocol:
    """
    Protocol for injecting skill messages into conversation.

    Thread-safe with atomic state updates.
    Uses LockManager with reference counting for safe lock eviction.
    """

    @staticmethod
    @contextmanager
    def _conversation_lock(conversation_id: str, lock_manager: Optional[LockManager] = None):
        """Get or create lock for conversation using LockManager"""
        if lock_manager is None:
            lock_manager = get_lock_manager()

        with lock_manager.acquire(conversation_id) as lock:
            yield lock

    @staticmethod
    def inject_into_state(
        messages: List[Dict[str, Any]],
        conversation_id: str,
        agent_state: Any,
        lock_manager: Optional[LockManager] = None
    ) -> bool:
        """
        Thread-safely inject messages into LangGraph agent state.

        Args:
            messages: Messages to inject (from SkillActivationResult)
            conversation_id: Conversation ID
            agent_state: Current agent state
            lock_manager: Optional lock manager (uses global if None)

        Returns:
            Success status
        """
        with MessageInjectionProtocol._conversation_lock(conversation_id, lock_manager):
            try:
                # Atomic state read
                state = agent_state.get_state({"configurable": {"thread_id": conversation_id}})
                current_messages = list(state.messages.get("messages", []))

                # Build new message list
                new_messages = current_messages.copy()
                for msg_dict in messages:
                    role = msg_dict.get("role")
                    if role == MessageType.USER.value:
                        new_messages.append(HumanMessage(content=msg_dict["content"]))
                    elif role == MessageType.ASSISTANT.value:
                        additional_kwargs = msg_dict.get("additional_kwargs", {})
                        new_messages.append(AIMessage(
                            content=msg_dict["content"],
                            additional_kwargs=additional_kwargs
                        ))

                # Atomic state update
                agent_state.update_state(
                    {"configurable": {"thread_id": conversation_id}},
                    {"messages": new_messages}
                )

                return True
            except Exception as e:
                logger.error(f"Failed to inject messages: {e}")
                return False
```

---

## Token Counting & Monitoring

### Dynamic Token Counter (v1.9.1)

**统一的 Token 计数系统，支持动态模型识别和插件式编码器注册。**

> **移除说明**: v1.9 之前的 `TokenCounter` 类已被 `DynamicTokenCounter` 替代，后者完全兼容前者的功能，并增加了动态模型识别、配置文件支持等特性。

**基于用户需求增强的动态模型编码系统，支持多模型和插件式编码器注册。**

```python
from typing import Protocol, Callable, Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import yaml
from pathlib import Path

class ModelFamily(str, Enum):
    """支持的模型系列"""
    CLAUDE = "claude"           # Anthropic Claude
    GPT = "gpt"                 # OpenAI GPT
    GEMINI = "gemini"           # Google Gemini
    GLM = "glm"                 # Zhipu GLM
    QWEN = "qwen"               # Alibaba Qwen
    LLAMA = "llama"             # Meta Llama
    MISTRAL = "mistal"          # Mistral AI
    DEEPSEEK = "deepseek"       # DeepSeek
    CUSTOM = "custom"           # 自定义模型

@dataclass
class EncoderConfig:
    """编码器配置"""
    model_family: ModelFamily
    encoding_name: str
    safety_margin: float = 1.0
    use_exact_counting: bool = False
    exact_counting_api: Optional[str] = None
    # 编码器特定的参数
    encoder_params: Dict[str, Any] = None

    def __post_init__(self):
        if self.encoder_params is None:
            self.encoder_params = {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "model_family": self.model_family.value,
            "encoding_name": self.encoding_name,
            "safety_margin": self.safety_margin,
            "use_exact_counting": self.use_exact_counting,
            "exact_counting_api": self.exact_counting_api,
            "encoder_params": self.encoder_params,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncoderConfig":
        """从字典创建配置"""
        if "model_family" in data and isinstance(data["model_family"], str):
            data["model_family"] = ModelFamily(data["model_family"])
        return cls(**data)

    def validate(self) -> bool:
        """验证配置有效性"""
        if self.safety_margin < 1.0:
            raise ValueError("safety_margin must be >= 1.0")
        return True

class TokenEncoder(Protocol):
    """Token 编码器协议"""

    def encode(self, text: str) -> List[int]:
        """编码文本为 token IDs"""
        ...

    def decode(self, tokens: List[int]) -> str:
        """解码 token IDs 为文本"""
        ...

    def count_tokens(self, text: str) -> int:
        """计算 token 数量"""
        ...

class ModelEncoderRegistry:
    """
    动态模型编码器注册表

    特性：
    1. 插件式编码器注册
    2. 模型系列自动识别
    3. 配置文件支持
    4. 运行时动态加载
    5. 编码器缓存
    """

    # 单例实例
    _instance: Optional["ModelEncoderRegistry"] = None

    # 编码器缓存
    _encoders: Dict[str, TokenEncoder] = {}
    _configs: Dict[str, EncoderConfig] = {}

    # 模型系列映射
    _model_family_patterns: Dict[ModelFamily, List[str]] = {
        ModelFamily.CLAUDE: ["claude-3", "claude-2"],
        ModelFamily.GPT: ["gpt-4", "gpt-3.5", "gpt-35"],
        ModelFamily.GEMINI: ["gemini-2", "gemini-1.5", "gemini-1"],
        ModelFamily.GLM: ["glm-4", "glm-3"],
        ModelFamily.QWEN: ["qwen-2.5", "qwen-2", "qwen-1.5"],
        ModelFamily.LLAMA: ["llama-3.1", "llama-3", "llama-2"],
        ModelFamily.MISTRAL: ["mistral-large", "mistral-7b", "mixtral"],
        ModelFamily.DEEPSEEK: ["deepseek-r1", "deepseek-v3"],
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._load_default_configs()
            self._load_config_from_file()

    def _load_default_configs(self):
        """加载默认编码器配置"""
        # Claude 系列
        self.register_encoder_config(
            model_pattern="claude-*",
            config=EncoderConfig(
                model_family=ModelFamily.CLAUDE,
                encoding_name="cl100k_base",
                safety_margin=1.15,  # 15% margin for Claude tokenizer
                use_exact_counting=False,  # 使用 tiktoken 估算，精度足够
            )
        )

        # GPT 系列
        self.register_encoder_config(
            model_pattern="gpt-*",
            config=EncoderConfig(
                model_family=ModelFamily.GPT,
                encoding_name="cl100k_base",
                safety_margin=1.0,  # 精确计数
                use_exact_counting=False,  # tiktoken 对 GPT 是准确的
            )
        )

        # Gemini 系列（使用 tiktoken 近似）
        self.register_encoder_config(
            model_pattern="gemini-*",
            config=EncoderConfig(
                model_family=ModelFamily.GEMINI,
                encoding_name="cl100k_base",  # 近似
                safety_margin=1.2,  # 20% margin for approximation
                use_exact_counting=False,
            )
        )

        # GLM 系列
        self.register_encoder_config(
            model_pattern="glm-*",
            config=EncoderConfig(
                model_family=ModelFamily.GLM,
                encoding_name="cl100k_base",  # 近似
                safety_margin=1.25,  # 25% margin
                use_exact_counting=False,
            )
        )

        # Qwen 系列
        self.register_encoder_config(
            model_pattern="qwen-*",
            config=EncoderConfig(
                model_family=ModelFamily.QWEN,
                encoding_name="cl100k_base",  # 近似
                safety_margin=1.2,  # 20% margin
                use_exact_counting=False,
            )
        )

    def _load_config_from_file(self, path: Optional[Path] = None):
        """
        从配置文件加载编码器配置

        配置文件格式 (YAML):
        ```yaml
        encoders:
          claude-3-sonnet:
            model_family: claude
            encoding_name: cl100k_base
            safety_margin: 1.15
            use_exact_counting: false

          gpt-4o:
            model_family: gpt
            encoding_name: cl100k_base
            safety_margin: 1.0
            use_exact_counting: false

          # 自定义模型
          my-custom-model:
            model_family: custom
            encoding_name: my_custom_encoding
            safety_margin: 1.3
            use_exact_counting: true
            exact_counting_api: "https://my-api.com/count-tokens"
        ```
        """
        if path is None:
            # 默认配置文件路径
            config_paths = [
                Path("config/token_encoders.yaml"),
                Path("config/token_encoders.yml"),
                Path("~/.ba-agent/token_encoders.yaml").expanduser(),
            ]
            path = next((p for p in config_paths if p.exists()), None)

        if path is None:
            return

        try:
            with open(path, "r") as f:
                config_data = yaml.safe_load(f)

            for model_pattern, encoder_config in config_data.get("encoders", {}).items():
                self.register_encoder_config(
                    model_pattern=model_pattern,
                    config=EncoderConfig(**encoder_config)
                )

            logger.info(f"Loaded encoder configs from {path}")
        except Exception as e:
            logger.warning(f"Failed to load encoder config from {path}: {e}")

    def register_encoder_config(
        self,
        model_pattern: str,
        config: EncoderConfig
    ):
        """
        注册编码器配置

        Args:
            model_pattern: 模型名称模式（支持通配符，如 "claude-*"）
            config: 编码器配置
        """
        self._configs[model_pattern] = config

    def register_custom_encoder(
        self,
        model_pattern: str,
        encoder: TokenEncoder,
        config: Optional[EncoderConfig] = None
    ):
        """
        注册自定义编码器

        Args:
            model_pattern: 模型名称模式
            encoder: Token 编码器实例
            config: 可选配置
        """
        self._encoders[model_pattern] = encoder
        if config:
            self._configs[model_pattern] = config

    def detect_model_family(self, model: str) -> ModelFamily:
        """
        自动检测模型系列

        Args:
            model: 模型名称

        Returns:
            模型系列
        """
        model_lower = model.lower()

        for family, patterns in self._model_family_patterns.items():
            for pattern in patterns:
                if pattern in model_lower:
                    return family

        # 默认返回 CUSTOM
        return ModelFamily.CUSTOM

    def get_encoder_config(self, model: str) -> EncoderConfig:
        """
        获取模型的编码器配置

        Args:
            model: 模型名称

        Returns:
            编码器配置

        Raises:
            ValueError: 如果找不到匹配的配置
        """
        # 精确匹配
        if model in self._configs:
            return self._configs[model]

        # 模式匹配（支持通配符）
        for pattern, config in self._configs.items():
            if self._match_pattern(model, pattern):
                return config

        # 基于模型系列的默认配置
        family = self.detect_model_family(model)
        family_pattern = f"{family.value}-*"
        if family_pattern in self._configs:
            return self._configs[family_pattern]

        # 最后的回退：使用通用配置
        return EncoderConfig(
            model_family=ModelFamily.CUSTOM,
            encoding_name="cl100k_base",
            safety_margin=1.2,  # 保守估计
        )

    def _match_pattern(self, model: str, pattern: str) -> bool:
        """
        匹配模型名称模式

        支持通配符：
        - "claude-*" 匹配 "claude-3-sonnet"
        - "gpt-4*" 匹配 "gpt-4o"
        """
        if "*" not in pattern:
            return model == pattern

        # 简单的通配符匹配
        import fnmatch
        return fnmatch.fnmatch(model.lower(), pattern.lower())

    def get_encoder(self, model: str) -> TokenEncoder:
        """
        获取模型的 Token 编码器

        Args:
            model: 模型名称

        Returns:
            Token 编码器
        """
        # 检查缓存
        if model in self._encoders:
            return self._encoders[model]

        # 获取配置
        config = self.get_encoder_config(model)

        # 创建编码器
        encoder = self._create_encoder(config)

        # 缓存编码器
        self._encoders[model] = encoder

        return encoder

    def _create_encoder(self, config: EncoderConfig) -> TokenEncoder:
        """创建编码器实例"""
        encoding_name = config.encoding_name

        # 使用 tiktoken 创建编码器
        try:
            import tiktoken
            return tiktoken.get_encoding(encoding_name)
        except KeyError:
            logger.warning(f"Encoding '{encoding_name}' not found in tiktoken, using cl100k_base")
            import tiktoken
            return tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.error(f"Failed to create encoder: {e}")
            raise

class DynamicTokenCounter:
    """
    动态 Token 计数器

    特性：
    1. 自动识别模型系列
    2. 支持配置文件
    3. 插件式编码器注册
    4. 精确/估算两种模式
    5. 多模型 API 支持
    """

    def __init__(self, registry: Optional[ModelEncoderRegistry] = None):
        self._registry = registry or ModelEncoderRegistry()
        self._api_clients: Dict[str, Any] = {}

    def configure_api_client(
        self,
        model_family: ModelFamily,
        client: Any,
        api_key: Optional[str] = None
    ):
        """
        配置 API 客户端用于精确计数

        Args:
            model_family: 模型系列
            client: API 客户端实例
            api_key: API 密钥（如果需要）
        """
        self._api_clients[model_family.value] = client

    def count_tokens(
        self,
        text: str,
        model: str = "claude-3-sonnet"
    ) -> int:
        """
        计算文本的 Token 数量

        Args:
            text: 要计算的文本
            model: 模型名称（影响编码方式）

        Returns:
            Token 数量（包含安全余量）
        """
        if not text:
            return 0

        # 获取编码器配置
        config = self._registry.get_encoder_config(model)

        # 如果支持精确计数且有 API 客户端，使用精确计数
        if config.use_exact_counting:
            exact_count = self._count_tokens_exact(text, model, config)
            if exact_count is not None:
                return exact_count

        # 使用 tiktoken 估算
        encoder = self._registry.get_encoder(model)
        estimated = len(encoder.encode(text))

        # 应用安全余量
        return int(estimated * config.safety_margin)

    def _count_tokens_exact(
        self,
        text: str,
        model: str,
        config: EncoderConfig
    ) -> Optional[int]:
        """
        使用配置的编码器精确计算 Token 数量

        Args:
            text: 文本
            model: 模型名称
            config: 编码器配置

        Returns:
            精确 Token 数量

        Note:
            对于大多数模型，tiktoken 已经提供足够精确的计数。
            只有在配置了特定 API 客户端时才使用 API 调用。
        """
        family = config.model_family

        # 检查是否有 API 客户端
        if family.value not in self._api_clients:
            return None

        try:
            # 使用配置的 API 客户端进行精确计数
            # 注意：当前设计中，tiktoken 已经足够精确
            # 此方法保留用于未来扩展（如模型提供商提供 token 计数 API）
            logger.debug(f"Using API client for {family.value} token counting")
            # 实际 API 调用逻辑由各 API 客户端实现

        except Exception as e:
            logger.warning(f"Exact token counting failed: {e}")

        return None

    def count_message_tokens(
        self,
        message: Dict[str, Any],
        model: str = "claude-3-sonnet"
    ) -> int:
        """
        计算消息的 Token 数量

        Args:
            message: 消息对象
            model: 模型名称

        Returns:
            Token 数量
        """
        tokens = 0

        # Role
        tokens += self.count_tokens(message.get("role", ""), model)

        # Content
        content = message.get("content", [])
        if isinstance(content, list):
            for block in content:
                block_type = block.get("type", "")
                if block_type == "text":
                    tokens += self.count_tokens(block.get("text", ""), model)
                elif block_type == "thinking":
                    tokens += self.count_tokens(block.get("thinking", ""), model)
                elif block_type == "tool_use":
                    tokens += self.count_tokens(block.get("name", ""), model)
                    input_data = block.get("input", {})
                    tokens += self.count_tokens(json.dumps(input_data), model)
                elif block_type == "tool_result":
                    tokens += self.count_tokens(block.get("content", ""), model)
        elif isinstance(content, str):
            tokens += self.count_tokens(content, model)

        return tokens

    def count_conversation_tokens(
        self,
        messages: List[Dict[str, Any]],
        model: str = "claude-3-sonnet"
    ) -> int:
        """
        计算对话的总 Token 数量

        Args:
            messages: 消息列表
            model: 模型名称

        Returns:
            总 Token 数量
        """
        return sum(self.count_message_tokens(msg, model) for msg in messages)

    def get_model_info(self, model: str) -> Dict[str, Any]:
        """
        获取模型的编码器信息

        Args:
            model: 模型名称

        Returns:
            模型信息字典
        """
        config = self._registry.get_encoder_config(model)
        family = self._registry.detect_model_family(model)

        return {
            "model": model,
            "model_family": family.value,
            "encoding_name": config.encoding_name,
            "safety_margin": config.safety_margin,
            "use_exact_counting": config.use_exact_counting,
            "has_api_client": family.value in self._api_clients,
        }

# 全局单例
_global_token_counter: Optional[DynamicTokenCounter] = None

def get_token_counter() -> DynamicTokenCounter:
    """获取全局 Token 计数器实例"""
    global _global_token_counter
    if _global_token_counter is None:
        _global_token_counter = DynamicTokenCounter()
    return _global_token_counter

# 便捷函数
def count_tokens(text: str, model: str = "claude-3-sonnet") -> int:
    """计算文本的 Token 数量（使用全局计数器）"""
    return get_token_counter().count_tokens(text, model)

def count_message_tokens(message: Dict[str, Any], model: str = "claude-3-sonnet") -> int:
    """计算消息的 Token 数量（使用全局计数器）"""
    return get_token_counter().count_message_tokens(message, model)

def count_conversation_tokens(messages: List[Dict[str, Any]], model: str = "claude-3-sonnet") -> int:
    """计算对话的 Token 数量（使用全局计数器）"""
    return get_token_counter().count_conversation_tokens(messages, model)
```

**使用示例**:

```python
# 基本使用
counter = get_token_counter()

# 自动识别模型
tokens = counter.count_tokens("Hello, world!", model="claude-3-5-sonnet-20241022")
# 自动使用 Claude 配置（15% safety margin）

tokens = counter.count_tokens("Hello, world!", model="gpt-4o")
# 自动使用 GPT 配置（精确计数，无 margin）

tokens = counter.count_tokens("Hello, world!", model="gemini-2.0-flash-exp")
# 自动使用 Gemini 配置（20% safety margin）

# 获取模型信息
info = counter.get_model_info("glm-4-plus")
print(info)
# {
#     "model": "glm-4-plus",
#     "model_family": "glm",
#     "encoding_name": "cl100k_base",
#     "safety_margin": 1.25,
#     "use_exact_counting": false,
#     "has_api_client": false
# }

# 配置文件支持 (config/token_encoders.yaml)
# 添加自定义模型配置后自动加载

# 注册自定义编码器
registry = ModelEncoderRegistry()
registry.register_custom_encoder(
    model_pattern="my-model-*",
    encoder=MyCustomEncoder(),
    config=EncoderConfig(
        model_family=ModelFamily.CUSTOM,
        encoding_name="my_encoding",
        safety_margin=1.0
    )
)
```

**关键特性**:

1. **自动模型识别**: 通过模型名称自动识别系列并应用相应配置
2. **配置文件支持**: 从 `config/token_encoders.yaml` 加载自定义配置
3. **插件式扩展**: 可注册自定义编码器和配置
4. **动态切换**: 运行时根据传入的 `model` 参数动态切换编码方式
5. **精确/估算混合**: 支持精确 API 计数和 tiktoken 估算两种模式

### Monitoring Metrics

```python
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime
import json

@dataclass
class ToolMetrics:
    """Metrics for a single tool execution"""
    tool_name: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    success: bool
    error_code: Optional[str] = None
    retry_count: int = 0
    output_level: str = "STANDARD"

@dataclass
class ConversationMetrics:
    """Metrics for a conversation"""
    conversation_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_ms: float = 0.0

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0

    # Tool executions
    tool_calls: List[ToolMetrics] = field(default_factory=list)
    successful_calls: int = 0
    failed_calls: int = 0
    retried_calls: int = 0

    # Skill activations
    skill_activations: int = 0
    unique_skills: List[str] = field(default_factory=list)

    # Context management
    messages_count: int = 0
    compression_events: int = 0

    def get_tool_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get statistics per tool.

        Returns:
            Dict mapping tool_name to stats:
            - call_count: Number of calls
            - avg_duration_ms: Average duration
            - avg_tokens: Average token usage
            - success_rate: Success rate (0-1)
            - error_rate: Error rate (0-1)
        """
        stats = {}
        for metric in self.tool_calls:
            name = metric.tool_name
            if name not in stats:
                stats[name] = {
                    "call_count": 0,
                    "total_duration": 0.0,
                    "total_tokens": 0,
                    "success_count": 0,
                    "error_count": 0,
                }
            s = stats[name]
            s["call_count"] += 1
            s["total_duration"] += metric.duration_ms
            s["total_tokens"] += metric.total_tokens
            if metric.success:
                s["success_count"] += 1
            else:
                s["error_count"] += 1

        # Calculate averages
        for name, s in stats.items():
            count = s["call_count"]
            stats[name] = {
                "call_count": count,
                "avg_duration_ms": s["total_duration"] / count,
                "avg_tokens": s["total_tokens"] / count,
                "success_rate": s["success_count"] / count,
                "error_rate": s["error_count"] / count,
            }

        return stats

    def to_report(self) -> str:
        """Generate human-readable metrics report"""
        tool_stats = self.get_tool_stats()
        tool_lines = []
        for name, stats in sorted(tool_stats.items(), key=lambda x: -x[1]["call_count"]):
            tool_lines.append(f"""
  {name}:
    - Calls: {stats['call_count']}
    - Avg Duration: {stats['avg_duration_ms']:.1f}ms
    - Avg Tokens: {stats['avg_tokens']:.0f}
    - Success Rate: {stats['success_rate']:.1%}
""")

        return f"""
Conversation Metrics Report
============================
Conversation ID: {self.conversation_id}
Duration: {self.total_duration_ms / 1000:.1f}s

Token Usage:
  - Input: {self.total_input_tokens:,}
  - Output: {self.total_output_tokens:,}
  - Total: {self.total_tokens:,}

Tool Calls:
  - Total: {len(self.tool_calls)}
  - Successful: {self.successful_calls}
  - Failed: {self.failed_calls}
  - Retried: {self.retried_calls}

Per-Tool Statistics:
{''.join(tool_lines)}

Skills Activated:
  - Total: {self.skill_activations}
  - Unique: {len(self.unique_skills)}
  - Skills: {', '.join(self.unique_skills) if self.unique_skills else 'None'}

Context Management:
  - Messages: {self.messages_count}
  - Compressions: {self.compression_events}
"""

class MetricsCollector:
    """
    Global metrics collector for monitoring.

    Aggregates metrics across all conversations.
    """

    def __init__(self):
        self._conversations: Dict[str, ConversationMetrics] = {}
        self._lock = threading.Lock()

    def get_or_create_conversation(self, conversation_id: str) -> ConversationMetrics:
        """Get or create conversation metrics"""
        with self._lock:
            if conversation_id not in self._conversations:
                self._conversations[conversation_id] = ConversationMetrics(
                    conversation_id=conversation_id,
                    start_time=datetime.now()
                )
            return self._conversations[conversation_id]

    def record_tool_call(self, metrics: ToolMetrics, conversation_id: str):
        """Record a tool execution"""
        conv = self.get_or_create_conversation(conversation_id)
        conv.tool_calls.append(metrics)
        conv.total_tokens += metrics.total_tokens

        if metrics.success:
            conv.successful_calls += 1
        else:
            conv.failed_calls += 1

        if metrics.retry_count > 0:
            conv.retried_calls += 1

    def get_global_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics across all conversations"""
        with self._lock:
            total_calls = sum(len(c.tool_calls) for c in self._conversations.values())
            total_tokens = sum(c.total_tokens for c in self._conversations.values())
            total_duration = sum(c.total_duration_ms for c in self._conversations.values())

            return {
                "total_conversations": len(self._conversations),
                "total_tool_calls": total_calls,
                "total_tokens": total_tokens,
                "total_duration_seconds": total_duration / 1000,
                "avg_tokens_per_call": total_tokens / total_calls if total_calls > 0 else 0,
            }
```

---

## Multi-Round Conversation Flow

### Flow Specification

```python
class ConversationRound(BaseModel):
    """A single round of conversation (ReAct loop)"""
    round_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str

    # Messages
    user_message: str
    thoughts: List[str] = Field(default_factory=list)  # Agent's reasoning
    tool_calls: List[ToolCallMessage] = Field(default_factory=list)
    tool_observations: List[str] = Field(default_factory=list)  # Simple strings
    skill_activations: List[SkillActivationResult] = Field(default_factory=list)

    # Final response
    final_answer: Optional[str] = None

    # Metrics
    tokens_used: int = 0
    latency_ms: float = 0.0

    # State
    status: Literal["pending", "in_progress", "completed", "error"] = "pending"

class MultiRoundConversation(BaseModel):
    """Multi-round conversation manager"""
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str

    # History
    rounds: List[ConversationRound] = Field(default_factory=list)

    # Active context
    active_skill_context: Dict[str, Any] = Field(default_factory=dict)
    context_modifiers: List[ContextModifier] = Field(default_factory=list)

    # Memory management
    context_window_limit: int = 200000  # Tokens
    compression_threshold: float = 0.8    # 80%

    def should_compress_context(self) -> bool:
        """Check if context needs compression"""
        total_tokens = sum(r.tokens_used for r in self.rounds)
        return total_tokens > (self.context_window_limit * self.compression_threshold)

    def get_compressed_history(self) -> List[Dict[str, Any]]:
        """
        Get compressed conversation history.

        Strategy:
        - Keep recent rounds complete
        - Summarize old rounds to key decisions
        - Preserve tool observations (critical for reasoning)
        """
        if not self.should_compress_context():
            return self._get_full_history()

        # Compress old rounds
        compressed = []
        for i, round_data in enumerate(self.rounds):
            if i < len(self.rounds) - 5:  # Keep last 5 rounds complete
                # Compress to summary
                compressed.append({
                    "role": "system",
                    "content": self._create_round_summary(round_data)
                })
            else:
                # Keep complete
                compressed.extend(self._round_to_messages(round_data))

        return compressed

    def _create_round_summary(self, round_data: ConversationRound) -> str:
        """Create summary of a conversation round"""
        parts = [
            f"Round {round_data.round_id}:",
            f"  Request: {round_data.user_message[:100]}...",
            f"  Tools: {[tc.tool_name for tc in round_data.tool_calls]}",
        ]
        if round_data.final_answer:
            parts.append(f"  Answer: {round_data.final_answer[:100]}...")
        return "\n".join(parts)

    def _round_to_messages(self, round_data: ConversationRound) -> List[Dict[str, Any]]:
        """Convert a round to message list (Claude Code format)"""
        messages = []

        # User message
        messages.append({
            "role": "user",
            "content": round_data.user_message
        })

        # Tool calls and observations (ReAct loop)
        for tool_call, observation in zip(round_data.tool_calls, round_data.tool_observations):
            # Assistant: Tool use
            messages.append({
                "role": "assistant",
                "content": [{
                    "type": "tool_use",
                    "id": tool_call.tool_call_id,
                    "name": tool_call.tool_name,
                    "input": tool_call.parameters
                }]
            })

            # User: Tool result (observation)
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_call.tool_call_id,
                    "content": observation,  # Simple observation string
                    "is_error": False
                }]
            })

        # Final answer
        if round_data.final_answer:
            messages.append({
                "role": "assistant",
                "content": round_data.final_answer
            })

        return messages
```

---

## Context Management Strategy

### Compression Strategy Selection

```python
from enum import Enum
from typing import Callable, Optional, Dict, Any

class ContextCompressionStrategy(str, Enum):
    """上下文压缩策略"""
    TRUNCATE = "truncate"      # 简单截断（快速，免费）
    EXTRACT = "extract"        # 提取关键信息（规则，快速）
    SUMMARIZE = "summarize"    # LLM 摘要（高质量，有成本）

class CompressionCostEstimate:
    """压缩成本估算"""

    # Token 估算（每 1000 tokens）
    TRUNCATE_COST = 0.0          # 免费
    EXTRACT_COST = 0.001        # 规则处理成本极低
    SUMMARIZE_COST = 0.003       # LLM 摘要成本（假设使用小模型）

    @classmethod
    def estimate_cost(cls, strategy: ContextCompressionStrategy, input_tokens: int) -> float:
        """估算压缩成本（美元）"""
        tokens_in_k = input_tokens / 1000
        return tokens_in_k * {
            ContextCompressionStrategy.TRUNCATE: cls.TRUNCATE_COST,
            ContextCompressionStrategy.EXTRACT: cls.EXTRACT_COST,
            ContextCompressionStrategy.SUMMARIZE: cls.SUMMARIZE_COST,
        }[strategy]

class LLMCompressor:
    """
    LLM 摘要器

    使用小模型生成上下文摘要，平衡质量和成本
    """

    def __init__(
        self,
        model: str = "claude-3-haiku",  # 小模型，快速且便宜
        max_summary_tokens: int = 500,
        timeout_ms: int = 10000
    ):
        self.model = model
        self.max_summary_tokens = max_summary_tokens
        self.timeout_ms = timeout_ms

    async def summarize_messages(
        self,
        messages: List[Dict[str, Any]],
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """
        使用 LLM 生成消息摘要

        Args:
            messages: 要摘要的消息列表
            focus_areas: 关注点（如 tool_calls, errors, decisions）

        Returns:
            生成的摘要文本
        """
        import anthropic

        # 构建提示词
        prompt = self._build_summary_prompt(messages, focus_areas)

        try:
            client = anthropic.Anthropic()
            response = await asyncio.to_thread(
                lambda: client.messages.create(
                    model=self.model,
                    max_tokens=self.max_summary_tokens,
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=self.timeout_ms / 1000
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            # 降级到提取模式
            return self._extract_key_info(messages)

    def _build_summary_prompt(
        self,
        messages: List[Dict[str, Any]],
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """构建 LLM 摘要提示词"""
        parts = [
            "请将以下对话历史总结为简洁的摘要（最多 300 字）：\n\n"
        ]

        # 添加关注点
        if focus_areas:
            parts.append(f"重点关注：{', '.join(focus_areas)}\n")

        # 添加对话内容
        for msg in messages[-20:]:  # 只发送最近 20 条消息
            role = msg.get("role", "")
            content = msg.get("content", "")

            if isinstance(content, list):
                content_str = self._format_content_blocks(content)
            else:
                content_str = str(content)[:200]  # 限制每条消息长度

            parts.append(f"{role}: {content_str}\n")

        parts.append("\n摘要应包括：")
        parts.append("- 用户的主要请求")
        parts.append("- 执行的工具调用和结果")
        parts.append("- 重要的决策和发现")
        parts.append("- 最终结论")

        return "\n".join(parts)

    def _format_content_blocks(self, blocks: List[Dict]) -> str:
        """格式化内容块"""
        formatted = []
        for block in blocks:
            block_type = block.get("type", "")
            if block_type == "text":
                formatted.append(block.get("text", "")[:200])
            elif block_type == "tool_use":
                tool_name = block.get("name", "")
                formatted.append(f"[调用工具: {tool_name}]")
            elif block_type == "tool_result":
                formatted.append("[工具结果]")
            elif block_type == "thinking":
                formatted.append("[思考过程]")
        return " ".join(formatted)

    def _extract_key_info(self, messages: List[Dict[str, Any]]) -> str:
        """降级方法：提取关键信息"""
        key_info = []

        # 提取用户请求
        for msg in messages:
            if msg.get("role") == "user":
                content = str(msg.get("content", ""))[:200]
                key_info.append(f"用户: {content}...")
                break

        # 提取工具调用
        tool_calls = []
        for msg in messages:
            if "tool_use" in str(msg.get("content", "")):
                tool_calls.append("[工具调用]")

        # 提取最终答案
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                content = str(msg.get("content", ""))[:200]
                if "tool" not in content.lower():  # 不是工具调用
                    key_info.append(f"助手: {content}...")
                break

        return "\n".join(key_info) if key_info else "[对话摘要不可用]"

class SummaryCache(TTLCache[str, Dict[str, Any]]):
    """
    摘要缓存 - 避免重复摘要

    继承 TTLCache 基类，特化用于 LLM 摘要缓存。

    缓存值格式：
    ```python
    {
        "summary": str,           # 摘要内容
        "timestamp": str,         # ISO 格式时间戳
        "metadata": Dict          # 可选元数据
    }
    ```
    """

    def __init__(self, ttl_hours: int = 24, max_entries: int = 1000):
        """
        初始化摘要缓存

        Args:
            ttl_hours: TTL 小时数（默认 24 小时）
            max_entries: 最大条目数（默认 1000）
        """
        super().__init__(
            ttl=timedelta(hours=ttl_hours),
            max_entries=max_entries
        )

    def _make_key(self, conversation_id: str, message_hash: str) -> str:
        """生成缓存键"""
        return f"{conversation_id}:{message_hash}"

    def get_cached_summary(
        self,
        conversation_id: str,
        message_hash: str
    ) -> Optional[str]:
        """
        获取缓存的摘要

        Args:
            conversation_id: 对话 ID
            message_hash: 消息哈希

        Returns:
            摘要内容，如果不存在或已过期则返回 None
        """
        key = self._make_key(conversation_id, message_hash)
        cached = self.get(key)
        if cached:
            return cached.get("summary")
        return None

    def cache_summary(
        self,
        conversation_id: str,
        message_hash: str,
        summary: str,
        metadata: Optional[Dict] = None
    ):
        """
        缓存摘要

        Args:
            conversation_id: 对话 ID
            message_hash: 消息哈希
            summary: 摘要内容
            metadata: 可选元数据
        """
        key = self._make_key(conversation_id, message_hash)
        value = {
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.set(key, value)

class ContextCompressionConfig:
    """上下文压缩配置 - 统一的配置基类"""

    def __init__(
        self,
        strategy: ContextCompressionStrategy = ContextCompressionStrategy.EXTRACT,
        enable_llm_summarization: bool = True,
        llm_summarization_threshold: int = 50,  # 超过 50 条消息才使用 LLM
        summary_cache_ttl: int = 24,  # 摘要缓存 24 小时
        max_compression_cost_per_hour: float = 0.1  # 每小时最大压缩成本
    ):
        self.strategy = strategy
        self.enable_llm_summarization = enable_llm_summarization
        self.llm_threshold = llm_summarization_threshold
        self.summary_cache_ttl = summary_cache_ttl
        self.max_cost_per_hour = max_compression_cost_per_hour

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "strategy": self.strategy.value if isinstance(self.strategy, Enum) else self.strategy,
            "enable_llm_summarization": self.enable_llm_summarization,
            "llm_threshold": self.llm_threshold,
            "summary_cache_ttl": self.summary_cache_ttl,
            "max_cost_per_hour": self.max_cost_per_hour,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextCompressionConfig":
        """从字典创建配置"""
        # 处理枚举
        if "strategy" in data and isinstance(data["strategy"], str):
            data["strategy"] = ContextCompressionStrategy(data["strategy"])
        return cls(**data)

    def validate(self) -> bool:
        """验证配置有效性"""
        if self.llm_threshold < 0:
            raise ValueError("llm_threshold must be non-negative")
        if self.summary_cache_ttl < 0:
            raise ValueError("summary_cache_ttl must be non-negative")
        if self.max_cost_per_hour < 0:
            raise ValueError("max_cost_per_hour must be non-negative")
        return True

class AdvancedContextManager:
    """
    高级上下文管理器 - 支持多种压缩策略和 LLM 摘要

    特性：
    1. 同步压缩支持（适合同步工具系统）
    2. LLM 智能摘要（Claude 3 Haiku）- 后台线程执行
    3. 三种压缩策略（TRUNCATE/EXTRACT/SUMMARIZE）
    4. 自动策略选择
    5. 摘要缓存

    IMPORTANT: 同步系统中的压缩策略
    - 主链路同步：TRUNCATE（截断）、EXTRACT（规则提取）
    - 后台线程：SUMMARIZE（LLM 摘要，写入缓存供下一轮使用）
    """

    def __init__(
        self,
        max_tokens: int = 200000,
        compression_config: Optional[ContextCompressionConfig] = None
    ):
        self.max_tokens = max_tokens
        self.compression_threshold = 0.8

        # 压缩配置
        self.config = compression_config or ContextCompressionConfig()

        # 组件
        self._messages: List[MessageWrapper] = []
        self._token_counter = get_token_counter()  # 使用单例
        self._lock = threading.Lock()

        # LLM 压缩器（按需创建）
        self._llm_compressor: Optional[LLMCompressor] = None
        self._summary_cache = SummaryCache()

    @property
    def llm_compressor(self) -> LLMCompressor:
        """懒加载 LLM 压缩器"""
        if self._llm_compressor is None and self.config.enable_llm_summarization:
            self._llm_compressor = LLMCompressor()
        return self._llm_compressor

    def add_message(
        self,
        message: Dict[str, Any],
        importance: MessageImportance = MessageImportance.MEDIUM,
        round_id: str = ""
    ):
        """添加消息（线程安全）"""
        with self._lock:
            tokens = self._token_counter.count_message_tokens(message)

            wrapper = MessageWrapper(
                message=message,
                importance=importance,
                timestamp=datetime.now(),
                tokens=tokens,
                round_id=round_id
            )

            self._messages.append(wrapper)

            # 检查是否需要压缩
            if self._should_compress():
                self._compress_context()

    def _should_compress(self) -> bool:
        """检查是否需要压缩"""
        total_tokens = sum(m.tokens for m in self._messages)
        return total_tokens > (self.max_tokens * self.compression_threshold)

    def _compress_context(self):
        """
        执行上下文压缩（同步）

        同步系统中的压缩策略：
        1. TRUNCATE: 直接截断，保留最近 N 条消息
        2. EXTRACT: 基于重要性的规则提取
        3. SUMMARIZE: 触发后台线程进行 LLM 摘要，当前轮使用 EXTRACT

        NOTE: LLM 摘要不能在同步主链路中执行（会阻塞）。
              应该在后台线程执行，结果写入缓存，下一轮对话使用。
        """
        if len(self._messages) < 20:
            return

        # 计算当前成本
        current_tokens = sum(m.tokens for m in self._messages)

        # 决定压缩策略
        strategy = self._select_compression_strategy(current_tokens)

        if strategy == ContextCompressionStrategy.TRUNCATE:
            self._compress_truncate()
        elif strategy == ContextCompressionStrategy.EXTRACT:
            self._compress_extract()
        elif strategy == ContextCompressionStrategy.SUMMARIZE:
            # 同步系统中：先使用 EXTRACT，后台触发 SUMMARIZE
            self._compress_extract()
            self._trigger_background_summarization()

    def _trigger_background_summarization(self):
        """
        触发后台线程进行 LLM 摘要

        LLM 摘要结果将写入 SummaryCache，下一轮对话时可以使用。
        """
        if not self.config.enable_llm_summarization:
            return

        import threading

        def summarize_in_background():
            try:
                # 在后台线程执行 LLM 摘要
                summary = self.llm_compressor.summarize_messages(self._messages)

                # 写入缓存
                message_hash = self._compute_messages_hash()
                self._summary_cache.set(
                    f"summary_{message_hash}",
                    {"summary": summary, "timestamp": datetime.now()}
                )
            except Exception as e:
                logger.warning(f"Background summarization failed: {e}")

        # 启动后台线程
        thread = threading.Thread(target=summarize_in_background, daemon=True)
        thread.start()

    def _select_compression_strategy(
        self,
        current_tokens: int
    ) -> ContextCompressionStrategy:
        """
        根据配置和成本选择压缩策略

        决策逻辑：
        1. 如果配置了固定策略，使用配置的策略
        2. 如果消息少，使用 EXTRACT
        3. 如果消息多且成本允许，使用 SUMMARIZE
        4. 否则使用 TRUNCATE
        """
        # 使用配置的策略
        if self.config.strategy != ContextCompressionStrategy.EXTRACT:
            return self.config.strategy

        # 自动选择
        message_count = len(self._messages)

        if message_count < 30:
            return ContextCompressionStrategy.EXTRACT
        elif message_count >= self.config.llm_threshold:
            # 估算 LLM 成本
            estimated_cost = CompressionCostEstimate.estimate_cost(
                ContextCompressionStrategy.SUMMARIZE,
                current_tokens
            )

            if estimated_cost < self.config.max_cost_per_hour:
                return ContextCompressionStrategy.SUMMARIZE

        return ContextCompressionStrategy.EXTRACT

    def _compress_truncate(self):
        """截断策略：保留最近 N 条消息"""
        keep_count = 5
        if len(self._messages) > keep_count:
            # 删除旧消息
            del self._messages[:-keep_count]

    def _compress_extract(self):
        """提取策略：基于重要性的提取"""
        rounds = self._group_by_round()

        # 找出需要压缩的轮次
        rounds_to_compress = []
        for round_id, group in rounds.items():
            has_important = any(
                m.importance in (MessageImportance.HIGH, MessageImportance.CRITICAL)
                for m in group
            )

            if not has_important and len(rounds) > 5:
                rounds_to_compress.append(round_id)

        # 压缩
        for round_id in rounds_to_compress:
            self._compress_round_extract(round_id)

    async def _compress_summarize(self):
        """LLM 摘要策略：使用 LLM 生成摘要"""
        rounds = self._group_by_round()
        current_round = self._messages[-1].round_id if self._messages else ""

        # 找出需要摘要的轮次
        rounds_to_summarize = []
        for round_id, group in rounds.items():
            if round_id == current_round:
                continue

            has_critical = any(
                m.importance == MessageImportance.CRITICAL
                for m in group
            )

            if not has_critical:
                rounds_to_summarize.append(round_id)

        if not rounds_to_summarize:
            return

        # 使用 LLM 生成摘要
        compressor = self.llm_compressor
        if compressor is None:
            # 降级到提取模式
            for round_id in rounds_to_summarize:
                self._compress_round_extract(round_id)
            return

        # 按 round_id 分组生成摘要
        for round_id in rounds_to_summarize:
            messages = [
                m.message for m in self._messages
                if m.round_id == round_id
            ]

            # 生成消息哈希用于缓存
            import hashlib
            content_str = json.dumps(messages, sort_keys=True)
            message_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

            # 检查缓存
            cached_summary = self._summary_cache.get_cached_summary(
                round_id, message_hash
            )

            if cached_summary:
                summary = cached_summary
            else:
                # 生成新摘要
                focus_areas = ["tool_calls", "errors", "decisions"]
                summary = await compressor.summarize_messages(messages, focus_areas)

                # 缓存摘要
                self._summary_cache.cache_summary(round_id, message_hash, summary)

            # 替换为摘要
            for i, wrapper in enumerate(self._messages):
                if wrapper.round_id == round_id:
                    wrapper.compressed_content = summary
                    wrapper.is_compressed = True

    def _compress_round_extract(self, round_id: str):
        """提取策略：压缩单个轮次"""
        for wrapper in self._messages:
            if wrapper.round_id == round_id and not wrapper.is_compressed:
                wrapper.compressed_content = self._create_compressed_summary(wrapper)
                wrapper.is_compressed = True

    def _create_compressed_summary(self, wrapper: MessageWrapper) -> str:
        """创建压缩摘要"""
        msg = wrapper.message

        # Tool observation 保留关键信息
        if "tool_result" in str(msg.get("content", "")):
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        tool_content = str(block.get("content", ""))[:200]
                        return f"[Tool Result: {tool_content}...]"

        # 其他消息压缩为简单摘要
        role = msg.get("role", "")
        content_str = str(msg.get("content", ""))[:100]

        return f"[{role}] {content_str}..."

    def _group_by_round(self) -> Dict[str, List[MessageWrapper]]:
        """按轮次分组消息"""
        rounds: Dict[str, List[MessageWrapper]] = {}
        for wrapper in self._messages:
            round_id = wrapper.round_id or "default"
            if round_id not in rounds:
                rounds[round_id] = []
            rounds[round_id].append(wrapper)
        return rounds

    def get_compressed_messages(self) -> List[Dict[str, Any]]:
        """获取压缩后的消息列表（线程安全）"""
        with self._lock:
            result = []
            for wrapper in self._messages:
                if wrapper.is_compressed and wrapper.compressed_content:
                    result.append({
                        "role": "system",
                        "content": wrapper.compressed_content,
                        "compressed": True,
                        "original_round_id": wrapper.round_id
                    })
                else:
                    result.append(wrapper.message)
            return result

    @property
    def total_tokens(self) -> int:
        """获取当前总 Token 数（线程安全）"""
        with self._lock:
            return sum(m.tokens for m in self._messages)
```

---

## Implementation Roadmap
    """
    Manages conversation context and memory.

    Inspired by Clawdbot's FocusManager and Manus AI's context handling.
    """

    def __init__(self, max_tokens: int = 200000):
        self.max_tokens = max_tokens
        self.compression_threshold = 0.8

        # Context layers
        self.system_context: List[str] = []
        self.conversation_history: List[Dict[str, Any]] = []
        self.active_context: Dict[str, Any] = {}

    def add_system_context(self, context: str):
        """Add system-level context"""
        self.system_context.append(context)

    def add_message(self, message: Dict[str, Any]):
        """Add message to conversation history"""
        self.conversation_history.append(message)

        # Check if compression needed
        if self._should_compress():
            self._compress_context()

    def _should_compress(self) -> bool:
        """Check if context compression is needed"""
        # Simple char-based estimation (can be enhanced with tiktoken)
        total_chars = sum(len(str(msg.get("content", ""))) for msg in self.conversation_history)
        estimated_tokens = total_chars / 3  # Rough estimate
        return estimated_tokens > (self.max_tokens * self.compression_threshold)

    def _compress_context(self, keep_count: int = 5):
        """
        Compress conversation context.

        Strategy:
        - Keep last N rounds complete
        - Summarize earlier rounds
        - Preserve tool observations
        """
        if len(self.conversation_history) < 20:
            return

        recent = self.conversation_history[-keep_count:]
        older = self.conversation_history[:-keep_count]

        # Summarize older rounds
        summary = self._create_summary(older)

        # Rebuild history
        self.conversation_history = [
            {"role": "system", "content": summary}
        ] + recent

    def _create_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Create summary of older messages"""
        # Extract tool calls and results
        tool_activities = []
        for msg in messages:
            if "tool_use" in str(msg.get("content", "")):
                tool_activities.append(f"- Action: {msg.get('content', {})}")
            elif "tool_result" in str(msg.get("content", "")):
                content = msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if block.get("type") == "tool_result":
                            tool_activities.append(f"- Observation: {str(block.get('content', ''))[:100]}...")

        return "\n".join([
            "## Previous Context Summary",
            "\n".join(tool_activities[-20:])  # Keep last 20 activities
        ])
```

---

## Implementation Roadmap

### Phase 1: Core Message Format (Week 1)

- [x] ~~Simplify `ToolOutput` model~~ → **Clarify**: Use `observation` + `output_level`
- [ ] Create `OutputLevel` enum (BRIEF/STANDARD/FULL)
- [ ] Implement `ToolResultMessage` with observation + output_level + raw_data
- [ ] Update `StandardMessage` to match Claude Code format
- [ ] Implement observation formatting helpers (_format_brief, _format_standard, _format_full)
- [ ] Write unit tests (20 tests)

### Phase 2: Tool Communication Protocol (Week 2)

- [ ] Implement `ToolExecutionResult` with observation + output_level
- [ ] Implement `from_raw()` classmethod for level-based formatting
- [ ] Update all tools to support output_level parameter
- [ ] Implement error handling with proper observation messages
- [ ] Write integration tests (15 tests)

### Phase 3: Skill Communication Protocol (Week 2)

- [ ] Implement `SkillActivationRequest` with load_level for progressive disclosure
- [ ] Implement `SkillLoader` with 3-level loading
- [ ] Update skill system to use progressive disclosure
- [ ] Write skill integration tests (10 tests)

### Phase 4: Multi-Round Conversation (Week 3)

- [ ] Implement `ConversationRound` with ReAct loop tracking
- [ ] Implement `ContextManager` with compression
- [ ] Update BAAgent to use new message formats
- [ ] Write E2E tests (5 tests)

### Phase 5: Migration & Testing (Week 4)

- [ ] Migrate existing tools to simple observation format
- [ ] Update BAAgent to use Claude Code-style messages
- [ ] Update all tests
- [ ] Performance benchmarking
- [ ] Documentation updates

---

## Production Considerations

### 1. File Cleanup Strategy

```python
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict
import heapq
import threading

class DataFileManager:
    """
    管理工具数据的文件存储和清理

    清理策略：
    1. 基于时间：清理超过 max_age_hours 的文件
    2. 基于大小：当总大小超过 max_size_gb 时，按 LRU 清理
    3. 定期清理：每小时执行一次（使用守护线程）
    """

    STORAGE_DIR = Path("tool_data")
    METADATA_FILE = STORAGE_DIR / ".metadata.json"

    def __init__(
        self,
        max_age_hours: int = 24,
        max_size_gb: int = 10,
        cleanup_interval_seconds: int = 3600,
        auto_start: bool = True
    ):
        self.max_age = timedelta(hours=max_age_hours)
        self.max_size_bytes = max_size_gb * 1024 * 1024 * 1024
        self.cleanup_interval = cleanup_interval_seconds
        self._lock = threading.Lock()
        self._metadata: Dict[str, Dict] = {}

        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        # 自动启动后台清理任务
        if auto_start:
            self.start_cleanup_daemon()

    def start_cleanup_daemon(self):
        """显式启动清理守护线程（线程安全）"""
        with self._lock:
            if self._cleanup_thread is not None:
                logger.warning("Cleanup daemon already running")
                return

            def cleanup_thread_func():
                """后台清理线程主循环"""
                logger.info("Starting data file cleanup daemon")
                while not self._shutdown_event.is_set():
                    try:
                        self.cleanup_expired()
                        self.cleanup_by_size()
                    except Exception as e:
                        logger.error(f"Cleanup task error: {e}")

                    # 等待指定间隔或直到关闭事件
                    self._shutdown_event.wait(self.cleanup_interval)

                logger.info("Data file cleanup daemon stopped")

            self._cleanup_thread = threading.Thread(
                target=cleanup_thread_func,
                daemon=True,
                name="DataFileManager-Cleanup"
            )
            self._cleanup_thread.start()

    def stop_cleanup_daemon(self, timeout: float = 5.0):
        """
        停止清理守护线程（优雅关闭）

        Args:
            timeout: 等待线程结束的超时时间（秒）
        """
        with self._lock:
            if self._cleanup_thread is None:
                return

        self._shutdown_event.set()

        if self._cleanup_thread is not None:
            self._cleanup_thread.join(timeout=timeout)
            with self._lock:
                self._cleanup_thread = None

        logger.info("Cleanup daemon stopped")

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时自动停止清理线程"""
        self.stop_cleanup_daemon()

    def register_file(self, file_path: str, metadata: Dict):
        """注册新文件，记录元数据"""
        with self._lock:
            self._metadata[file_path] = {
                "created_at": datetime.now().isoformat(),
                "accessed_at": datetime.now().isoformat(),
                "size_bytes": metadata.get("size_bytes", 0),
                "tool_call_id": metadata.get("tool_call_id"),
                "conversation_id": metadata.get("conversation_id"),
            }
            self._save_metadata()

    def touch_file(self, file_path: str):
        """更新文件访问时间（用于 LRU）"""
        with self._lock:
            if file_path in self._metadata:
                self._metadata[file_path]["accessed_at"] = datetime.now().isoformat()
                self._save_metadata()

    def cleanup_expired(self) -> int:
        """清理过期文件"""
        now = datetime.now()
        expired_files = []
        total_freed = 0

        with self._lock:
            for file_path, meta in self._metadata.items():
                created_at = datetime.fromisoformat(meta["created_at"])
                if now - created_at > self.max_age:
                    expired_files.append(file_path)

            for file_path in expired_files:
                try:
                    path = Path(file_path)
                    if path.exists():
                        size = path.stat().st_size
                        path.unlink()
                        total_freed += size
                    del self._metadata[file_path]
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")

            if expired_files:
                self._save_metadata()

        logger.info(f"Cleaned up {len(expired_files)} expired files, freed {total_freed / 1024 / 1024:.1f} MB")
        return len(expired_files)

    def cleanup_by_size(self) -> int:
        """按大小限制清理（LRU 策略）"""
        total_size = sum(meta["size_bytes"] for meta in self._metadata.values())

        if total_size <= self.max_size_bytes:
            return 0

        # 按 accessed_at 排序（最老的先删）
        files_by_lru = sorted(
            self._metadata.items(),
            key=lambda x: x[1]["accessed_at"]
        )

        freed_files = []
        freed_bytes = 0
        target_size = self.max_size_bytes * 0.8  # 清理到 80%

        with self._lock:
            for file_path, meta in files_by_lru:
                if freed_bytes + total_size - self.max_size_bytes < target_size:
                    break

                try:
                    path = Path(file_path)
                    if path.exists():
                        size = path.stat().st_size
                        path.unlink()
                        freed_bytes += size
                    freed_files.append(file_path)
                    del self._metadata[file_path]
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")

            if freed_files:
                self._save_metadata()

        logger.info(f"Cleaned up {len(freed_files)} files by size, freed {freed_bytes / 1024 / 1024:.1f} MB")
        return len(freed_files)

    def _save_metadata(self):
        """保存元数据到文件"""
        try:
            with open(self.METADATA_FILE, 'w') as f:
                json.dump(self._metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def _load_metadata(self):
        """从文件加载元数据"""
        try:
            if self.METADATA_FILE.exists():
                with open(self.METADATA_FILE) as f:
                    self._metadata = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            self._metadata = {}
```

### 2. Activation Chain 管理（完整的 Push/Pop 逻辑）

```python
class SkillActivationStack:
    """
    管理 Skill 激活链的栈结构

    关键设计：
    - activation_chain 是调用栈（不是历史记录）
    - 每个激活时 push，完成时 pop
    - 支持嵌套调用的正确追踪
    """

    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth
        self._stack: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def push(self, skill_name: str, activation_id: str) -> bool:
        """
        推入新的 Skill 激活

        Returns:
            True if activation allowed, False if would exceed max depth
        """
        with self._lock:
            # 检查循环依赖
            if self.contains(skill_name):
                cycle_path = [f["skill_name"] for f in self._stack] + [skill_name]
                raise ValueError(
                    f"Circular dependency detected: {' → '.join(cycle_path)}"
                )

            # 检查深度
            if len(self._stack) >= self.max_depth:
                raise ValueError(
                    f"Maximum skill activation depth ({self.max_depth}) exceeded. "
                    f"Current stack: {' → '.join(self.get_stack_names())}"
                )

            # 推入栈
            self._stack.append({
                "skill_name": skill_name,
                "activation_id": activation_id,
                "timestamp": datetime.now().isoformat(),
            })
            return True

    def pop(self, skill_name: str, activation_id: str) -> bool:
        """
        弹出 Skill 激活

        Args:
            skill_name: 期望弹出的 skill 名称
            activation_id: 期望弹出的 activation ID

        Returns:
            True if pop 成功，False if栈顶不匹配
        """
        with self._lock:
            if not self._stack:
                logger.warning(f"Attempted to pop from empty stack: {skill_name}")
                return False

            top = self._stack[-1]
            if top["skill_name"] != skill_name or top["activation_id"] != activation_id:
                logger.error(
                    f"Stack mismatch: expected {top['skill_name']} "
                    f"but got {skill_name}"
                )
                return False

            self._stack.pop()
            return True

    def contains(self, skill_name: str) -> bool:
        """检查 skill 是否在当前栈中"""
        return any(f["skill_name"] == skill_name for f in self._stack)

    def get_stack_names(self) -> List[str]:
        """获取当前栈中的所有 skill 名称"""
        return [f["skill_name"] for f in self._stack]

    def get_depth(self) -> int:
        """获取当前栈深度"""
        return len(self._stack)

    def get_chain(self) -> List[str]:
        """获取完整调用链（与旧 API 兼容）"""
        return self.get_stack_names()

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """自动清理栈"""
        while self._stack:
            self._stack.pop()

# 使用示例
stack = SkillActivationStack(max_depth=3)

try:
    # 激活 Skill A
    stack.push("skill_a", "act_1")

    # 激活 Skill B（从 A 内部）
    stack.push("skill_b", "act_2")

    # 激活 Skill C（从 B 内部）
    stack.push("skill_c", "act_3")

    # 完成 Skill C
    stack.pop("skill_c", "act_3")

    # 完成 Skill B
    stack.pop("skill_b", "act_2")

    # 完成 Skill A
    stack.pop("skill_a", "act_1")

except ValueError as e:
    logger.error(f"Skill activation error: {e}")
```

### 3. 增强的上下文压缩（重要性评分）

```python
from dataclasses import dataclass, field
from enum import Enum

class MessageImportance(Enum):
    """消息重要性级别"""
    CRITICAL = 1   # 用户消息、错误
    HIGH = 2       # Tool observations
    MEDIUM = 3     # Agent thoughts
    LOW = 4        # 系统消息

@dataclass
class MessageWrapper:
    """包装消息，添加重要性元数据"""
    message: Dict[str, Any]
    importance: MessageImportance
    timestamp: datetime
    tokens: int
    round_id: str
    is_compressed: bool = False
    compressed_content: Optional[str] = None

class BasicContextManager:
    """
    基础上下文管理器 - 简单的基于重要性的压缩

    特性：
    1. 基于重要性的智能压缩
    2. 保留关键 Tool observations
    3. Token 准确计数
    4. 线程安全
    5. 同步操作（无 LLM 依赖）

    适用场景：
    - 不需要 LLM 摘要的简单应用
    - 对延迟敏感的场景
    - 资源受限环境
    """

    def __init__(self, max_tokens: int = 200000):
        self.max_tokens = max_tokens
        self.compression_threshold = 0.8
        self._messages: List[MessageWrapper] = []
        self._lock = threading.Lock()
        self._token_counter = get_token_counter()  # 使用单例

    def add_message(
        self,
        message: Dict[str, Any],
        importance: MessageImportance = MessageImportance.MEDIUM,
        round_id: str = ""
    ):
        """添加消息（线程安全）"""
        with self._lock:
            tokens = self._token_counter.count_message_tokens(message)

            wrapper = MessageWrapper(
                message=message,
                importance=importance,
                timestamp=datetime.now(),
                tokens=tokens,
                round_id=round_id
            )

            self._messages.append(wrapper)

            # 检查是否需要压缩
            if self._should_compress():
                self._compress_context()

    def _should_compress(self) -> bool:
        """检查是否需要压缩"""
        total_tokens = sum(m.tokens for m in self._messages)
        return total_tokens > (self.max_tokens * self.compression_threshold)

    def _compress_context(self):
        """
        基于重要性的智能压缩

        压缩优先级（从低到高）：
        1. LOW 重要性且超过 3 轮前的消息
        2. MEDIUM 重要性且超过 5 轮前的消息
        3. HIGH/CRITICAL 永不压缩
        4. Tool observations 总是保留原始内容
        """
        if len(self._messages) < 20:
            return

        # 计算每个轮次
        current_round = self._messages[-1].round_id if self._messages else ""
        round_groups: Dict[str, List[MessageWrapper]] = {}
        for m in self._messages:
            if m.round_id not in round_groups:
                round_groups[m.round_id] = []
            round_groups[m.round_id].append(m)

        # 找出需要压缩的轮次
        rounds_to_compress = []
        for round_id, group in round_groups.items():
            if round_id == current_round:
                continue  # 跳过当前轮次

            # 检查是否需要压缩该轮次
            has_important = any(
                m.importance in (MessageImportance.HIGH, MessageImportance.CRITICAL)
                for m in group
            )

            if not has_important and len(round_groups) > 5:
                rounds_to_compress.append(round_id)

        # 执行压缩
        for round_id in rounds_to_compress:
            self._compress_round(round_id)

    def _compress_round(self, round_id: str):
        """压缩单个轮次"""
        for i, wrapper in enumerate(self._messages):
            if wrapper.round_id == round_id and not wrapper.is_compressed:
                # 生成压缩摘要
                wrapper.compressed_content = self._create_compressed_summary(wrapper)
                wrapper.is_compressed = True

    def _create_compressed_summary(self, wrapper: MessageWrapper) -> str:
        """创建压缩摘要"""
        msg = wrapper.message

        # Tool observation 保留关键信息
        if "tool_result" in str(msg.get("content", "")):
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        tool_content = str(block.get("content", ""))[:200]
                        return f"[Tool Result: {tool_content}...]"

        # 其他消息压缩为简单摘要
        role = msg.get("role", "")
        content_str = str(msg.get("content", ""))[:100]

        return f"[{role}] {content_str}..."

    def get_compressed_messages(self) -> List[Dict[str, Any]]:
        """获取压缩后的消息列表"""
        with self._lock:
            result = []
            for wrapper in self._messages:
                if wrapper.is_compressed and wrapper.compressed_content:
                    # 返回压缩版本
                    result.append({
                        "role": "system",
                        "content": wrapper.compressed_content,
                        "compressed": True
                    })
                else:
                    # 返回原始版本
                    result.append(wrapper.message)
            return result

    @property
    def total_tokens(self) -> int:
        """获取当前总 Token 数（线程安全）"""
        with self._lock:
            return sum(m.tokens for m in self._messages)
```

### 4. 完整的线程安全考虑

```python
import threading
from contextlib import contextmanager
from typing import TypeVar, Generic, TypeVar, Generic

T = TypeVar('T')

class ThreadSafeContainer(Generic[T]):
    """
    线程安全的通用容器

    用于所有需要并发访问的数据结构：
    - ContextManager._messages
    - MetricsCollector._conversations
    - MessageInjectionProtocol._locks
    """

    def __init__(self):
        self._data: Dict[str, T] = {}
        self._lock = threading.RLock()  # 可重入锁
        self._lock_count = 0

    @contextmanager
    def _acquire(self):
        """获取锁（支持上下文管理器）"""
        self._lock.acquire()
        try:
            self._lock_count += 1
            yield
        finally:
            self._lock_count -= 1
            self._lock.release()

    def get(self, key: str) -> Optional[T]:
        """线程安全的获取"""
        with self._acquire():
            return self._data.get(key)

    def set(self, key: str, value: T):
        """线程安全的设置"""
        with self._acquire():
            self._data[key] = value

    def delete(self, key: str):
        """线程安全的删除"""
        with self._acquire():
            if key in self._data:
                del self._data[key]

    def keys(self) -> List[str]:
        """线程安全的键列表"""
        with self._acquire():
            return list(self._data.keys())

    def items(self) -> List[tuple]:
        """线程安全的项列表"""
        with self._acquire():
            return list(self._data.items())

# 应用到 ContextManager
class ThreadSafeContextManager(BasicContextManager):
    """线程安全的上下文管理器（使用 ThreadSafeContainer）"""

    def __init__(self, max_tokens: int = 200000):
        super().__init__(max_tokens)
        self._container = ThreadSafeContainer[MessageWrapper]()

    def add_message(
        self,
        message: Dict[str, Any],
        importance: MessageImportance = MessageImportance.MEDIUM,
        round_id: str = ""
    ):
        """线程安全地添加消息"""
        tokens = self._token_counter.count_message_tokens(message)

        wrapper = MessageWrapper(
            message=message,
            importance=importance,
            timestamp=datetime.now(),
            tokens=tokens,
            round_id=round_id
        )

        # 使用线程安全容器
        message_id = f"{round_id}_{len(self._container.items())}"
        self._container.set(message_id, wrapper)

# 应用到 MetricsCollector
class ThreadSafeMetricsCollector(MetricsCollector):
    """线程安全的指标收集器"""

    def __init__(self):
        self._container = ThreadSafeContainer[ConversationMetrics]()

    def record_tool_call(self, metrics: ToolMetrics, conversation_id: str):
        """线程安全地记录工具调用"""
        conv = self._container.get(conversation_id)
        if conv is None:
            with self._container._acquire():
                conv = ConversationMetrics(
                    conversation_id=conversation_id,
                    start_time=datetime.now()
                )
                self._container.set(conversation_id, conv)

        with self._container._acquire():
            conv.tool_calls.append(metrics)
            conv.total_tokens += metrics.total_tokens
            if metrics.success:
                conv.successful_calls += 1
            else:
                conv.failed_calls += 1
```

### 5. Schema 版本控制

```python
from typing import Literal
from enum import Enum

class SchemaVersion(str, Enum):
    """消息格式版本"""
    V1_0 = "1.0"  # 初始版本
    V1_4 = "1.4"  # 概念修正版本
    V1_5 = "1.5"  # Output Level 澄清版本
    V1_6 = "1.6"  # 生产增强版本
    V1_9 = "1.9"  # 重构优化版本（P0/P1/P2）
    LATEST = "1.9"  # 当前版本

# 版本兼容性矩阵
COMPATIBILITY = {
    "1.9": ["1.9", "1.6", "1.5", "1.4"],  # v1.9 可向后兼容读取
    "1.6": ["1.6", "1.5", "1.4"],
    "1.5": ["1.5", "1.4"],
    "1.4": ["1.4"],
}

class VersionedToolResult(ToolResultMessage):
    """带版本控制的消息格式"""

    schema_version: Literal["1.4", "1.5", "1.6"] = SchemaVersion.LATEST.value

    def is_compatible_with(self, target_version: str) -> bool:
        """检查与目标版本的兼容性"""
        return target_version in COMPATIBILITY.get(self.schema_version, [])

    def migrate_to(self, target_version: str) -> "VersionedToolResult":
        """迁移到目标版本"""
        if self.schema_version == target_version:
            return self

        # 迁移逻辑
        if self.schema_version == "1.4" and target_version == "1.5":
            # 添加 output_level 字段
            return VersionedToolResult(
                **self.model_dump(),
                schema_version="1.5",
                output_level=OutputLevel.STANDARD
            )

        # 更多迁移规则...

        raise ValueError(f"Cannot migrate from {self.schema_version} to {target_version}")

    @classmethod
    def from_legacy(cls, data: Dict, source_version: str) -> "VersionedToolResult":
        """从旧版本创建"""
        # 根据源版本进行转换
        if source_version == "1.4":
            # v1.4 没有 output_level，添加默认值
            if "output_level" not in data:
                data = data.copy()
                data["output_level"] = OutputLevel.STANDARD

        return cls(schema_version=SchemaVersion.LATEST.value, **data)
```

### 6. 可观测性配置

```python
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

class TraceSampling(str, Enum):
    """追踪采样率"""
    ALWAYS = "always"       # 100% 采样
    HIGH = "high"           # 50% 采样
    MEDIUM = "medium"       # 10% 采样
    LOW = "low"             # 1% 采样
    NEVER = "never"         # 不采样

@dataclass
class ObservabilityConfig:
    """统一的可观测性配置"""

    # 启用开关
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_logging: bool = True

    # 追踪配置
    trace_sampling: TraceSampling = TraceSampling.MEDIUM
    trace_export_timeout_ms: int = 5000
    trace_batch_size: int = 100

    # 指标配置
    metrics_export_interval_s: int = 60
    metrics_export_timeout_ms: int = 3000

    # 日志配置
    log_level: str = "INFO"
    log_format: str = "json"  # json 或 text
    log_output: List[str] = field(default_factory=lambda: ["stdout", "file"])

    # OpenTelemetry 集成
    otlp_endpoint: Optional[str] = None  # 例如: "http://localhost:4317"
    otlp_headers: Optional[Dict[str, str]] = None
    otlp_compression: str = "gzip"

    # 自定义标签
    service_name: str = "ba-agent"
    environment: str = "production"
    extra_tags: Dict[str, str] = field(default_factory=dict)

    def get_sampling_rate(self) -> float:
        """获取采样率"""
        sampling_map = {
            TraceSampling.ALWAYS: 1.0,
            TraceSampling.HIGH: 0.5,
            TraceSampling.MEDIUM: 0.1,
            TraceSampling.LOW: 0.01,
            TraceSampling.NEVER: 0.0,
        }
        return sampling_map.get(self.trace_sampling, 0.1)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        from dataclasses import asdict
        data = asdict(self)
        # 处理枚举
        data["trace_sampling"] = self.trace_sampling.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservabilityConfig":
        """从字典创建配置"""
        if "trace_sampling" in data and isinstance(data["trace_sampling"], str):
            data = data.copy()
            data["trace_sampling"] = TraceSampling(data["trace_sampling"])
        return cls(**data)

    def validate(self) -> bool:
        """验证配置有效性"""
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log_level: {self.log_level}")
        if self.log_format not in ["json", "text"]:
            raise ValueError(f"Invalid log_format: {self.log_format}")
        if self.metrics_export_interval_s <= 0:
            raise ValueError("metrics_export_interval_s must be positive")
        return True

# 全局可观测性配置
_global_observability_config: Optional[ObservabilityConfig] = None

def get_observability_config() -> ObservabilityConfig:
    """获取全局可观测性配置"""
    global _global_observability_config
    if _global_observability_config is None:
        _global_observability_config = ObservabilityConfig()
    return _global_observability_config

def configure_observability(config: ObservabilityConfig):
    """配置可观测性"""
    global _global_observability_config
    _global_observability_config = config

# 集成到工具执行
def execute_with_observability(
    tool_func: Callable,
    tool_name: str
) -> Callable:
    """
    为工具函数添加可观测性包装

    自动追踪：
    - 执行时间
    - Token 使用
    - 成功/失败状态
    - 自定义指标
    """
    import time
    from opentelemetry import trace

    config = get_observability_config()
    tracer = trace.get_tracer(__name__)

    def wrapper(*args, **kwargs):
        # 决定是否采样
        if random.random() > config.get_sampling_rate():
            return tool_func(*args, **kwargs)

        with tracer.start_as_current_span(f"tool.{tool_name}") as span:
            start_time = time.time()

            try:
                result = tool_func(*args, **kwargs)

                # 记录成功指标
                span.set_attribute("tool.name", tool_name)
                span.set_attribute("tool.success", True)
                span.set_attribute("tool.duration_ms", (time.time() - start_time) * 1000)

                return result

            except Exception as e:
                # 记录失败指标
                span.set_attribute("tool.success", False)
                span.set_attribute("tool.error", str(e))
                span.record_exception(e)
                raise

    return wrapper
```

---

## Sources

Research sources for this design:

- [Claude Code: Best practices for agentic coding](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Tracing Claude Code's LLM Traffic](https://medium.com/@georgesung/tracing-claude-codes-llm-traffic-agentic-loop-sub-agents-tool-use-prompts-7796941806f5)
- [从ReAct到CodeAct再到OpenManus - Zhihu](https://zhuanlan.zhihu.com/p/684765123)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)

---

**Document Status**: Design v1.9 - LLM-Enhanced Context Management
**Last Updated**: 2026-02-05
**Next Review Date**: 2026-02-12
**Approval Required**: @ba-agent-team

---

## Change History

### v2.0.0 (2026-02-06) - LangChain Implementation Alignment

**重大更新：对齐实际实现（LangChain ChatAnthropic + 同步工具）。**

**核心变更**：

1. **Carrier 与 Semantic 分离**
   - 新增 "Carrier（载体）" 概念，与 Observation（语义）分离
   - 明确研究层（Claude Code）与实现层（LangChain ToolMessage）的区别
   - 更新 Summary 表格，从 4 个概念扩展到 5 个

2. **LangChain 作为主协议**
   - Internal Message Format 章节：LangChain BaseMessage 为主
   - External/Research Format 章节：Claude Code blocks 降级为可选
   - 添加 LangChain tool-call loop 标准循环描述

3. **Tool Result 转换方法**
   - `to_tool_message()`: 返回 LangChain ToolMessage（主要方法）
   - `to_user_message()`: 标记为 deprecated（仅用于研究/调试）
   - ToolExecutionResult 添加 `to_tool_message()` 方法

4. **tool_call_id 来源明确化**
   - ToolInvocationRequest 明确：tool_call_id 来自 AIMessage.tool_calls[i]["id"]
   - 添加正确/错误示例对比
   - 添加 idempotency_key 和 get_or_generate_idempotency_key() 方法

5. **同步压缩策略**
   - AdvancedContextManager: `async def _compress_context()` → `def _compress_context()`
   - SUMMARIZE 策略改为：主链路使用 EXTRACT，后台线程执行 LLM 摘要
   - 添加 `_trigger_background_summarization()` 方法

6. **OutputLevel 措辞修正**
   - 将 "Progressive Disclosure" 改为 "verbosity/detail level"
   - 明确 OutputLevel 仅用于控制工具输出的详细程度
   - Progressive Disclosure 专用于 Skills 系统

**文档结构优化**:
- 添加 "Implementation Layer" 说明，区分研究层和实现层
- 标注 deprecated 方法，避免混淆
- 添加更多 LangChain 特定示例

**与实现一致性**: 现在文档与 `backend/agents/agent.py` 的实际实现完全一致

### v1.9.5 (2026-02-06) - Review Fixes

**修复文档 review 发现的问题。**

**修复内容**:

1. **删除重复的 ToolInvocationRequest 定义**
   - 删除 Line 1177 的重复定义
   - 保留 Line 811 的完整版本
   - 添加交叉引用说明

2. **更新 SchemaVersion**
   - 添加 V1_9 = "1.9" 版本
   - 更新 LATEST = "1.9"
   - 更新版本兼容性矩阵

3. **修复 ABC import 位置**
   - 在 BaseConfig 定义前添加 `from abc import ABC, abstractmethod`

4. **文档优化**
   - 从 4689 行减少到 4665 行（节省 24 行）
   - 添加幂等性使用示例

### v1.9.4 (2026-02-06) - P2 Configuration Unification

**统一配置类接口，添加配置序列化支持。**

**新增功能**:

1. **统一配置类接口**
   - `to_dict()`: 序列化为字典
   - `from_dict()`: 从字典反序列化
   - `validate()`: 验证配置有效性

2. **配置类更新**
   - `EncoderConfig`: 添加 to_dict/from_dict/validate
   - `ContextCompressionConfig`: 添加 to_dict/from_dict/validate
   - `ObservabilityConfig`: 添加 to_dict/from_dict/validate

3. **配置类文档**
   - 新增 "Configuration Classes" 章节
   - 统一接口说明
   - 使用示例

**文档优化**:
- 添加配置类统一接口文档
- 添加配置序列化示例
- 统一配置验证逻辑

### v1.9.3 (2026-02-06) - P1 Code Quality Improvements

**提升代码质量，提取通用组件，统一锁管理。**

**新增组件**:

1. **TTLCache 基类** (泛型缓存抽象)
   - `TTLCache[K, V]`: 通用 TTL 缓存基类
   - 支持泛型键值对
   - 自动过期清理
   - 线程安全
   - 最大条目限制

2. **IdempotencyCache 重构**
   - 继承 `TTLCache[str, ToolExecutionResult]`
   - 保留语义化方法名 (`get_cached_result`, `cache_result`)
   - 消除重复代码

3. **SummaryCache 重构**
   - 继承 `TTLCache[str, Dict[str, Any]]`
   - 简化实现，复用基类逻辑

4. **ThreadSafeMixin**
   - 为类提供简单的线程安全支持
   - 统一锁管理模式
   - 上下文管理器支持 (`with self._with_lock()`)

**代码优化**:
- 提取 ~80 行重复的 TTL 逻辑
- 统一锁管理接口
- 改善代码可维护性

### v1.9.2 (2026-02-06) - P0 Redundancy Elimination

**消除设计文档中的严重冗余，提升代码可维护性。**

**修复内容**:

1. **TokenCounter 统一**
   - 删除旧 `TokenCounter` 类（~175 行）
   - 保留 `DynamicTokenCounter` 作为唯一实现
   - 所有引用改为使用 `get_token_counter()` 单例
   - 支持动态模型识别和配置文件

2. **ContextManager 类重构**
   - 第一个 `EnhancedContextManager` → `AdvancedContextManager`
     - 支持 LLM 摘要、异步操作、3 种压缩策略
   - 第二个 `EnhancedContextManager` → `BasicContextManager`
     - 简单同步版本，无 LLM 依赖
   - `ThreadSafeContextManager` 改为继承 `BasicContextManager`

**文档优化**:
- 从 4478 行减少到 4318 行（节省 160 行）
- 消除同名类冲突
- 统一 TokenCounter 使用单例模式

### v1.9 (2026-02-06) - LLM-Enhanced Context Management

**基于用户需求实现的 LLM 摘要压缩功能。**

**新增内容**:

1. **LLM 摘要压缩** (ContextCompressionStrategy)
   - 三种压缩策略：TRUNCATE（免费）/EXTRACT（规则）/SUMMARIZE（LLM）
   - 自动策略选择：根据消息数量、成本、配置动态选择
   - 使用 Claude 3 Haiku（小模型，快速，成本优化）

2. **LLMCompressor 类**
   - 异步摘要生成：anthropic.AsyncAnthropic
   - 智能摘要 Prompt：保留关键信息（用户意图、工具调用、结果）
   - Token 成本控制：max_summary_tokens（默认 500）
   - 超时和错误处理

3. **SummaryCache 类**
   - 避免重复摘要相同内容
   - 基于 round_id + message_hash 的缓存键
   - TTL 过期清理（默认 24 小时）
   - 线程安全实现

4. **AdvancedContextManager 升级**
   - `_compress_truncate()`: 简单截断（快速，免费）
   - `_compress_extract()`: 提取关键信息（规则，中等速度）
   - `_compress_summarize()`: LLM 摘要（高质量，有成本）
   - 智能策略选择：根据消息数量、重要性、成本

5. **CompressionCostEstimate**
   - 估算各策略的 Token 成本
   - 输入/输出 Token 计数
   - API 调用成本估算（Claude 定价）

**v1.9 新增评分**:

| 方面 | v1.7 | v1.9 |
|------|------|------|
| 上下文压缩 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 成本优化 | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 智能化 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

### v1.8 (2026-02-06) - Bug Fixes and Production Improvements

**修复设计评审中的高优先级问题。**

**高优先级修复**:

1. **Token Counter 修正**
   - 添加 15% safety margin 用于 Claude tokenizer
   - cl100k_base 是 OpenAI 的，不是 Claude 的
   - 准确计数 + 安全余量

2. **DataFileManager 后台任务修复**
   - 从 `asyncio.create_task` 改为 `threading.Thread`
   - 显式 `start_cleanup_daemon()` 方法
   - 优雅关闭 `stop_cleanup_daemon()`
   - 上下文管理器支持

3. **LockManager 锁管理改进**
   - 替代 LRU 缓存避免驱逐问题
   - 引用计数确保只驱逐未使用的锁
   - 自动清理机制

**中优先级新增**:

4. **ToolErrorType 完整分类**
   - `is_retryable` 属性：判断错误是否可重试
   - 区分可重试（TIMEOUT, RATE_LIMIT）vs 不可重试错误

5. **IdempotencyCache 幂等性支持**
   - 防止重复执行相同工具调用
   - TTL 过期清理
   - 自动生成幂等键（tool_name + parameters hash）

### v1.7 (2026-02-05) - Production-Grade Completeness

**基于设计评审反馈的完整性和健壮性增强。**

**新增内容**:

1. **文件清理策略** (DataFileManager)
   - 基于时间的清理：max_age_hours（默认 24 小时）
   - 基于大小的清理：max_size_gb（默认 10GB）
   - LRU 策略清理：按访问时间排序
   - 后台定期清理任务（每小时）
   - 元数据持久化到 .metadata.json

2. **Activation Chain 完整管理** (SkillActivationStack)
   - 明确 activation_chain 是"调用栈"而非"历史记录"
   - 完整的 push/pop 逻辑
   - 支持嵌套调用的正确追踪
   - 上下文管理器支持自动清理
   - 循环依赖检测显示完整路径

3. **增强的上下文压缩** (BasicContextManager)
   - 基于重要性的智能压缩（MessageImportance 枚举）
   - CRITICAL（用户消息、错误）永不压缩
   - HIGH（Tool observations）保留关键信息
   - Token 准确计数（使用 DynamicTokenCounter）
   - 线程安全实现
   - 同步操作，无 LLM 依赖

4. **完整的线程安全** (ThreadSafeContainer)
   - 通用线程安全容器
   - 使用 RLock 可重入锁
   - 上下文管理器支持
   - 应用到 ContextManager、MetricsCollector

5. **Schema 版本控制** (VersionedToolResult)
   - schema_version 字段标识版本
   - 版本兼容性矩阵
   - migrate_to() 版本迁移方法
   - from_legacy() 旧版本数据导入

6. **可观测性配置** (ObservabilityConfig)
   - 统一的可观测性配置类
   - 追踪采样率配置（ALWAYS/HIGH/MEDIUM/LOW/NEVER）
   - OpenTelemetry 集成支持
   - execute_with_observability 包装器

**设计评分提升**:

| 方面 | v1.6 | v1.7 |
|------|------|------|
| 完整性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 健壮性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 可维护性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

### v1.6 (2026-02-05) - Production-Ready Enhancements

**Comprehensive improvements based on design review feedback.**

**Addressed Issues**:

1. **Output Level Decision Mechanism**
   - Added `get_effective_output_level()` with fallback chain:
     - Explicit parameter > Tool config > Global default > Dynamic adjustment
   - Dynamic adjustment based on context window usage (>80% → BRIEF)

2. **File-Based Data Storage** (Memory Management)
   - Large data (>1MB) stored in files instead of memory
   - `data_file` field contains path to stored data
   - `data_summary` generated for FULL level
   - Subsequent tool calls can access stored data via file path

3. **Lock Management** (Prevent Memory Leak)
   - Changed from unbounded `_locks: Dict` to LRU cache
   - `@lru_cache(maxsize=1000)` on `_get_lock()`
   - Automatic lock eviction when cache is full

4. **Standardized Error Format**
   - Added `format_error_observation()` method
   - Consistent error format across all tools:
     ```
     Operation failed.
     Error Type: {type}
     Error Code: {code}
     Error Message: {message}
     Tool Call ID: {id}
     ```

5. **Indirect Cycle Detection**
   - Enhanced `can_activate_nested()` to detect indirect cycles
   - `activation_chain` accumulated across all nested activations
   - Clear error messages showing full cycle path

6. **Accurate Token Counting**
   - Added `TokenCounter` class using tiktoken
   - Supports multiple models (claude-3, gpt-4, etc.)
   - `count_tokens()`, `count_message_tokens()`, `count_conversation_tokens()`

7. **Retry Policy**
   - Added `ToolRetryPolicy` with exponential backoff
   - Configurable: `max_retries`, `backoff_multiplier`, `max_delay_ms`
   - Timeout-specific handling with `timeout_multiplier`

8. **Timeout Handling**
   - Added `ToolTimeoutHandler` class
   - Pre-execution input size validation
   - Async execution with timeout using `asyncio.wait_for()`
   - Graceful fallback on timeout

9. **Monitoring Metrics**
   - Added `ToolMetrics` and `ConversationMetrics` dataclasses
   - Per-tool statistics: call count, avg duration, success rate
   - Global `MetricsCollector` for cross-conversation aggregation
   - Human-readable reports with `to_report()`

**Key Changes**:
- All tools now support file-based storage for large data
- Lock management uses LRU cache (max 1000 conversations)
- Error format is standardized across all tools
- Token counting uses tiktoken (accurate, not estimation)
- Comprehensive monitoring and metrics collection
- Production-ready retry and timeout handling

**Further clarification based on user feedback about orthogonal concepts.**

Key insight: **ReAct Observation** (semantic) and **Output Level** (engineering) are ORTHOGONAL:

1. **ReAct Observation** (Semantic Concept)
   - The actual content that LLM sees and reasons with
   - Direct input to the next Thought in ReAct loop
   - Example: "Found 3 Python files in the project"

2. **Output Level** (Engineering Optimization)
   - Controls HOW detailed to format the observation
   - BRIEF: Key facts only
   - STANDARD: Actionable information
   - FULL: Complete data
   - Example: Same data, different formatting levels

3. **Corrected Understanding**
   - Observation ≠ Output Level (they're independent)
   - Observation is WHAT (semantic content)
   - Output Level is HOW (formatting detail)
   - Both are orthogonal to Progressive Disclosure (Skills loading)

**Key Changes**:
- Added `OutputLevel` enum (BRIEF/STANDARD/FULL)
- Updated `ToolResultMessage` with `output_level` field
- Added `raw_data` preservation (for engineering use)
- Updated "Summary of Separation" table with 4 concepts
- Added observation formatting helper functions
- Clarified the orthogonal relationship in diagrams

### v1.4 (2026-02-05) - Conceptual Correction

**Major redesign based on user feedback about conceptual confusion.**

Corrected three previously conflated concepts:

1. **ReAct Pattern** (Agent Execution Loop)
   - Clarified as control flow pattern: Thought → Action → Observation
   - NOT a tool output format
   - This is how the agent reasons, not how tools return data

2. **Tool Output Format** (Simplified)
   - Removed `summary` and `result` fields
   - Now returns simple `observation` string only
   - Matches Claude Code's straightforward approach
   - Tool results are sent as `role: "user"` messages

3. **Progressive Disclosure** (Skills System)
   - Clarified as information loading strategy for Skills
   - Level 1: Frontmatter metadata (~100 tokens)
   - Level 2: Full SKILL.md (~5000 tokens)
   - Level 3: Resource files (on-demand)
   - NOT related to tool output format

**Key Changes**:
- Removed incorrect "Three-Layer Context: Summary → Observation → Result" from executive summary
- Removed incorrect "ReAct Compatible" claim from tool output format
- Simplified `ToolExecutionResult` to single `observation` field
- Added detailed "Core Concepts Clarification" section
- Updated all diagrams and code examples
- Clarified that tool results are simple user messages with observation strings

### v1.3 (2026-02-05) - Engineering Production-Ready

*Previous version with conceptual errors (kept for reference)*

### v1.2 (2026-02-05) - Production Environment Enhancements

### v1.1 (2026-02-05) - Review Response

---

## Appendix: ReAct Pattern in Detail

### Understanding ReAct

ReAct (Reasoning + Acting) is a paradigm where language models generate reasoning traces and task-specific actions in an interleaved manner.

```
Thought: I need to find information about Python files in the project
Action: Search[Glob]("**/*.py")
Observation: src/main.py, utils/helper.py, tests/test_main.py
Thought: I should read the main file to understand the structure
Action: Read[FileReader]("src/main.py")
Observation: [file content]
Thought: Now I understand the project structure
Final Answer: The project has three Python files...
```

### Key Insights

1. **Thought**: The model's internal reasoning process
2. **Action**: The tool/skill being invoked
3. **Observation**: The raw result from tool execution
4. This is a **reasoning pattern**, not a data structure

### Common Misconceptions

❌ **Incorrect**: "Tool output should have summary → observation → result format"
✅ **Correct**: "Tool output has a single `observation` field (the ReAct Observation)"

❌ **Incorrect**: "Output Level is part of ReAct"
✅ **Correct**: "Output Level is an engineering optimization, orthogonal to ReAct Observation"

❌ **Incorrect**: "Progressive disclosure applies to tool outputs"
✅ **Correct**: "Progressive disclosure applies to Skills system (metadata → full → resources)"

❌ **Incorrect**: "ReAct defines the tool output format"
✅ **Correct**: "ReAct defines the agent's reasoning loop, not tool output format"

### Orthogonal Concepts Summary

| Concept | Type | Purpose |
|---------|------|---------|
| **ReAct** | Control Flow | Agent reasoning pattern |
| **Observation** | Semantic | What the tool returns (LLM input) |
| **Output Level** | Engineering | How detailed to format (token optimization) |
| **Progressive Disclosure** | Information Loading | How to load Skills (3-level) |

These are **four independent, orthogonal concepts**.
