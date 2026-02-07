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
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
# LangGraph V2.0 迁移 - 使用新的 langchain.agents API
# 使用别名避免与本地 create_agent 便捷函数冲突
from langchain.agents import create_agent as langchain_create_agent

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
# NEW: Skills system integration
from backend.skills import (
    SkillLoader,
    SkillRegistry,
    SkillActivator,
    SkillMessageFormatter,
    create_skill_tool,
    SkillMessage,
    ContextModifier,
    MessageType as SkillMessageType,  # 别名避免冲突
    MessageVisibility,
)
# NEW v2.1: Pipeline components integration
from backend.pipeline import (
    get_token_counter,
    AdvancedContextManager,
    CompressionMode,
)

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
        use_default_tools: bool = True,
    ):
        """
        初始化 BA-Agent

        Args:
            config: Agent 配置，如果不提供则从全局配置加载
            tools: 可用工具列表（如果为 None 且 use_default_tools=True，则加载默认工具）
            system_prompt: 系统提示词，如果不提供则使用默认提示词
            use_default_tools: 是否加载默认工具列表（默认 True）
        """
        # 加载配置
        self.config = config or self._load_default_config()
        self.app_config = get_config()

        # 初始化 LLM
        self.llm = self._init_llm()

        # 初始化工具
        # 只有在明确请求默认工具时才加载 (use_default_tools=True 且未提供 tools)
        # tools=None 时的默认行为：只加载 skill_tool（在后面添加）
        if tools is None:
            self.tools = []
        elif use_default_tools and len(tools) == 0:
            # 空列表 + use_default_tools=True → 加载所有默认工具
            self.tools = self._load_default_tools()
        else:
            self.tools = tools

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

        # NEW: 初始化 Skills System
        self.skill_loader = self._init_skill_loader()
        self.skill_registry = SkillRegistry(self.skill_loader) if self.skill_loader else None
        self.skill_activator = SkillActivator(
            self.skill_loader,
            self.skill_registry
        ) if self.skill_loader else None

        # NEW: 创建 Skill meta-tool 并添加到工具列表
        self.skill_tool = self._init_skill_tool()
        if self.skill_tool:
            self.tools.append(self.skill_tool)

        # NEW v2.1: 初始化 Pipeline 组件
        self.token_counter = get_token_counter()

        # 创建 AdvancedContextManager 实例 (使用配置和现有 LLM)
        self.context_manager = AdvancedContextManager(
            max_tokens=self.app_config.llm.max_tokens,
            compression_mode=CompressionMode.EXTRACT,  # 智能压缩，非简单截断
            llm_summarizer=self.llm,  # 复用现有 LLM 用于 SUMMARIZE 模式
            token_counter=self.token_counter,  # 共享 token counter
        )

        # Active skill context modifier tracking
        self._active_skill_context: Dict[str, Any] = {}

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

    def _load_default_tools(self) -> List[BaseTool]:
        """
        加载默认工具列表

        Returns:
            默认工具列表
        """
        from tools import (
            execute_command_tool,
            run_python_tool,
            web_search_tool,
            web_reader_tool,
            file_reader_tool,
            file_write_tool,
            query_database_tool,
            vector_search_tool,
        )
        # 记忆搜索工具 (clawdbot 风格：Agent 主动调用)
        from backend.memory.tools import (
            memory_search_v2_tool,
        )

        default_tools = [
            # 核心执行工具
            execute_command_tool,      # 命令行执行
            run_python_tool,            # Python 沙盒

            # Web 工具
            web_search_tool,            # Web 搜索
            web_reader_tool,            # Web 读取

            # 文件工具
            file_reader_tool,           # 文件读取
            file_write_tool,            # 文件写入

            # 数据工具
            query_database_tool,        # SQL 查询
            vector_search_tool,         # 向量检索

            # 记忆搜索工具 (clawdbot 风格：Agent 主动调用)
            memory_search_v2_tool,      # 混合搜索 (FTS5 + Vector)
        ]

        logger.info(f"Loaded {len(default_tools)} default tools")
        return default_tools

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
        获取默认系统提示词（包含 Skills 部分和结构化响应格式）

        Returns:
            系统提示词
        """
        # 基础业务提示词
        base_prompt = """# BA-Agent 系统提示词

