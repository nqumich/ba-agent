"""
BA-Agent 服务

集成 BAAgent 与 API，提供 Agent 查询、对话管理等功能

架构分层：
- BAAgent (backend/agents/agent.py): 核心 Agent 实现，包含 Memory Flush、Skills、Pipeline
- BAAgentService (本文件): API 服务层，轻量包装，提供 HTTP 接口
"""

from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
from datetime import datetime

from backend.models.response import (
    StructuredResponse,
    parse_structured_response,
)
from backend.core.context_manager import create_context_manager

logger = logging.getLogger(__name__)

# 全局共享的 MemorySaver 实例
# 所有 Agent 实例共享同一个 checkpointer，确保跨模型的对话历史可以被访问
_shared_memory_saver = None


def get_shared_memory_saver():
    """
    获取全局共享的 MemorySaver 实例

    确保所有 Agent（无论是默认 Agent 还是动态创建的 Agent）使用同一个 checkpointer，
    从而实现跨模型的对话历史保存和恢复。

    Returns:
        MemorySaver: 全局共享的 checkpointer 实例
    """
    global _shared_memory_saver
    if _shared_memory_saver is None:
        from langgraph.checkpoint.memory import MemorySaver
        _shared_memory_saver = MemorySaver()
        logger.info("创建全局共享 MemorySaver 实例")
    return _shared_memory_saver


