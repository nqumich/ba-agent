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
        # Implementation for LangGraph compatibility
        pass
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
class MessageInjectionProtocol:
    """
    Protocol for injecting skill messages into conversation.

    Based on Claude Code's sub-agent communication pattern.
    """

    @staticmethod
    def inject_into_state(
        messages: List[Dict[str, Any]],
        conversation_id: str,
        agent_state: Any
    ) -> bool:
        """
        Inject messages into LangGraph agent state.

        Args:
            messages: Messages to inject
            conversation_id: Conversation ID
            agent_state: Current agent state

        Returns:
            Success status
        """
        try:
            # Get current state
            state = agent_state.get_state({"configurable": {"thread_id": conversation_id}})
            current_messages = list(state.messages.get("messages", []))

            # Add new messages
            for msg_dict in messages:
                if msg_dict.get("role") == "user":
                    current_messages.append(HumanMessage(content=msg_dict["content"]))
                elif msg_dict.get("role") == "assistant":
                    additional_kwargs = msg_dict.get("additional_kwargs", {})
                    current_messages.append(AIMessage(
                        content=msg_dict["content"],
                        additional_kwargs=additional_kwargs
                    ))

            # Update state
            agent_state.update_state(
                {"configurable": {"thread_id": conversation_id}},
                {"messages": current_messages}
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
        """Check if context compression is needed"""
        # Estimate tokens (rough: 1 token ≈ 4 characters)
        total_chars = sum(len(str(m.get("content", ""))) for m in self.conversation_history)
        estimated_tokens = total_chars // 4

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
        """Create summary of older messages"""
        # Extract key information
        tool_calls = [m for m in messages if "tool_use" in str(m.get("content", ""))]
        results = [m for m in messages if "tool_result" in str(m.get("content", ""))]

        summary_parts = [
            f"Summary of {len(messages)} previous messages:",
            f"- {len(tool_calls)} tool calls executed",
            f"- {len(results)} tool results received",
        ]

        return "\n".join(summary_parts)

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

**Document Status**: Design Draft - Pending Review
**Next Review Date**: 2026-02-12
**Approval Required**: @ba-agent-team
