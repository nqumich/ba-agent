# BA-Agent Information Pipeline Design Document

> **Date**: 2026-02-05
> **Version**: v1.4 (Conceptual Correction)
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

**Tool Output** is how tools return data to the agent. In Claude Code, this is **simple and straightforward**.

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
- The `content` field contains the plain observation string
- **No** summary/observation/result three-layer structure
- **No** complex nested formats
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

| Concept | Purpose | Scope |
|---------|---------|-------|
| **ReAct** | Agent reasoning pattern | Control flow |
| **Tool Output** | Data return format | Tool results |
| **Progressive Disclosure** | Information loading strategy | Skills system |

These are **three separate, independent concepts** that should not be conflated.

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
2. **Simple observation format**: Tool results are plain text strings, not complex nested structures
3. **ReAct is execution flow**: The Thought→Action→Observation pattern is how the agent reasons, not a data format
4. **Minimal wrapping**: No unnecessary layers between tool execution and agent observation

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

### 3. Tool Result Format (SIMPLE)

```python
class ToolResultMessage(BaseModel):
    """Format for tool execution results - SIMPLE format like Claude Code"""
    tool_call_id: str  # References ToolCallMessage.tool_call_id

    # Simple observation string (NOT multi-layer)
    observation: str

    # Status
    success: bool = True
    error_message: Optional[str] = None

    def to_content_block(self) -> ContentBlock:
        """Convert to ContentBlock for LLM"""
        content = self.observation if self.success else f"Error: {self.error_message}"
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

**Design Decision**: Removed the `summary` and `result` fields. Tools now return a simple `observation` string, matching Claude Code's approach.

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

    # Execution context
    timeout_ms: int = 120000

    # Security
    caller_id: str  # Agent or skill ID
    permission_level: str = "default"
```

#### Phase 2: Tool Execution Result (SIMPLE)

**Direction**: Tool → Agent

```python
class ToolExecutionResult(BaseModel):
    """Simple result format from tool execution"""
    request_id: str

    # Simple observation string
    observation: str

    # Status
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_llm_message(self) -> Dict[str, Any]:
        """
        Convert to message for LLM.
        KEY: Simple observation string, not multi-layer format.
        Tool results are sent as USER messages.
        """
        content = self.observation if self.success else f"Error: {self.error_message}"

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
        """Check if nested skill activation is allowed"""
        if skill_name in self.activation_chain:
            return False  # Circular dependency
        return self.activation_depth < self.max_depth
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

class MessageInjectionProtocol:
    """
    Protocol for injecting skill messages into conversation.

    Thread-safe with atomic state updates.
    """

    _locks: Dict[str, threading.Lock] = {}
    _locks_lock = threading.Lock()

    @classmethod
    @contextmanager
    def _conversation_lock(cls, conversation_id: str):
        """Get or create lock for conversation"""
        with cls._locks_lock:
            if conversation_id not in cls._locks:
                cls._locks[conversation_id] = threading.Lock()
        lock = cls._locks[conversation_id]
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

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

- [ ] Simplify `ToolOutput` model - remove summary/result, keep only observation
- [ ] Update `StandardMessage` to match Claude Code format
- [ ] Implement `to_langchain_format()` method
- [ ] Write unit tests (20 tests)

### Phase 2: Tool Communication Protocol (Week 2)

- [ ] Implement `ToolExecutionResult` with simple observation format
- [ ] Update all tools to return simple observation strings
- [ ] Implement error handling
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

## Sources

Research sources for this design:

- [Claude Code: Best practices for agentic coding](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Tracing Claude Code's LLM Traffic](https://medium.com/@georgesung/tracing-claude-codes-llm-traffic-agentic-loop-sub-agents-tool-use-prompts-7796941806f5)
- [从ReAct到CodeAct再到OpenManus - Zhihu](https://zhuanlan.zhihu.com/p/684765123)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)

---

**Document Status**: Design v1.4 - Conceptual Correction
**Last Updated**: 2026-02-05
**Next Review Date**: 2026-02-12
**Approval Required**: @ba-agent-team

---

## Change History

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
✅ **Correct**: "Tool output is a simple observation string; the agent formats its own response"

❌ **Incorrect**: "Progressive disclosure applies to tool outputs"
✅ **Correct**: "Progressive disclosure applies to Skills system (metadata → full → resources)"

❌ **Incorrect**: "ReAct defines the tool output format"
✅ **Correct**: "ReAct defines the agent's reasoning loop, not tool output format"
