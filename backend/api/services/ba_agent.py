"""
BA-Agent 服务

集成 BAAgent 与 API，提供 Agent 查询、对话管理等功能
"""

from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BAAgentService:
    """
    BA-Agent 服务类

    负责管理 Agent 实例、处理查询、维护对话状态
    """

    def __init__(
        self,
        model_name: str = "claude-3-5-sonnet-20241022",
        enable_memory: bool = True,
        enable_skills: bool = True
    ):
        """
        初始化 BA-Agent 服务

        Args:
            model_name: 使用的模型名称
            enable_memory: 是否启用记忆系统
            enable_skills: 是否启用 Skills
        """
        self.model_name = model_name
        self.enable_memory = enable_memory
        self.enable_skills = enable_skills

        # 对话状态管理
        self._conversations: Dict[str, Dict[str, Any]] = {}

        # Agent 实例（延迟初始化）
        self._agent = None

        logger.info(f"BAAgentService 初始化: model={model_name}, memory={enable_memory}, skills={enable_skills}")

    def initialize(self):
        """初始化 Agent 实例"""
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain.agents import create_agent
            from langgraph.checkpoint.memory import MemorySaver

            from backend.tools import get_default_tools
            from backend.skills import SkillRegistry, SkillActivator
            from backend.api.state import get_app_state

            # 创建模型
            model = ChatAnthropic(
                model=self.model_name,
                temperature=0.7,
                max_tokens=4096
            )

            # 获取工具
            tools = get_default_tools()

            # 如果启用 Skills，添加 Skills 工具
            if self.enable_skills:
                from backend.skills.skill_tool import create_skill_tool
                skill_registry = get_app_state().get("skill_registry")
                if skill_registry:
                    skill_tool = create_skill_tool(skill_registry)
                    tools.append(skill_tool)
                    logger.info("Skills 工具已添加到 Agent")

            # 创建 memory
            memory = MemorySaver()

            # 创建 Agent
            self._agent = create_agent(
                model,
                tools,
                checkpointer=memory
            )

            logger.info("BAAgent 实例初始化完成")

        except Exception as e:
            logger.error(f"BAAgent 初始化失败: {e}", exc_info=True)
            raise

    @property
    def agent(self):
        """获取 Agent 实例（延迟初始化）"""
        if self._agent is None:
            self.initialize()
        return self._agent

    async def query(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        file_context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行 Agent 查询

        Args:
            message: 用户消息
            conversation_id: 对话 ID
            file_context: 文件上下文
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            Agent 响应结果
        """
        try:
            import time
            start_time = time.time()

            # 确保对话存在
            if not conversation_id:
                conversation_id = self._create_conversation(user_id, session_id)

            # 构建消息
            messages = self._build_messages(message, file_context)

            # 构建配置
            config = {
                "configurable": {
                    "thread_id": conversation_id
                }
            }

            # 调用 Agent
            logger.info(f"Agent 查询: conversation_id={conversation_id}, message={message[:100]}...")

            result = self.agent.invoke(
                {"messages": messages},
                config=config
            )

            # 处理响应
            duration_ms = (time.time() - start_time) * 1000

            # 更新对话状态
            self._update_conversation(conversation_id, {
                "last_message_at": datetime.utcnow().isoformat() + "Z",
                "message_count": self._conversations[conversation_id]["message_count"] + 1
            })

            # 提取响应内容
            response_content = self._extract_response_content(result)

            return {
                "response": response_content,
                "conversation_id": conversation_id,
                "duration_ms": duration_ms,
                "tool_calls": self._extract_tool_calls(result),
                "artifacts": self._extract_artifacts(result)
            }

        except Exception as e:
            logger.error(f"Agent 查询失败: {e}", exc_info=True)
            return {
                "response": f"查询失败: {str(e)}",
                "conversation_id": conversation_id,
                "error": str(e)
            }

    def _create_conversation(
        self,
        user_id: Optional[str],
        session_id: Optional[str]
    ) -> str:
        """创建新对话"""
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

    def _build_messages(
        self,
        message: str,
        file_context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = []

        # 添加文件上下文
        if file_context and "file_id" in file_context:
            file_ref = f"upload:{file_context['file_id']}"
            messages.append({
                "role": "system",
                "content": f"用户已上传文件，文件引用: {file_ref}"
            })

        # 添加用户消息
        messages.append({
            "role": "user",
            "content": message
        })

        return messages

    def _extract_response_content(self, result: Dict[str, Any]) -> str:
        """提取响应内容"""
        try:
            messages = result.get("messages", [])
            if messages:
                # 获取最后一条 AI 消息
                for msg in reversed(messages):
                    if hasattr(msg, 'content'):
                        content = msg.content
                        if isinstance(content, list):
                            # 处理多模态内容
                            return "\n".join(
                                item.get("text", str(item))
                                for item in content
                                if isinstance(item, dict)
                            )
                        return str(content)
                    elif isinstance(msg, dict) and "content" in msg:
                        return str(msg["content"])
            return "无响应内容"
        except Exception as e:
            logger.error(f"提取响应内容失败: {e}")
            return f"响应解析失败: {str(e)}"

    def _extract_tool_calls(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取工具调用信息"""
        tool_calls = []

        try:
            messages = result.get("messages", [])
            for msg in messages:
                if hasattr(msg, 'tool_calls'):
                    for call in msg.tool_calls:
                        tool_calls.append({
                            "tool": call.get("name", "unknown"),
                            "input": call.get("args", {}),
                            "id": call.get("id", "")
                        })
        except Exception as e:
            logger.error(f"提取工具调用失败: {e}")

        return tool_calls

    def _extract_artifacts(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取生成的工件"""
        artifacts = []

        try:
            messages = result.get("messages", [])
            for msg in messages:
                if hasattr(msg, 'content'):
                    content = msg.content
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "artifact_id" in item:
                                artifacts.append(item)
        except Exception as e:
            logger.error(f"提取工件失败: {e}")

        return artifacts

    def _update_conversation(self, conversation_id: str, updates: Dict[str, Any]):
        """更新对话状态"""
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
        """获取对话历史"""
        # TODO: 从 MemoryStore 或 checkpointer 获取完整历史
        # 这里返回基本信息
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return []

        # 模拟返回部分历史
        return [
            {
                "conversation_id": conversation_id,
                "created_at": conversation["created_at"],
                "message_count": conversation["message_count"]
            }
        ]

    def end_conversation(self, conversation_id: str) -> bool:
        """结束对话"""
        if conversation_id in self._conversations:
            # 标记为已结束
            self._conversations[conversation_id]["status"] = "ended"
            self._conversations[conversation_id]["ended_at"] = datetime.utcnow().isoformat() + "Z"
            logger.info(f"对话已结束: {conversation_id}")
            return True
        return False

    def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "agent_initialized": self._agent is not None,
            "model_name": self.model_name,
            "enable_memory": self.enable_memory,
            "enable_skills": self.enable_skills,
            "active_conversations": len([
                c for c in self._conversations.values()
                if c.get("status") != "ended"
            ]),
            "total_conversations": len(self._conversations)
        }


__all__ = ["BAAgentService"]
