"""
Dynamic Token Counter

Multi-model token counting with tiktoken integration.

Design v2.0.1:
- Support for multiple LLM providers (OpenAI, Anthropic, etc.)
- Automatic model detection and tokenizer selection
- Efficient counting with caching
- Message format support (LangChain BaseMessage)
"""

import functools
import re
from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, BaseMessage


class TokenCounter:
    """Base class for token counters."""

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        raise NotImplementedError

    def count_messages(self, messages: List[BaseMessage]) -> int:
        """Count tokens in a list of messages."""
        total = 0
        for msg in messages:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            total += self.count_tokens(content)
        return total


class TikTokenCounter(TokenCounter):
    """Token counter using tiktoken (OpenAI models)."""

    def __init__(self, model: str = "gpt-4"):
        """
        Initialize tiktoken counter.

        Args:
            model: Model name for tokenizer selection
        """
        self.model = model
        self._tokenizer = None

    @property
    def tokenizer(self):
        """Lazy load tokenizer."""
        if self._tokenizer is None:
            try:
                import tiktoken
                # Try to get encoding for model
                try:
                    self._tokenizer = tiktoken.encoding_for_model(self.model)
                except KeyError:
                    # Fall back to cl100k_base (GPT-4)
                    self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                raise ImportError(
                    "tiktoken is required for token counting. "
                    "Install with: pip install tiktoken"
                )
        return self._tokenizer

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        try:
            tokens = self.tokenizer.encode(text)
            return len(tokens)
        except Exception:
            # Fallback to approximate count
            return len(text) // 4


