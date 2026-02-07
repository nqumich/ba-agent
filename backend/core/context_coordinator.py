"""
Context Coordinator - 上下文协调器

统一协调 LangGraph、ContextManager 和 Memory Flush 的交互

职责：
1. 准备发送给 LLM 的消息列表
2. 协调文件清理和上下文构建
3. 确保系统提示在第一位
4. 保持消息顺序

设计原则：
- 单一职责：专注于消息准备和清理
- 委托模式：文件清理委托给 ContextManager
- 无状态：不保存任何状态，所有状态由 LangGraph 管理
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from langchain_core.messages import BaseMessage, SystemMessage

if TYPE_CHECKING:
    from backend.core.context_manager import ContextManager
    from backend.agents.agent import BAAgent

logger = logging.getLogger(__name__)


class ContextCoordinator:
    """
    上下文协调器

    负责准备发送给 LLM 的消息列表，统一协调文件清理和上下文构建。
    """

    def __init__(
        self,
        context_manager: "ContextManager",
    ):
        """
        初始化上下文协调器

        Args:
            context_manager: ContextManager 实例，用于文件清理
        """
        self.context_manager = context_manager
        logger.info("ContextCoordinator 初始化完成")

    def prepare_messages(
        self,
        state_messages: List[BaseMessage],
        session_id: Optional[str] = None,
    ) -> List[BaseMessage]:
        """
        准备发送给 LLM 的消息列表

        功能：
        1. 清理大文件内容（委托给 ContextManager）
        2. 确保系统提示在第一位
        3. 保持消息顺序

        Args:
            state_messages: LangGraph 状态中的消息列表
            session_id: 会话 ID（用于代码列表）

        Returns:
            清理后的消息列表
        """
        logger.info(f"[ContextCoordinator] 准备消息: 输入 {len(state_messages)} 条")

        # 使用 ContextManager 清理消息
        cleaned_messages = self.context_manager.clean_langchain_messages(
            state_messages,
            session_id=session_id
        )

        # 确保系统提示在第一位
        # 注意：这里不强制插入系统提示，由 call_model 负责
        # 我们只负责清理文件内容

        logger.info(f"[ContextCoordinator] 准备完成: 输出 {len(cleaned_messages)} 条")

        return cleaned_messages

    def prepare_messages_with_system_prompt(
        self,
        state_messages: List[BaseMessage],
        system_prompt: str,
        session_id: Optional[str] = None,
    ) -> List[BaseMessage]:
        """
        准备发送给 LLM 的消息列表（包含系统提示）

        功能：
        1. 清理大文件内容（委托给 ContextManager）
        2. 确保系统提示在第一位
        3. 保持消息顺序

        Args:
            state_messages: LangGraph 状态中的消息列表
            system_prompt: 系统提示词
            session_id: 会话 ID（用于代码列表）

        Returns:
            清理后的消息列表（系统提示在第一位）
        """
        logger.info(f"[ContextCoordinator] 准备消息（含系统提示）: 输入 {len(state_messages)} 条")

        # 使用 ContextManager 清理消息
        cleaned_messages = self.context_manager.clean_langchain_messages(
            state_messages,
            session_id=session_id
        )

        # 确保系统提示在第一位
        if not cleaned_messages or not isinstance(cleaned_messages[0], SystemMessage):
            cleaned_messages.insert(0, SystemMessage(content=system_prompt))
            logger.info("[ContextCoordinator] 已插入系统提示到第一位")
        elif cleaned_messages[0].content != system_prompt:
            # 替换第一条系统提示
            cleaned_messages[0] = SystemMessage(content=system_prompt)
            logger.info("[ContextCoordinator] 已替换系统提示")

        logger.info(f"[ContextCoordinator] 准备完成: 输出 {len(cleaned_messages)} 条")

        return cleaned_messages


def create_context_coordinator(
    context_manager: "ContextManager",
) -> ContextCoordinator:
    """
    创建 ContextCoordinator 实例的便捷函数

    Args:
        context_manager: ContextManager 实例

    Returns:
        ContextCoordinator 实例
    """
    return ContextCoordinator(context_manager)
