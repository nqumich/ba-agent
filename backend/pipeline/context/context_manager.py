"""
Advanced Context Manager

LLM-based context compression and management.

Design v2.0.1:
- Synchronous compression (main thread uses TRUNCATE/EXTRACT)
- Background LLM summarization
- Token-aware message filtering
- Configurable compression strategies
"""

import json
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from backend.pipeline.token import DynamicTokenCounter


class CompressionMode(str, Enum):
    """Context compression mode."""
    TRUNCATE = "truncate"  # Simple truncation (fast, loses information)
    EXTRACT = "extract"    # Extract key messages (smart, needs heuristics)
    SUMMARIZE = "summarize"  # LLM summarization (best, slow)


class MessagePriority(str, Enum):
    """Message priority for filtering."""
    CRITICAL = "critical"  # Must keep (system messages, errors)
    HIGH = "high"         # Should keep (user messages, tool results)
    MEDIUM = "medium"     # Maybe keep (assistant reasoning)
    LOW = "low"           # Can drop (verbose logs)


class AdvancedContextManager:
    """
    Advanced context manager with LLM-based summarization.

    Features:
    - Token-aware compression
    - Multiple compression modes
    - Message priority filtering
    - Background summarization
    - Configurable strategies
    """

    def __init__(
        self,
        max_tokens: int = 100000,
        compression_mode: CompressionMode = CompressionMode.TRUNCATE,
        llm_summarizer: Optional[Any] = None,
        token_counter: Optional[DynamicTokenCounter] = None,
    ):
        """
        Initialize advanced context manager.

        Args:
            max_tokens: Maximum context tokens before compression
            compression_mode: Default compression mode
            llm_summarizer: LLM for SUMMARIZE mode (e.g., ChatAnthropic)
            token_counter: Token counter for accurate counting
        """
        self.max_tokens = max_tokens
        self.compression_mode = compression_mode
        self.llm_summarizer = llm_summarizer
        self.token_counter = token_counter or DynamicTokenCounter()

        # Background summarization state
        self._background_summaries: Dict[str, BaseMessage] = {}
        self._background_lock = threading.Lock()

    def compress(
        self,
        messages: List[BaseMessage],
        target_tokens: Optional[int] = None,
        mode: Optional[CompressionMode] = None,
    ) -> List[BaseMessage]:
        """
        Compress message list to fit within target token limit.

        Args:
            messages: List of messages to compress
            target_tokens: Target token count (uses max_tokens if not specified)
            mode: Compression mode (uses default if not specified)

        Returns:
            Compressed message list
        """
        target = target_tokens or self.max_tokens
        mode = mode or self.compression_mode

        # Count current tokens
        current_tokens = self.count_tokens(messages)

        if current_tokens <= target:
            # No compression needed
            return messages

        # Compress based on mode
        if mode == CompressionMode.TRUNCATE:
            return self._truncate(messages, target)
        elif mode == CompressionMode.EXTRACT:
            return self._extract(messages, target)
        elif mode == CompressionMode.SUMMARIZE:
            return self._summarize(messages, target)
        else:
            # Default to truncate
            return self._truncate(messages, target)

    def _truncate(
        self,
        messages: List[BaseMessage],
        target_tokens: int,
    ) -> List[BaseMessage]:
        """
        Simple truncation - drop oldest messages.

        Keeps system messages and drops from front until target is reached.
        """
        # Separate system messages
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        conversation = [m for m in messages if not isinstance(m, SystemMessage)]

        # Drop from front (oldest) until we fit
        result = []
        current_count = 0

        # Start with system messages
        for msg in system_msgs:
            current_count += self._count_single(msg)
            result.append(msg)

        # Add conversation messages from end (newest) until we'd exceed target
        for msg in reversed(conversation):
            msg_tokens = self._count_single(msg)
            if current_count + msg_tokens > target:
                # Would exceed, stop here
                break
            result.insert(len(system_msgs), msg)
            current_count += msg_tokens

        return result

    def _extract(
        self,
        messages: List[BaseMessage],
        target_tokens: int,
    ) -> List[BaseMessage]:
        """
        Extract key messages based on priority.

        Priority:
        1. System messages (CRITICAL)
        2. User messages (HIGH)
        3. Tool results (HIGH)
        4. Assistant messages (MEDIUM)
        5. Low-priority assistant messages (LOW)
        """
        # Assign priorities
        prioritized = []

        for msg in messages:
            priority = self._get_priority(msg)
            prioritized.append((priority, msg))

        # Sort by priority (keep highest priority)
        prioritized.sort(key=lambda x: self._priority_order(x[0]))

        # Keep messages until target is reached
        result = []
        current_count = 0

        for priority, msg in prioritized:
            msg_tokens = self._count_single(msg)
            if current_count + msg_tokens > target:
                # Would exceed, skip
                continue
            result.append(msg)
            current_count += msg_tokens

        # Sort back to original order
        # We need to track original positions
        result_with_pos = [(m, messages.index(m)) for m in result]
        result_with_pos.sort(key=lambda x: x[1])
        result = [m for m, _ in result_with_pos]

        return result

    def _summarize(
        self,
        messages: List[BaseMessage],
        target_tokens: int,
    ) -> List[BaseMessage]:
        """
        LLM-based summarization.

        Compresses old messages into a summary and keeps recent messages.
        """
        if not self.llm_summarizer:
            # No LLM, fall back to extract
            return self._extract(messages, target_tokens)

        # Separate system and conversation
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        conversation = [m for m in messages if not isinstance(m, SystemMessage)]

        if len(conversation) <= 2:
            # Too few messages to summarize
            return messages

        # Split: recent messages (keep) + old messages (summarize)
        # Keep last 4 messages, summarize the rest
        keep_count = 4
        old_messages = conversation[:-keep_count]
        recent_messages = conversation[-keep_count:]

        # Create summary of old messages
        summary_text = self._create_summary(old_messages)

        # Build new message list
        result = []

        # System messages
        result.extend(system_msgs)

        # Summary (as system message for context)
        result.append(SystemMessage(content=f"[Previous conversation summary]\\n{summary_text}"))

        # Recent messages
        result.extend(recent_messages)

        return result

    def _create_summary(self, messages: List[BaseMessage]) -> str:
        """Create summary of messages using LLM."""
        try:
            # Format messages for summarization
            prompt = self._format_for_summary(messages)

            # Call LLM
            response = self.llm_summarizer.invoke(prompt)

            # Extract summary text
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)

        except Exception as e:
            # Fallback to simple summary
            return f"[Error creating summary: {e}] Previous conversation contained {len(messages)} messages."

    def _format_for_summary(self, messages: List[BaseMessage]) -> str:
        """Format messages for LLM summarization."""
        lines = ["Summarize the following conversation:"]
        lines.append("")

        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "User"
            elif isinstance(msg, AIMessage):
                role = "Assistant"
            elif isinstance(msg, ToolMessage):
                role = "Tool"
            elif isinstance(msg, SystemMessage):
                role = "System"
            else:
                role = "Unknown"

            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Truncate very long messages
            if len(content) > 1000:
                content = content[:1000] + "..."

            lines.append(f"{role}: {content}")

        lines.append("")
        lines.append("Provide a concise summary of the key points discussed.")

        return "\\n".join(lines)

    def summarize_async(
        self,
        messages: List[BaseMessage],
        conversation_id: str,
    ) -> None:
        """
        Start background summarization for a conversation.

        Args:
            messages: Messages to summarize
            conversation_id: Unique ID for this conversation
        """
        def _background_task():
            try:
                summary_text = self._create_summary(messages)
                summary_msg = SystemMessage(content=f"[Summary]\\n{summary_text}")

                with self._background_lock:
                    self._background_summaries[conversation_id] = summary_msg
            except Exception:
                pass  # Silently fail for background task

        thread = threading.Thread(target=_background_task, daemon=True)
        thread.start()

    def get_background_summary(self, conversation_id: str) -> Optional[BaseMessage]:
        """Get background summary if available."""
        with self._background_lock:
            return self._background_summaries.get(conversation_id)

    def _get_priority(self, msg: BaseMessage) -> MessagePriority:
        """Get priority for a message."""
        if isinstance(msg, SystemMessage):
            return MessagePriority.CRITICAL

        if isinstance(msg, ToolMessage):
            # Check if it's an error
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if "error" in content.lower() or "failed" in content.lower():
                return MessagePriority.HIGH
            return MessagePriority.MEDIUM

        if isinstance(msg, HumanMessage):
            return MessagePriority.HIGH

        if isinstance(msg, AIMessage):
            # Check if it has tool calls
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                return MessagePriority.HIGH
            return MessagePriority.MEDIUM

        return MessagePriority.LOW

    def _priority_order(self, priority: MessagePriority) -> int:
        """Convert priority to order (lower = keep first)."""
        return {
            MessagePriority.CRITICAL: 0,
            MessagePriority.HIGH: 1,
            MessagePriority.MEDIUM: 2,
            MessagePriority.LOW: 3,
        }[priority]

    def count_tokens(self, messages: List[BaseMessage]) -> int:
        """Count tokens in message list."""
        return self.token_counter.count_messages(messages)

    def _count_single(self, msg: BaseMessage) -> int:
        """Count tokens in a single message."""
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        return self.token_counter.count_tokens(content)


# Global singleton instance
_global_context_manager: Optional[AdvancedContextManager] = None


def get_context_manager() -> AdvancedContextManager:
    """Get global context manager instance."""
    global _global_context_manager
    if _global_context_manager is None:
        _global_context_manager = AdvancedContextManager()
    return _global_context_manager


__all__ = [
    "CompressionMode",
    "MessagePriority",
    "AdvancedContextManager",
    "get_context_manager",
]