class AnthropicTokenCounter(TokenCounter):
    """Token counter for Anthropic models (Claude)."""

    def __init__(self, model: str = "claude-3-opus"):
        """
        Initialize Anthropic counter.

        Args:
            model: Model name (used for tokenization strategy)
        """
        self.model = model

    def count_tokens(self, text: str) -> int:
        """
        Count tokens for Anthropic models.

        Anthropic uses a different tokenizer than OpenAI.
        For accurate counts, we'd need their internal tokenizer.
        This is an approximation based on character count.
        """
        # Approximate: 1 token ≈ 3.5 characters for Claude
        # This is less accurate than tiktoken but works without internal tokenizer
        return int(len(text) / 3.5)

    def count_messages(self, messages: List[BaseMessage]) -> int:
        """
        Count tokens for Anthropic message format.

        Anthropic API format:
        - System message: separate from conversation
        - User/Assistant messages: alternating
        - Tool results: included as user messages
        """
        total = 0

        # Count system message separately
        for msg in messages:
            if isinstance(msg, SystemMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                total += self.count_tokens(content)

        # Count conversation messages
        for msg in messages:
            if not isinstance(msg, SystemMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                total += self.count_tokens(content)

        return total


class ApproximateTokenCounter(TokenCounter):
    """
    Approximate token counter for when no tokenizer is available.

    Rule of thumb: 1 token ≈ 4 characters (English) or 2-3 characters (Chinese)
    """

    def __init__(self, chars_per_token: float = 4.0):
        """
        Initialize approximate counter.

        Args:
            chars_per_token: Characters per token ratio (default: 4 for English)
        """
        self.chars_per_token = chars_per_token

    def count_tokens(self, text: str) -> int:
        """Approximate token count based on character count."""
        return int(len(text) / self.chars_per_token)


class DynamicTokenCounter:
    """
    Dynamic token counter that selects appropriate tokenizer based on model.

    Model Family Detection:
    - OpenAI: gpt-*, o1-* → tiktoken
    - Anthropic: claude-* → AnthropicTokenCounter
    - Other: ApproximateTokenCounter
    """

    # Model family patterns
    MODEL_PATTERNS = {
        "openai": [
            r"^gpt-",
            r"^o1-",
            r"^chatgpt-",
        ],
        "anthropic": [
            r"^claude-",
        ],
    }

    def __init__(self, default_model: str = "gpt-4"):
        """
        Initialize dynamic token counter.

        Args:
            default_model: Default model to use if not specified
        """
        self.default_model = default_model
        self._counters: Dict[str, TokenCounter] = {}
        self._cache: Dict[str, int] = {}

    def detect_model_family(self, model: str) -> str:
        """
        Detect model family from model name.

        Args:
            model: Model name or ID

        Returns:
            Model family: 'openai', 'anthropic', or 'other'
        """
        model_lower = model.lower()

        # Check Anthropic first (claude-*)
        for pattern in self.MODEL_PATTERNS["anthropic"]:
            if re.match(pattern, model_lower):
                return "anthropic"

        # Check OpenAI
        for pattern in self.MODEL_PATTERNS["openai"]:
            if re.match(pattern, model_lower):
                return "openai"

        return "other"

    def get_counter(self, model: str) -> TokenCounter:
        """
        Get appropriate token counter for model.

        Args:
            model: Model name

        Returns:
            TokenCounter instance
        """
        # Check cache
        if model in self._counters:
            return self._counters[model]

        # Detect model family
        family = self.detect_model_family(model)

        # Create appropriate counter
        if family == "openai":
            counter = TikTokenCounter(model)
        elif family == "anthropic":
            counter = AnthropicTokenCounter(model)
        else:
            counter = ApproximateTokenCounter()

        # Cache and return
        self._counters[model] = counter
        return counter

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count
            model: Model name (uses default if not specified)

        Returns:
            Token count
        """
        model = model or self.default_model

        # Check cache
        cache_key = f"{model}:{hash(text)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get counter and count
        counter = self.get_counter(model)
        count = counter.count_tokens(text)

        # Cache result
        self._cache[cache_key] = count
        return count

    def count_messages(
        self,
        messages: List[BaseMessage],
        model: Optional[str] = None
    ) -> int:
        """
        Count tokens in a list of messages.

        Args:
            messages: List of LangChain messages
            model: Model name (uses default if not specified)

        Returns:
            Total token count
        """
        model = model or self.default_model
        counter = self.get_counter(model)
        return counter.count_messages(messages)

    def count_dict(
        self,
        data: Dict[str, Any],
        model: Optional[str] = None
    ) -> int:
        """
        Count tokens in a dictionary (JSON).

        Args:
            data: Dictionary to count
            model: Model name (uses default if not specified)

        Returns:
            Token count
        """
        import json
        text = json.dumps(data, ensure_ascii=False)
        return self.count_tokens(text, model)

    def estimate_input_tokens(
        self,
        messages: List[BaseMessage],
        model: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Estimate input tokens with breakdown by message type.

        Args:
            messages: List of LangChain messages
            model: Model name

        Returns:
            Dictionary with breakdown
        """
        model = model or self.default_model
        counter = self.get_counter(model)

        breakdown = {
            "system": 0,
            "user": 0,
            "assistant": 0,
            "tool": 0,
            "total": 0,
        }

        for msg in messages:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            count = counter.count_tokens(content)

            if isinstance(msg, SystemMessage):
                breakdown["system"] += count
            elif isinstance(msg, HumanMessage):
                breakdown["user"] += count
            elif isinstance(msg, AIMessage):
                breakdown["assistant"] += count
            elif isinstance(msg, ToolMessage):
                breakdown["tool"] += count

            breakdown["total"] += count

        return breakdown

    def clear_cache(self) -> None:
        """Clear token count cache."""
        self._cache.clear()


# Global singleton instance
_global_token_counter: Optional[DynamicTokenCounter] = None


def get_token_counter() -> DynamicTokenCounter:
    """Get global token counter instance."""
    global _global_token_counter
    if _global_token_counter is None:
        _global_token_counter = DynamicTokenCounter()
    return _global_token_counter


__all__ = [
    "TokenCounter",
    "TikTokenCounter",
    "AnthropicTokenCounter",
    "ApproximateTokenCounter",
    "DynamicTokenCounter",
    "get_token_counter",
]
