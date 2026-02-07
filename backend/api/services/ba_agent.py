"""
BA-Agent 服务

集成 BAAgent 与 API，提供 Agent 查询、对话管理等功能
"""

from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
from datetime import datetime

from backend.models.response import (
    StructuredResponse,
    parse_structured_response,
    STRUCTURED_RESPONSE_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class BAAgentService:
    """
    BA-Agent 服务类

    负责管理 Agent 实例、处理查询、维护对话状态
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
            model_name: 使用的模型名称（默认从环境变量 BA_DEFAULT_MODEL 读取，本地默认 glm-4.7.7）
            enable_memory: 是否启用记忆系统
            enable_skills: 是否启用 Skills
        """
        import os

        # 本地开发默认使用 GLM-4
        if model_name is None:
            model_name = os.getenv("BA_DEFAULT_MODEL", "glm-4.7")

        self.model_name = model_name
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
            from langchain.agents import create_agent
            from langgraph.checkpoint.memory import MemorySaver

            from tools import get_default_tools
            from backend.skills import SkillRegistry, SkillActivator
            from backend.api.state import get_app_state
            import os

            # 根据模型名称创建相应的模型实例
            if self.model_name.startswith("glm-"):
                # GLM 模型 (智谱 AI)
                from langchain_community.chat_models import ChatZhipuAI
                model = ChatZhipuAI(
                    model=self.model_name,
                    temperature=0.7,
                    max_tokens=4096,
                    api_key=os.getenv("ZHIPUAI_API_KEY", os.getenv("GLM_API_KEY", ""))
                )
            elif self.model_name.startswith("gpt-"):
                # OpenAI 模型
                from langchain_openai import ChatOpenAI
                model = ChatOpenAI(
                    model=self.model_name,
                    temperature=0.7,
                    max_tokens=4096,
                    api_key=os.getenv("OPENAI_API_KEY", ""),
                    base_url=os.getenv("OPENAI_BASE_URL")
                )
            elif self.model_name.startswith("gemini-"):
                # Google Gemini 模型
                from langchain_google_genai import ChatGoogleGenerativeAI
                model = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    temperature=0.7,
                    api_key=os.getenv("GOOGLE_API_KEY", "")
                )
            else:
                # 默认使用 Anthropic Claude
                from langchain_anthropic import ChatAnthropic
                model = ChatAnthropic(
                    model=self.model_name,
                    temperature=0.7,
                    max_tokens=4096,
                    api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                    base_url=os.getenv("ANTHROPIC_BASE_URL")
                )

            # 获取工具
            tools = get_default_tools()

            # 如果启用 Skills，添加 Skills 工具
            if self.enable_skills:
                from backend.skills.skill_tool import create_skill_tool
                skill_registry = get_app_state().get("skill_registry")
                skill_activator = get_app_state().get("skill_activator")
                if skill_registry and skill_activator:
                    skill_tool = create_skill_tool(skill_registry, skill_activator)
                    if skill_tool:
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

    def _create_model_for_request(self, model_name: str, api_key: str = None):
        """
        为特定请求创建模型实例

        Args:
            model_name: 模型名称
            api_key: API 密钥（可选）

        Returns:
            模型实例
        """
        import os

        if model_name.startswith("glm-"):
            # GLM 模型 (智谱 AI)
            from langchain_community.chat_models import ChatZhipuAI
            final_api_key = api_key or os.getenv("ZHIPUAI_API_KEY", os.getenv("GLM_API_KEY", ""))
            logger.info(f"创建 ChatZhipuAI: model={model_name}, api_key_from_param={api_key is not None}, final_key_length={len(final_api_key) if final_api_key else 0}")
            return ChatZhipuAI(
                model=model_name,
                temperature=0.7,
                max_tokens=4096,
                api_key=final_api_key
            )
        elif model_name.startswith("gpt-"):
            # OpenAI 模型
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                temperature=0.7,
                max_tokens=4096,
                api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
                base_url=os.getenv("OPENAI_BASE_URL")
            )
        elif model_name.startswith("gemini-"):
            # Google Gemini 模型
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=0.7,
                api_key=api_key or os.getenv("GOOGLE_API_KEY", "")
            )
        else:
            # 默认使用 Anthropic Claude
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model_name,
                temperature=0.7,
                max_tokens=4096,
                api_key=api_key or os.getenv("ANTHROPIC_API_KEY", ""),
                base_url=os.getenv("ANTHROPIC_BASE_URL")
            )

    def _create_agent_for_request(self, model_name: str, api_key: str = None):
        """
        为特定请求创建 Agent 实例

        Args:
            model_name: 模型名称
            api_key: API 密钥（可选）

        Returns:
            Agent 实例
        """
        from langchain.agents import create_agent
        from langgraph.checkpoint.memory import MemorySaver
        from tools import get_default_tools
        from backend.api.state import get_app_state

        # 创建模型
        model = self._create_model_for_request(model_name, api_key)

        # 获取工具
        tools = get_default_tools()

        # 如果启用 Skills，添加 Skills 工具
        if self.enable_skills:
            from backend.skills.skill_tool import create_skill_tool
            skill_registry = get_app_state().get("skill_registry")
            skill_activator = get_app_state().get("skill_activator")
            if skill_registry and skill_activator:
                skill_tool = create_skill_tool(skill_registry, skill_activator)
                if skill_tool:
                    tools.append(skill_tool)

        # 创建 memory
        memory = MemorySaver()

        # 创建 Agent
        return create_agent(model, tools, checkpointer=memory)

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
            agent_to_use = self.agent
            model_to_log = self.model_name

            # 如果指定了模型或 API Key，创建临时 Agent
            if model or api_key:
                effective_model = model or self.model_name
                logger.info(f"创建动态 Agent: model={effective_model}, api_key_provided={api_key is not None}, api_key_length={len(api_key) if api_key else 0}")
                agent_to_use = self._create_agent_for_request(effective_model, api_key)
                model_to_log = effective_model
            else:
                logger.info(f"使用默认 Agent: model={self.model_name}")

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
            logger.info(f"Agent 查询: model={model_to_log}, conversation_id={conversation_id}, message={message[:100]}...")

            result = agent_to_use.invoke(
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

            # 提取响应内容（返回元组：final_report_content, structured_response）
            final_report_content, structured_response = self._extract_response_content(
                result,
                session_id=session_id
            )

            # 构建元数据
            metadata = {
                "content_type": "text",
                "has_structured_response": structured_response is not None
            }

            if structured_response:
                # 从结构化响应中提取元数据
                metadata["action_type"] = structured_response.action.type
                metadata["current_round"] = structured_response.current_round
                metadata["task_analysis"] = structured_response.task_analysis
                metadata["execution_plan"] = structured_response.execution_plan

                # 根据动作类型设置不同的元数据
                if structured_response.is_tool_call():
                    # 工具调用状态
                    tool_calls = structured_response.get_tool_calls()
                    metadata["tool_calls"] = [
                        {
                            "tool_name": tc.tool_name,
                            "tool_call_id": tc.tool_call_id,
                            "arguments": tc.arguments
                        }
                        for tc in tool_calls
                    ]
                    metadata["status"] = "processing"

                elif structured_response.is_complete():
                    # 完成状态
                    metadata["status"] = "complete"

                    # 推荐问题和下载链接
                    if structured_response.action.recommended_questions:
                        metadata["recommended_questions"] = structured_response.action.recommended_questions
                    if structured_response.action.download_links:
                        metadata["download_links"] = structured_response.action.download_links

                    # 检测 final_report 是否包含模型生成的 HTML（如 ECharts 图表）
                    final_report = structured_response.get_final_report()
                    has_model_html = '<div' in final_report or '<script' in final_report or 'echarts' in final_report.lower()
                    metadata["contains_html"] = has_model_html
                    metadata["content_type"] = "html" if has_model_html else "markdown"

            return {
                "response": final_report_content,
                "conversation_id": conversation_id,
                "duration_ms": duration_ms,
                "tool_calls": self._extract_tool_calls(result),
                "artifacts": self._extract_artifacts(result),
                "metadata": metadata
            }

        except Exception as e:
            import json
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

            # 构建错误详情
            error_detail = {
                "error_type": error_type,
                "error_message": error_msg,
                "model": model_to_log if 'model_to_log' in locals() else self.model_name,
            }

            # 尝试从 httpx.HTTPStatusError 中提取真实 API 响应
            raw_api_error = None
            zhipu_error = None

            # httpx.HTTPStatusError 有 response 属性
            if error_type == "HTTPStatusError" and hasattr(e, 'response'):
                try:
                    response_text = e.response.text
                    logger.info(f"API 原始响应: {response_text}")

                    # 尝试解析 JSON 响应
                    response_json = json.loads(response_text)
                    if 'error' in response_json:
                        zhipu_error = response_json['error']
                        error_detail["zhipu_code"] = zhipu_error.get('code')
                        error_detail["zhipu_message"] = zhipu_error.get('message')
                        raw_api_error = f"[{zhipu_error.get('code')}] {zhipu_error.get('message')}"
                except:
                    raw_api_error = response_text if 'response_text' in locals() else None

            # 如果没有提取到智谱错误，尝试其他方式
            if not zhipu_error:
                # 检查 LangChain 异常
                if hasattr(e, '__cause__') and e.__cause__:
                    raw_api_error = str(e.__cause__)

            if raw_api_error:
                error_detail["raw_error"] = raw_api_error

            # 添加建议
            if zhipu_error:
                code = zhipu_error.get('code', '')
                if code == '1113':
                    error_detail["suggestion"] = "智谱 AI 账户余额不足，请充值: https://bigmodel.cn/usercenter/balance"
                elif code == '1000':
                    error_detail["suggestion"] = "智谱 AI 身份验证失败，请检查 API Key 是否正确"
                elif code == '1301':
                    error_detail["suggestion"] = "智谱 AI 请求过于频繁，请稍后再试"
                else:
                    error_detail["suggestion"] = f"智谱 AI 错误: {zhipu_error.get('message')}"
            elif "429" in error_msg:
                error_detail["suggestion"] = "API 返回 429 错误，可能是账户余额不足或请求过于频繁。请检查您的账户余额: https://bigmodel.cn/usercenter/balance"
            elif "401" in error_msg or "authentication" in error_msg.lower():
                error_detail["suggestion"] = "API 认证失败，请检查 API Key 是否正确"
            elif "timeout" in error_msg.lower():
                error_detail["suggestion"] = "请求超时，请稍后重试"
            elif "connection" in error_msg.lower():
                error_detail["suggestion"] = "网络连接失败，请检查网络设置"

            # 返回错误，优先显示原始 API 错误
            response_msg = raw_api_error if raw_api_error else error_msg
            return {
                "response": f"查询失败: {response_msg}",
                "conversation_id": conversation_id,
                "error": error_detail
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
        """构建消息列表，包含结构化响应系统提示"""
        messages = []

        # 添加结构化响应系统提示
        messages.append({
            "role": "system",
            "content": STRUCTURED_RESPONSE_SYSTEM_PROMPT
        })

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

    def _extract_response_content(
        self,
        result: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> tuple[str, Optional[StructuredResponse]]:
        """
        提取响应内容并解析结构化响应

        实现代码管理流程：
        1. 代码检测：当模型返回包含代码块时（```python...```），检测出来
        2. 代码标识生成：生成唯一且可读的标识，格式 `code_{YYYYMMDD}_{random}`
        3. 代码保存：将代码保存到 FileStore 中的 `.py` 文件
        4. 上下文清理：用概述替换原始代码（如 `<!-- CODE_SAVED: code_20250207_abc123 -->`）
        5. 支持 review：当需要 review 代码时，通过 file_reader 读取，读取后再次清理

        Args:
            result: Agent 执行结果
            session_id: 会话 ID（用于代码文件关联）

        Returns:
            (final_report_content, structured_response)
            - final_report_content: 最终报告内容（纯文本或模型生成的 HTML）
            - structured_response: 解析后的结构化响应对象（包含 task_analysis、execution_plan 等）
        """
        try:
            messages = result.get("messages", [])
            raw_content = None

            if messages:
                # 获取最后一条 AI 消息
                for msg in reversed(messages):
                    if hasattr(msg, 'content'):
                        content = msg.content
                        if isinstance(content, list):
                            # 处理多模态内容
                            raw_content = "\n".join(
                                item.get("text", str(item))
                                for item in content
                                if isinstance(item, dict)
                            )
                        else:
                            raw_content = str(content)
                        break
                    elif isinstance(msg, dict) and "content" in msg:
                        raw_content = str(msg["content"])
                        break

            if not raw_content:
                return "无响应内容", None

            # 解析结构化响应
            structured_response = parse_structured_response(raw_content)

            if structured_response is None:
                # 解析失败，返回原始内容
                logger.warning(f"无法解析结构化响应，返回原始内容")
                return raw_content, None

            # 获取最终报告内容
            final_report = structured_response.get_final_report()

            # 代码管理流程
            try:
                from backend.api.state import get_app_state
                from backend.filestore.stores.code_store import CodeStore

                app_state = get_app_state()
                file_store = app_state.get("file_store")

                if file_store:
                    code_store = file_store.code

                    # 检测是否有代码保存标识（说明可能需要 review）
                    code_markers = CodeStore.extract_code_saved_markers(final_report)

                    # 如果检测到代码块，执行保存和清理流程
                    if CodeStore.has_code_blocks(final_report):
                        logger.info("检测到代码块，开始代码管理流程")

                        # 提取所有代码块
                        code_blocks = CodeStore.extract_code_blocks(final_report)

                        # 处理每个代码块
                        processed_report = final_report
                        for i, block in enumerate(code_blocks):
                            code = block["code"]
                            language = block["language"]

                            # 只处理 Python 代码
                            if language in ("python", "py"):
                                # 生成唯一标识
                                code_id = code_store.generate_code_id()

                                # 生成代码描述（取前50个字符）
                                description = code[:50].replace('\n', ' ')
                                if len(code) > 50:
                                    description += "..."

                                # 保存代码到 FileStore
                                code_ref = code_store.store(
                                    content=code.encode('utf-8'),
                                    code_id=code_id,
                                    session_id=session_id,
                                    description=description
                                )

                                logger.info(f"代码已保存: {code_id}, file_ref={code_ref.file_id}")

                                # 替换代码块为保存标识
                                # 构建完整的代码块（包括反引号）进行替换
                                code_block_full = f"```{language}\n{code}\n```"
                                processed_report = CodeStore.replace_code_with_marker(
                                    processed_report,
                                    code_block_full,
                                    code_id,
                                    description
                                )

                        # 更新结构化响应中的内容
                        if processed_report != final_report:
                            structured_response.action.content = processed_report
                            logger.info("代码块已替换为保存标识")
                            final_report = processed_report

            except Exception as code_error:
                # 代码管理流程出错不影响主流程
                logger.warning(f"代码管理流程出错（已跳过）: {code_error}", exc_info=True)

            # 返回处理后的 final_report 内容
            return final_report, structured_response

        except Exception as e:
            logger.error(f"提取响应内容失败: {e}", exc_info=True)
            return f"响应解析失败: {str(e)}", None

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
