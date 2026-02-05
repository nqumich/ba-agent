# BA-Agent Information Pipeline Design Document

> **日期**: 2026-02-05
> **版本**: v1.0
> **作者**: BA-Agent Development Team
> **状态**: Design Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
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

This document defines the comprehensive information pipeline architecture for BA-Agent, a business analysis AI agent system. The design is based on research into Claude Code's architecture and best practices from other agentic systems like Manus AI and OpenClaw.

### Key Design Principles

1. **Standardized Message Format**: All components use a consistent message format
2. **Three-Layer Context**: Summary → Observation → Result (progressive disclosure)
3. **ReAct Compatible**: Observation format follows standard ReAct patterns
4. **Tool Telemetry**: Built-in observability for all tool executions
5. **Context Modifiers**: Skills can modify agent execution context
6. **Memory Management**: Efficient context window usage through compression

---

## Current State Analysis

### Existing BA-Agent Components

#### 1. Tool Output Format (`backend/models/tool_output.py`)

```python
class ToolOutput(BaseModel):
    # Model context (passed to next round)
    result: Optional[Any] = None
    summary: str = ""
    observation: str = ""

    # Token efficiency
    response_format: ResponseFormat = ResponseFormat.STANDARD

    # Engineering telemetry (not passed to model)
    telemetry: ToolTelemetry = Field(default_factory=ToolTelemetry)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # State management
    state_update: Optional[Dict[str, Any]] = None
    checkpoint: Optional[str] = None
```

**Strengths**:
- Well-structured three-layer context (summary/observation/result)
- Built-in telemetry for observability
- Response format levels for token efficiency
- ReAct-compatible observation format

**Gaps**:
- Not consistently used across all tools
- No standard tool call format definition
- Missing error handling specification

#### 2. Skill Message Protocol (`backend/skills/message_protocol.py`)

```python
@dataclass
class SkillMessage:
    type: MessageType  # METADATA/INSTRUCTION/PERMISSIONS
    content: Any
    visibility: MessageVisibility  # VISIBLE/HIDDEN
    role: str = "user"

@dataclass
class ContextModifier:
    allowed_tools: Optional[List[str]] = None
    model: Optional[str] = None
    disable_model_invocation: bool = False

@dataclass
class SkillActivationResult:
    skill_name: str
    messages: List[SkillMessage]
    context_modifier: ContextModifier
    success: bool = True
    error: Optional[str] = None
```

**Strengths**:
- Clear separation of message types
- Context modifier well-defined
- Good visibility control

**Gaps**:
- No standard error response format
- Missing message flow documentation

#### 3. Agent Implementation (`backend/agents/agent.py`)

**Current Flow**:
```
User Request → BAAgent.invoke() → LangGraph Agent
                ↓
        Tool Call → Tool Execution → ToolResult
                ↓
        Skill Activation → Message Injection → Context Modifier Application
                ↓
        Response → User
```

**Gaps**:
- No standardized message format for LangGraph messages
- Tool result extraction logic is brittle
- Message injection timing not well-defined

---

## Claude Code Research Findings

### 1. Message Format Structure

Based on tracing Claude Code's LLM traffic, the message format follows this structure:

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "...",
          "cache_control": {"type": "ephemeral"}
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {
          "type": "thinking",
          "thinking": "..."
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
          "content": "file1.py\nfile2.py...",
          "is_error": false
        }
      ]
    }
  ]
}
```

### 2. Tool Result Format

**Critical Insight**: Tool results are sent as `role: "user"` messages!

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "call_3cs6eu75",
      "content": "/path/to/file1.py\n/path/to/file2.py",
      "is_error": false
    }
  ]
}
```

### 3. Agentic Loop Pattern

```
User Request
    ↓
LLM generates tool_use
    ↓
Tool executes
    ↓
Result returned as tool_result (user message)
    ↓
LLM processes result → Next action or Final Answer
```