class BAAgentService:
    """
    BA-Agent 服务类 (API 层)

    职责：
    - 包装 BAAgent，提供 HTTP API 接口
    - 对话状态管理（conversation_id、message_count）
    - 代码管理流程（保存到 FileStore）
    - 错误处理和 API 响应格式化

    设计原则：
    - 保持轻量，不包含复杂业务逻辑
    - 核心功能委托给 BAAgent 实现
    """

    def __init__(
        self,
        model_name: str = None,
        enable_memory: bool = True,
        enable_skills: bool = True
    ):
        """
        初始化 BA-Agent 服务

        Args:
            model_name: 使用的模型名称（默认从环境变量 BA_DEFAULT_MODEL 读取，本地默认 glm-4.7）
            enable_memory: 是否启用记忆系统
            enable_skills: 是否启用 Skills
        """
        import os

        # 本地开发默认使用 GLM-4
        if model_name is None:
            model_name = os.getenv("BA_DEFAULT_MODEL", "glm-4.7")

        self.model_name = model_name
        self.enable_memory = enable_memory
        self.enable_skills = enable_skills

        # 对话状态管理（仅 API 层需要，BAAgent 有自己的记忆系统）
        self._conversations: Dict[str, Dict[str, Any]] = {}

        # BAAgent 实例（延迟初始化）
        self._ba_agent = None

        # 上下文管理器（用于新对话的系统提示构建）
        self._context_manager = None

        logger.info(f"BAAgentService 初始化: model={model_name}, memory={enable_memory}, skills={enable_skills}")

    def initialize(self):
        """
        初始化 BAAgent 实例

        使用 BAAgent (backend/agents/agent.py) 作为核心实现
        """
        try:
            from backend.agents.agent import BAAgent
            from backend.api.state import get_app_state

            # 获取全局共享的 MemorySaver
            shared_memory = get_shared_memory_saver()

            # 创建 BAAgent 实例
            # 通过设置 _memory 属性，让 BAAgent 使用全局共享的 MemorySaver
            ba_agent_instance = BAAgent.__new__(BAAgent)
            ba_agent_instance._memory = shared_memory
            ba_agent_instance.__init__(
                config=None,  # 使用默认配置
                tools=None,  # BAAgent 会自动加载默认工具
                system_prompt=None,  # 使用默认系统提示
                use_default_tools=True,
            )
            self._ba_agent = ba_agent_instance

            logger.info("BAAgent 实例初始化完成（使用全局共享 MemorySaver）")

        except Exception as e:
            logger.error(f"BAAgent 初始化失败: {e}", exc_info=True)
            raise

    @property
    def agent(self):
        """
        获取 BAAgent 实例（延迟初始化）

        保持向后兼容，API 代码可以通过这个属性访问底层 Agent
        """
        if self._ba_agent is None:
            self.initialize()
        return self._ba_agent

    @property
    def context_manager(self):
        """获取上下文管理器（用于新对话的系统提示构建）"""
        if self._context_manager is None:
            from backend.api.state import get_app_state
            file_store = get_app_state().get("file_store")
            self._context_manager = create_context_manager(file_store)
        return self._context_manager

    def _create_agent_for_request(self, model_name: str, api_key: str = None):
        """
        为特定请求创建 BAAgent 实例

        当用户指定不同的模型或 API Key 时，创建临时的 BAAgent 实例

        Args:
            model_name: 模型名称
            api_key: API 密钥（可选）

        Returns:
            BAAgent 实例
        """
        from backend.agents.agent import BAAgent
        from backend.models.agent import AgentConfig

        # 获取全局共享的 MemorySaver
        shared_memory = get_shared_memory_saver()

        # 创建针对该模型的配置
        config = AgentConfig(
            name=f"BA-Agent-{model_name}",
            model=model_name,
            temperature=0.7,
            max_tokens=4096,
            system_prompt="你是 BA-Agent，一个专业的商业分析助手。",  # 简化提示词
            tools=[],
            memory_enabled=self.enable_memory,
            hooks_enabled=True,
        )

        # 创建临时 BAAgent（使用全局共享 MemorySaver）
        temp_agent_instance = BAAgent.__new__(BAAgent)
        temp_agent_instance._memory = shared_memory

        # 调用 __init__
        temp_agent_instance.__init__(
            config=config,
            tools=None,
            system_prompt=None,
            use_default_tools=True,
        )

        logger.info(f"创建临时 BAAgent: model={model_name}, 使用全局共享 MemorySaver")
        return temp_agent_instance

    async def query(
        self,
        message: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        conversation_id: Optional[str] = None,
        file_context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行 Agent 查询

        Args:
            message: 用户消息
            model: 使用的模型名称（可选，覆盖默认模型）
            api_key: API 密钥（可选，覆盖环境变量）
            conversation_id: 对话 ID
            file_context: 文件上下文
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            Agent 响应结果
        """
        try:
            import time
            import traceback
            start_time = time.time()

            # 确定使用的 Agent
            agent_to_use = self._ba_agent
            model_to_log = self.model_name

            # 如果指定了模型或 API Key，创建临时 Agent
            if model or api_key:
                effective_model = model or self.model_name
                logger.info(f"创建动态 Agent: model={effective_model}, api_key_provided={api_key is not None}")
                agent_to_use = self._create_agent_for_request(effective_model, api_key)
                model_to_log = effective_model
            else:
                # 确保 Agent 已初始化
                if agent_to_use is None:
                    self.initialize()
                agent_to_use = self._ba_agent

            # 确保对话存在
            is_new_conversation = conversation_id is None
            if is_new_conversation:
                conversation_id = self._create_conversation(user_id, session_id)

            # === 统一调用路径 ===
            # 所有查询都通过 BAAgent.invoke()，由 ContextCoordinator 处理：
            # - 文件清理（统一在 ContextManager 中）
            # - 系统提示词插入
            # - 对话历史管理（由 LangGraph checkpointer 自动处理）
            # - Memory Flush（由 BAAgent 内部处理）

            # 如果有 file_context，将其添加到消息中
            enhanced_message = message
            if file_context:
                # 将文件上下文信息添加到消息中
                file_info = self.context_manager._build_file_context(file_context)
                if file_info:
                    file_context_str = "\n\n".join([
                        f"[{msg.get('role', 'system')}] {msg.get('content', '')}"
                        for msg in file_info
                    ])
                    enhanced_message = f"{file_context_str}\n\n用户消息：{message}"

            logger.info(f"Agent 查询: model={model_to_log}, conversation_id={conversation_id}, message={message[:100]}...")

            result = agent_to_use.invoke(
                message=enhanced_message,
                conversation_id=conversation_id,
                user_id=user_id,
                session_id=session_id,  # 传递 session_id 供 ContextCoordinator 使用
            )

            # 处理响应
            duration_ms = (time.time() - start_time) * 1000

            # 更新对话状态（API 层的简单计数）
            self._update_conversation(conversation_id, {
                "last_message_at": datetime.utcnow().isoformat() + "Z",
                "message_count": self._conversations[conversation_id]["message_count"] + 1
            })

            # 提取响应内容
            response_content = result.get("response", "")
            success = result.get("success", True)
            error = result.get("error")

            # 解析结构化响应（如果存在）
            structured_response = None
            if success:
                try:
                    structured_response = parse_structured_response(response_content)
                except:
                    pass

            # 构建元数据
            metadata = {
                "content_type": "text",
                "has_structured_response": structured_response is not None,
                "tokens_used": result.get("tokens_used", 0),
                "session_tokens": result.get("session_tokens", 0),
            }

            if structured_response:
                metadata["action_type"] = structured_response.action.type
                metadata["current_round"] = structured_response.current_round
                metadata["task_analysis"] = structured_response.task_analysis
                metadata["execution_plan"] = structured_response.execution_plan

                if structured_response.is_complete():
                    metadata["status"] = "complete"
                    if structured_response.action.recommended_questions:
                        metadata["recommended_questions"] = structured_response.action.recommended_questions
                    if structured_response.action.download_links:
                        metadata["download_links"] = structured_response.action.download_links

                    final_report = structured_response.get_final_report()
                    has_html = '<div' in final_report or '<script' in final_report or 'echarts' in final_report.lower()
                    metadata["contains_html"] = has_html
                    metadata["content_type"] = "html" if has_html else "markdown"

            return {
                "response": response_content,
                "conversation_id": conversation_id,
                "duration_ms": duration_ms,
                "tool_calls": result.get("tool_calls", []),
                "artifacts": result.get("artifacts", []),
                "metadata": metadata
            }

        except Exception as e:
            import traceback
            error_type = type(e).__name__
            error_msg = str(e)
            error_traceback = traceback.format_exc()

            # 详细的错误日志
            logger.error(
                f"Agent 查询失败: "
                f"type={error_type}, "
                f"msg={error_msg}, "
                f"model={model_to_log if 'model_to_log' in locals() else 'unknown'}, "
                f"conversation_id={conversation_id}, "
                f"traceback={error_traceback}"
            )

            # 构建错误响应
            return {
                "response": f"查询失败: {error_msg}",
                "conversation_id": conversation_id,
                "error": {
                    "error_type": error_type,
                    "error_message": error_msg,
                    "model": model_to_log if 'model_to_log' in locals() else self.model_name,
                }
            }

    def _create_conversation(
        self,
        user_id: Optional[str],
        session_id: Optional[str]
    ) -> str:
        """创建新对话（API 层记录）"""
        import uuid
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        self._conversations[conversation_id] = {
            "conversation_id": conversation_id,
            "user_id": user_id or "anonymous",
            "session_id": session_id or "default",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "message_count": 0,
            "last_message_at": None
        }

        logger.info(f"创建新对话: {conversation_id}")
        return conversation_id

    def _update_conversation(self, conversation_id: str, updates: Dict[str, Any]):
        """更新对话状态（API 层记录）"""
        if conversation_id in self._conversations:
            self._conversations[conversation_id].update(updates)

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取对话信息"""
        return self._conversations.get(conversation_id)

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取对话历史

        从 BAAgent 的 checkpointer 获取完整历史
        """
        if self._ba_agent is None:
            return []

        try:
            messages = self._ba_agent.get_conversation_history(conversation_id)
            return [
                {
                    "role": getattr(msg, 'type', 'unknown'),
                    "content": str(msg.content) if hasattr(msg, 'content') else str(msg),
                }
                for msg in messages[-limit:]
            ]
        except Exception as e:
            logger.warning(f"获取对话历史失败: {e}")
            return []

    def end_conversation(self, conversation_id: str) -> bool:
        """结束对话"""
        if conversation_id in self._conversations:
            self._conversations[conversation_id]["status"] = "ended"
            self._conversations[conversation_id]["ended_at"] = datetime.utcnow().isoformat() + "Z"
            logger.info(f"对话已结束: {conversation_id}")
            return True
        return False

    def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "agent_initialized": self._ba_agent is not None,
            "model_name": self.model_name,
            "enable_memory": self.enable_memory,
            "enable_skills": self.enable_skills,
            "active_conversations": len([
                c for c in self._conversations.values()
                if c.get("status") != "ended"
            ]),
            "total_conversations": len(self._conversations)
        }


__all__ = ["BAAgentService", "get_shared_memory_saver"]