你是一个专业的商业分析助手 (BA-Agent)，面向非技术业务人员，专注于电商业务分析。

## 核心能力

1. **异动检测** - 自动检测 GMV、订单量、转化率等关键指标的异常变化
2. **归因分析** - 分析指标变化的根本原因（维度下钻、事件影响等）
3. **报告生成** - 自动生成日报、周报、月报，包含数据图表
4. **数据可视化** - 生成 ECharts 图表代码，前端渲染展示

## 工作流程

1. 理解用户需求
2. 判断是否需要调用工具（查询数据、执行代码等）
3. 如需工具，调用相应工具获取结果
4. 基于工具结果生成最终报告，**必须使用结构化 JSON 格式**

## 可用工具

- `query_database`: SQL 查询
- `bac_code_agent`: Python 代码执行（数据分析）
- `web_search`: 网络搜索
- `web_reader`: 网页读取
- `file_reader`: 文件读取
- `file_write`: 文件写入
- `execute_command`: 命令行执行

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

        # 结构化响应格式（仅用于最终响应）
        response_format_prompt = """

## 最终响应格式要求（重要！）

当调用工具完成后，你**必须**按照以下 JSON 格式返回最终响应：

```json
{
    "task_analysis": "思维链：1. 识别意图; 2. 数据处理过程; 3. 关键发现",
    "execution_plan": "R1: 数据获取; R2: 数据分析; R3: 报告生成(当前)",
    "current_round": 当前轮次,
    "action": {
        "type": "complete",
        "content": "最终报告内容（可包含 HTML/ECharts 代码）",
        "recommended_questions": ["推荐问题1", "推荐问题2"],
        "download_links": ["结果文件.xlsx"]
    }
}
```

### Content 格式说明

**content 可以包含：**
1. 纯文本分析结果
2. HTML 代码（ECharts 图表）
3. Markdown 格式

**带图表的报告示例：**
```json
{
    "action": {
        "type": "complete",
        "content": "销售数据分析完成：\\n\\n1. Q1销售额500万，同比增长15%\\n2. Q3增长最快\\n\\n<div class='chart-wrapper'><div id='chart-trend' style='width:100%;height:400px;'></div></div>\\n<script>(function(){const chart = echarts.init(document.getElementById('chart-trend'));chart.setOption({xAxis: {type: 'category', data: ['Q1','Q2','Q3','Q4']}, yAxis: {type: 'value'}, series: [{type: 'line', data: [500, 520, 580, 570]}]});})();</script>",
        "recommended_questions": ["Q3增长原因？", "地区分布如何？"],
        "download_links": ["analysis_result.xlsx"]
    }
}
```

### 重要规则

1. **工具调用阶段**：使用 LangChain 原生工具调用机制，返回 tool_calls
2. **最终响应**：必须返回上述 JSON 格式（包装在代码块中）
3. **终止条件**：当工具调用完成、分析完成、或可以直接回答时，返回 JSON 响应
"""

        # 组合提示词
        full_prompt = base_prompt + "\n" + response_format_prompt

        # 添加 Skills 部分（如果有）
        skills_section = self._build_skills_section()
        if skills_section:
            full_prompt = full_prompt + "\n\n" + skills_section

        return full_prompt

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

    def _init_skill_loader(self) -> Optional[SkillLoader]:
        """
        初始化 Skills System Loader

        Returns:
            SkillLoader 实例，如果 skills 目录不存在则返回 None
        """
        # 定义 skills 目录
        skills_dirs = [
            Path("skills"),              # Project skills
            Path(".claude/skills"),      # User skills
        ]

        # 检查是否至少有一个目录存在
        has_skills = any(d.exists() for d in skills_dirs)

        if not has_skills:
            logger.info("No skills directories found, skills system disabled")
            return None

        return SkillLoader(skills_dirs=skills_dirs)

    def _init_skill_tool(self) -> Optional[BaseTool]:
        """
        初始化 Skill meta-tool

        Returns:
            StructuredTool 实例，如果没有 skills 则返回 None
        """
        if self.skill_registry is None or self.skill_activator is None:
            return None

        try:
            return create_skill_tool(self.skill_registry, self.skill_activator)
        except Exception as e:
            logger.warning(f"Failed to create skill tool: {e}")
            return None

    def _build_skills_section(self) -> str:
        """
        构建 Skills 发现部分，用于系统提示词

        Returns:
            Skills 发现部分的格式化字符串，如果没有 skills 则返回空字符串
        """
        # Check if skill_registry exists and is initialized
        # Use getattr to handle cases where __init__ is not complete yet
        skill_registry = getattr(self, 'skill_registry', None)
        if skill_registry is None:
            return ""

        # 获取格式化的 skills 列表
        skills_list = skill_registry.get_formatted_skills_list()

        if not skills_list:
            return ""

        # 使用 formatter 构建完整的 skills section
        formatter = SkillMessageFormatter()
        return formatter.format_skills_list_for_prompt(skills_list)

    def _handle_skill_activation_result(
        self,
        result: Dict[str, Any],
        conversation_id: str,
        config: RunnableConfig
    ) -> Optional[Dict[str, Any]]:
        """
        Handle skill activation result from tool call.

        When the activate_skill tool is called, it returns a SkillActivationResult.
        This method processes that result by:
        1. Injecting skill messages into the conversation
        2. Applying context modifiers (tool permissions, model override)
        3. Continuing the conversation with the skill active

        Args:
            result: The result dict from activate_skill tool
            conversation_id: Current conversation ID
            config: Current runnable config

        Returns:
            Updated result after processing, or None if no skill was activated
        """
        # Check if this is a skill activation result
        if not result.get("success") or "skill_name" not in result:
            return None

        skill_name = result["skill_name"]
        messages_data = result.get("messages", [])
        context_data = result.get("context_modifier", {})

        # Log skill activation
        logger.info(f"Processing skill activation: {skill_name}")

        # Apply context modifier
        context_modifier = ContextModifier(
            allowed_tools=context_data.get("allowed_tools"),
            model=context_data.get("model"),
            disable_model_invocation=context_data.get("disable_model_invocation", False)
        )
        self._apply_context_modifier(context_modifier, skill_name)

        # Inject messages into conversation
        if messages_data:
            self._inject_skill_messages(messages_data, conversation_id, config)

        # Store active skill context
        self._active_skill_context[skill_name] = context_modifier.to_dict()

        logger.info(
            f"Skill '{skill_name}' activated: "
            f"{len(messages_data)} messages injected, "
            f"context={context_modifier.to_dict()}"
        )

        return result

    def _inject_skill_messages(
        self,
        messages_data: List[Dict[str, Any]],
        conversation_id: str,
        config: RunnableConfig
    ) -> None:
        """
        Inject skill messages into the conversation.

        Args:
            messages_data: List of message dicts from skill activation
            conversation_id: Current conversation ID
            config: Current runnable config
        """
        # Get current conversation state
        state = self.agent.get_state(config)
        current_messages = list(state.messages.get("messages", []))

        # Convert and add each message
        for msg_data in messages_data:
            # Determine message type based on content
            if msg_data.get("isMeta") is True:
                # Hidden instruction message - create as AIMessage with metadata
                msg = AIMessage(
                    content=msg_data["content"],
                    additional_kwargs={"isMeta": True}
                )
            else:
                # Visible message - create as HumanMessage
                msg = HumanMessage(content=msg_data["content"])

            current_messages.append(msg)

        # Update state with new messages
        self.agent.update_state(config, {"messages": current_messages})

        logger.debug(f"Injected {len(messages_data)} messages into conversation {conversation_id}")

    def _apply_context_modifier(
        self,
        context_modifier: ContextModifier,
        skill_name: str
    ) -> None:
        """
        Apply context modifier from skill activation.

        This modifies the agent's execution context based on skill requirements:
        - allowed_tools: Pre-approve specific tools for this skill
        - model: Switch to a different model (if supported)
        - disable_model_invocation: Prevent skill from calling LLM

        Args:
            context_modifier: The context modifier to apply
            skill_name: Name of the skill being activated
        """
        # Always set the currently active skill
        self._active_skill_context["current_skill"] = skill_name

        # Apply tool permissions
        if context_modifier.allowed_tools is not None:
            logger.info(
                f"Skill '{skill_name}' granted access to: "
                f"{context_modifier.allowed_tools}"
            )
            # Store in active context for tool permission checks
            self._active_skill_context[f"{skill_name}_allowed_tools"] = context_modifier.allowed_tools

        # Apply model override
        if context_modifier.model is not None:
            logger.info(f"Skill '{skill_name}' requesting model: {context_modifier.model}")
            self._active_skill_context[f"{skill_name}_model"] = context_modifier.model
            # Attempt to switch model
            self._switch_model_for_skill(context_modifier.model, skill_name)

        # Apply model invocation disable
        if context_modifier.disable_model_invocation:
            logger.info(f"Skill '{skill_name}' has model invocation disabled")
            self._active_skill_context[f"{skill_name}_disable_model"] = True
            self._active_skill_context["disable_model_invocation"] = True

    def _check_tool_allowed(self, tool_name: str) -> bool:
        """
        Check if a tool is allowed to be used based on active skill context.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool is allowed, False otherwise
        """
        current_skill = self._active_skill_context.get("current_skill")
        if not current_skill:
            # No active skill, all tools are allowed
            return True

        allowed_tools_key = f"{current_skill}_allowed_tools"
        allowed_tools = self._active_skill_context.get(allowed_tools_key)

        if allowed_tools is None:
            # No restriction specified, all tools allowed
            return True

        # Check if tool is in the allowed list
        return tool_name in allowed_tools

    def _switch_model_for_skill(self, model: str, skill_name: str) -> bool:
        """
        Switch to a different model for the active skill.

        Args:
            model: Model identifier to switch to
            skill_name: Name of the skill requesting the switch

        Returns:
            True if model was switched, False otherwise
        """
        try:
            # Only switch if it's different from current model
            if self.config.model == model:
                logger.debug(f"Already using model {model}, no switch needed")
                return True

            logger.info(f"Switching model from {self.config.model} to {model} for skill '{skill_name}'")

            # Update the config
            self.config.model = model

            # Recreate the LLM instance
            self.llm = self._init_llm()

            # Recreate the agent with new LLM
            self.agent = self._create_agent()

            # Mark that we've switched models
            self._active_skill_context["model_switched"] = True
            self._active_skill_context["original_model"] = self.config.model

            logger.info(f"Successfully switched to model {model}")
            return True

        except Exception as e:
            logger.error(f"Failed to switch model to {model}: {e}")
            # Store the failure
            self._active_skill_context[f"{skill_name}_model_switch_failed"] = str(e)
            return False

    def _get_active_skill_model(self) -> Optional[str]:
        """
        Get the model requested by the active skill.

        Returns:
            Model identifier if a skill has requested a model switch, None otherwise
        """
        current_skill = self._active_skill_context.get("current_skill")
        if not current_skill:
            return None

        return self._active_skill_context.get(f"{current_skill}_model")

    def _is_model_invocation_disabled(self) -> bool:
        """
        Check if model invocation is disabled for the current skill.

        Returns:
            True if model invocation should be disabled, False otherwise
        """
        return self._active_skill_context.get("disable_model_invocation", False)

    def _get_total_tokens(self, result: Dict[str, Any]) -> int:
        """
        从 Agent 结果中提取总 token 数 (增强版 v2.1)

        v2.1 改进:
        - 优先使用 DynamicTokenCounter 进行精确计数
        - 保留从 LLM 响应 metadata 提取的后备方案
        - 支持调用前预计数和调用后验证

        Args:
            result: Agent 返回结果

        Returns:
            总 token 数
        """
        total = 0

        # v2.1: 优先使用 DynamicTokenCounter
        messages = result.get("messages", [])
        if messages:
            try:
                # 使用新的 token_counter 精确计数
                counted = self.token_counter.count_messages(messages)
                if counted > 0:
                    return counted
            except Exception:
                pass  # 降级到旧方法

        # 后备方案：从 LLM 响应 metadata 中获取
        if "response_metadata" in result:
            metadata = result["response_metadata"]
            if "usage" in metadata:
                usage = metadata["usage"]
                total += usage.get("input_tokens", 0)
                total += usage.get("output_tokens", 0)

        # 后备方案：从 messages 中的 usage_metadata 获取
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

        v2.1 改进:
        - 使用 DynamicTokenCounter 进行更精确的 token 计算

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

        v2.1 改进:
        - 使用 DynamicTokenCounter 精确计算消息 token
        - 为后续压缩提供准确的 token 数据

        Args:
            conversation_id: 对话 ID
            messages: 消息列表
            current_tokens: 当前使用的 token 数

        Returns:
            Flush 结果，如果未触发则返回 None
        """
        if self.memory_flush is None:
            return None

        # v2.1: 使用 DynamicTokenCounter 精确计算
        try:
            actual_tokens = self.token_counter.count_messages(messages)
        except Exception:
            actual_tokens = current_tokens  # 降级

        # 始终更新消息缓存（积累上下文）
        for msg in messages:
            if isinstance(msg, HumanMessage):
                self.memory_flush.add_message("user", msg.content)
            elif isinstance(msg, AIMessage):
                self.memory_flush.add_message("assistant", msg.content)

        # 检查是否应该运行 flush
        if not self._should_run_memory_flush(actual_tokens):
            return None

        # 记录当前 compaction_count
        self.memory_flush_compaction_count = self.compaction_count

        # 检查并触发 flush
        result = self.memory_flush.check_and_flush(actual_tokens)

        if result["flushed"]:
            # 更新 compaction 计数
            self.compaction_count += 1
            # 记录日志 (用户不可见)
            logger.info(
                f"Memory Flush triggered: {result['reason']}, "
                f"{result['memories_extracted']} memories extracted, "
                f"{result['memories_written']} memories written"
            )

            # v2.1: 使用 AdvancedContextManager 执行智能压缩
            # 获取当前状态以获取完整消息列表
            config = {"configurable": {"thread_id": conversation_id}}
            state = self.agent.get_state(config)
            all_messages = list(state.messages.get("messages", [])) if state else []

            if all_messages:
                # 智能压缩到 50% 容量
                target_tokens = int(self.app_config.llm.max_tokens * 0.5)
                compressed = self.context_manager.compress(
                    all_messages,
                    target_tokens=target_tokens,
                    mode=CompressionMode.EXTRACT,
                )
                self.agent.update_state(config, {"messages": compressed})

                logger.info(
                    f"Context compressed (v2.1): {len(all_messages)} -> {len(compressed)} messages, "
                    f"tokens: {actual_tokens} -> {self.token_counter.count_messages(compressed)}"
                )

            # 重置 token 计数
            self.session_tokens = 0

        return result if result["flushed"] else None

    def _compact_conversation(
        self,
        conversation_id: str,
        keep_recent: int = 10
    ) -> bool:
        """
        压缩对话历史 (v2.1: 使用 AdvancedContextManager)

        v2.1 改进:
        - 使用 AdvancedContextManager 智能压缩
        - 按优先级保留消息 (CRITICAL/HIGH/MEDIUM/LOW)
        - 保留系统消息和关键用户消息
        - 代替原来的简单截断 (keep_recent=N)

        Args:
            conversation_id: 对话 ID
            keep_recent: 保留最近的消息数量 (降级选项，默认 10 条)

        Returns:
            是否成功压缩
        """
        try:
            config = {"configurable": {"thread_id": conversation_id}}
            state = self.agent.get_state(config)

            if not state or not state.messages:
                return False

            # 获取当前所有消息
            all_messages = list(state.messages.get("messages", []))

            if len(all_messages) <= keep_recent:
                # 消息数量不足，无需压缩
                return False

            # v2.1: 使用 AdvancedContextManager 智能压缩
            target_tokens = int(self.app_config.llm.max_tokens * 0.5)  # 压缩到 50%
            compressed_messages = self.context_manager.compress(
                all_messages,
                target_tokens=target_tokens,
                mode=CompressionMode.EXTRACT,  # 智能提取，非简单截断
            )

            # 更新状态
            self.agent.update_state(config, {"messages": compressed_messages})

            logger.info(
                f"Conversation compacted (v2.1): {len(all_messages)} -> {len(compressed_messages)} "
                f"messages (target_tokens={target_tokens}, mode=EXTRACT)"
            )

            return True

        except Exception as e:
            logger.error(f"Conversation compaction failed: {e}")
            return False

    def _create_agent(self):
        """
        创建 LangGraph Agent（自定义版本，支持结构化响应）

        使用 LangGraph 的 StateGraph 构建自定义 Agent：
        1. agent_node: LLM 决策节点（调用工具或返回结构化响应）
        2. tool_node: 工具执行节点
        3. 条件边：根据响应类型决定下一步

        Returns:
            Compiled LangGraph Agent
        """
        from langgraph.graph import END, StateGraph
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        from langgraph.prebuilt import ToolNode
        import json

        # 创建工具节点
        tool_node = ToolNode(self.tools)

        # 定义 Agent 状态类型
        class AgentState(TypedDict):
            messages: Sequence[BaseMessage]
            next: str  # "agent" 或 "end"

        def should_continue(state: AgentState) -> str:
            """
            决定下一步：继续调用工具还是结束

            基于 LLM 的响应判断：
            - 如果响应包含工具调用 → 调用工具
            - 如果响应是结构化 JSON (type=complete) → 结束
            """
            messages = state["messages"]
            last_message = messages[-1] if messages else None

            if not last_message or not isinstance(last_message, AIMessage):
                return "agent"

            # 检查是否有工具调用（LangChain 原生机制）
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"

            # 检查是否是结构化响应（type=complete）
            content = last_message.content
            if isinstance(content, str):
                # 尝试解析 JSON
                try:
                    # 提取 JSON 代码块
                    import re
                    json_pattern = r'```json\s*\n(.*?)\n```'
                    matches = re.findall(json_pattern, content, re.DOTALL)
                    for match in matches:
                        data = json.loads(match.strip())
                        if data.get("action", {}).get("type") == "tool_call":
                            # 需要调用工具 - 转换为 LangChain 工具调用
                            return "convert_to_tool_call"
                        elif data.get("action", {}).get("type") == "complete":
                            # 完成，结束
                            return "end"
                except (json.JSONDecodeError, KeyError):
                    pass

            # 默认继续
            return "end"

        def convert_to_tool_call(state: AgentState) -> dict:
            """
            将结构化 JSON 响应转换为 LangChain 工具调用

            当模型返回 type="tool_call" 的 JSON 时，转换为实际的工具调用
            """
            messages = list(state["messages"])
            last_message = messages[-1]

            if not isinstance(last_message, AIMessage):
                return {"messages": messages}

            content = last_message.content
            if not isinstance(content, str):
                return {"messages": messages}

            try:
                import re
                json_pattern = r'```json\s*\n(.*?)\n```'
                matches = re.findall(json_pattern, content, re.DOTALL)

                for match in matches:
                    data = json.loads(match.strip())
                    action = data.get("action", {})

                    if action.get("type") == "tool_call" and isinstance(action.get("content"), list):
                        # 提取工具调用列表
                        tool_calls_data = action["content"]

                        # 构建 tool_calls 列表（LangChain 格式）
                        tool_calls = []
                        for tc_data in tool_calls_data:
                            tool_calls.append({
                                "name": tc_data["tool_name"],
                                "args": tc_data["arguments"],
                                "id": tc_data["tool_call_id"]
                            })

                        # 创建新的 AIMessage，包含工具调用
                        new_message = AIMessage(
                            content="",  # 工具调用时 content 为空
                            tool_calls=tool_calls
                        )

                        # 替换最后一条消息
                        messages[-1] = new_message
                        return {"messages": messages}

            except Exception as e:
                logger = __import__('logging').getLogger(__name__)
                logger.error(f"Failed to convert to tool call: {e}")

            return {"messages": messages}

        def call_model(state: AgentState) -> dict:
            """
            调用 LLM 进行决策

            输入包含系统提示词和用户消息
            """
            messages = list(state["messages"])

            # 确保第一条消息是系统提示词
            if not messages or not isinstance(messages[0], SystemMessage):
                messages.insert(0, SystemMessage(content=self.system_prompt))

            # 调用 LLM
            response = self.llm.invoke(messages)
            return {"messages": messages + [response]}

        # 构建图
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.add_node("convert_to_tool_call", convert_to_tool_call)

        # 设置入口点
        workflow.set_entry_point("agent")

        # 添加条件边
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                "convert_to_tool_call": "convert_to_tool_call",
                "end": END
            }
        )

        # 工具执行后回到 agent
        workflow.add_edge("tools", "agent")

        # 转换后回到 agent（会触发工具调用）
        workflow.add_edge("convert_to_tool_call", "agent")

        # 编译图
        app = workflow.compile()

        return app

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

            # 检查是否有 skill 激活结果
            skill_result = self._extract_skill_activation_result(result)
            if skill_result:
                # 处理 skill 激活
                self._handle_skill_activation_result(
                    skill_result, conversation_id, config
                )

                # 继续对话（skill 指令已注入）
                result = self.agent.invoke(
                    {"messages": []},  # 不添加新消息，继续现有对话
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

    def _extract_skill_activation_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract skill activation result from agent response.

        Check if the agent called the activate_skill tool and extract the result.

        Args:
            result: Agent invoke result

        Returns:
            Skill activation result dict, or None if no skill was activated
        """
        messages = result.get("messages", [])

        for msg in reversed(messages):  # Check from most recent
            if isinstance(msg, AIMessage):
                # Check tool calls in the message
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if tool_call.get("name") == "activate_skill":
                            # Extract result from tool output
                            if hasattr(msg, 'additional_kwargs'):
                                additional = msg.additional_kwargs or {}
                                if "tool_output" in additional:
                                    import json
                                    try:
                                        return json.loads(additional["tool_output"])
                                    except json.JSONDecodeError:
                                        pass

                # Also check content for skill activation result
                if isinstance(msg.content, str):
                    import json
                    try:
                        content = json.loads(msg.content)
                        if isinstance(content, dict) and "skill_name" in content:
                            return content
                    except json.JSONDecodeError:
                        pass

        return None

    def _extract_response(self, result: Dict[str, Any]) -> str:
        """
        从 Agent 结果中提取响应文本

        支持结构化 JSON 响应格式的解析

        Args:
            result: Agent 返回结果

        Returns:
            响应文本（如果是结构化 JSON，则提取并返回显示内容）
        """
        messages = result.get("messages", [])
        if not messages:
            return ""

        # 获取最后一条 AI 消息
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, str):
                    # 尝试解析结构化响应
                    parsed = self._try_parse_structured_response(content)
                    if parsed:
                        return parsed
                    return content
                elif isinstance(content, list):
                    # 处理多模态内容
                    text_parts = [
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and "text" in part
                    ]
                    combined = "\n".join(text_parts)
                    # 尝试解析结构化响应
                    parsed = self._try_parse_structured_response(combined)
                    if parsed:
                        return parsed
                    return combined

        return ""

    def _try_parse_structured_response(self, content: str) -> Optional[str]:
        """
        尝试解析结构化响应

        Args:
            content: 原始响应内容

        Returns:
            解析后的显示内容，如果不是结构化响应则返回 None
        """
        try:
            from backend.models.response import parse_structured_response

            structured = parse_structured_response(content)
            if structured and structured.is_complete():
                # 是结构化的 complete 响应，提取显示内容
                final_report = structured.get_final_report()

                # 构建显示内容（与 ba_agent.py 中的逻辑一致）
                display_parts = []

                # 思维链分析（可折叠）
                if structured.task_analysis:
                    display_parts.append(f"""
<div class="task-analysis" style="margin-bottom: 12px; padding: 10px; background: #f0f7ff; border-left: 3px solid #2196F3; border-radius: 4px;">
    <details>
        <summary style="cursor: pointer; font-weight: 500; color: #1976D2;">💡 思维链分析</summary>
        <div style="margin-top: 8px; font-size: 13px; color: #555; white-space: pre-wrap;">{structured.task_analysis}</div>
    </details>
</div>
""")

                # 执行计划
                if structured.execution_plan:
                    display_parts.append(f"""
<div class="execution-plan" style="margin-bottom: 12px; padding: 10px; background: #fff3e0; border-left: 3px solid #FF9800; border-radius: 4px;">
    <div style="font-weight: 500; color: #E65100; margin-bottom: 4px;">📋 执行计划</div>
    <div style="font-size: 13px; color: #555;">{structured.execution_plan}</div>
</div>
""")

                # 最终报告
                has_html = '<div' in final_report or '<script' in final_report or 'echarts' in final_report.lower()

                if has_html:
                    display_parts.append(f'<div class="final-report">{final_report}</div>')
                else:
                    display_parts.append(f'<div class="final-report" style="line-height: 1.6;">{final_report.replace("\\n", "<br>")}</div>')

                # 推荐问题
                if structured.action.recommended_questions:
                    questions_html = '<br>'.join(
                        f'<button class="recommended-question" style="display: block; width: 100%; text-align: left; padding: 10px; margin: 6px 0; background: #f5f5f5; border: 1px solid #ddd; border-radius: 6px; cursor: pointer;">💡 {q}</button>'
                        for q in structured.action.recommended_questions
                    )
                    display_parts.append(f"""
<div class="recommended-questions" style="margin-top: 16px; padding: 12px; background: #f9f9f9; border-radius: 6px;">
    <div style="font-weight: 500; color: #333; margin-bottom: 8px;">🤔 推荐问题</div>
    {questions_html}
</div>
""")

                # 下载链接
                if structured.action.download_links:
                    links_html = '<br>'.join(
                        f'<a href="/api/v1/files/download/{filename}" style="display: inline-block; padding: 8px 16px; margin: 4px; background: #4CAF50; color: white; text-decoration: none; border-radius: 4px;">📥 {filename}</a>'
                        for filename in structured.action.download_links
                    )
                    display_parts.append(f"""
<div class="download-links" style="margin-top: 12px; padding: 12px; background: #e8f5e9; border-radius: 6px;">
    <div style="font-weight: 500; color: #2E7D32; margin-bottom: 8px;">📦 可下载文件</div>
    {links_html}
</div>
""")

                result = "\n".join(display_parts)

                # 添加 HTML 标记
                if has_html:
                    result = f"<!-- HAS_HTML -->{result}"

                return result

        except Exception as e:
            logger = __import__('logging').getLogger(__name__)
            logger.debug(f"Failed to parse structured response: {e}")

        return None

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