### 4. Sub-Agent Communication

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
      "text": "## Comprehensive Report\n..."
    },
    {
      "type": "text",
      "text": "agentId: a09479d (for resuming)"
    }
  ]
}
```

### 5. System Reminders

System messages injected with metadata:
```json
{
  "role": "user",
  "content": "<system-reminder>CRITICAL: This is a READ-ONLY task...</system-reminder>"
}
```

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
│                         │  (Meta-Tool) │                         │
│                         └──────────────┘                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Message Flow

```
User Request
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Standardized Request Format                        │
│  - User message with context                                   │
│  - System prompt with tool descriptions                        │
│  - Active skill context                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Agent Processing (LangGraph)                        │
│  - LLM reasoning                                               │
│  - Tool selection                                              │
│  - Parameter construction                                      │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Tool Execution                                      │
│  - Permission check (Context Modifier)                        │
│  - Tool invocation                                             │
│  - Result capture                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Response Format Selection                           │
│  - CONCISE: summary only                                       │
│  - STANDARD: summary + observation                             │
│  - DETAILED: full result + telemetry                           │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 5: Message Injection (if skill)                        │
│  - Skill activation result                                    │
│  - Context modifier application                               │
│  - Message list injection                                     │
└─────────────────────────────────────────────────────────────┘
    ↓
Final Response
```

---

## Message Format Specifications

### Message Validation Layer

```python
from functools import wraps

def validate_message(msg_type: Type[BaseModel]):
    """
    Decorator to validate message format at layer boundaries.

    Ensures message integrity across component boundaries.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract message from args (first arg usually self, second is message)
            if len(args) > 1:
                msg = args[1]
                try:
                    # Validate and parse message
                    if isinstance(msg, dict):
                        validated = msg_type(**msg)
                        # Replace with validated instance
                        args = list(args)
                        args[1] = validated
                        args = tuple(args)
                except Exception as e:
                    raise ValueError(f"Message validation failed: {e}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Example usage:
# @validate_message(ToolExecutionResult)
# def process_tool_result(self, result: ToolExecutionResult):
#     ...
```

### 1. Standard Message Format

### 1. Standard Message Format

All messages in BA-Agent follow this base structure:

```python
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum

class MessageType(str, Enum):
    """Message type identifiers"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_RESULT = "tool_result"
    TOOL_USE = "tool_use"
    SKILL_ACTIVATION = "skill_activation"

class ContentBlockType(str, Enum):
    """Content block types"""
    TEXT = "text"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    SYSTEM_REMINDER = "system_reminder"

class ContentBlock(BaseModel):
    """Standardized content block"""
    type: ContentBlockType
    content: Any

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
    conversation_id: str
    user_id: str

    def to_langchain_format(self) -> Dict[str, Any]:
        """Convert to LangChain message format"""
        # CRITICAL: Use .value for consistent serialization
        return {
            "role": self.role.value,  # Always use enum value
            "content": [block.model_dump(exclude_none=True) for block in self.content],
            "timestamp": self.timestamp,
            "message_id": self.message_id
        }
```

### 2. Tool Call Message Format

```python
class ToolCallMessage(BaseModel):
    """Format for tool invocation requests"""
    message_id: str
    tool_name: str
    parameters: Dict[str, Any]
    response_format: ResponseFormat = ResponseFormat.STANDARD

    # Context
    conversation_id: str
    user_id: str
    timestamp: str

    def to_content_block(self) -> ContentBlock:
        """Convert to ContentBlock for LLM"""
        return ContentBlock(
            type=ContentBlockType.TOOL_USE,
            id=self.message_id,
            name=self.tool_name,
            input=self.parameters
        )
