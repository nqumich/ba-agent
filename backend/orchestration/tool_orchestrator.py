"""
BA-Agent Tool Orchestrator

基于 Clawdbot/Manus 的渐进式工具使用模式：

- 状态机工具选择
- 工具掩码 (按前缀分组)
- 动态工具可见性控制
- KV-cache 友好设计
"""

from enum import Enum
from typing import List, Dict, Optional
from langchain_core.tools import StructuredTool


class AgentState(Enum):
    """Agent 状态枚举"""
    IDLE = "idle"           # 空闲，等待用户输入
    QUERY = "query"         # 查询数据
    ANALYZING = "analyzing" # 分析数据
    REPORTING = "reporting" # 生成报告
    DONE = "done"           # 完成


class ToolOrchestrator:
    """
    工具编排器 - 渐进式工具使用核心组件

    核心功能：
    1. 状态机工具选择
    2. 工具掩码 (按前缀分组)
    3. 动态工具可见性控制
    """

    # 状态转换规则
    TRANSITIONS = {
        AgentState.IDLE: [AgentState.QUERY],
        AgentState.QUERY: [AgentState.ANALYZING, AgentState.REPORTING],
        AgentState.ANALYZING: [AgentState.ANALYZING, AgentState.REPORTING],
        AgentState.REPORTING: [AgentState.IDLE, AgentState.DONE],
        AgentState.DONE: [AgentState.IDLE]
    }

    # 工具分组 (按前缀)
    TOOL_GROUPS = {
        "query": ["query_database", "read_file", "web_search", "read_webpage", "search_knowledge"],
        "exec": ["execute_command", "run_python"],
        "skill": ["invoke_skill"],
        "memory": ["memory_search", "memory_get", "memory_write"]
    }

    # 状态到工具组映射
    STATE_TOOLS = {
        AgentState.IDLE: [],
        AgentState.QUERY: ["query"],
        AgentState.ANALYZING: ["exec", "skill", "query"],
        AgentState.REPORTING: ["skill", "memory"],
        AgentState.DONE: []
    }

    def __init__(self, all_tools: List[StructuredTool]):
        """
        初始化工具编排器

        Args:
            all_tools: 所有可用工具的列表
        """
        self.all_tools = {tool.name: tool for tool in all_tools}
        self.state = AgentState.IDLE
        self.state_history = [AgentState.IDLE]

    def get_active_tools(self) -> List[StructuredTool]:
        """
        获取当前状态下的活跃工具

        Returns:
            当前状态允许的工具列表
        """
        # 获取当前状态允许的工具组
        allowed_groups = self.STATE_TOOLS.get(self.state, [])

        # 收集所有允许的工具名称
        allowed_tool_names = []
        for group in allowed_groups:
            allowed_tool_names.extend(self.TOOL_GROUPS.get(group, []))

        # 返回对应的工具对象
        active_tools = []
        for name in allowed_tool_names:
            if name in self.all_tools:
                active_tools.append(self.all_tools[name])

        return active_tools

    def transition(self, new_state: AgentState) -> bool:
        """
        状态转换

        Args:
            new_state: 目标状态

        Returns:
            转换是否成功
        """
        # 检查转换是否合法
        allowed_states = self.TRANSITIONS.get(self.state, [])
        if new_state not in allowed_states:
            return False

        # 记录转换
        old_state = self.state
        self.state = new_state
        self.state_history.append(new_state)

        return True

    def get_state(self) -> AgentState:
        """获取当前状态"""
        return self.state

    def get_state_info(self) -> Dict:
        """
        获取状态信息

        Returns:
            包含当前状态、历史和可用工具的信息
        """
        return {
            "current_state": self.state.value,
            "state_history": [s.value for s in self.state_history],
            "active_tools": [t.name for t in self.get_active_tools()],
            "available_transitions": [s.value for s in self.TRANSITIONS.get(self.state, [])]
        }

    def can_use_tool(self, tool_name: str) -> bool:
        """
        检查当前状态下是否可以使用特定工具

        Args:
            tool_name: 工具名称

        Returns:
            是否可用
        """
        active_tools = self.get_active_tools()
        return any(t.name == tool_name for t in active_tools)

    def get_tools_by_prefix(self, prefix: str) -> List[StructuredTool]:
        """
        按前缀获取工具 (用于工具掩码)

        Args:
            prefix: 工具名称前缀

        Returns:
            匹配前缀的工具列表
        """
        matching_tools = []
        for name, tool in self.all_tools.items():
            if name.startswith(prefix):
                matching_tools.append(tool)
        return matching_tools


# 预定义的工具状态转换提示
STATE_TRANSITION_PROMPTS = {
    (AgentState.IDLE, AgentState.QUERY): "开始查询数据...",
    (AgentState.QUERY, AgentState.ANALYZING): "数据查询完成，开始分析...",
    (AgentState.QUERY, AgentState.REPORTING): "数据查询完成，生成报告...",
    (AgentState.ANALYZING, AgentState.ANALYZING): "继续深入分析...",
    (AgentState.ANALYZING, AgentState.REPORTING): "分析完成，生成报告...",
    (AgentState.REPORTING, AgentState.IDLE): "报告生成完成，回到空闲状态...",
    (AgentState.REPORTING, AgentState.DONE): "任务完成！",
}
