# BA-Agent Information Pipeline Design Document

> **Date**: 2026-02-05
> **Version**: v1.7 (Production-Grade Completeness)
> **Author**: BA-Agent Development Team
> **Status**: Design Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Core Concepts Clarification](#core-concepts-clarification)
3. [Claude Code Research Findings](#claude-code-research-findings)
4. [Proposed Information Pipeline Architecture](#proposed-information-pipeline-architecture)
5. [Message Format Specifications](#message-format-specifications)
6. [Tool ↔ Agent Communication Protocol](#tool--agent-communication-protocol)
7. [Skill ↔ Agent Communication Protocol](#skill--agent-communication-protocol)
8. [Multi-Round Conversation Flow](#multi-round-conversation-flow)
9. [Context Management Strategy](#context-management-strategy)
10. [Implementation Roadmap](#implementation-roadmap)

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

**Tool Output** has TWO ORTHOGONAL aspects:

1. **ReAct Observation** (Semantic): What information the tool returns for Agent reasoning
2. **Output Level** (Engineering): How detailed the observation is (token optimization)

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
└─────────────────────────────────────────────────────────────┘
```

**Claude Code Format**:
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

**Key Points**:
- Tool results are sent as `role: "user"` messages
- The `content` field is the **observation** (ReAct Observation)
- **No** summary/observation/result three-layer structure (that was confusion)
- Output level controls HOW we format the observation from raw data
- The agent sees the tool result as a simple text observation

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
| **Progressive Disclosure** | Information loading strategy | Skills system | Level 1→2→3 for Skills |

These are **FOUR separate concepts**:
1. **ReAct**: The reasoning loop pattern
2. **Observation**: The semantic content returned by tools
3. **Output Level**: How detailed to format the observation (orthogonal to observation)
4. **Progressive Disclosure**: How to load skill information (unrelated to tools)

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

1. **Tool results are user messages**: The agent receives tool results as `role: "user"` messages
2. **Observation = ReAct Observation**: The `content` field IS the Observation that LLM reasons with
3. **Output Level ≠ ReAct**: Output level controls formatting detail, orthogonal to the Observation semantic
4. **ReAct is execution flow**: The Thought→Action→Observation pattern is how the agent reasons, not a data format
5. **Minimal wrapping**: No unnecessary layers between tool execution and agent observation

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

### 1. Standard Message Format

All messages in BA-Agent follow Claude Code's structure:

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
    """Standardized content block"""
    type: ContentBlockType

    # Text content
    text: Optional[str] = None

    # Thinking content
    thinking: Optional[str] = None

    # Tool use specific
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[Dict[str, Any]] = None

    # Tool result specific
    tool_use_id: Optional[str] = None
    is_error: bool = False

    # Caching
    cache_control: Optional[Dict[str, str]] = None

class StandardMessage(BaseModel):
    """Standard message format for BA-Agent"""
    role: MessageType
    content: List[ContentBlock]

    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Context
    conversation_id: str = ""
    user_id: str = ""

    def to_langchain_format(self) -> Dict[str, Any]:
        """Convert to LangChain message format"""
        return {
            "role": self.role.value,
            "content": [block.model_dump(exclude_none=True) for block in self.content],
            "timestamp": self.timestamp,
            "message_id": self.message_id,
        }
```

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
    Controls the detail level of observation (Progressive Disclosure)

    This is an ENGINEERING optimization for token efficiency,
    orthogonal to ReAct Observation (semantic concept).

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

    def to_user_message(self) -> StandardMessage:
        """
        Convert to user message for LLM.
        KEY: Tool results are sent as user messages in Claude Code!
        """
        return StandardMessage(
            role=MessageType.USER,
            content=[self.to_content_block()]
        )
```

**Design Decision**:
1. **Single observation field**: The ReAct Observation that LLM sees
2. **Output level control**: Progressive disclosure for token optimization
3. **File-based storage**: Large data stored in files, not memory
4. **Data summary**: Generated for FULL level to provide context
5. **Standardized error format**: Consistent error structure for Agent processing
6. **OutputLevel decision**: Parameter → Tool config → Global default → Dynamic

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

```python
class ToolInvocationRequest(BaseModel):
    """Request format when Agent calls a tool"""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

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

    def to_llm_message(self) -> Dict[str, Any]:
        """
        Convert to message for LLM.

        KEY:
        - observation IS the ReAct Observation
        - output_level controls its format
        - Tool results sent as USER messages
        - Errors use standardized format
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
    """Standardized error types"""
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    INVALID_PARAMETERS = "invalid_parameters"
    EXECUTION_ERROR = "execution_error"
    RESOURCE_ERROR = "resource_error"

class ToolErrorResponse(BaseModel):
    """Standardized error response"""
    request_id: str
    error_type: ToolErrorType
    error_code: str
    error_message: str

    def to_result(self) -> ToolExecutionResult:
        """Convert to ToolExecutionResult"""
        return ToolExecutionResult(
            request_id=self.request_id,
            observation=f"Tool Error [{self.error_code}]: {self.error_message}",
            success=False,
            error_code=self.error_code,
            error_message=self.error_message
        )
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
from functools import lru_cache
import asyncio

class MessageInjectionProtocol:
    """
    Protocol for injecting skill messages into conversation.

    Thread-safe with atomic state updates.
    Uses LRU cache for locks to prevent unbounded growth.
    """

    # Use LRU cache to limit lock storage (max 1000 conversations)
    @classmethod
    @lru_cache(maxsize=1000)
    def _get_lock(cls, conversation_id: str) -> threading.Lock:
        """Get or create lock for conversation (cached with LRU)"""
        return threading.Lock()

    @classmethod
    @contextmanager
    def _conversation_lock(cls, conversation_id: str):
        """Get or create lock for conversation"""
        lock = cls._get_lock(conversation_id)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    @classmethod
    def cleanup_lock(cls, conversation_id: str) -> bool:
        """
        Explicitly cleanup lock for a conversation.

        Note: With LRU cache, locks are automatically evicted when cache is full.
        This method is for explicit cleanup when conversation ends.
        """
        try:
            # Clear from LRU cache
            cls._get_lock.cache_clear()
            return True
        except Exception:
            return False

    @staticmethod
    def inject_into_state(
        messages: List[Dict[str, Any]],
        conversation_id: str,
        agent_state: Any
    ) -> bool:
        """
        Thread-safely inject messages into LangGraph agent state.

        Args:
            messages: Messages to inject (from SkillActivationResult)
            conversation_id: Conversation ID
            agent_state: Current agent state

        Returns:
            Success status
        """
        with MessageInjectionProtocol._conversation_lock(conversation_id):
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

### Accurate Token Counting

```python
import tiktoken
from functools import lru_cache

class TokenCounter:
    """
    Accurate token counting for LLM messages.

    Uses tiktoken for precise token counting instead of character estimation.
    """

    # Cache encoders (per model)
    _encoders: Dict[str, Any] = {}

    @classmethod
    def get_encoder(cls, model: str = "claude-3"):
        """
        Get tokenizer for model.

        Supports:
        - claude-3: cl100k_base encoding
        - gpt-4: cl100k_base encoding
        - gpt-3.5: cl100k_base encoding
        """
        if model not in cls._encoders:
            # Map to tiktoken encoding name
            encoding_map = {
                "claude-3": "cl100k_base",
                "claude-3.5": "cl100k_base",
                "claude-3-opus": "cl100k_base",
                "claude-3-sonnet": "cl100k_base",
                "gpt-4": "cl100k_base",
                "gpt-3.5-turbo": "cl100k_base",
            }
            encoding_name = encoding_map.get(model, "cl100k_base")
            cls._encoders[model] = tiktoken.get_encoding(encoding_name)
        return cls._encoders[model]

    @classmethod
    def count_tokens(cls, text: str, model: str = "claude-3") -> int:
        """
        Count tokens in text for specific model.

        Args:
            text: Text to count
            model: Model name (affects encoding)

        Returns:
            Exact token count
        """
        encoder = cls.get_encoder(model)
        return len(encoder.encode(text))

    @classmethod
    def count_message_tokens(
        cls,
        message: Dict[str, Any],
        model: str = "claude-3"
    ) -> int:
        """
        Count tokens in a message (including role and content structure).

        Args:
            message: Message in Claude Code format
            model: Model name

        Returns:
            Total token count for the message
        """
        # Count role
        tokens = cls.count_tokens(message.get("role", ""), model)

        # Count content blocks
        content = message.get("content", [])
        if isinstance(content, list):
            for block in content:
                block_type = block.get("type", "")
                if block_type == "text":
                    tokens += cls.count_tokens(block.get("text", ""), model)
                elif block_type == "tool_use":
                    tokens += cls.count_tokens(block.get("name", ""), model)
                    # Count input parameters
                    input_data = block.get("input", {})
                    tokens += cls.count_tokens(json.dumps(input_data), model)
                elif block_type == "tool_result":
                    tokens += cls.count_tokens(block.get("content", ""), model)
        elif isinstance(content, str):
            tokens += cls.count_tokens(content, model)

        return tokens

    @classmethod
    def count_conversation_tokens(
        cls,
        messages: List[Dict[str, Any]],
        model: str = "claude-3"
    ) -> int:
        """Count total tokens in conversation"""
        return sum(cls.count_message_tokens(msg, model) for msg in messages)
```

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

### Context Manager

```python
class ContextManager:
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
    3. 定期清理：每小时执行一次
    """

    STORAGE_DIR = Path("tool_data")
    METADATA_FILE = STORAGE_DIR / ".metadata.json"

    def __init__(
        self,
        max_age_hours: int = 24,
        max_size_gb: int = 10,
        cleanup_interval_seconds: int = 3600
    ):
        self.max_age = timedelta(hours=max_age_hours)
        self.max_size_bytes = max_size_gb * 1024 * 1024 * 1024
        self.cleanup_interval = cleanup_interval_seconds
        self._lock = threading.Lock()
        self._metadata: Dict[str, Dict] = {}

        # 启动后台清理任务
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """启动后台清理任务"""
        import asyncio

        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.cleanup_interval)
                    self.cleanup_expired()
                    self.cleanup_by_size()
                except Exception as e:
                    logger.error(f"Cleanup task error: {e}")

        # 在实际应用中，应该在单独的线程/进程中运行
        asyncio.create_task(cleanup_loop())

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

class EnhancedContextManager:
    """
    增强的上下文管理器

    特性：
    1. 基于重要性的智能压缩
    2. 保留关键 Tool observations
    3. Token 准确计数
    4. 线程安全
    """

    def __init__(self, max_tokens: int = 200000):
        self.max_tokens = max_tokens
        self.compression_threshold = 0.8
        self._messages: List[MessageWrapper] = []
        self._lock = threading.Lock()
        self._token_counter = TokenCounter()

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
class ThreadSafeContextManager(EnhancedContextManager):
    """线程安全的上下文管理器"""

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
    V1_6 = "1.6"  # 生产增强版本（当前）
    LATEST = "1.6"

# 版本兼容性矩阵
COMPATIBILITY = {
    "1.6": ["1.6", "1.5", "1.4"],  # v1.6 可读取 1.4-1.6
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

**Document Status**: Design v1.7 - Production-Grade Completeness
**Last Updated**: 2026-02-05
**Next Review Date**: 2026-02-12
**Approval Required**: @ba-agent-team

---

## Change History

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

3. **增强的上下文压缩** (EnhancedContextManager)
   - 基于重要性的智能压缩（MessageImportance 枚举）
   - CRITICAL（用户消息、错误）永不压缩
   - HIGH（Tool observations）保留关键信息
   - Token 准确计数（使用 TokenCounter）
   - 线程安全实现

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