```

### 3. Tool Result Message Format

```python
class ToolResultMessage(BaseModel):
    """Format for tool execution results"""
    tool_call_id: str  # References ToolCallMessage.message_id

    # Result data (three layers)
    summary: str                    # Human-readable summary
    observation: str                # ReAct-compatible observation
    result: Optional[Any] = None    # Full result data

    # Telemetry
    telemetry: ToolTelemetry
    response_format: ResponseFormat

    # Status
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_content_block(self) -> ContentBlock:
        """Convert to ContentBlock for LLM"""
        return ContentBlock(
            type=ContentBlockType.TOOL_RESULT,
            tool_use_id=self.tool_call_id,
            content=self.observation if self.success else f"Error: {self.error_message}",
            is_error=not self.success
        )

    def to_user_message(self) -> StandardMessage:
        """
        Convert to user message for LLM.
        KEY INSIGHT from Claude Code: Tool results are sent as user messages!
        """
        return StandardMessage(
            role=MessageType.USER,
            content=[self.to_content_block()],
            conversation_id="",
            user_id=""
        )
```

### 4. Skill Activation Message Format

```python
class SkillActivationMessage(BaseModel):
    """Format for skill activation requests"""
    skill_name: str
    activation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Context for skill
    conversation_context: List[Dict[str, Any]]
    user_request: str

    def to_tool_call(self) -> ToolCallMessage:
        """Convert to tool call format"""
        return ToolCallMessage(
            message_id=self.activation_id,
            tool_name="activate_skill",
            parameters={"skill_name": self.skill_name},
            response_format=ResponseFormat.STANDARD,
            conversation_id="",
            user_id="",
            timestamp=datetime.now().isoformat()
        )
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

    # Execution context
    response_format: ResponseFormat = ResponseFormat.STANDARD
    timeout_ms: int = 120000

    # Security
    caller_id: str  # Agent or skill ID
    permission_level: str = "default"  # default/restricted/admin
