"""
BA-Agent 主 Agent 类

使用 LangGraph 和 Claude 3.5 Sonnet 实现
"""

import os
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, TypedDict
from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.runnables import RunnableConfig
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

import logging

from config import get_config
from backend.models.agent import (
    AgentState as AgentModel,
    Conversation,
    Message,
    MessageRole,
    MessageType,
    AgentConfig as AgentConfigModel,
)
from backend.memory.flush import MemoryFlush, MemoryFlushConfig, MemoryExtractor
from backend.memory.index import MemoryIndexer, MemoryWatcher, get_index_db_path

logger = logging.getLogger(__name__)

# Clawdbot 风格的静默响应标记
SILENT_REPLY_TOKEN = "_SILENT_"


class AgentState(TypedDict):
    """Agent 状态定义"""

    messages: Sequence[BaseMessage]
    # 可以添加更多状态字段
    conversation_id: str
    user_id: str
    metadata: Dict[str, Any]


class BAAgent:
    """
    BA-Agent 主 Agent 类

    使用 LangGraph 和 Claude 3.5 Sonnet 实现对话式 Agent
    """

    def __init__(
        self,
        config: Optional[AgentConfigModel] = None,
        tools: Optional[List[BaseTool]] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        初始化 BA-Agent

        Args:
            config: Agent 配置，如果不提供则从全局配置加载
            tools: 可用工具列表
            system_prompt: 系统提示词，如果不提供则使用默认提示词
        """
        # 加载配置
        self.config = config or self._load_default_config()
        self.app_config = get_config()

        # 初始化 LLM
        self.llm = self._init_llm()

        # 初始化工具
        self.tools = tools or []

        # 初始化系统提示词
        self.system_prompt = system_prompt or self._get_default_system_prompt()

        # 创建 Agent
        self.agent = self._create_agent()

        # 初始化检查点保存器（用于对话历史）
        self.memory = MemorySaver()

        # 初始化 Memory Flush
        self.memory_flush = self._init_memory_flush()

        # 初始化 Memory Watcher
        self.memory_watcher = self._init_memory_watcher()

        # 会话 token 跟踪
        self.session_tokens = 0
        self.compaction_count = 0
        # Memory Flush 状态追踪 (Clawdbot 风格)
        self.memory_flush_compaction_count: Optional[int] = None

    def _load_default_config(self) -> AgentConfigModel:
        """
        从全局配置加载默认 Agent 配置

        Returns:
            Agent 配置
        """
        app_config = get_config()
        return AgentConfigModel(
            name="BA-Agent",
            model=app_config.llm.model,
            temperature=app_config.llm.temperature,
            max_tokens=app_config.llm.max_tokens,
            system_prompt=self._get_default_system_prompt(),
            tools=[],
            memory_enabled=app_config.memory.enabled,
            hooks_enabled=True,
        )

    def _init_llm(self) -> ChatAnthropic:
        """
        初始化 Claude LLM

        Returns:
            ChatAnthropic 实例
        """
        # 获取 API 密钥
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found. "
                "Please set ANTHROPIC_API_KEY environment variable or BA_ANTHROPIC_API_KEY."
            )

        # 获取自定义 API 端点（可选）
        # 优先级: 1. 环境变量 ANTHROPIC_BASE_URL 2. 配置文件中的 base_url
        base_url = os.environ.get("ANTHROPIC_BASE_URL") or self.app_config.llm.base_url

        # 创建 ChatAnthropic 实例
        llm_kwargs = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "api_key": api_key,
            "timeout": self.app_config.llm.timeout,
        }

        # 如果有自定义 base_url，添加到参数中
        if base_url:
            llm_kwargs["base_url"] = base_url

        llm = ChatAnthropic(**llm_kwargs)

        return llm

    def _get_api_key(self) -> str:
        """
        获取 Anthropic API 密钥

        优先级:
        1. 环境变量 ANTHROPIC_API_KEY
        2. 环境变量 BA_ANTHROPIC_API_KEY
        3. 配置文件中的值

        Returns:
            API 密钥
        """
        # 首先检查环境变量
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get(
            "BA_ANTHROPIC_API_KEY"
        )
        if api_key:
            return api_key

        # 然后检查配置
        if self.app_config.llm.provider == "anthropic":
            return self.app_config.llm.api_key

        return ""

    def _get_default_system_prompt(self) -> str:
        """
        获取默认系统提示词

        Returns:
            系统提示词
        """
        return """# BA-Agent 系统提示词

你是一个专业的商业分析助手 (BA-Agent)，面向非技术业务人员，专注于电商业务分析。

## 核心能力

1. **异动检测** - 自动检测 GMV、订单量、转化率等关键指标的异常变化
2. **归因分析** - 分析指标变化的根本原因（维度下钻、事件影响等）
3. **报告生成** - 自动生成日报、周报、月报，包含数据图表
4. **数据可视化** - 生成 ECharts 图表代码，前端渲染展示

## 工作流程

1. 理解用户需求（自然语言查询）
2. 查询相关数据（使用 query_database 工具）
3. 进行分析处理（调用相应 Skill）
4. 生成结果报告（使用 invoke_skill 工具）

## 注意事项

- 始终使用中文与用户交流
- 数据查询前先明确时间范围和指标
- 解释分析结果时提供业务洞察和建议
- 生成图表时提供完整的 ECharts 配置

## 记忆管理

- 重要信息会自动保存到长期记忆
- 每日操作记录在 daily log 中
- 当前任务计划存储在 task_plan.md 中

## Memory Flush 协议

当会话接近上下文限制时，系统会自动触发 Memory Flush：
1. 自动从对话中提取重要信息
2. 格式化为结构化的 Retain 格式 (W @, B @, O(c=) @)
3. 持久化到 memory/YYYY-MM-DD.md 文件
4. 释放上下文空间以继续对话

你会在此时收到专门的 Flush 指令，请专注于记忆提取工作。
"""

    def _init_memory_flush(self) -> Optional[MemoryFlush]:
        """
        初始化 Memory Flush

        Returns:
            MemoryFlush 实例，如果未启用则返回 None
        """
        if not self.app_config.memory.enabled:
            return None

        flush_config = self.app_config.memory.flush
        if not flush_config.enabled:
            return None

        # 创建 MemoryFlushConfig
        memory_flush_config = MemoryFlushConfig(
            soft_threshold=flush_config.soft_threshold_tokens,
            reserve=flush_config.reserve_tokens_floor,
            min_memory_count=flush_config.min_memory_count,
            max_memory_age_hours=flush_config.max_memory_age_hours,
        )

        # 创建 MemoryExtractor
        memory_path = Path(self.app_config.memory.memory_dir)
        extractor = MemoryExtractor(
            model=flush_config.llm_model,
            llm_timeout=flush_config.llm_timeout,
        )

        # 创建 MemoryFlush
        return MemoryFlush(
            config=memory_flush_config,
            memory_path=memory_path,
            extractor=extractor,
        )

    def _init_memory_watcher(self) -> Optional["MemoryWatcherWrapper"]:
        """
        初始化 Memory Watcher

        Returns:
            MemoryWatcherWrapper 实例，如果未启用则返回 None
        """
        if not self.app_config.memory.enabled:
            return None

        watcher_config = self.app_config.memory.watcher
        if not watcher_config.enabled:
            return None

        # 创建 MemoryIndexer
        index_path = get_index_db_path()

        indexer = MemoryIndexer(
            db_path=index_path,
        )

        # 创建 watch 路径列表
        watch_paths = [Path(p) for p in watcher_config.watch_paths]

        # 创建 MemoryWatcher
        watcher = MemoryWatcher(
            indexer=indexer,
            watch_paths=watch_paths,
            debounce_seconds=watcher_config.debounce_seconds,
        )

        # 创建包装器
        wrapper = MemoryWatcherWrapper(
            watcher=watcher,
            check_interval=watcher_config.check_interval_seconds,
        )

        # 启动监听线程
        wrapper.start()

        return wrapper

    def _get_total_tokens(self, result: Dict[str, Any]) -> int:
        """
        从 Agent 结果中提取总 token 数

        Args:
            result: Agent 返回结果

        Returns:
            总 token 数
        """
        total = 0

        # 尝试从 response_metadata 中获取
        if "response_metadata" in result:
            metadata = result["response_metadata"]
            if "usage" in metadata:
                usage = metadata["usage"]
                total += usage.get("input_tokens", 0)
                total += usage.get("output_tokens", 0)

        # 尝试从 messages 中获取
        messages = result.get("messages", [])
        for msg in messages:
            if isinstance(msg, AIMessage):
                if hasattr(msg, "usage_metadata"):
                    usage = msg.usage_metadata or {}
                    total += usage.get("input_tokens", 0)
                    total += usage.get("output_tokens", 0)
                if hasattr(msg, "response_metadata"):
                    metadata = msg.response_metadata or {}
                    if "usage" in metadata:
                        usage = metadata["usage"]
                        total += usage.get("input_tokens", 0)
                        total += usage.get("output_tokens", 0)

        return total

    def _should_run_memory_flush(self, current_tokens: int) -> bool:
        """
        判断是否应该运行 Memory Flush (Clawdbot 风格)

        Args:
            current_tokens: 当前使用的 token 数

        Returns:
            是否应该运行 flush
        """
        if self.memory_flush is None:
            return False

        # 获取配置
        flush_config = self.app_config.memory.flush
        context_window = self.app_config.llm.max_tokens  # 假设使用 max_tokens 作为上下文窗口
        soft_threshold = flush_config.soft_threshold_tokens
        reserve_tokens = flush_config.reserve_tokens_floor

        # 计算阈值 (Clawdbot: contextWindow - reserveTokensFloor - softThresholdTokens)
        threshold = context_window - reserve_tokens - soft_threshold

        # 检查 token 阈值
        if current_tokens < threshold:
            return False

        # 检查是否已经在本次 compaction 中 flush 过
        if (self.memory_flush_compaction_count is not None and
            self.memory_flush_compaction_count == self.compaction_count):
            return False

        return True

    def _check_and_flush(
        self,
        conversation_id: str,
        messages: List[BaseMessage],
        current_tokens: int,
    ) -> Optional[Dict[str, Any]]:
        """
        检查是否需要触发 Memory Flush

        Args:
            conversation_id: 对话 ID
            messages: 消息列表
            current_tokens: 当前使用的 token 数

        Returns:
            Flush 结果，如果未触发则返回 None
        """
        if self.memory_flush is None:
            return None

        # 始终更新消息缓存（积累上下文）
        for msg in messages:
            if isinstance(msg, HumanMessage):
                self.memory_flush.add_message("user", msg.content)
            elif isinstance(msg, AIMessage):
                self.memory_flush.add_message("assistant", msg.content)

        # 检查是否应该运行 flush
        if not self._should_run_memory_flush(current_tokens):
            return None

        # 记录当前 compaction_count
        self.memory_flush_compaction_count = self.compaction_count

        # 检查并触发 flush
        result = self.memory_flush.check_and_flush(current_tokens)

        if result["flushed"]:
            # 更新 compaction 计数
            self.compaction_count += 1
            # 记录日志 (用户不可见)
            logger.info(
                f"Memory Flush triggered: {result['reason']}, "
                f"{result['memories_extracted']} memories extracted, "
                f"{result['memories_written']} memories written"
            )
            # 重置 token 计数
            self.session_tokens = 0

        return result if result["flushed"] else None

    def _create_agent(self):
        """
        创建 LangGraph Agent

        使用 langgraph.prebuilt.create_react_agent

        Returns:
            Agent 实例
        """
        # 创建 prompt template
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # 使用 create_react_agent 创建 Agent
        agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=prompt,
        )

        return agent

    def add_tool(self, tool: BaseTool) -> None:
        """
        添加工具到 Agent

        Args:
            tool: 工具实例
        """
        self.tools.append(tool)
        # 重新创建 Agent
        self.agent = self._create_agent()

    def add_tools(self, tools: List[BaseTool]) -> None:
        """
        批量添加工具到 Agent

        Args:
            tools: 工具列表
        """
        self.tools.extend(tools)
        # 重新创建 Agent
        self.agent = self._create_agent()

    def invoke(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        config: Optional[RunnableConfig] = None,
    ) -> Dict[str, Any]:
        """
        调用 Agent

        Args:
            message: 用户消息
            conversation_id: 对话 ID
            user_id: 用户 ID
            config: 可选的运行配置

        Returns:
            Agent 响应结果
        """
        # 生成 ID（如果未提供）
        if conversation_id is None:
            conversation_id = f"conv_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        if user_id is None:
            user_id = "user_default"

        # 准备输入消息
        messages = [HumanMessage(content=message)]

        # 准备配置
        if config is None:
            config = {}

        # 添加线程 ID 用于记忆
        config["configurable"] = {"thread_id": conversation_id}

        # 调用 Agent
        try:
            result = self.agent.invoke(
                {"messages": messages},
                config,
            )

            # 提取 token 使用
            tokens_used = self._get_total_tokens(result)
            self.session_tokens += tokens_used

            # 检查是否需要 Memory Flush (静默执行，用户不可见)
            flush_result = self._check_and_flush(
                conversation_id,
                result.get("messages", []),
                self.session_tokens,
            )

            # Flush 结果不对用户暴露，只记录日志
            # (Clawdbot 风格: 静默轮次)

            # 提取响应
            response = self._extract_response(result)

            return {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "response": response,
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "tokens_used": tokens_used,
                "session_tokens": self.session_tokens,
                # flush_triggered 不再暴露给用户 (Clawdbot 风格: 静默)
            }

        except Exception as e:
            return {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "response": f"抱歉，处理过程中出现错误: {str(e)}",
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _extract_response(self, result: Dict[str, Any]) -> str:
        """
        从 Agent 结果中提取响应文本

        Args:
            result: Agent 返回结果

        Returns:
            响应文本
        """
        messages = result.get("messages", [])
        if not messages:
            return ""

        # 获取最后一条 AI 消息
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    # 处理多模态内容
                    text_parts = [
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and "text" in part
                    ]
                    return "\n".join(text_parts)

        return ""

    def stream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        config: Optional[RunnableConfig] = None,
    ):
        """
        流式调用 Agent

        Args:
            message: 用户消息
            conversation_id: 对话 ID
            user_id: 用户 ID
            config: 可选的运行配置

        Yields:
            Agent 响应片段
        """
        # 生成 ID（如果未提供）
        if conversation_id is None:
            conversation_id = f"conv_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        if user_id is None:
            user_id = "user_default"

        # 准备输入消息
        messages = [HumanMessage(content=message)]

        # 准备配置
        if config is None:
            config = {}

        # 添加线程 ID 用于记忆
        config["configurable"] = {"thread_id": conversation_id}

        # 流式调用 Agent
        try:
            for chunk in self.agent.stream(
                {"messages": messages},
                config,
            ):
                yield chunk

        except Exception as e:
            yield {
                "error": str(e),
                "success": False,
            }

    def get_conversation_history(
        self,
        conversation_id: str,
    ) -> List[BaseMessage]:
        """
        获取对话历史

        Args:
            conversation_id: 对话 ID

        Returns:
            消息列表
        """
        # 从检查点获取历史
        config = {"configurable": {"thread_id": conversation_id}}
        state = self.agent.get_state(config)

        return state.messages.get("messages", [])

    def reset_conversation(self, conversation_id: str) -> None:
        """
        重置对话历史

        Args:
            conversation_id: 对话 ID
        """
        # 删除检查点中的对话
        config = {"configurable": {"thread_id": conversation_id}}
        self.agent.update_state(config, {"messages": []})

    def shutdown(self) -> None:
        """
        关闭 Agent，释放资源

        停止 MemoryWatcher 线程
        """
        if self.memory_watcher:
            self.memory_watcher.stop()
            self.memory_watcher = None


class MemoryWatcherWrapper:
    """
    Memory Watcher 包装器

    在后台线程中运行 MemoryWatcher，定期检查文件变更
    """

    def __init__(
        self,
        watcher: MemoryWatcher,
        check_interval: float = 5.0,
    ):
        """
        初始化包装器

        Args:
            watcher: MemoryWatcher 实例
            check_interval: 检查间隔（秒）
        """
        self.watcher = watcher
        self.check_interval = check_interval
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()

    def _watch_loop(self) -> None:
        """监听循环"""
        import logging
        logger = logging.getLogger(__name__)

        while not self._stop_event.is_set():
            try:
                # 处理变更
                results = self.watcher.process_changes()

                if results["processed"] > 0 or results["failed"] > 0:
                    logger.info(
                        f"MemoryWatcher: 处理了 {results['processed']} 个文件变更"
                    )

                    if results["failed"] > 0:
                        logger.warning(
                            f"MemoryWatcher: {results['failed']} 个文件处理失败"
                        )

            except Exception as e:
                logger.error(f"MemoryWatcher 循环错误: {e}")

            # 等待指定间隔或停止事件
            self._stop_event.wait(self.check_interval)

    def start(self) -> None:
        """启动监听线程"""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self.watcher.start()

        self._thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="MemoryWatcher",
        )
        self._thread.start()

    def stop(self) -> None:
        """停止监听线程"""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        self.watcher.stop()

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running and self._thread is not None and self._thread.is_alive()


def create_agent(
    tools: Optional[List[BaseTool]] = None,
    system_prompt: Optional[str] = None,
) -> BAAgent:
    """
    创建 BA-Agent 实例的便捷函数

    Args:
        tools: 可用工具列表
        system_prompt: 自定义系统提示词

    Returns:
        BA-Agent 实例
    """
    return BAAgent(tools=tools, system_prompt=system_prompt)


# 导出
__all__ = [
    "BAAgent",
    "AgentState",
    "create_agent",
]