```

#### Phase 2: Tool Execution Result

**Direction**: Tool → Agent

```python
class ToolExecutionResult(BaseModel):
    """Standardized result format from tool execution"""
    request_id: str

    # Three-layer result
    summary: str                    # For quick LLM understanding
    observation: str                # ReAct-compatible
    result: Optional[Any] = None    # Full data

    # Response format
    response_format: ResponseFormat

    # Telemetry
    telemetry: ToolTelemetry

    # Status
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # State management (for tools that modify state)
    state_update: Optional[Dict[str, Any]] = None
    checkpoint: Optional[str] = None

    def to_llm_message(self) -> Dict[str, Any]:
        """
        Convert to message for LLM.
        CRITICAL: Tool results are sent as USER messages in Claude Code's architecture
        """
        content = self.observation if self.success else f"Error: {self.error_message}"

        if self.response_format == ResponseFormat.CONCISE:
            # Only summary
            final_content = self.summary
        elif self.response_format == ResponseFormat.STANDARD:
            # Summary + observation
            final_content = f"{self.summary}\n\nObservation: {content}"
        else:  # DETAILED or RAW
            # Full result
            final_content = f"{self.summary}\n\nObservation: {content}\n\nResult: {self.result}"

        return {
            "role": "user",  # KEY: Tool results are user messages
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": self.request_id,
                    "content": final_content,
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

class ToolRetryPolicy(BaseModel):
    """Retry configuration for tool execution"""
    max_retries: int = 3
    retry_on: List[ToolErrorType] = Field(
        default_factory=lambda: [ToolErrorType.TIMEOUT, ToolErrorType.RESOURCE_ERROR]
    )
    backoff_multiplier: float = 1.5
    initial_delay_ms: int = 1000
    max_delay_ms: int = 10000

    def should_retry(self, error_type: ToolErrorType, attempt: int) -> bool:
        """Check if operation should be retried"""
        return error_type in self.retry_on and attempt < self.max_retries

    def get_delay(self, attempt: int) -> int:
        """Calculate delay with exponential backoff"""
        delay = self.initial_delay_ms * (self.backoff_multiplier ** attempt)
        return min(int(delay), self.max_delay_ms)
```

class ToolErrorResponse(BaseModel):
    """Standardized error response"""
    request_id: str
    error_type: ToolErrorType
    error_code: str
    error_message: str

    # Debug information
    traceback: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)

    def to_result(self) -> ToolExecutionResult:
        """Convert to ToolExecutionResult"""
        return ToolExecutionResult(
            request_id=self.request_id,
            summary=f"Error: {self.error_message}",
            observation=f"Observation: Tool Error [{self.error_code}] - {self.error_message}",
            result=None,
            response_format=ResponseFormat.STANDARD,
            telemetry=ToolTelemetry(
                success=False,
                error_code=self.error_code,
                error_message=self.error_message
            ),
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

    # Parameters
    parameters: Dict[str, Any] = Field(default_factory=dict)

    # Execution options
    response_format: ResponseFormat = ResponseFormat.STANDARD

    # Circular dependency prevention
    activation_depth: int = 0
    max_depth: int = 3

    def can_activate_nested(self) -> bool:
        """Check if nested skill activation is allowed"""
        return self.activation_depth < self.max_depth

    def create_nested_request(self, nested_skill: str) -> "SkillActivationRequest":
        """Create request for nested skill activation"""
        if not self.can_activate_nested():
            raise ValueError(f"Maximum skill activation depth ({self.max_depth}) exceeded")
        return SkillActivationRequest(
            skill_name=nested_skill,
            conversation_id=self.conversation_id,
            user_request=self.user_request,
            conversation_history=self.conversation_history,
            activation_depth=self.activation_depth + 1,
            max_depth=self.max_depth
        )
```

#### Phase 2: Skill Activation Result

**Direction**: Skill System → Agent

```python
class SkillActivationResult(BaseModel):
    """Result from skill activation"""
    activation_id: str
    skill_name: str

    # Messages to inject
    messages: List[SkillMessage]

    # Context modifier
    context_modifier: ContextModifier

    # Status
    success: bool
    error: Optional[str] = None

    def to_llm_messages(self) -> List[Dict[str, Any]]:
        """
        Convert to messages for LLM injection.

        Returns a list of LangChain-compatible messages.
        """
        result = []

        for msg in self.messages:
            if msg.visibility == MessageVisibility.HIDDEN:
                # Hidden instruction - use AIMessage with isMeta flag
                result.append({
                    "role": "assistant",
                    "content": msg.content,
                    "additional_kwargs": {"isMeta": True}
                })
            else:
                # Visible message - use HumanMessage
                result.append({
                    "role": "user",
                    "content": msg.content
                })

        return result
```

### Message Injection Protocol

```python
import threading
from contextlib import contextmanager

class MessageInjectionProtocol:
    """
    Protocol for injecting skill messages into conversation.

    Thread-safe with atomic state updates.

    Based on Claude Code's sub-agent communication pattern.
    """

    # Per-conversation locks for thread safety
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
            messages: Messages to inject
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
    """A single round of conversation"""
    round_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str

    # Messages
    user_message: str
    assistant_thought: Optional[str] = None  # Thinking before action
    tool_calls: List[ToolCallMessage] = Field(default_factory=list)
    tool_results: List[ToolResultMessage] = Field(default_factory=list)
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

        Implements strategy from Clawdbot/OpenClaw:
        - Keep recent rounds complete
        - Compress old rounds to summaries
        - Preserve tool calls and results
        """
        if not self.should_compress_context():
            # Return full history
            return self._get_full_history()

        # Compress old rounds
        compressed = []
        for i, round_data in enumerate(self.rounds):
            if i < len(self.rounds) - 3:  # Keep last 3 rounds complete
                # Compress to summary
                compressed.append({
                    "role": "system",
                    "content": f"[Round {i+1} Summary] {round_data.final_answer or 'Incomplete'}"
                })
            else:
                # Keep complete
                compressed.extend(self._round_to_messages(round_data))

        return compressed

    def _round_to_messages(self, round_data: ConversationRound) -> List[Dict[str, Any]]:
        """Convert a round to message list"""
        messages = []

        # User message
        messages.append({
            "role": "user",
            "content": round_data.user_message
        })

        # Tool calls and results (if any)
        for tool_call in round_data.tool_calls:
            messages.append({
                "role": "assistant",
                "content": [{
                    "type": "tool_use",
                    "id": tool_call.message_id,
                    "name": tool_call.tool_name,
                    "input": tool_call.parameters
                }]
            })

        for tool_result in round_data.tool_results:
            messages.append({
                "role": "user",  # Tool results are user messages!
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_result.tool_call_id,
                    "content": tool_result.observation,
                    "is_error": not tool_result.success
                }]
            })

        # Final answer (if any)
        if round_data.final_answer:
            messages.append({
                "role": "assistant",
                "content": round_data.final_answer
            })

        return messages
```

### Context Management

```python
class ContextManager:
    """
    Manages conversation context and memory.

    Inspired by Clawdbot's FocusManager and MemoryFlush.
    """

    def __init__(self, max_tokens: int = 200000):
        self.max_tokens = max_tokens
        self.compression_threshold = 0.8
        self.refocus_interval = 5  # Rounds between refocus

        # Context layers
        self.system_context: List[str] = []
        self.conversation_history: List[Dict[str, Any]] = []
        self.active_context: Dict[str, Any] = {}

        # Focus management
        self.round_count = 0

    def add_system_context(self, context: str):
        """Add system-level context"""
        self.system_context.append(context)

    def add_message(self, message: Dict[str, Any]):
        """Add message to conversation history"""
        self.conversation_history.append(message)
        self.round_count += 1

        # Check if refocus needed
        if self.round_count % self.refocus_interval == 0:
            self._refocus()

        # Check if compression needed
        if self._should_compress():
            self._compress_context()

    def _should_compress(self) -> bool:
        """
        Check if context compression is needed.

        Improved token estimation:
        - English: ~4 characters per token
        - Chinese: ~1.5 characters per token
        - Mixed: Weighted average
        """
        total_chars = 0
        chinese_chars = 0

        for msg in self.conversation_history:
            content = str(msg.get("content", ""))
            total_chars += len(content)
            # Count Chinese characters (CJK range)
            chinese_chars += sum(1 for c in content if '\u4e00' <= c <= '\u9fff')

        # Calculate weighted token estimate
        if total_chars == 0:
            return False

        chinese_ratio = chinese_chars / total_chars
        # Blend char/token ratios based on content
        chars_per_token = 4 * (1 - chinese_ratio) + 1.5 * chinese_ratio
        estimated_tokens = int(total_chars / chars_per_token)

        return estimated_tokens > (self.max_tokens * self.compression_threshold)

    def _compress_context(self):
        """
        Compress conversation context.

        Strategy (from Clawdbot/OpenClaw):
        - Keep last N rounds complete
        - Summarize earlier rounds
        - Preserve tool calls and critical information
        """
        if len(self.conversation_history) < 10:
            return

        # Keep last 5 rounds
        keep_count = 5
        recent = self.conversation_history[-keep_count:]
        older = self.conversation_history[:-keep_count]

        # Summarize older rounds
        summary = self._create_summary(older)

        # Rebuild history
        self.conversation_history = [
            {"role": "system", "content": summary}
        ] + recent

    def _create_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Create semantic summary of older messages.

        Enhanced to preserve key decisions and tool outcomes.
        """
        # Extract key decisions and tool outcomes
        key_decisions = self._extract_key_decisions(messages)
        tool_outcomes = self._extract_tool_outcomes(messages)

        summary_parts = [
            f"## Previous Context Summary",
            f"### Key Decisions",
            *key_decisions,
            f"",
            f"### Tool Outcomes",
            *tool_outcomes,
        ]

        return "\n".join(summary_parts)

    def _extract_key_decisions(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract key decisions from conversation history"""
        decisions = []
        for msg in messages:
            content = str(msg.get("content", ""))
            # Look for decision patterns
            if any(keyword in content.lower() for keyword in ["decided", "selected", "chose", "确定", "选择"]):
                # Extract the decision sentence
                decisions.append(f"- {content[:100]}...")
        return decisions[:5]  # Keep top 5

    def _extract_tool_outcomes(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract tool execution outcomes"""
        outcomes = []
        for msg in messages:
            if "tool_result" in str(msg.get("content", "")):
                content = msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if block.get("type") == "tool_result":
                            tool_name = block.get("name", "unknown")
                            outcome = "✓" if not block.get("is_error") else "✗"
                            outcomes.append(f"- {tool_name}: {outcome}")
        return outcomes[:10]  # Keep top 10

    def _refocus(self):
        """Re-focus on main task (from Manus AI)"""
        if not self.system_context:
            return

        # Inject system context as reminder
        focus_message = {
            "role": "system",
            "content": f"\n# Context Reminder (Round {self.round_count})\n\n" + "\n".join(self.system_context)
        }

        self.conversation_history.append(focus_message)
```

---

## Implementation Roadmap

### Phase 1: Core Message Format (Week 1)

- [ ] Define `StandardMessage` and `ContentBlock` in `backend/models/message.py`
- [ ] Implement `to_langchain_format()` method
- [ ] Add message validation
- [ ] Write unit tests (20 tests)

### Phase 2: Tool Communication Protocol (Week 2)

- [ ] Implement `ToolInvocationRequest`
- [ ] Implement `ToolExecutionResult` with `to_llm_message()`
- [ ] Implement `ToolErrorResponse` and error types
- [ ] Update all tools to use new format
- [ ] Write integration tests (15 tests)

### Phase 3: Skill Communication Protocol (Week 2)

- [ ] Update `SkillActivationResult` with new methods
- [ ] Implement `MessageInjectionProtocol`
- [ ] Update skill system to use new format
- [ ] Write skill integration tests (10 tests)

### Phase 4: Multi-Round Conversation (Week 3)

- [ ] Implement `ConversationRound` and `MultiRoundConversation`
- [ ] Implement `ContextManager`
- [ ] Add context compression
- [ ] Implement refocus mechanism
- [ ] Write E2E tests (5 tests)

### Phase 5: Migration & Testing (Week 4)

- [ ] Migrate existing tools to new format
- [ ] Update BAAgent to use new message formats
- [ ] Update tests
- [ ] Performance benchmarking
- [ ] Documentation updates

---

## Sources

Research sources for this design:

- [Claude Code: Best practices for agentic coding](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Tracing Claude Code's LLM Traffic](https://medium.com/@georgesung/tracing-claude-codes-llm-traffic-agentic-loop-sub-agents-tool-use-prompts-7796941806f5)

---

**Document Status**: Design v1.1 - Updated based on review feedback
**Last Updated**: 2026-02-05
**Next Review Date**: 2026-02-12
**Approval Required**: @ba-agent-team

---

## Change History

### v1.1 (2026-02-05) - Review Response

Addressed 7 issues identified in design review:

1. **Fixed Message Format Consistency** (Issue #1)
   - Changed `to_langchain_format()` to use `.value` for enum serialization
   - All message formats now consistently use enum values

2. **Enhanced Context Compression** (Issue #2)
   - Added `_extract_key_decisions()` to preserve important decisions
   - Added `_extract_tool_outcomes()` to preserve tool execution results
   - Context now retains semantic information during compression

3. **Added Retry Policy** (Issue #3)
   - New `ToolRetryPolicy` class with configurable retry behavior
   - Exponential backoff with max delay cap
   - `should_retry()` and `get_delay()` methods

4. **Fixed Race Conditions** (Issue #4)
   - Added per-conversation locking mechanism
   - Atomic state read-modify-write operations
   - Context manager for lock lifecycle management

5. **Added Message Validation Layer** (Issue #5)
   - `@validate_message` decorator for format validation
   - Validates messages at layer boundaries
   - Prevents format errors from propagating

6. **Prevented Circular Dependencies** (Issue #6)
   - Added `activation_depth` and `max_depth` to `SkillActivationRequest`
   - `can_activate_nested()` check before nested activation
   - `create_nested_request()` for safe nested calls

7. **Improved Token Estimation** (Issue #7)
   - Distinguishes between Chinese and English text
   - Weighted char/token ratio: 4.0 (EN) vs 1.5 (ZH)
   - More accurate context compression triggers
